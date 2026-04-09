"""
YamieAgent — Agentic RAG core for YamieBot.

Replaces the classical RAG pipeline (embed → Pinecone → filter → LLM) with
an agentic loop where Claude controls retrieval. Claude decides when to search,
what to search for, and can issue multiple refined searches before generating
an answer.

Architecture:
    User question
    → Build Anthropic messages array (system + conversation history + question)
    → Claude API call (with search_knowledge_base tool available)
    → Claude calls tool → Pinecone search → results returned to Claude
    → Claude may search again with refined terms, or generate final answer
    → QueryResponse returned (identical contract to old QueryEngine)

Drop-in replacement for QueryEngine.
backend/engine.py swaps one import — nothing else changes.
"""

import structlog
from datetime import datetime
from typing import Optional
import anthropic

from src.config import Config, get_config
from src.agent.models import QueryResponse, RetrievedChunk
from src.agent.tools import KnowledgeBaseSearcher, SEARCH_KNOWLEDGE_BASE_TOOL
from src.agent.system_prompt import ACTIVE_SYSTEM_PROMPT, ACTIVE_SYSTEM_PROMPT_VERSION
from src.memory.conversation_memory import ConversationMemory

logger = structlog.get_logger(__name__)

# Claude Sonnet 4.6 — near-Opus quality, significantly cheaper, fast enough for WhatsApp
CLAUDE_MODEL = "claude-sonnet-4-6"

# Safety ceiling on tool calls per query.
# Prevents infinite loops if Claude gets confused. In practice it searches 1-3 times.
MAX_TOOL_CALLS = 5


class YamieAgent:
    """
    Agentic RAG engine for YamieBot.

    Public interface is identical to the old QueryEngine:
        agent.query(question, user_id) → QueryResponse
        agent.get_stats() → dict

    Internal architecture is completely different:
    - No LlamaIndex
    - No separate retrieval + responder steps
    - Claude controls retrieval via tool use
    - Conversation history passed as native Anthropic messages (not injected as string)
    """

    def __init__(self, config: Config = None):
        self.config = config or get_config()

        logger.info(
            "yamie_agent_initialization_started",
            model=CLAUDE_MODEL,
            system_prompt_version=ACTIVE_SYSTEM_PROMPT_VERSION,
        )

        try:
            self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
            self.searcher = KnowledgeBaseSearcher(config=self.config)
            self.memory = ConversationMemory(config=self.config)

            logger.info(
                "yamie_agent_initialized",
                model=CLAUDE_MODEL,
                system_prompt_version=ACTIVE_SYSTEM_PROMPT_VERSION,
                status="ready",
            )

        except Exception as e:
            logger.error("yamie_agent_initialization_failed", error=str(e), error_type=type(e).__name__)
            raise RuntimeError(f"YamieAgent initialization failed: {e}")

    def query(
        self,
        question: str,
        user_id: str = "default_user",
        top_k: Optional[int] = None,
    ) -> QueryResponse:
        """
        Answer a question using agentic RAG.

        Claude controls retrieval: it decides when to search, what to search
        for, and can issue multiple refined searches before answering.

        Args:
            question:  The user's question (raw input — sanitized internally)
            user_id:   User identifier for conversation memory (phone number or session ID)
            top_k:     Chunks to retrieve per namespace (overrides config default)

        Returns:
            QueryResponse with answer, all retrieved chunks, and timing metadata.
            Identical shape to what the old QueryEngine returned.
        """
        query_start = datetime.utcnow()

        # Sanitize and validate input
        try:
            question = self._sanitize_question(question)
        except ValueError as e:
            logger.warning("invalid_question", error=str(e))
            raise

        logger.info("agent_query_started", user_id=user_id, question=question[:100])

        # Build Anthropic messages array from Redis conversation history
        # This is the correct way to pass history to Claude — native message format,
        # NOT a string injection hack.
        conversation = self.memory.get_conversation(user_id)
        messages = self._build_messages(conversation, question)

        # Accumulate all chunks retrieved during this query for admin dashboard logging
        all_passed_chunks: list[RetrievedChunk] = []
        all_filtered_chunks: list[RetrievedChunk] = []
        tool_calls_made = 0
        final_answer = ""

        # ── Agentic loop ──────────────────────────────────────────────────────
        # Claude decides: search (tool_use) or answer (end_turn).
        # We execute every search request and feed results back.
        # Loop continues until Claude answers or we hit the tool call ceiling.
        # ─────────────────────────────────────────────────────────────────────
        while True:
            try:
                response = self.client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=self.config.llm_max_tokens,
                    temperature=self.config.llm_temperature,
                    system=ACTIVE_SYSTEM_PROMPT,
                    tools=[SEARCH_KNOWLEDGE_BASE_TOOL],
                    messages=messages,
                )
            except anthropic.APIError as e:
                logger.error("claude_api_error", error=str(e), status_code=getattr(e, "status_code", None))
                return self._error_response(question, query_start)
            except Exception as e:
                logger.error("claude_unexpected_error", error=str(e), error_type=type(e).__name__)
                return self._error_response(question, query_start)

            # ── Case 1: Claude is done — extract the final text answer ────────
            if response.stop_reason == "end_turn":
                final_answer = self._extract_text(response)
                logger.info(
                    "agent_answered",
                    tool_calls_made=tool_calls_made,
                    answer_length=len(final_answer),
                )
                break

            # ── Case 2: Claude wants to search ───────────────────────────────
            elif response.stop_reason == "tool_use":
                tool_use_block = next(
                    (b for b in response.content if b.type == "tool_use"), None
                )

                if not tool_use_block:
                    logger.error("tool_use_block_missing")
                    final_answer = self._extract_text(response)
                    break

                tool_input = tool_use_block.input
                tool_calls_made += 1

                logger.info(
                    "tool_called",
                    call_number=tool_calls_made,
                    query=tool_input.get("query", "")[:100],
                    namespaces=tool_input.get("namespaces"),
                    top_k=tool_input.get("top_k"),
                )

                # Execute the search
                try:
                    passed, filtered = self.searcher.search(
                        query=tool_input["query"],
                        namespaces=tool_input.get("namespaces"),
                        top_k=tool_input.get("top_k") or top_k or self.config.query_top_k,
                    )
                except Exception as e:
                    logger.error("tool_execution_failed", error=str(e))
                    passed, filtered = [], []

                all_passed_chunks.extend(passed)
                all_filtered_chunks.extend(filtered)

                tool_result_text = self.searcher.format_for_claude(passed)

                # Extend the messages array with Claude's tool_use + our tool_result.
                # This is the correct Anthropic API pattern for tool calls.
                messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_block.id,
                                "content": tool_result_text,
                            }
                        ],
                    },
                ]

                # Hit the ceiling — force a final answer without tools
                if tool_calls_made >= MAX_TOOL_CALLS:
                    logger.warning(
                        "tool_call_limit_reached",
                        limit=MAX_TOOL_CALLS,
                        action="forcing_final_answer",
                    )
                    try:
                        final_response = self.client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=self.config.llm_max_tokens,
                            temperature=self.config.llm_temperature,
                            system=ACTIVE_SYSTEM_PROMPT,
                            # No tools — forces Claude to generate text answer
                            messages=messages,
                        )
                        final_answer = self._extract_text(final_response)
                    except Exception as e:
                        logger.error("forced_final_answer_failed", error=str(e))
                        final_answer = (
                            "Het spijt me, ik kon geen volledig antwoord vinden. "
                            "Probeer je vraag specifieker te formuleren."
                        )
                    break

            # ── Case 3: Unexpected stop reason ───────────────────────────────
            else:
                logger.warning("unexpected_stop_reason", stop_reason=response.stop_reason)
                final_answer = self._extract_text(response) or (
                    "Er is een onverwachte fout opgetreden. Probeer het opnieuw."
                )
                break

        # ── Save conversation turn to Redis ───────────────────────────────────
        # We save only the final Q → A pair, not the intermediate tool messages.
        # This keeps Redis memory clean and the next call's message history correct.
        if final_answer:
            try:
                self.memory.add_turn(user_id, question, final_answer)
            except Exception as e:
                logger.warning("memory_save_failed", error=str(e), user_id=user_id)

        total_time = (datetime.utcnow() - query_start).total_seconds()

        # Determine has_answer — used by admin dashboard and Supabase logging
        has_answer = bool(final_answer) and not any(
            phrase in final_answer.lower()
            for phrase in [
                "geen informatie gevonden",
                "niet gevonden",
                "weet ik niet",
                "kan ik niet",
                "geen antwoord",
                "geen relevante",
            ]
        )

        logger.info(
            "agent_query_completed",
            user_id=user_id,
            response_time_seconds=round(total_time, 3),
            tool_calls=tool_calls_made,
            chunks_passed=len(all_passed_chunks),
            chunks_filtered=len(all_filtered_chunks),
            has_answer=has_answer,
        )

        return QueryResponse(
            question=question,
            answer=final_answer,
            sources=all_passed_chunks,
            has_answer=has_answer,
            response_time_seconds=total_time,
            filtered_chunks=all_filtered_chunks,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_messages(self, conversation: list[dict], current_question: str) -> list[dict]:
        """
        Convert Redis conversation history to Anthropic messages array format.

        Old system: injected history as a string inside the prompt → ugly, imprecise.
        New system: native Anthropic messages format → Claude understands context perfectly.

        Each turn in Redis is {question, answer, timestamp}.
        We convert to alternating user/assistant messages, then append the current question.
        """
        messages: list[dict] = []

        for turn in conversation:
            messages.append({"role": "user", "content": turn["question"]})
            messages.append({"role": "assistant", "content": turn["answer"]})

        messages.append({"role": "user", "content": current_question})

        return messages

    def _extract_text(self, response) -> str:
        """Extract the text content from a Claude API response."""
        if not response or not response.content:
            return ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                return block.text.strip()
        return ""

    def _sanitize_question(self, question: str) -> str:
        """
        Sanitize and validate user input.

        Blocks HTML/script injection and obvious SQL injection patterns.
        Everything else is allowed — users are restaurant staff asking work questions.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        question = question.strip()

        if len(question) > 500:
            raise ValueError(
                f"Vraag is te lang ({len(question)} tekens). Maximum is 500 tekens."
            )

        # Normalize whitespace
        question = " ".join(question.split())

        question_lower = question.lower()

        # Block HTML/script injection
        for pattern in ["<script", "</script>", "<iframe", "javascript:", "onerror=", "onload="]:
            if pattern in question_lower:
                raise ValueError("HTML/script patronen zijn niet toegestaan in vragen.")

        # Block obvious SQL injection patterns
        for pattern in ["'; drop", '"; drop', "' or '1'='1", "';--", '";--']:
            if pattern in question_lower:
                raise ValueError("Injectiepatronen gedetecteerd in de vraag.")

        return question

    def _error_response(self, question: str, query_start: datetime) -> QueryResponse:
        """Create a safe error response when something goes wrong."""
        return QueryResponse(
            question=question,
            answer="Sorry, er is een fout opgetreden. Probeer het opnieuw.",
            sources=[],
            has_answer=False,
            response_time_seconds=(datetime.utcnow() - query_start).total_seconds(),
        )

    def get_stats(self) -> dict:
        """
        System statistics — compatible with old QueryEngine.get_stats() interface.
        Used by the admin dashboard system page.
        """
        try:
            retriever_stats = self.searcher.get_stats()
        except Exception:
            retriever_stats = {}

        return {
            "retriever": retriever_stats,
            "config": {
                "top_k": self.config.query_top_k,
                "similarity_threshold": self.config.query_similarity_threshold,
                "llm_model": CLAUDE_MODEL,
                "temperature": self.config.llm_temperature,
                "max_tokens": self.config.llm_max_tokens,
                "embedding_model": self.config.embedding_model,
                "chunk_size": self.config.chunk_size,
                "system_prompt_version": ACTIVE_SYSTEM_PROMPT_VERSION,
            },
        }
