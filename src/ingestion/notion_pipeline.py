"""
Notion Ingestion Pipeline - Production-ready pipeline for Notion → Pinecone.

This pipeline:
1. Loads documents from Notion using NotionLoader
2. Chunks them using the existing DocumentChunker
3. Embeds and stores in Pinecone with proper namespace isolation

Usage:
    from src.ingestion.notion_pipeline import NotionIngestionPipeline
    
    pipeline = NotionIngestionPipeline()
    
    # Ingest a single Notion page tree
    results = pipeline.ingest_page(
        page_id="2f04b2c6-b052-80d9-b2de-fbe6403d5d57",
        namespace="operations-department",
        clear_existing=True
    )
    
    # Or ingest multiple sources
    results = pipeline.ingest_all(clear_existing=True)

Author: YamieBot Team
Last Updated: February 2026
"""

import structlog
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import Document, BaseNode
from llama_index.embeddings.openai import OpenAIEmbedding
from pinecone import Pinecone

from src.config import Config, get_config
from src.ingestion.notion_loader import NotionLoader
from src.ingestion.chunker import DocumentChunker
from src.ingestion.vector_store import create_storage_context

logger = structlog.get_logger(__name__)


# =============================================================================
# NOTION SOURCES REGISTRY
# =============================================================================

@dataclass
class NotionSource:
    """
    Represents a Notion page/section to ingest.
    
    Attributes:
        page_id: The Notion page ID (from the URL or API)
        namespace: Pinecone namespace for this content
        name: Human-readable name for logging
        description: What this source contains
        include_nested: Whether to recursively load child pages
        include_files: Whether to extract embedded PDF/DOCX files
    """
    page_id: str
    namespace: str
    name: str
    description: str = ""
    include_nested: bool = True
    include_files: bool = True


# Define your Notion sources here - add more as you expand
# Define your Notion sources here - add more as you expand
NOTION_SOURCES: Dict[str, NotionSource] = {
    "operations-department": NotionSource(
        page_id="2f04b2c6-b052-80d9-b2de-fbe6403d5d57",
        namespace="operations-department",
        name="Operations Department",
        description="SOPs, weekly reports, franchise procedures",
        include_nested=True,
        include_files=True,
    ),
    
    "yamie-pastabar": NotionSource(
        page_id="2a74b2c6-b052-8028-8ced-d0d2e312ee24",
        namespace="yamie-pastabar",
        name="Yamie Pastabar",
        description="Yamie PastaBar brand content and locations",
        include_nested=True,
        include_files=True,
    ),
    
    "flaminwok": NotionSource(
        page_id="2a74b2c6-b052-8083-b467-f42215fbfcf2",
        namespace="flaminwok",
        name="Flamin'wok",
        description="Flamin'wok brand content and locations",
        include_nested=True,
        include_files=True,
    ),
    
    "smokey-joes": NotionSource(
        page_id="2a74b2c6-b052-8064-973b-d112b64fdec8",
        namespace="smokey-joes",
        name="Smokey Joe's",
        description="Smokey Joe's brand content and locations",
        include_nested=True,
        include_files=True,
    ),
    
    "officiele-documenten": NotionSource(
        page_id="2a74b2c6-b052-802e-a9ee-f848a2c7548a",
        namespace="officiele-documenten",
        name="Officiële documenten",
        description="Official documents including franchise handbook and werkdocumenten",
        include_nested=True,
        include_files=True,
    ),
}


# =============================================================================
# INGESTION RESULTS
# =============================================================================

@dataclass
class IngestionResult:
    """Results from a single source ingestion."""
    source_name: str
    namespace: str
    status: str  # "success", "failed", "skipped"
    documents_loaded: int = 0
    chunks_created: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Results from the entire pipeline run."""
    status: str  # "success", "partial", "failed"
    sources_processed: int = 0
    sources_failed: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    duration_seconds: float = 0.0
    results: List[IngestionResult] = field(default_factory=list)


# =============================================================================
# NOTION INGESTION PIPELINE
# =============================================================================

class NotionIngestionPipeline:
    """
    Production-ready pipeline for ingesting Notion content into Pinecone.
    
    Features:
    - Namespace isolation (each source gets its own namespace)
    - Proper error handling with partial success support
    - Detailed logging and statistics
    - Dry-run mode for testing
    - Cost estimation
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the Notion ingestion pipeline.
        
        Args:
            config: Optional configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        
        # Initialize components
        self.notion_loader = NotionLoader()
        self.chunker = DocumentChunker(self.config)
        
        logger.info(
            "notion_pipeline_initialized",
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            embedding_model=self.config.embedding_model,
        )
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def ingest_page(
        self,
        page_id: str,
        namespace: str,
        name: str = "Custom Source",
        clear_existing: bool = False,
        dry_run: bool = False,
        include_nested: bool = True,
        include_files: bool = True,
    ) -> IngestionResult:
        """
        Ingest a single Notion page tree into Pinecone.
        
        Args:
            page_id: Notion page ID to start from
            namespace: Pinecone namespace for this content
            name: Human-readable name for logging
            clear_existing: If True, clears namespace before ingesting
            dry_run: If True, loads and chunks but doesn't embed/store
            include_nested: Whether to recursively load child pages
            include_files: Whether to extract embedded PDF/DOCX files
            
        Returns:
            IngestionResult with statistics and status
        """
        start_time = datetime.utcnow()
        
        logger.info(
            "page_ingestion_started",
            name=name,
            page_id=page_id,
            namespace=namespace,
            clear_existing=clear_existing,
            dry_run=dry_run,
        )
        
        try:
            # Stage 1: Load from Notion
            logger.info("stage_started", stage="1/3", name="Loading from Notion")
            documents = self.notion_loader.load_from_page(
                page_id=page_id,
                namespace=namespace,
                include_nested_pages=include_nested,
                include_files=include_files,
            )
            
            if not documents:
                logger.warning("no_documents_loaded", name=name)
                return IngestionResult(
                    source_name=name,
                    namespace=namespace,
                    status="skipped",
                    error="No documents found in Notion page",
                    duration_seconds=self._elapsed(start_time),
                )
            
            logger.info(
                "documents_loaded",
                count=len(documents),
                pages=sum(1 for d in documents if d.metadata.get("source_type") == "notion_page"),
                files=sum(1 for d in documents if "embedded" in d.metadata.get("source_type", "")),
            )
            
            # Stage 2: Chunk documents
            logger.info("stage_started", stage="2/3", name="Chunking documents")
            nodes = self.chunker.chunk(documents)
            
            logger.info("chunks_created", count=len(nodes))
            
            # Dry run exit point
            if dry_run:
                cost_estimate = self._estimate_cost(nodes)
                logger.info(
                    "dry_run_complete",
                    documents=len(documents),
                    chunks=len(nodes),
                    estimated_cost_usd=round(cost_estimate, 4),
                )
                return IngestionResult(
                    source_name=name,
                    namespace=namespace,
                    status="dry_run",
                    documents_loaded=len(documents),
                    chunks_created=len(nodes),
                    duration_seconds=self._elapsed(start_time),
                    details={"estimated_cost_usd": round(cost_estimate, 4)},
                )
            
            # Stage 3: Embed and store
            logger.info("stage_started", stage="3/3", name="Embedding and storing")
            
            # Temporarily override config namespace for this ingestion
            original_namespace = self.config.pinecone_namespace
            self.config.pinecone_namespace = namespace
            
            try:
                storage_context = create_storage_context(
                    self.config,
                    clear_namespace=clear_existing,
                )
                
                embed_model = OpenAIEmbedding(
                    model=self.config.embedding_model,
                    dimensions=self.config.embedding_dimensions,
                    embed_batch_size=self.config.embedding_batch_size,
                )
                
                # Build index (embeds + stores)
                VectorStoreIndex(
                    nodes=nodes,
                    storage_context=storage_context,
                    embed_model=embed_model,
                    show_progress=True,
                )
                
            finally:
                # Restore original namespace
                self.config.pinecone_namespace = original_namespace
            
            duration = self._elapsed(start_time)
            
            logger.info(
                "page_ingestion_complete",
                name=name,
                namespace=namespace,
                documents=len(documents),
                chunks=len(nodes),
                duration_seconds=round(duration, 2),
            )
            
            return IngestionResult(
                source_name=name,
                namespace=namespace,
                status="success",
                documents_loaded=len(documents),
                chunks_created=len(nodes),
                duration_seconds=round(duration, 2),
            )
            
        except Exception as e:
            logger.error(
                "page_ingestion_failed",
                name=name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return IngestionResult(
                source_name=name,
                namespace=namespace,
                status="failed",
                error=str(e),
                duration_seconds=self._elapsed(start_time),
            )
    
    def ingest_source(
        self,
        source_key: str,
        clear_existing: bool = False,
        dry_run: bool = False,
    ) -> IngestionResult:
        """
        Ingest a registered Notion source by its key.
        
        Args:
            source_key: Key from NOTION_SOURCES registry
            clear_existing: If True, clears namespace before ingesting
            dry_run: If True, loads and chunks but doesn't embed/store
            
        Returns:
            IngestionResult with statistics and status
        """
        if source_key not in NOTION_SOURCES:
            available = list(NOTION_SOURCES.keys())
            logger.error(
                "source_not_found",
                source_key=source_key,
                available_sources=available,
            )
            return IngestionResult(
                source_name=source_key,
                namespace="unknown",
                status="failed",
                error=f"Source '{source_key}' not found. Available: {available}",
            )
        
        source = NOTION_SOURCES[source_key]
        
        return self.ingest_page(
            page_id=source.page_id,
            namespace=source.namespace,
            name=source.name,
            clear_existing=clear_existing,
            dry_run=dry_run,
            include_nested=source.include_nested,
            include_files=source.include_files,
        )
    
    def ingest_all(
        self,
        clear_existing: bool = False,
        dry_run: bool = False,
        source_keys: Optional[List[str]] = None,
    ) -> PipelineResult:
        """
        Ingest multiple Notion sources.
        
        Args:
            clear_existing: If True, clears each namespace before ingesting
            dry_run: If True, loads and chunks but doesn't embed/store
            source_keys: Specific sources to ingest (defaults to all registered)
            
        Returns:
            PipelineResult with overall statistics and per-source results
        """
        start_time = datetime.utcnow()
        
        # Determine which sources to process
        keys_to_process = source_keys or list(NOTION_SOURCES.keys())
        
        logger.info(
            "multi_source_ingestion_started",
            sources=keys_to_process,
            count=len(keys_to_process),
            clear_existing=clear_existing,
            dry_run=dry_run,
        )
        
        results = []
        total_docs = 0
        total_chunks = 0
        failed_count = 0
        
        for i, source_key in enumerate(keys_to_process, 1):
            logger.info(
                "processing_source",
                source=source_key,
                progress=f"{i}/{len(keys_to_process)}",
            )
            
            result = self.ingest_source(
                source_key=source_key,
                clear_existing=clear_existing,
                dry_run=dry_run,
            )
            
            results.append(result)
            total_docs += result.documents_loaded
            total_chunks += result.chunks_created
            
            if result.status == "failed":
                failed_count += 1
        
        duration = self._elapsed(start_time)
        
        # Determine overall status
        if failed_count == 0:
            status = "success"
        elif failed_count < len(keys_to_process):
            status = "partial"
        else:
            status = "failed"
        
        logger.info(
            "multi_source_ingestion_complete",
            status=status,
            sources_processed=len(keys_to_process),
            sources_failed=failed_count,
            total_documents=total_docs,
            total_chunks=total_chunks,
            duration_seconds=round(duration, 2),
        )
        
        return PipelineResult(
            status=status,
            sources_processed=len(keys_to_process),
            sources_failed=failed_count,
            total_documents=total_docs,
            total_chunks=total_chunks,
            duration_seconds=round(duration, 2),
            results=results,
        )
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def list_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered Notion sources.
        
        Returns:
            Dictionary of source information
        """
        return {
            key: {
                "name": source.name,
                "namespace": source.namespace,
                "description": source.description,
                "page_id": source.page_id,
            }
            for key, source in NOTION_SOURCES.items()
        }
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """
        Get statistics for a specific Pinecone namespace.
        
        Args:
            namespace: The namespace to check
            
        Returns:
            Dictionary with vector count and other stats
        """
        try:
            pc = Pinecone(api_key=self.config.pinecone_api_key)
            index = pc.Index(self.config.pinecone_index_name)
            stats = index.describe_index_stats()
            
            namespace_stats = stats.get("namespaces", {}).get(namespace, {})
            
            return {
                "namespace": namespace,
                "vector_count": namespace_stats.get("vector_count", 0),
                "exists": namespace in stats.get("namespaces", {}),
            }
        except Exception as e:
            logger.error("stats_fetch_failed", namespace=namespace, error=str(e))
            return {"namespace": namespace, "error": str(e)}
    
    def _elapsed(self, start_time: datetime) -> float:
        """Calculate elapsed seconds from start time."""
        return (datetime.utcnow() - start_time).total_seconds()
    
    def _estimate_cost(self, nodes: List[BaseNode]) -> float:
        """
        Estimate embedding cost for a set of nodes using accurate token counting.
        
        Based on OpenAI pricing (as of early 2025):
        - text-embedding-3-large: $0.00013 per 1K tokens
        - text-embedding-3-small: $0.00002 per 1K tokens
        """
        try:
            import tiktoken
            
            # Use cl100k_base encoding (used by text-embedding-3 models)
            encoding = tiktoken.get_encoding("cl100k_base")
            
            # Accurately count tokens
            total_tokens = sum(len(encoding.encode(node.text)) for node in nodes)
            
        except ImportError:
            # Fallback to rough estimate if tiktoken not installed
            logger.warning(
                "tiktoken_not_installed",
                message="Using rough token estimate. Install tiktoken for accuracy: pip install tiktoken"
            )
            total_tokens = sum(len(node.text.split()) * 1.3 for node in nodes)
        
        # Determine cost per 1K tokens based on model
        if "small" in self.config.embedding_model.lower():
            cost_per_1k = 0.00002
        else:
            cost_per_1k = 0.00013
        
        return (total_tokens / 1000) * cost_per_1k


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    """
    Quick test of the pipeline.
    Run: python -m src.ingestion.notion_pipeline
    """
    import sys
    
    print("\n" + "=" * 70)
    print("🧪 NOTION PIPELINE TEST")
    print("=" * 70)
    
    pipeline = NotionIngestionPipeline()
    
    print("\n📋 Registered Sources:")
    for key, info in pipeline.list_sources().items():
        print(f"  • {key}: {info['name']}")
        print(f"    Namespace: {info['namespace']}")
        print(f"    Description: {info['description']}")
    
    print("\n" + "=" * 70)
    print("To run actual ingestion, use: python scripts/run_notion_ingestion.py")
    print("=" * 70 + "\n")