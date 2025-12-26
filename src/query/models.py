"""
Data models for the query system.
Defines typed structures for requests, responses, and retrieved chunks.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class RetrievedChunk:
    """
    Represents a single chunk retrieved from the vector database.
    """
    text: str                          # The actual chunk text
    source: str                        # Source document (e.g., "menu.pdf")
    category: str                      # Document category (menu, sop, hr, equipment)
    similarity_score: float            # Cosine similarity score (0.0 to 1.0)
    metadata: dict = field(default_factory=dict)  # Additional metadata
    
    def __str__(self) -> str:
        return f"[{self.source}] (score: {self.similarity_score:.3f})"


@dataclass
class QueryRequest:
    """
    Represents an incoming query request.
    """
    question: str                      # User's question
    top_k: int = 5                     # Number of chunks to retrieve
    category_filter: Optional[str] = None  # Optional category filter (e.g., "menu")
    
    def validate(self) -> None:
        """Validate the request."""
        if not self.question or not self.question.strip():
            raise ValueError("Question cannot be empty")
        
        if self.top_k < 1 or self.top_k > 20:
            raise ValueError("top_k must be between 1 and 20")
        
        if self.category_filter and self.category_filter not in ["menu", "sop", "hr", "equipment", "general"]:
            raise ValueError(f"Invalid category: {self.category_filter}")


@dataclass
class QueryResponse:
    """
    Represents the response to a query.
    Contains the answer, sources, and metadata.
    """
    question: str                      # Original question
    answer: str                        # Generated answer
    sources: List[RetrievedChunk]      # Chunks used to generate answer
    has_answer: bool                   # True if answer found, False if "I don't know"
    confidence: str                    # "high", "medium", "low"
    response_time_seconds: float       # How long it took to generate
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def get_source_names(self) -> List[str]:
        """Get unique list of source document names."""
        return list(set(chunk.source for chunk in self.sources))
    
    def __str__(self) -> str:
        """Pretty print the response."""
        sources_str = ", ".join(self.get_source_names())
        return (
            f"\n{'='*80}\n"
            f"Question: {self.question}\n"
            f"{'-'*80}\n"
            f"Answer: {self.answer}\n"
            f"{'-'*80}\n"
            f"Sources: {sources_str}\n"
            f"Confidence: {self.confidence}\n"
            f"Response Time: {self.response_time_seconds:.2f}s\n"
            f"{'='*80}\n"
        )