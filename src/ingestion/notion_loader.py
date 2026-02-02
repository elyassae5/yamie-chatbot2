"""
Notion Loader - Production-ready loader for fetching content from Notion.

Features:
- Recursive page loading (nested pages)
- Recursive block loading (nested bullets, toggles, etc.)
- PDF and DOCX file extraction
- Full source path tracking (breadcrumb trail for every chunk)
- Namespace support for Pinecone separation
- Outputs LlamaIndex Document objects

Usage:
    from src.ingestion.notion_loader import NotionLoader
    
    loader = NotionLoader()
    documents = loader.load_from_page(
        page_id="your-page-id",
        namespace="operations-department"
    )
    
    # Each document has metadata like:
    # {
    #     "namespace": "operations-department",
    #     "source_path": "Operations Department/Salesgesprek + SOP/Volledig gesprek.pdf",
    #     "page_title": "Volledig gesprek.pdf",
    #     "source_type": "notion_embedded_pdf",
    #     ...
    # }
"""

import os
import re
import tempfile
import requests
import structlog
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import unquote

from dotenv import load_dotenv
from llama_index.core.schema import Document

load_dotenv()

logger = structlog.get_logger(__name__)


# =============================================================================
# FILE EXTRACTION SUPPORT
# =============================================================================

# Check for PDF support (using pypdf)
try:
    import pypdf
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Check for DOCX support
try:
    import docx2txt
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


# =============================================================================
# NOTION LOADER
# =============================================================================

class NotionLoader:
    """
    Production-ready Notion content loader.
    
    Loads content from Notion pages with full source path tracking.
    Each document knows exactly where it came from:
    - Namespace (for Pinecone separation)
    - Source path (full breadcrumb: "Parent/Child/Grandchild/file.pdf")
    - Source type (notion_page, notion_embedded_pdf, notion_embedded_docx)
    """
    
    NOTION_VERSION = "2022-06-28"
    BASE_URL = "https://api.notion.com/v1"
    
    # Block types that contain text content
    TEXT_BLOCK_TYPES = {
        "paragraph",
        "heading_1",
        "heading_2", 
        "heading_3",
        "bulleted_list_item",
        "numbered_list_item",
        "to_do",
        "toggle",
        "quote",
        "callout",
        "code",
        "divider",
        "table_row",
    }
    
    # Block types that contain files we can extract
    FILE_BLOCK_TYPES = {"file", "pdf"}
    
    # File extensions we can extract text from
    SUPPORTED_FILE_EXTENSIONS = {".pdf", ".docx"}
    
    def __init__(self, api_key: str = None):
        """
        Initialize the Notion loader.
        
        Args:
            api_key: Notion API key. Reads from NOTION_API_KEY env var if not provided.
        """
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Notion API key not found. "
                "Set NOTION_API_KEY in .env or pass api_key parameter."
            )
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": self.NOTION_VERSION
        }
        
        # Log initialization with file support status
        logger.info(
            "notion_loader_initialized",
            pdf_support=PDF_SUPPORT,
            docx_support=DOCX_SUPPORT
        )
        
        if not PDF_SUPPORT:
            logger.warning("pdf_support_disabled", reason="pypdf not installed - run: pip install pypdf")
        if not DOCX_SUPPORT:
            logger.warning("docx_support_disabled", reason="docx2txt not installed")
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def load_from_page(
        self,
        page_id: str,
        namespace: str,
        include_nested_pages: bool = True,
        include_files: bool = True,
    ) -> List[Document]:
        """
        Load all content from a Notion page and its children.
        
        Args:
            page_id: The root Notion page ID to load from
            namespace: Namespace identifier for Pinecone (e.g., "operations-department")
            include_nested_pages: Whether to recursively load child pages (default: True)
            include_files: Whether to extract embedded PDF/DOCX files (default: True)
            
        Returns:
            List of LlamaIndex Document objects, each with full source path metadata
            
        Example:
            loader = NotionLoader()
            docs = loader.load_from_page(
                page_id="2f04b2c6-b052-80d9-b2de-fbe6403d5d57",
                namespace="operations-department"
            )
        """
        logger.info(
            "load_started",
            page_id=page_id,
            namespace=namespace,
            include_nested_pages=include_nested_pages,
            include_files=include_files
        )
        
        documents = []
        
        # Get root page info to start the path
        root_page = self._fetch_page(page_id)
        if not root_page:
            logger.error("root_page_not_found", page_id=page_id)
            return documents
        
        root_title = self._extract_page_title(root_page)
        
        # Recursively load all content
        self._load_page_recursive(
            page_id=page_id,
            namespace=namespace,
            parent_path=root_title,
            documents=documents,
            include_nested_pages=include_nested_pages,
            include_files=include_files
        )
        
        # Log summary
        page_count = sum(1 for d in documents if d.metadata.get("source_type") == "notion_page")
        file_count = sum(1 for d in documents if "embedded" in d.metadata.get("source_type", ""))
        
        logger.info(
            "load_completed",
            namespace=namespace,
            total_documents=len(documents),
            pages=page_count,
            embedded_files=file_count
        )
        
        return documents
    
    def search_accessible_pages(self) -> List[Dict[str, str]]:
        """
        Find all pages the integration has access to.
        
        Returns:
            List of dicts with page info: {"id", "title", "url"}
        """
        logger.info("searching_accessible_pages")
        
        pages = []
        payload = {
            "filter": {"property": "object", "value": "page"},
            "page_size": 100
        }
        
        while True:
            response = self._api_request("POST", "/search", json=payload)
            if not response:
                break
            
            for page in response.get("results", []):
                pages.append({
                    "id": page["id"],
                    "title": self._extract_page_title(page),
                    "url": page.get("url", "")
                })
            
            if response.get("has_more"):
                payload["start_cursor"] = response["next_cursor"]
            else:
                break
        
        logger.info("search_completed", pages_found=len(pages))
        return pages
    
    # =========================================================================
    # RECURSIVE LOADING
    # =========================================================================
    
    def _load_page_recursive(
        self,
        page_id: str,
        namespace: str,
        parent_path: str,
        documents: List[Document],
        include_nested_pages: bool,
        include_files: bool,
    ):
        """
        Recursively load a page and all its descendants.
        
        Args:
            page_id: Current page to load
            namespace: Pinecone namespace
            parent_path: Path from root to this page (e.g., "Operations Department/Weekly reports")
            documents: List to append documents to
            include_nested_pages: Whether to recurse into child pages
            include_files: Whether to extract embedded files
        """
        logger.debug("loading_page", page_id=page_id, path=parent_path)
        
        # Fetch page metadata
        page_info = self._fetch_page(page_id)
        if not page_info:
            return
        
        page_title = self._extract_page_title(page_info)
        page_url = page_info.get("url", "")
        
        # Fetch all blocks (with recursive child blocks for nested bullets etc.)
        blocks = self._fetch_all_blocks(page_id)
        
        # Extract text content from blocks
        text_content = self._blocks_to_text(blocks)
        
        # Create document for page text if there's content
        if text_content and text_content.strip():
            doc = Document(
                text=text_content,
                metadata={
                    # Core identifiers
                    "namespace": namespace,
                    "source_path": parent_path,
                    "source_type": "notion_page",
                    
                    # Page details
                    "page_id": page_id,
                    "page_title": page_title,
                    "page_url": page_url,
                    
                    # For compatibility with existing chunker
                    "file_name": page_title,
                    
                    # Stats
                    "char_count": len(text_content),
                    "word_count": len(text_content.split()),
                    "ingested_at": datetime.utcnow().isoformat(),
                }
            )
            documents.append(doc)
            
            logger.debug(
                "page_extracted",
                path=parent_path,
                chars=len(text_content)
            )
        
        # Extract embedded files (PDF, DOCX)
        if include_files:
            file_docs = self._extract_embedded_files(
                blocks=blocks,
                namespace=namespace,
                parent_path=parent_path
            )
            documents.extend(file_docs)
        
        # Recurse into child pages
        if include_nested_pages:
            child_pages = [b for b in blocks if b.get("type") == "child_page"]
            
            for child_block in child_pages:
                child_id = child_block["id"]
                child_title = child_block.get("child_page", {}).get("title", "Untitled")
                child_path = f"{parent_path}/{child_title}"
                
                self._load_page_recursive(
                    page_id=child_id,
                    namespace=namespace,
                    parent_path=child_path,
                    documents=documents,
                    include_nested_pages=include_nested_pages,
                    include_files=include_files
                )
    
    # =========================================================================
    # NOTION API HELPERS
    # =========================================================================
    
    def _api_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Optional[Dict]:
        """Make a request to the Notion API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=30,
                **kwargs
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    "api_request_failed",
                    endpoint=endpoint,
                    status=response.status_code,
                    error=response.text[:200]
                )
                return None
                
        except requests.RequestException as e:
            logger.error("api_request_error", endpoint=endpoint, error=str(e))
            return None
    
    def _fetch_page(self, page_id: str) -> Optional[Dict]:
        """Fetch page metadata."""
        return self._api_request("GET", f"/pages/{page_id}")
    
    def _fetch_all_blocks(self, block_id: str) -> List[Dict]:
        """
        Fetch all blocks from a page/block, including nested children.
        
        Handles:
        - Pagination (pages with 100+ blocks)
        - Nested blocks (sub-bullets, toggle contents, etc.)
        """
        all_blocks = []
        
        # Fetch direct children (with pagination)
        params = {"page_size": 100}
        
        while True:
            response = self._api_request(
                "GET",
                f"/blocks/{block_id}/children",
                params=params
            )
            
            if not response:
                break
            
            blocks = response.get("results", [])
            
            for block in blocks:
                all_blocks.append(block)
                
                # Recursively fetch nested blocks (but not child_page - those are separate)
                if block.get("has_children") and block.get("type") != "child_page":
                    nested = self._fetch_all_blocks(block["id"])
                    all_blocks.extend(nested)
            
            if response.get("has_more"):
                params["start_cursor"] = response["next_cursor"]
            else:
                break
        
        return all_blocks
    
    def _extract_page_title(self, page: Dict) -> str:
        """Extract title from a page object."""
        title = "Untitled"
        
        # Standard page with properties
        if "properties" in page:
            for prop in page["properties"].values():
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    if title_array:
                        title = title_array[0].get("plain_text", "Untitled")
                        break
        
        # Child page block
        if title == "Untitled" and "child_page" in page:
            title = page["child_page"].get("title", "Untitled")
        
        # Clean up: replace non-breaking spaces with regular spaces, strip whitespace
        title = title.replace("\xa0", " ").strip()
        
        return title
    
    # =========================================================================
    # TEXT EXTRACTION
    # =========================================================================
    
    def _blocks_to_text(self, blocks: List[Dict]) -> str:
        """
        Convert blocks to plain text with basic formatting preserved.
        """
        lines = []
        
        for block in blocks:
            block_type = block.get("type", "")
            
            if block_type in self.TEXT_BLOCK_TYPES:
                text = self._extract_block_text(block)
                
                if text:
                    # Apply formatting based on block type
                    if block_type == "heading_1":
                        text = f"\n# {text}\n"
                    elif block_type == "heading_2":
                        text = f"\n## {text}\n"
                    elif block_type == "heading_3":
                        text = f"\n### {text}\n"
                    elif block_type in ("bulleted_list_item", "numbered_list_item"):
                        text = f"• {text}"
                    elif block_type == "to_do":
                        checked = block.get("to_do", {}).get("checked", False)
                        text = f"{'☑' if checked else '☐'} {text}"
                    elif block_type == "quote":
                        text = f"> {text}"
                    elif block_type == "code":
                        lang = block.get("code", {}).get("language", "")
                        text = f"```{lang}\n{text}\n```"
                    elif block_type == "divider":
                        text = "\n---\n"
                    
                    lines.append(text)
            
            # Note child pages (they're loaded separately)
            elif block_type == "child_page":
                title = block.get("child_page", {}).get("title", "Untitled")
                lines.append(f"\n[See: {title}]\n")
            
            # Note databases
            elif block_type == "child_database":
                title = block.get("child_database", {}).get("title", "Untitled")
                lines.append(f"\n[Database: {title}]\n")
        
        return "\n".join(lines)
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract plain text from a single block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        
        # Most text blocks have rich_text
        rich_text = block_data.get("rich_text", [])
        return "".join(item.get("plain_text", "") for item in rich_text)
    
    # =========================================================================
    # FILE EXTRACTION
    # =========================================================================
    
    def _extract_embedded_files(
        self,
        blocks: List[Dict],
        namespace: str,
        parent_path: str
    ) -> List[Document]:
        """
        Extract text from embedded PDF and DOCX files.
        """
        documents = []
        
        for block in blocks:
            block_type = block.get("type", "")
            
            if block_type not in self.FILE_BLOCK_TYPES:
                continue
            
            block_data = block.get(block_type, {})
            
            # Get file URL (internal Notion file or external)
            file_info = block_data.get("file") or block_data.get("external")
            if not file_info:
                continue
            
            file_url = file_info.get("url", "")
            if not file_url:
                continue
            
            # Get filename
            file_name = block_data.get("name") or self._filename_from_url(file_url)
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # Check if we support this file type
            if file_ext not in self.SUPPORTED_FILE_EXTENSIONS:
                logger.debug("skipping_unsupported_file", file=file_name, ext=file_ext)
                continue
            
            logger.info("extracting_file", file=file_name, path=parent_path)
            
            # Extract text
            file_text = None
            
            if file_ext == ".pdf":
                file_text = self._extract_pdf(file_url)
            elif file_ext == ".docx":
                file_text = self._extract_docx(file_url)
            
            if file_text and file_text.strip():
                # Build full path including the file
                full_path = f"{parent_path}/{file_name}"
                
                doc = Document(
                    text=file_text,
                    metadata={
                        # Core identifiers
                        "namespace": namespace,
                        "source_path": full_path,
                        "source_type": f"notion_embedded_{file_ext[1:]}",  # pdf or docx
                        
                        # File details
                        "file_name": file_name,
                        "parent_page_path": parent_path,
                        
                        # Stats
                        "char_count": len(file_text),
                        "word_count": len(file_text.split()),
                        "ingested_at": datetime.utcnow().isoformat(),
                    }
                )
                documents.append(doc)
                
                logger.info(
                    "file_extracted",
                    file=file_name,
                    path=full_path,
                    chars=len(file_text)
                )
            else:
                logger.warning("file_extraction_failed", file=file_name)
        
        return documents
    
    def _extract_pdf(self, url: str) -> Optional[str]:
        """Download and extract text from a PDF."""
        if not PDF_SUPPORT:
            return None
        
        try:
            # Download
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(response.content)
                temp_path = f.name
            
            # Extract text using pypdf
            text_parts = []
            reader = pypdf.PdfReader(temp_path)
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            # Cleanup
            os.unlink(temp_path)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error("pdf_extraction_error", error=str(e))
            return None
    
    def _extract_docx(self, url: str) -> Optional[str]:
        """Download and extract text from a DOCX."""
        if not DOCX_SUPPORT:
            return None
        
        try:
            # Download
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(response.content)
                temp_path = f.name
            
            # Extract text
            text = docx2txt.process(temp_path)
            
            # Cleanup
            os.unlink(temp_path)
            
            return text
            
        except Exception as e:
            logger.error("docx_extraction_error", error=str(e))
            return None
    
    def _filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        # Remove query params
        path = url.split("?")[0]
        
        # Get last path segment
        segments = path.split("/")
        for segment in reversed(segments):
            if "." in segment:
                return unquote(segment)
        
        return "unknown_file"


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    """
    Test the Notion loader.
    
    Run: python -m src.ingestion.notion_loader
    """
    import sys
    
    # Simple logging setup for testing
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
        stream=sys.stdout
    )
    
    print()
    print("=" * 70)
    print("🔍 NOTION LOADER TEST")
    print("=" * 70)
    
    # Initialize loader
    try:
        loader = NotionLoader()
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    
    # Operations Department page ID
    PAGE_ID = "2f04b2c6-b052-80d9-b2de-fbe6403d5d57"
    NAMESPACE = "operations-department"
    
    print(f"\n📄 Loading: Operations Department")
    print(f"   Page ID: {PAGE_ID}")
    print(f"   Namespace: {NAMESPACE}")
    print(f"\n⏳ Fetching all pages and files...\n")
    
    # Load content
    documents = loader.load_from_page(
        page_id=PAGE_ID,
        namespace=NAMESPACE,
        include_nested_pages=True,
        include_files=True
    )
    
    # Results summary
    print()
    print("=" * 70)
    print(f"✅ LOADED {len(documents)} DOCUMENTS")
    print("=" * 70)
    
    page_docs = [d for d in documents if d.metadata.get("source_type") == "notion_page"]
    pdf_docs = [d for d in documents if "pdf" in d.metadata.get("source_type", "")]
    docx_docs = [d for d in documents if "docx" in d.metadata.get("source_type", "")]
    
    print(f"\n📄 Notion pages: {len(page_docs)}")
    print(f"📎 Embedded PDFs: {len(pdf_docs)}")
    print(f"📎 Embedded DOCX: {len(docx_docs)}")
    
    # Show each document's source path
    print(f"\n{'=' * 70}")
    print("SOURCE PATHS (this is what you'll see when debugging retrieval):")
    print("=" * 70)
    
    for i, doc in enumerate(documents, 1):
        source_path = doc.metadata.get("source_path", "unknown")
        source_type = doc.metadata.get("source_type", "unknown")
        chars = doc.metadata.get("char_count", 0)
        
        # Type indicator
        if source_type == "notion_page":
            icon = "📄"
        elif "pdf" in source_type:
            icon = "📕"
        elif "docx" in source_type:
            icon = "📘"
        else:
            icon = "📁"
        
        print(f"\n{i:2}. {icon} {source_path}")
        print(f"      Type: {source_type} | {chars:,} chars")
    
    print(f"\n{'=' * 70}")
    print("TEST COMPLETE")
    print("=" * 70)
    print()