"""
Main ingestion pipeline orchestrator.
Coordinates document loading, chunking, embedding, and vector storage.
"""

import logging
from datetime import datetime
from typing import Optional
 
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.ingestion.loader import DocumentLoader
from src.ingestion.chunker import DocumentChunker
from src.ingestion.vector_store import create_storage_context

logger = logging.getLogger(__name__)


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
        
        logger.info("Initializing ingestion pipeline")
        
        # Initialize components
        self.loader = DocumentLoader(self.config)
        self.chunker = DocumentChunker(self.config)
        
        logger.debug("Pipeline components initialized")

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
        
        logger.info("="*80)
        logger.info("🚀 STARTING INGESTION PIPELINE")
        logger.info("="*80)
        
        # Display configuration
        self.config.display()
        
        try:
            # Stage 1: Load documents
            logger.info("\n" + "="*80)
            logger.info("STAGE 1/4: Loading Documents")
            logger.info("="*80)
            
            documents = self._load_documents()
            
            # Stage 2: Chunk documents
            logger.info("\n" + "="*80)
            logger.info("STAGE 2/4: Chunking Documents")
            logger.info("="*80)
            
            nodes = self._chunk_documents(documents, inspect_chunks)
            
            # Dry run exit point
            if dry_run:
                return self._handle_dry_run(documents, nodes, start_time)
            
            # Stage 3: Create storage context
            logger.info("\n" + "="*80)
            logger.info("STAGE 3/4: Initializing Vector Store")
            logger.info("="*80)
            
            storage_context = self._create_storage_context(clear_existing)
            
            # Stage 4: Embed and store
            logger.info("\n" + "="*80)
            logger.info("STAGE 4/4: Embedding and Storing Vectors")
            logger.info("="*80)
            
            self._embed_and_store(nodes, storage_context)
            
            # Success!
            return self._create_success_result(documents, nodes, start_time)
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
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
            logger.info(f"✓ Loaded {len(documents)} document(s)")
            return documents
        except Exception as e:
            logger.error(f"Document loading failed: {e}")
            raise

    def _chunk_documents(self, documents, inspect_chunks: bool):
        """Chunk documents into nodes."""
        try:
            nodes = self.chunker.chunk(documents)
            logger.info(f"✓ Created {len(nodes)} chunk(s)")
            
            # Optional inspection
            if inspect_chunks:
                logger.info("\n" + "-"*80)
                logger.info("Inspecting Chunks...")
                logger.info("-"*80)
                self.chunker.inspect(nodes, num_samples=5)
            
            return nodes
        except Exception as e:
            logger.error(f"Chunking failed: {e}")
            raise

    def _create_storage_context(self, clear_existing: bool):
        """Initialize Pinecone storage context."""
        try:
            storage_context = create_storage_context(
                self.config,
                clear_namespace=clear_existing,
            )
            logger.info("✓ Storage context initialized")
            return storage_context
        except Exception as e:
            logger.error(f"Storage context creation failed: {e}")
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
            
            logger.info(f"Using embedding model: {self.config.embedding_model}")
            logger.info(f"Batch size: {self.config.embedding_batch_size}")
            logger.info(f"Dimensions: {self.config.embedding_dimensions}")
            logger.info("\nGenerating embeddings and uploading to Pinecone...")
            
            # Build index (this does embedding + storage)
            VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True,
            )
            
            logger.info("✓ Vectors embedded and stored successfully")
            
        except Exception as e:
            logger.error(f"Embedding/storage failed: {e}")
            logger.error("Note: If namespace was cleared, vectors may be lost!")
            raise

    def _handle_dry_run(self, documents, nodes, start_time) -> dict:
        """Handle dry run completion."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("\n" + "="*80)
        logger.info("✓ DRY RUN COMPLETE")
        logger.info("="*80)
        logger.info("No embeddings were created or stored.")
        logger.info("This was a test run to verify document loading and chunking.")
        
        # Estimate costs
        estimated_cost = self._estimate_embedding_cost(nodes)
        logger.info(f"\nEstimated embedding cost: ${estimated_cost:.4f}")
        logger.info(f"Chunks that would be embedded: {len(nodes)}")
        
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
        return estimated_cost

    def _create_success_result(self, documents, nodes, start_time) -> dict:
        """Create success result dictionary with statistics."""
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("\n" + "="*80)
        logger.info("✅ INGESTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Documents processed: {len(documents)}")
        logger.info(f"Chunks created: {len(nodes)}")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Index: {self.config.pinecone_index_name}")
        logger.info(f"Namespace: {self.config.pinecone_namespace}")
        
        # Calculate statistics
        avg_chunk_size = sum(len(node.text) for node in nodes) / len(nodes) if nodes else 0
        
        logger.info(f"\nStatistics:")
        logger.info(f"  Average chunk size: {avg_chunk_size:.0f} chars")
        logger.info(f"  Vectors per document: {len(nodes) / len(documents):.1f}")
        logger.info(f"  Processing speed: {len(nodes) / duration:.1f} chunks/sec")
        
        return {
            "status": "success",
            "documents": len(documents),
            "chunks": len(nodes),
            "duration_seconds": round(duration, 2),
            "avg_chunk_size_chars": round(avg_chunk_size, 0),
            "chunks_per_document": round(len(nodes) / len(documents), 1),
            "processing_speed_chunks_per_sec": round(len(nodes) / duration, 1),
            "index": self.config.pinecone_index_name,
            "namespace": self.config.pinecone_namespace,
        }