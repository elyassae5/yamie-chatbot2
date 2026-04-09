"""
Tool definitions and execution for the YamieBot agent.

The agent has one primary tool: search_knowledge_base.
Claude calls this tool autonomously — it decides when to search,
what to search for, and can issue multiple refined searches before answering.

No LlamaIndex. Direct Pinecone SDK calls.
Embeddings still use OpenAI text-embedding-3-large (must match what was ingested).
"""

import json
import structlog
from typing import Optional
from openai import OpenAI
from pinecone import Pinecone
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

from src.config import Config, get_config
from src.agent.models import RetrievedChunk

logger = structlog.get_logger(__name__)

NAMESPACES = [
    "yamie-pastabar",
    "flaminwok",
    "smokey-joes",
    "operations-department",
    "officiele-documenten",
]

# ─────────────────────────────────────────────────────────────────────────────
# TOOL SCHEMA
# This is exactly what Claude sees. The description is in Dutch so Claude
# reasons about searches in the same language as the user.
# ─────────────────────────────────────────────────────────────────────────────

SEARCH_KNOWLEDGE_BASE_TOOL = {
    "name": "search_knowledge_base",
    "description": (
        "Zoek in de interne kennisbank van de Yamie-groep naar relevante informatie.\n\n"
        "Gebruik dit tool wanneer je specifieke informatie nodig hebt over:\n"
        "- Procedures, beleid, of richtlijnen\n"
        "- Medewerkers, functies, of contactgegevens\n"
        "- Vestigingen, adressen, of locatie-informatie\n"
        "- Menu's, allergenen, of productinformatie\n"
        "- Franchise-informatie of operationele documenten\n\n"
        "Tips voor betere resultaten:\n"
        "- Gebruik specifieke zoektermen (naam, locatie, procedure)\n"
        "- Als de eerste zoekopdracht weinig oplevert, zoek opnieuw met andere termen\n"
        "- Gebruik de namespaces om gericht te zoeken per merk of afdeling\n"
        "- Gebruik dit tool NIET voor begroetingen of smalltalk"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "De zoekterm of vraag om in de kennisbank te zoeken. "
                    "Gebruik specifieke, gerichte termen voor de beste resultaten."
                ),
            },
            "namespaces": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": NAMESPACES,
                },
                "description": (
                    "Optioneel: specifieke namespaces om in te zoeken. "
                    "Laat leeg om alle namespaces te doorzoeken. "
                    "yamie-pastabar = Yamie Pastabar vestigingen en documenten. "
                    "flaminwok = Flamin'wok vestigingen en documenten. "
                    "smokey-joes = Smokey Joe's vestigingen en documenten. "
                    "operations-department = procedures, SOPs, rapporten, franchisebeleid. "
                    "officiele-documenten = menu's, allergenenlijsten, handboek."
                ),
            },
            "top_k": {
                "type": "integer",
                "description": (
                    "Aantal resultaten per namespace om op te halen (standaard 5, max 10). "
                    "Verhoog dit als je meer context nodig hebt."
                ),
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE SEARCHER
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeBaseSearcher:
    """
    Executes vector similarity searches against Pinecone.

    Replaces the LlamaIndex-based Retriever entirely.
    Direct Pinecone SDK calls — no framework overhead.

    Embedding model must match what was used during ingestion (text-embedding-3-large, 3072d).
    This cannot be changed without a full Pinecone re-ingest.
    """

    def __init__(self, config: Config = None):
        self.config = config or get_config()

        self._openai_client = OpenAI(api_key=self.config.openai_api_key)
        self._pinecone_client = Pinecone(api_key=self.config.pinecone_api_key)
        self._index = self._pinecone_client.Index(self.config.pinecone_index_name)

        logger.info(
            "knowledge_base_searcher_initialized",
            index=self.config.pinecone_index_name,
            embedding_model=self.config.embedding_model,
            embedding_dimensions=self.config.embedding_dimensions,
        )

    def _embed(self, text: str) -> list[float]:
        """
        Embed text using OpenAI.

        Uses the same model and dimensions as the ingestion pipeline.
        Changing this without re-ingesting all vectors would break retrieval.
        """
        response = self._openai_client.embeddings.create(
            model=self.config.embedding_model,
            input=text,
            dimensions=self.config.embedding_dimensions,
        )
        return response.data[0].embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _query_namespace(
        self,
        vector: list[float],
        namespace: str,
        top_k: int,
    ) -> list[dict]:
        """Query a single Pinecone namespace with retry logic."""
        results = self._index.query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )
        return results.get("matches", [])

    def _extract_text(self, metadata: dict) -> str:
        """
        Extract chunk text from Pinecone metadata.

        LlamaIndex stores text under 'text' key by default (text_key parameter).
        Falls back to parsing '_node_content' JSON if 'text' key is absent
        (older LlamaIndex versions stored the full node as JSON here).
        """
        # Primary path: direct 'text' field (LlamaIndex default)
        text = metadata.get("text", "")
        if text:
            return text

        # Fallback: full node content as JSON string
        node_content_raw = metadata.get("_node_content")
        if node_content_raw:
            try:
                node_content = json.loads(node_content_raw)
                text = node_content.get("text", "")
                if text:
                    return text
            except (json.JSONDecodeError, TypeError):
                pass

        return ""

    def search(
        self,
        query: str,
        namespaces: Optional[list[str]] = None,
        top_k: int = 5,
        threshold: Optional[float] = None,
    ) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
        """
        Search Pinecone across specified namespaces.

        Returns:
            (passed_chunks, filtered_chunks)
            passed_chunks   — above similarity threshold, returned to Claude
            filtered_chunks — below threshold, kept for admin dashboard logging only
                              Claude never sees these.
        """
        threshold = threshold if threshold is not None else self.config.query_similarity_threshold
        namespaces_to_search = namespaces if namespaces else NAMESPACES
        top_k = min(max(top_k, 1), 10)

        # Embed once, reuse for all namespace queries
        try:
            query_vector = self._embed(query)
        except Exception as e:
            logger.error("embedding_failed", query=query[:100], error=str(e))
            return [], []

        all_chunks: list[RetrievedChunk] = []

        for namespace in namespaces_to_search:
            try:
                matches = self._query_namespace(query_vector, namespace, top_k)

                for match in matches:
                    metadata = match.get("metadata", {})
                    text = self._extract_text(metadata)

                    if not text:
                        logger.warning(
                            "empty_chunk_skipped",
                            match_id=match.get("id"),
                            namespace=namespace,
                        )
                        continue

                    # Prefer descriptive source_path over raw file_name
                    source = metadata.get("source_path") or metadata.get("file_name", "unknown")

                    all_chunks.append(RetrievedChunk(
                        text=text,
                        source=source,
                        category=metadata.get("category", "general"),
                        similarity_score=match.get("score", 0.0),
                        metadata={**metadata, "namespace": namespace},
                    ))

            except Exception as e:
                logger.warning(
                    "namespace_search_failed",
                    namespace=namespace,
                    error=str(e),
                )

        # Sort highest score first, then split by threshold
        all_chunks.sort(key=lambda c: c.similarity_score, reverse=True)
        passed = [c for c in all_chunks if c.similarity_score >= threshold]
        filtered = [c for c in all_chunks if c.similarity_score < threshold]

        logger.info(
            "search_completed",
            query=query[:100],
            namespaces=namespaces_to_search,
            total_retrieved=len(all_chunks),
            passed_threshold=len(passed),
            filtered_out=len(filtered),
            threshold=threshold,
        )

        return passed, filtered

    def format_for_claude(self, chunks: list[RetrievedChunk]) -> str:
        """
        Format retrieved chunks as readable text for Claude.

        Claude receives this as the tool_result content.
        Scores are shown so Claude can reason about relevance.
        """
        if not chunks:
            return (
                "Geen relevante informatie gevonden in de kennisbank voor deze zoekopdracht. "
                "Probeer te zoeken met andere termen als je denkt dat er wel informatie over is."
            )

        parts = [f"Gevonden {len(chunks)} relevant fragment(en) uit de kennisbank:\n"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[Fragment {i} | Bron: {chunk.source} | Score: {chunk.similarity_score:.3f}]"
            )
            parts.append(chunk.text.strip())
            parts.append("")  # blank line between chunks

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Pinecone index statistics — used by admin dashboard system page."""
        try:
            stats = self._index.describe_index_stats()
            return {
                "total_vectors": stats.get("total_vector_count", 0),
                "dimension": stats.get("dimension", 0),
                "active_namespaces": NAMESPACES,
                "namespace_vectors": {
                    ns: data.get("vector_count", 0)
                    for ns, data in stats.get("namespaces", {}).items()
                },
                "multi_namespace_mode": True,
            }
        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            return {}
