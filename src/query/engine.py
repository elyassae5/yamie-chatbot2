"""
Query engine - main orchestrator for the question-answering system.
Ties together retrieval, prompt building, and answer generation with
comprehensive structured logging and monitoring.
"""

import structlog
from typing import Optional
from datetime import datetime
import openai

from src.config import Config, get_config
from src.query.models import QueryRequest, QueryResponse
from src.query.retriever import Retriever
from src.query.responder import Responder
from src.memory.conversation_memory import ConversationMemory

logger = structlog.get_logger(__name__)


class QueryEngine:
    """
    Main query engine that orchestrates the RAG pipeline.
    
    This is the public API for asking questions. It coordinates:
    1. Input validation and sanitization
    2. Document retrieval from vector store
    3. Answer generation using LLM
    4. Response assembly and metadata tracking
    
    The engine handles errors gracefully and ensures the system
    fails safely if any component encounters an issue.
    """
    
    def __init__(self, config: Config = None):
        """
        Initialize the query engine with retriever and responder.
        
        Args:
            config: Optional configuration object (uses default if not provided)
        """
        self.config = config or get_config()
        
        logger.info("query_engine_initialization_started")
        
        try:
            # Initialize components
            logger.info("initializing_component", component="retriever")
            self.retriever = Retriever(config=self.config)
            
            logger.info("initializing_component", component="responder")
            self.responder = Responder(config=self.config)
            
            logger.info("initializing_component", component="conversation_memory")
            self.memory = ConversationMemory(config=self.config)
            
            logger.info(
                "query_engine_ready",
                status="initialized",
                components=["retriever", "responder", "memory"]
            )
            
        except Exception as e:
            logger.error(
                "query_engine_initialization_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Query engine initialization failed: {e}")
    
    def query(
        self,
        question: str,
        user_id: str = "default_user",
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
    ) -> QueryResponse:
        """
        Answer a question using the RAG pipeline.
        
        This is the main entry point for querying the system.
        
        Pipeline stages:
        1. Validate and sanitize input
        2. Create query request object
        3. Retrieve relevant chunks from vector store
        4. Generate answer using LLM
        5. Return structured response
         
        Args:
            question: User's question
            user_id: User identifier for conversation tracking
            top_k: Number of chunks to retrieve (default from config)
            category_filter: Optional category to search in 
                           ("menu", "sop", "hr", "equipment", "franchise", "operations")
            
        Returns:
            QueryResponse with answer, sources, and metadata
            
        Raises:
            ValueError: If question is invalid (empty, too long, etc.)
            
        Example:
            >>> engine = QueryEngine()
            >>> response = engine.query("Wie is Daoud?")
            >>> print(response.answer)
            "Daoud is verantwoordelijk voor managementondersteuning..."
            >>> print(response.sources)
            [smokey_joes_interne_franchisehandleiding.docx]
        """
        query_start = datetime.utcnow()
        
        logger.info(
            "query_started",
            question=question,
            user_id=user_id,
            top_k=top_k or self.config.query_top_k,
            category_filter=category_filter
        )
        
        # Sanitize input
        try:
            question = self._sanitize_question(question)
            logger.debug("question_sanitized", sanitized_question=question)
        except ValueError as e:
            logger.warning("invalid_question", error=str(e), original_question=question)
            raise
        
        # Create request object
        request = QueryRequest(
            question=question,
            top_k=top_k or self.config.query_top_k,
            category_filter=category_filter,
        )
        
        # Validate request
        try:
            request.validate()
        except ValueError as e:
            logger.error("request_validation_failed", error=str(e), request=request)
            raise
        
        # Transform question using conversation history (if available)
        original_question = question  # Keep original for display
        search_question = self._transform_question_with_history(question, user_id)
        
        if search_question != original_question:
            logger.info(
                "question_transformed",
                original=original_question,
                transformed=search_question,
                user_id=user_id
            )
        
        # Update request with transformed question for retrieval
        request.question = search_question
        
        # Step 1: Retrieve relevant chunks
        logger.info(
            "retrieval_started",
            stage="1/2",
            query=search_question,
            top_k=request.top_k,
            category_filter=category_filter
        )
        
        try:
            chunks = self.retriever.retrieve(request)
            logger.info(
                "retrieval_completed",
                chunks_retrieved=len(chunks) if chunks else 0,
                query=search_question
            )
        except Exception as e:
            logger.error(
                "retrieval_failed",
                error=str(e),
                error_type=type(e).__name__,
                query=search_question
            )
            # Return error response instead of crashing
            return self._create_error_response(
                question=question,
                error_message="Failed to retrieve relevant information. Please try again.",
                query_start=query_start
            )
        
        # Handle no results
        if not chunks:
            logger.warning(
                "no_chunks_found",
                question=search_question,
                top_k=request.top_k,
                category_filter=category_filter
            )
            return self._create_no_results_response(question, query_start)
        
        # Step 2: Generate answer using LLM
        logger.info(
            "answer_generation_started",
            stage="2/2",
            chunks_available=len(chunks),
            has_conversation_history=bool(self.memory.get_conversation(user_id))
        )
        
        try:
            response = self.responder.generate_answer(
                question=original_question,  # Use original question for user-facing answer
                chunks=chunks,
                conversation_history=self.memory.get_context_string(user_id),
            )
            logger.info(
                "answer_generated",
                has_answer=response.has_answer,
                sources_count=len(response.sources)
            )
        except Exception as e:
            logger.error(
                "answer_generation_failed",
                error=str(e),
                error_type=type(e).__name__,
                question=original_question
            )
            return self._create_error_response(
                question=original_question,
                error_message="Failed to generate answer. Please try again.",
                query_start=query_start
            )
        
        # Save conversation turn to memory
        if self.memory and response.has_answer:
            try:
                self.memory.add_turn(user_id, original_question, response.answer)
                logger.debug(
                    "conversation_saved",
                    user_id=user_id,
                    turn_saved=True
                )
            except Exception as e:
                logger.warning(
                    "conversation_save_failed",
                    error=str(e),
                    user_id=user_id
                )
        
        # Calculate total query time
        total_time = (datetime.utcnow() - query_start).total_seconds()
        
        logger.info(
            "query_completed",
            user_id=user_id,
            question=original_question,
            response_time_seconds=total_time,
            has_answer=response.has_answer,
            chunks_retrieved=len(chunks),
            sources_count=len(response.sources)
        )
        
        return response
    
    def _transform_question_with_history(self, question: str, user_id: str) -> str:
        """
        Transform vague questions into standalone questions using conversation history.
        
        This solves the "pronoun problem" where users say things like:
        - "What about vacation days?" (after asking about sick days)
        - "How much is it?" (after asking about a specific item)
        - "Tell me more about that" (referring to previous topic)
        
        Args:
            question: The user's current question
            user_id: User identifier to retrieve conversation history
            
        Returns:
            Transformed standalone question that can be searched independently
        """
        # Check if memory is available
        if not self.memory or not self.memory.health_check():
            logger.debug(
                "question_transformation_skipped",
                reason="memory_unavailable",
                user_id=user_id
            )
            return question
        
        # Get conversation history
        conversation = self.memory.get_conversation(user_id)
        
        # If no history, return question as-is
        if not conversation:
            logger.debug(
                "question_transformation_skipped",
                reason="no_history",
                user_id=user_id
            )
            return question
        
        # Build history context (last 5 turns max for efficiency)
        recent_history = conversation[-5:] if len(conversation) > 5 else conversation
        history_text = "\n".join([
            f"User ASKED: {turn['question']}\nAssistant ANSWERED: {turn['answer']}"
            for turn in recent_history
        ])
        
        # Create transformation prompt
        prompt = f"""Given this recent conversation (HISTORY):

{history_text}

The user now asks: "{question}"

If this question refers to something from the conversation history 
(EITHER TO ONE OF THE USER'S PREVIOUS QUESTIONS OR TO A PART OF THE ASSISTANT'S ANSWERS [eg. its last one]), 
rewrite it as a standalone question that can be understood without the history.

If the question is already standalone and clear, return it exactly as-is.

Standalone question:"""
        
        try:
            # Use GPT-4o-mini for fast, cheap transformation
            logger.debug(
                "question_transformation_started",
                user_id=user_id,
                history_turns=len(recent_history)
            )
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            
            transformed_question = response.choices[0].message.content.strip()
            
            # Remove quotes if the model added them
            if transformed_question.startswith('"') and transformed_question.endswith('"'):
                transformed_question = transformed_question[1:-1]
            if transformed_question.startswith("'") and transformed_question.endswith("'"):
                transformed_question = transformed_question[1:-1]
            
            logger.debug(
                "question_transformation_completed",
                original=question,
                transformed=transformed_question,
                user_id=user_id
            )
            return transformed_question
            
        except Exception as e:
            logger.warning(
                "question_transformation_failed",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id,
                fallback="using_original_question"
            )
            return question
    
    def _sanitize_question(self, question: str) -> str:
        """
        Sanitize and validate the input question.
        
        Ensures:
        - Question is not empty
        - Question is not too long (prevents abuse)
        - Whitespace is normalized
        
        Args:
            question: Raw user input
            
        Returns:
            Sanitized question string
            
        Raises:
            ValueError: If question is invalid
        """
        if not question:
            raise ValueError("Question cannot be empty")
        
        # Strip whitespace
        question = question.strip()
        
        if not question:
            raise ValueError("Question cannot be empty after stripping whitespace")
        
        # Length validation (prevent abuse)
        if len(question) > 500:
            logger.warning(
                "question_length_warning",
                length=len(question),
                max_length=500,
                truncated=False
            )
        
        # Normalize whitespace (remove multiple spaces)
        question = ' '.join(question.split())
        
        logger.debug("question_sanitized", length=len(question))
        
        return question
    
    def _create_no_results_response(self, question: str, query_start: datetime) -> QueryResponse:
        """
        Create a response when no relevant chunks are found.
        
        Args:
            question: Original question
            query_start: Query start time
            
        Returns:
            QueryResponse indicating no information available
        """
        response_time = (datetime.utcnow() - query_start).total_seconds()
        
        logger.info(
            "no_results_response_created",
            question=question,
            response_time_seconds=response_time
        )
        
        return QueryResponse(
            question=question,
            answer="Ik heb die informatie niet in de bedrijfsdocumenten. (I don't have that information in the company documents.)",
            sources=[],
            has_answer=False,
            response_time_seconds=response_time,
        )
    
    def _create_error_response(
        self, 
        question: str, 
        error_message: str, 
        query_start: datetime
    ) -> QueryResponse:
        """
        Create an error response when something goes wrong.
        
        Args:
            question: Original question
            error_message: User-friendly error message
            query_start: Query start time
            
        Returns:
            QueryResponse with error message
        """
        response_time = (datetime.utcnow() - query_start).total_seconds()
        
        logger.error(
            "error_response_created",
            question=question,
            error_message=error_message,
            response_time_seconds=response_time
        )
        
        return QueryResponse(
            question=question,
            answer=f"Sorry, er is een fout opgetreden. (Sorry, an error occurred.) {error_message}",
            sources=[],
            has_answer=False,
            response_time_seconds=response_time,
        )
    
    def get_stats(self) -> dict:
        """
        Get statistics about the query engine and its components.
        
        Useful for monitoring system health and performance.
        
        Returns:
            Dictionary with comprehensive system statistics:
            - retriever: Vector store stats (total vectors, namespace, etc.)
            - config: Current configuration settings
        """
        logger.debug("fetching_engine_stats")
        
        try:
            retriever_stats = self.retriever.get_stats()
            logger.debug("retriever_stats_fetched", stats=retriever_stats)
        except Exception as e:
            logger.error(
                "retriever_stats_fetch_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            retriever_stats = {}
        
        stats = {
            "retriever": retriever_stats,
            "config": {
                "top_k": self.config.query_top_k,
                "similarity_threshold": self.config.query_similarity_threshold,
                "llm_model": self.config.llm_model,
                "temperature": self.config.llm_temperature,
                "max_tokens": self.config.llm_max_tokens,
                "embedding_model": self.config.embedding_model,
                "chunk_size": self.config.chunk_size,
            }
        }
        
        logger.debug("engine_stats_compiled", stats_keys=list(stats.keys()))
        return stats