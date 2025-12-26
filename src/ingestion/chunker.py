"""
Text chunking using LlamaIndex SentenceSplitter.
Converts Documents into sentence-aware Nodes.
"""

from typing import List

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, BaseNode

from src.config import Config


class DocumentChunker:
    """Chunks documents into nodes using sentence-aware splitting."""

    def __init__(self, config: Config):
        self.splitter = SentenceSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def chunk(self, documents: List[Document]) -> List[BaseNode]:
        if not documents:
            raise ValueError("No documents provided for chunking")

        nodes = self.splitter.get_nodes_from_documents(documents)

        if not nodes:
            raise ValueError("No nodes created during chunking")

        print(f"Created {len(nodes)} chunks")
        return nodes

    def inspect(self, nodes: List[BaseNode], num_samples: int = 3) -> None:
        """
        Inspect sample chunks for debugging and quality checks.
        """
        print("\n" + "=" * 80)
        print(f"Sample Chunks (showing {min(num_samples, len(nodes))})")
        print("=" * 80)

        for i, node in enumerate(nodes[:num_samples]):
            print(f"\n--- Chunk {i + 1} ---")
            print(f"Source: {node.metadata.get('file_name', 'unknown')}")
            print(f"Category: {node.metadata.get('category', 'unknown')}")
            print(f"Length: {len(node.text)} chars")
            print("\nPreview:")
            print(node.text[:300])
            print("-" * 80)
