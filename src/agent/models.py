"""
Data models for the agentic query system.

Identical contract to src/query/models.py — all downstream consumers
(backend/routes/webhook.py, backend/routes/query.py, admin dashboard)
work unchanged.
"""

from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass
class RetrievedChunk:
    """A single chunk retrieved from the vector database."""
    text: str
    source: str
    category: str
    similarity_score: float
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.source}] (score: {self.similarity_score:.3f})"


@dataclass
class QueryResponse:
    """
    Response returned by YamieAgent.query().

    Identical shape to the old QueryEngine.query() response so all
    downstream code (webhook, API route, Supabase logger) works without changes.
    """
    question: str
    answer: str
    sources: List[RetrievedChunk]        # chunks passed to Claude (above threshold)
    has_answer: bool
    response_time_seconds: float
    filtered_chunks: List[RetrievedChunk] = field(default_factory=list)  # below threshold, admin only
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def get_source_names(self) -> List[str]:
        return list(set(chunk.source for chunk in self.sources))

    def __str__(self) -> str:
        sources_str = ", ".join(self.get_source_names())
        return (
            f"\n{'='*80}\n"
            f"Question: {self.question}\n"
            f"{'-'*80}\n"
            f"Answer: {self.answer}\n"
            f"{'-'*80}\n"
            f"Sources: {sources_str}\n"
            f"Response Time: {self.response_time_seconds:.2f}s\n"
            f"{'='*80}\n"
        )
