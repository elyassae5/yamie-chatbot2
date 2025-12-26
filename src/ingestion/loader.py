"""
Document loader with metadata extraction and basic validation.
Uses LlamaIndex SimpleDirectoryReader for robust PDF handling.
"""

from pathlib import Path
from typing import List
from datetime import datetime

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document

from src.config import Config


class DocumentLoader:
    """Loads documents and enriches them with minimal metadata."""

    CATEGORY_KEYWORDS = {
        "menu": ["menu", "pizza", "pasta", "dish", "food", "drink"],
        "sop": ["sop", "procedure", "process", "operating"],
        "hr": ["hr", "policy", "employee", "staff", "leave", "sick"],
        "equipment": ["equipment", "machine", "maintenance", "repair", "cleaning"],
    }

    def __init__(self, config: Config):
        self.data_dir = Path(config.data_dir)
        self.supported_extensions = config.supported_extensions

    def _categorize(self, filename: str) -> str:
        filename_lower = filename.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in filename_lower for keyword in keywords):
                return category
        return "general"

    def _is_valid(self, document: Document) -> bool:
        """Reject empty  documents."""
        return bool(document.text and document.text.strip())

    def _enrich_metadata(self, document: Document) -> Document:
        filename = document.metadata.get("file_name", "unknown")

        document.metadata.update({
            "category": self._categorize(filename),
            "ingested_at": datetime.utcnow().isoformat(),
            "char_count": len(document.text),
            "word_count": len(document.text.split()),
        })

        return document

    def load(self) -> List[Document]:
        """Load, validate, and enrich documents."""
        print(f"\n Loading documents from {self.data_dir}")

        reader = SimpleDirectoryReader(
            input_dir=str(self.data_dir),
            required_exts=self.supported_extensions,
            filename_as_id=True,
        )

        documents = reader.load_data()
        if not documents:
            raise ValueError(f"No documents found in {self.data_dir}")

        valid_docs = []
        skipped = []

        for doc in documents:
            if not self._is_valid(doc):
                skipped.append(doc.metadata.get("file_name", "unknown"))
                continue

            valid_docs.append(self._enrich_metadata(doc))

        print(f" Loaded {len(valid_docs)} valid documents")
        if skipped:
            print(f" Skipped {len(skipped)} empty/broken documents")

        return valid_docs
