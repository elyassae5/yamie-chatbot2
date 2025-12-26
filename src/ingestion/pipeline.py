"""
Main ingestion pipeline orchestrator.
Loads documents, chunks them, embeds, and stores vectors.
"""

from datetime import datetime
from typing import Optional

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.ingestion.loader import DocumentLoader
from src.ingestion.chunker import DocumentChunker
from src.ingestion.vector_store import create_storage_context


class IngestionPipeline:

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

        self.loader = DocumentLoader(self.config)
        self.chunker = DocumentChunker(self.config)

    def run(self, clear_existing: bool = False, dry_run: bool = False, inspect_chunks: bool = False) -> dict:
        
        start_time = datetime.utcnow()

        print("\nStarting YamieBot ingestion pipeline")
        self.config.display()

        # Load documents
        documents = self.loader.load()

        # Chunk documents
        nodes = self.chunker.chunk(documents)

        if inspect_chunks:
            self.chunker.inspect(nodes, num_samples=5)

        if dry_run:
            print("\nDry run complete (no embeddings created)")
            return {
                "status": "dry_run",
                "documents": len(documents),
                "chunks": len(nodes),
            }

        # Create storage context (Pinecone)
        storage_context = create_storage_context(
            self.config,
            clear_namespace=clear_existing,
        )

        # Create embedding model
        embed_model = OpenAIEmbedding(
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dimensions,
            embed_batch_size=self.config.embedding_batch_size,
        )

        # Build index (embed + store)
        print("\nEmbedding and storing vectors...")
        VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=embed_model,
            show_progress=True,
        )

        duration = (datetime.utcnow() - start_time).total_seconds()

        print("\nIngestion complete")
        print(f"Documents processed: {len(documents)}")
        print(f"Chunks created: {len(nodes)}")
        print(f"Duration: {duration:.2f}s")

        return {
            "status": "success",
            "documents": len(documents),
            "chunks": len(nodes),
            "duration_seconds": round(duration, 2),
            "index": self.config.pinecone_index_name,
            "namespace": self.config.pinecone_namespace,
        }
