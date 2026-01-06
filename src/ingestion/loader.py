"""
Document loader with metadata extraction and validation.
Uses LlamaIndex SimpleDirectoryReader for robust document handling (PDF, DOCX, etc).
"""

import structlog
from pathlib import Path
from typing import List
from datetime import datetime

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document

from src.config import Config

logger = structlog.get_logger(__name__)


class DocumentLoader:
    """Loads documents and enriches them with comprehensive metadata."""

    # Enhanced category keywords - now includes franchise/training terminology
    CATEGORY_KEYWORDS = {
        "menu": ["menu", "menukaart", "pizza", "pasta", "dish", "food", "drink", "gerecht"],
        "franchise": ["franchise", "franchisenemer", "handleiding", "training", "inwerkprotocol", "protocol"],
        "sop": ["sop", "procedure", "proces", "process", "operating", "werkwijze", "instructie"],
        "hr": ["hr", "policy", "beleid", "employee", "staff", "medewerker", "personeel", "leave", "verlof", "sick", "ziek"],
        "equipment": ["equipment", "apparatuur", "machine", "maintenance", "onderhoud", "repair", "reparatie", "cleaning", "schoonmaken"],
        "operations": ["operations", "operationeel", "opening", "closing", "openen", "sluiten", "shift", "dienst"],
    }

    def __init__(self, config: Config):
        self.data_dir = Path(config.data_dir)
        self.supported_extensions = config.supported_extensions

    def _categorize(self, filename: str) -> str:
        """
        Automatically categorize document based on filename keywords.
        Returns the first matching category, or 'general' if no match.
        """
        filename_lower = filename.lower()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in filename_lower for keyword in keywords):
                logger.debug(
                    "document_categorized",
                    filename=filename,
                    category=category
                )
                return category
        
        logger.debug(
            "document_categorized",
            filename=filename,
            category="general",
            reason="no_match"
        )
        return "general"

    def _is_valid(self, document: Document) -> bool:
        """
        Validate document has actual text content.
        Returns False for empty or whitespace-only documents.
        """
        if not document.text:
            return False
        
        text_stripped = document.text.strip()
        if not text_stripped:
            return False
        
        return True

    def _enrich_metadata(self, document: Document, file_path: Path = None) -> Document:
        """
        Enrich document with comprehensive metadata for better retrieval and analysis.
        """
        filename = document.metadata.get("file_name", "unknown")
        
        # Core metadata
        metadata = {
            "category": self._categorize(filename),
            "ingested_at": datetime.utcnow().isoformat(),
            "char_count": len(document.text),
            "word_count": len(document.text.split()),
        }
        
        # Add file-specific metadata if available
        if file_path and file_path.exists():
            metadata.update({
                "file_size_kb": round(file_path.stat().st_size / 1024, 2),
                "file_extension": file_path.suffix.lower(),
            })
        
        document.metadata.update(metadata)
        
        logger.debug(
            "metadata_enriched",
            filename=filename,
            category=metadata['category'],
            word_count=metadata['word_count'],
            char_count=metadata['char_count']
        )
        
        return document

    def load(self) -> List[Document]:
        """
        Load, validate, and enrich all documents from the data directory.
        
        Returns:
            List of valid, enriched Document objects
            
        Raises:
            ValueError: If no documents found or data directory doesn't exist
        """
        logger.info(
            "document_loading_started",
            data_dir=str(self.data_dir)
        )
        
        # Validate data directory exists
        if not self.data_dir.exists():
            error_msg = f"Data directory does not exist: {self.data_dir}"
            logger.error(
                "data_directory_not_found",
                data_dir=str(self.data_dir)
            )
            raise ValueError(error_msg)
        
        # Initialize reader
        try:
            reader = SimpleDirectoryReader(
                input_dir=str(self.data_dir),
                required_exts=self.supported_extensions,
                filename_as_id=True,
            )
            logger.debug(
                "reader_initialized",
                supported_extensions=self.supported_extensions
            )
        except Exception as e:
            logger.error(
                "reader_initialization_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        
        # Load documents
        try:
            documents = reader.load_data()
            logger.debug("documents_loaded", count=len(documents))
        except Exception as e:
            logger.error(
                "documents_loading_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        
        if not documents:
            error_msg = f"No documents found in {self.data_dir} with extensions {self.supported_extensions}"
            logger.error(
                "no_documents_found",
                data_dir=str(self.data_dir),
                supported_extensions=self.supported_extensions
            )
            raise ValueError(error_msg)
        
        logger.info(
            "documents_found",
            count=len(documents),
            data_dir=str(self.data_dir)
        )
        
        # Validate and enrich documents
        valid_docs = []
        skipped = []
        
        for doc in documents:
            filename = doc.metadata.get("file_name", "unknown")
            
            try:
                # Validate document
                if not self._is_valid(doc):
                    logger.warning(
                        "document_skipped",
                        filename=filename,
                        reason="invalid_or_empty"
                    )
                    skipped.append(filename)
                    continue
                
                # Get file path for additional metadata
                file_path = self.data_dir / filename
                
                # Enrich with metadata
                enriched_doc = self._enrich_metadata(doc, file_path)
                valid_docs.append(enriched_doc)
                
                logger.info(
                    "document_processed",
                    filename=filename,
                    status="success"
                )
                
            except Exception as e:
                logger.error(
                    "document_processing_failed",
                    filename=filename,
                    error=str(e),
                    error_type=type(e).__name__
                )
                skipped.append(filename)
                continue
        
        # Summary logging
        logger.info(
            "document_loading_completed",
            valid_documents=len(valid_docs),
            skipped_documents=len(skipped),
            total_found=len(documents)
        )
        
        if skipped:
            logger.warning(
                "documents_skipped",
                count=len(skipped),
                filenames=skipped
            )
        
        return valid_docs