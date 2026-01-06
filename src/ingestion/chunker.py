"""
Text chunking using LlamaIndex SentenceSplitter.
Converts Documents into sentence-aware Nodes with comprehensive validation.
"""

import structlog
from typing import List

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, BaseNode

from src.config import Config

logger = structlog.get_logger(__name__)


class DocumentChunker:
    """
    Chunks documents into nodes using sentence-aware splitting.
    Preserves sentence boundaries for better semantic coherence.
    """

    def __init__(self, config: Config):
        self.config = config
        
        # Validate chunk configuration
        self._validate_config()
        
        # Initialize splitter
        self.splitter = SentenceSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        
        logger.info(
            "chunker_initialized",
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )

    def _validate_config(self) -> None:
        """Validate chunking configuration makes sense."""
        if self.config.chunk_size < 50:
            logger.warning(
                "chunk_size_very_small",
                chunk_size=self.config.chunk_size,
                threshold=50
            )
        
        if self.config.chunk_size > 2000:
            logger.warning(
                "chunk_size_very_large",
                chunk_size=self.config.chunk_size,
                threshold=2000
            )
        
        if self.config.chunk_overlap >= self.config.chunk_size:
            logger.error(
                "invalid_chunk_config",
                reason="overlap_exceeds_size",
                chunk_overlap=self.config.chunk_overlap,
                chunk_size=self.config.chunk_size
            )
            raise ValueError(
                f"Chunk overlap ({self.config.chunk_overlap}) must be less than "
                f"chunk size ({self.config.chunk_size})"
            )
        
        if self.config.chunk_overlap < 0:
            logger.error(
                "invalid_chunk_config",
                reason="negative_overlap",
                chunk_overlap=self.config.chunk_overlap
            )
            raise ValueError(f"Chunk overlap cannot be negative: {self.config.chunk_overlap}")

    def chunk(self, documents: List[Document]) -> List[BaseNode]:
        """
        Chunk documents into nodes with sentence-aware splitting.
        
        Args:
            documents: List of Document objects to chunk
            
        Returns:
            List of BaseNode objects (chunks with metadata)
            
        Raises:
            ValueError: If no documents provided or chunking fails
        """
        if not documents:
            error_msg = "No documents provided for chunking"
            logger.error("chunking_failed", reason="no_documents")
            raise ValueError(error_msg)

        logger.info(
            "chunking_started",
            documents_count=len(documents)
        )
        
        try:
            nodes = self.splitter.get_nodes_from_documents(documents)
            logger.debug("nodes_created", count=len(nodes) if nodes else 0)
        except Exception as e:
            logger.error(
                "chunking_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ValueError(f"Failed to chunk documents: {e}")

        if not nodes:
            error_msg = "No nodes created during chunking (documents may be empty)"
            logger.error(
                "chunking_failed",
                reason="no_nodes_created"
            )
            raise ValueError(error_msg)

        # Calculate and log statistics
        self._log_chunk_statistics(nodes)
        
        logger.info(
            "chunking_completed",
            chunks_created=len(nodes)
        )
        return nodes

    def _log_chunk_statistics(self, nodes: List[BaseNode]) -> None:
        """Calculate and log useful statistics about chunks."""
        if not nodes:
            return
        
        # Character counts
        char_counts = [len(node.text) for node in nodes]
        total_chars = sum(char_counts)
        avg_chars = total_chars / len(nodes)
        min_chars = min(char_counts)
        max_chars = max(char_counts)
        
        # Word counts  
        word_counts = [len(node.text.split()) for node in nodes]
        avg_words = sum(word_counts) / len(nodes)
        
        logger.info(
            "chunk_statistics",
            total_chunks=len(nodes),
            avg_chars=round(avg_chars, 0),
            avg_words=round(avg_words, 0),
            min_chars=min_chars,
            max_chars=max_chars
        )

    def inspect(self, nodes: List[BaseNode], num_samples: int = 4) -> None:
        """
        Inspect sample chunks for debugging and quality checks.
        Shows chunk content, metadata, and distribution statistics.
        
        Args:
            nodes: List of nodes to inspect
            num_samples: Number of sample chunks to display (default: 3)
        """
        if not nodes:
            logger.warning("chunk_inspection_skipped", reason="no_nodes")
            return
        
        logger.info(
            "chunk_inspection_started",
            total_chunks=len(nodes),
            samples_to_show=min(num_samples, len(nodes))
        )
        
        # Overall statistics
        char_counts = [len(node.text) for node in nodes]
        word_counts = [len(node.text.split()) for node in nodes]
        
        logger.info(
            "chunk_overall_statistics",
            total_chunks=len(nodes),
            avg_chars=round(sum(char_counts) / len(nodes), 0),
            avg_words=round(sum(word_counts) / len(nodes), 0),
            min_chars=min(char_counts),
            max_chars=max(char_counts)
        )
        
        # Category distribution
        categories = {}
        for node in nodes:
            cat = node.metadata.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        logger.info(
            "chunk_category_distribution",
            categories=categories
        )
        
        for cat, count in sorted(categories.items()):
            percentage = round(count / len(nodes) * 100, 1)
            logger.debug(
                "category_breakdown",
                category=cat,
                count=count,
                percentage=percentage
            )
        
        # Sample chunks
        logger.info("chunk_samples", message="Showing sample chunks")
        
        for i, node in enumerate(nodes[:num_samples]):
            logger.info(
                "chunk_sample",
                chunk_number=i + 1,
                source=node.metadata.get('file_name', 'unknown'),
                category=node.metadata.get('category', 'unknown'),
                length_chars=len(node.text),
                length_words=len(node.text.split()),
                original_doc_size=node.metadata.get('char_count', 'unknown'),
                text_preview=node.text[:400] + ("..." if len(node.text) > 400 else "")
            )