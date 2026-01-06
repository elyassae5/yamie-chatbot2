"""
Main ingestion pipeline orchestrator.
Coordinates document loading, chunking, embedding, and vector storage.
"""

import structlog
from datetime import datetime
from typing import Optional
 
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.ingestion.loader import DocumentLoader
from src.ingestion.chunker import DocumentChunker
from src.ingestion.vector_store import create_storage_context

logger = structlog.get_logger(__name__)


class IngestionPipeline:
    """
    Orchestrates the complete document ingestion pipeline.
    
    Pipeline stages:
    1. Load documents from data directory
    2. Chunk documents into nodes
    3. Generate embeddings for each node
    4. Store vectors in Pinecone
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the ingestion pipeline.
        
        Args:
            config: Optional configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        
        logger.info("pipeline_initialization_started")
        
        # Initialize components
        self.loader = DocumentLoader(self.config)
        self.chunker = DocumentChunker(self.config)
        
        logger.debug("pipeline_components_initialized")

    def run(
        self, 
        clear_existing: bool = False, 
        dry_run: bool = False, 
        inspect_chunks: bool = False
    ) -> dict:
        """
        Run the complete ingestion pipeline.
        
        Args:
            clear_existing: If True, deletes existing vectors in namespace before ingestion
            dry_run: If True, runs all steps except embedding/storage (for testing)
            inspect_chunks: If True, displays sample chunks for debugging
            
        Returns:
            Dictionary with ingestion results and statistics
            
        Raises:
            Exception: If any pipeline stage fails
        """
        start_time = datetime.utcnow()
        
        logger.info(
            "pipeline_run_started",
            clear_existing=clear_existing,
            dry_run=dry_run,
            inspect_chunks=inspect_chunks
        )
        logger.info("pipeline_message", message="🚀 STARTING INGESTION PIPELINE")
        
        # Display configuration
        self.config.display()
        
        try:
            # Stage 1: Load documents
            logger.info("pipeline_stage", stage="1/4", name="Loading Documents")
            documents = self._load_documents()
            
            # Stage 2: Chunk documents
            logger.info("pipeline_stage", stage="2/4", name="Chunking Documents")
            nodes = self._chunk_documents(documents, inspect_chunks)
            
            # Dry run exit point
            if dry_run:
                return self._handle_dry_run(documents, nodes, start_time)
            
            # Stage 3: Create storage context
            logger.info("pipeline_stage", stage="3/4", name="Initializing Vector Store")
            storage_context = self._create_storage_context(clear_existing)
            
            # Stage 4: Embed and store
            logger.info("pipeline_stage", stage="4/4", name="Embedding and Storing Vectors")
            self._embed_and_store(nodes, storage_context)
            
            # Success!
            return self._create_success_result(documents, nodes, start_time)
            
        except Exception as e:
            logger.error(
                "pipeline_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "status": "failed",
                "error": str(e),
                "duration_seconds": round(duration, 2),
            }

    def _load_documents(self):
        """Load documents from data directory."""
        try:
            documents = self.loader.load()
            logger.info(
                "documents_loaded",
                count=len(documents),
                status="success"
            )
            return documents
        except Exception as e:
            logger.error(
                "document_loading_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def _chunk_documents(self, documents, inspect_chunks: bool):
        """Chunk documents into nodes."""
        try:
            nodes = self.chunker.chunk(documents)
            logger.info(
                "chunks_created",
                count=len(nodes),
                status="success"
            )
            
            # Optional inspection
            if inspect_chunks:
                logger.info("chunk_inspection", status="starting")
                self.chunker.inspect(nodes, num_samples=5)
            
            return nodes
        except Exception as e:
            logger.error(
                "chunking_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def _create_storage_context(self, clear_existing: bool):
        """Initialize Pinecone storage context."""
        try:
            storage_context = create_storage_context(
                self.config,
                clear_namespace=clear_existing,
            )
            logger.info(
                "storage_context_initialized",
                clear_existing=clear_existing,
                status="success"
            )
            return storage_context
        except Exception as e:
            logger.error(
                "storage_context_creation_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def _embed_and_store(self, nodes, storage_context):
        """Generate embeddings and store vectors in Pinecone."""
        try:
            # Create embedding model
            embed_model = OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
                embed_batch_size=self.config.embedding_batch_size,
            )
            
            logger.info(
                "embedding_configuration",
                model=self.config.embedding_model,
                batch_size=self.config.embedding_batch_size,
                dimensions=self.config.embedding_dimensions
            )
            logger.info("embedding_started", message="Generating embeddings and uploading to Pinecone...")
            
            # Build index (this does embedding + storage)
            VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True,
            )
            
            logger.info("embedding_completed", status="success")
            
        except Exception as e:
            logger.error(
                "embedding_storage_failed",
                error=str(e),
                error_type=type(e).__name__,
                warning="vectors_may_be_lost_if_namespace_cleared"
            )
            raise

    def _handle_dry_run(self, documents, nodes, start_time) -> dict:
        """Handle dry run completion."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("dry_run_completed", message="✓ DRY RUN COMPLETE")
        logger.info("dry_run_note", message="No embeddings were created or stored")
        
        # Estimate costs
        estimated_cost = self._estimate_embedding_cost(nodes)
        logger.info(
            "dry_run_estimate",
            estimated_cost_usd=round(estimated_cost, 4),
            chunks_to_embed=len(nodes)
        )
        
        return {
            "status": "dry_run",
            "documents": len(documents),
            "chunks": len(nodes),
            "duration_seconds": round(duration, 2),
            "estimated_cost_usd": round(estimated_cost, 4),
        }

    def _estimate_embedding_cost(self, nodes) -> float:
        """
        Estimate the cost of embedding all nodes.
        Based on OpenAI's pricing for text-embedding-3-large.
        """
        total_tokens = sum(len(node.text.split()) * 1.3 for node in nodes)  # Rough token estimate
        
        # Pricing (as of Dec 2024)
        # text-embedding-3-large: $0.00013 per 1K tokens
        # text-embedding-3-small: $0.00002 per 1K tokens
        
        if "small" in self.config.embedding_model.lower():
            cost_per_1k = 0.00002
        else:  # large model
            cost_per_1k = 0.00013
        
        estimated_cost = (total_tokens / 1000) * cost_per_1k
        
        logger.debug(
            "cost_estimation",
            total_tokens=round(total_tokens, 0),
            cost_per_1k=cost_per_1k,
            estimated_cost_usd=round(estimated_cost, 4)
        )
        
        return estimated_cost

    def _create_success_result(self, documents, nodes, start_time) -> dict:
        """Create success result dictionary with statistics."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Calculate statistics
        avg_chunk_size = sum(len(node.text) for node in nodes) / len(nodes) if nodes else 0
        chunks_per_doc = len(nodes) / len(documents) if documents else 0
        processing_speed = len(nodes) / duration if duration > 0 else 0
        
        logger.info("ingestion_completed", message="✅ INGESTION COMPLETE!")
        logger.info(
            "ingestion_summary",
            documents_processed=len(documents),
            chunks_created=len(nodes),
            duration_seconds=round(duration, 2),
            index=self.config.pinecone_index_name,
            namespace=self.config.pinecone_namespace
        )
        
        logger.info(
            "ingestion_statistics",
            avg_chunk_size_chars=round(avg_chunk_size, 0),
            chunks_per_document=round(chunks_per_doc, 1),
            processing_speed_chunks_per_sec=round(processing_speed, 1)
        )
        
        return {
            "status": "success",
            "documents": len(documents),
            "chunks": len(nodes),
            "duration_seconds": round(duration, 2),
            "avg_chunk_size_chars": round(avg_chunk_size, 0),
            "chunks_per_document": round(chunks_per_doc, 1),
            "processing_speed_chunks_per_sec": round(processing_speed, 1),
            "index": self.config.pinecone_index_name,
            "namespace": self.config.pinecone_namespace,
        }