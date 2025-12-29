"""
Text chunking using LlamaIndex SentenceSplitter.
Converts Documents into sentence-aware Nodes with comprehensive validation.
"""

import logging
from typing import List

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, BaseNode

from src.config import Config

logger = logging.getLogger(__name__)


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
            f"Chunker initialized: size={config.chunk_size}, "
            f"overlap={config.chunk_overlap}"
        )

    def _validate_config(self) -> None:
        """Validate chunking configuration makes sense."""
        if self.config.chunk_size < 50:
            logger.warning(f"Chunk size {self.config.chunk_size} is very small (<50 tokens)")
        
        if self.config.chunk_size > 2000:
            logger.warning(f"Chunk size {self.config.chunk_size} is very large (>2000 tokens)")
        
        if self.config.chunk_overlap >= self.config.chunk_size:
            raise ValueError(
                f"Chunk overlap ({self.config.chunk_overlap}) must be less than "
                f"chunk size ({self.config.chunk_size})"
            )
        
        if self.config.chunk_overlap < 0:
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
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Chunking {len(documents)} document(s)...")
        
        try:
            nodes = self.splitter.get_nodes_from_documents(documents)
        except Exception as e:
            logger.error(f"Chunking failed: {e}")
            raise ValueError(f"Failed to chunk documents: {e}")

        if not nodes:
            error_msg = "No nodes created during chunking (documents may be empty)"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Calculate and log statistics
        self._log_chunk_statistics(nodes)
        
        logger.info(f"✓ Created {len(nodes)} chunks")
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
            f"Chunk statistics: "
            f"total={len(nodes)}, "
            f"avg_chars={avg_chars:.0f}, "
            f"avg_words={avg_words:.0f}, "
            f"min_chars={min_chars}, "
            f"max_chars={max_chars}"
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
            logger.warning("No nodes to inspect")
            return
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"CHUNK INSPECTION - Showing {min(num_samples, len(nodes))} of {len(nodes)} chunks")
        logger.info(f"{'=' * 80}")
        
        # Overall statistics
        char_counts = [len(node.text) for node in nodes]
        word_counts = [len(node.text.split()) for node in nodes]
        
        logger.info(f"\nOverall Statistics:")
        logger.info(f"  Total chunks: {len(nodes)}")
        logger.info(f"  Average length: {sum(char_counts) / len(nodes):.0f} chars, {sum(word_counts) / len(nodes):.0f} words")
        logger.info(f"  Size range: {min(char_counts)} - {max(char_counts)} chars")
        
        # Category distribution
        categories = {}
        for node in nodes:
            cat = node.metadata.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        logger.info(f"\nCategory Distribution:")
        for cat, count in sorted(categories.items()):
            logger.info(f"  {cat}: {count} chunks ({count/len(nodes)*100:.1f}%)")
        
        # Sample chunks
        logger.info(f"\n{'=' * 80}")
        logger.info("SAMPLE CHUNKS")
        logger.info(f"{'=' * 80}")
        
        for i, node in enumerate(nodes[:num_samples]):
            logger.info(f"\n--- Chunk {i + 1} ---")
            logger.info(f"Source: {node.metadata.get('file_name', 'unknown')}")
            logger.info(f"Category: {node.metadata.get('category', 'unknown')}")
            logger.info(f"Length: {len(node.text)} chars ({len(node.text.split())} words)")
            
            if 'char_count' in node.metadata:
                logger.info(f"Original doc size: {node.metadata['char_count']} chars")
            
            logger.info(f"\nPreview (first 400 chars):")
            preview = node.text[:400]
            if len(node.text) > 400:
                preview += "..."
            logger.info(preview)
            logger.info("-" * 80)