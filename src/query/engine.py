"""
Query engine - main orchestrator for the question-answering system.
Ties together retrieval, prompt building, and answer generation with
comprehensive logging and monitoring.
"""

import logging
from typing import Optional
from datetime import datetime
import openai

from src.config import Config, get_config
from src.query.models import QueryRequest, QueryResponse
from src.query.retriever import Retriever
from src.query.responder import Responder
from src.memory.conversation_memory import ConversationMemory

logger = logging.getLogger(__name__)


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
        
        logger.info("="*80)
        logger.info("INITIALIZING YAMIEBOT QUERY ENGINE")
        logger.info("="*80)
        
        try:
            # Initialize components
            logger.info("Initializing retriever...")
            self.retriever = Retriever(config=self.config)
            
            logger.info("Initializing responder...")
            self.responder = Responder(config=self.config)
            
            logger.info("Initializing conversation memory...")
            self.memory = ConversationMemory(config=self.config)
            
            logger.info("="*80)
            logger.info("✓ QUERY ENGINE READY")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"Failed to initialize query engine: {e}", exc_info=True)
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
            question: User's question (in Dutch or English)
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
        
        logger.info("="*80)
        logger.info("NEW QUERY")
        logger.info("="*80)
        logger.debug(f"Question: '{question}'")
        
        # Sanitize input
        try:
            question = self._sanitize_question(question)
        except ValueError as e:
            logger.warning(f"Invalid question: {e}")
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
            logger.error(f"Request validation failed: {e}")
            raise
        
        logger.info(f"Top-k: {request.top_k}")
        if category_filter:
            logger.info(f"Category filter: {category_filter}")
        
        # Transform question using conversation history (if available)
        original_question = question  # Keep original for display
        search_question = self._transform_question_with_history(question, user_id)
        
        if search_question != original_question:
            logger.info(f"Question transformed for search: '{search_question}'")
        
        # Update request with transformed question for retrieval
        request.question = search_question
        
        # Step 1: Retrieve relevant chunks
        logger.info("\n--- STAGE 1/2: RETRIEVAL ---")
        
        try:
            chunks = self.retriever.retrieve(request)
        except Exception as e:
            logger.error(f"Retrieval failed: {e}", exc_info=True)
            # Return error response instead of crashing
            return self._create_error_response(
                question=question,
                error_message="Failed to retrieve relevant information. Please try again.",
                query_start=query_start
            )
        
        # Handle no results
        if not chunks:
            logger.warning("No relevant chunks found")
            return self._create_no_results_response(question, query_start)
        
        # Step 2: Generate answer using LLM
        logger.info("\n--- STAGE 2/2: ANSWER GENERATION ---")
        
        try:
            response = self.responder.generate_answer(
                question=original_question,  # Use original question for user-facing answer
                chunks=chunks,
                conversation_history=self.memory.get_context_string(user_id),
            )
        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            return self._create_error_response(
                question=original_question,
                error_message="Failed to generate answer. Please try again.",
                query_start=query_start
            )
        
        # Save conversation turn to memory
        if self.memory and response.has_answer:
            try:
                self.memory.add_turn(user_id, original_question, response.answer)
                logger.debug(f"Saved conversation turn to memory for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to save to memory: {e}")
        
        # Calculate total query time
        total_time = (datetime.utcnow() - query_start).total_seconds()
        
        logger.info("="*80)
        logger.info(f"✓ QUERY COMPLETED in {total_time:.2f}s")
        logger.info(f"Has answer: {response.has_answer}")
        logger.info("="*80)
        
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
            logger.debug("Memory not available, skipping question transformation")
            return question
        
        # Get conversation history
        conversation = self.memory.get_conversation(user_id)
        
        # If no history, return question as-is
        if not conversation:
            logger.debug("No conversation history, using question as-is")
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
(EITHER TO ONE OF THE USER'S PREVIOUS QUESTIONS OR TO A PART OF THE ASSISTANT'S ANSWERS), 
rewrite it as a standalone question that can be understood without the history.

If the question is already standalone and clear, return it exactly as-is.

Standalone question:"""
        
        try:
            # Use GPT-4o-mini for fast, cheap transformation
            logger.debug("Transforming question with conversation history...")
            
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
            
            logger.debug(f"Transformed: '{question}' → '{transformed_question}'")
            return transformed_question
            
        except Exception as e:
            logger.warning(f"Question transformation failed: {e}. Using original question.")
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
            logger.warning(f"Question too long ({len(question)} chars) but not a big problem!")
        
        # Normalize whitespace (remove multiple spaces)
        question = ' '.join(question.split())
        
        logger.debug(f"Sanitized question: '{question}' ({len(question)} chars)")
        
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
        
        logger.info(f"Creating 'no results' response (took {response_time:.2f}s)")
        
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
        
        logger.error(f"Creating error response: {error_message}")
        
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
        logger.debug("Fetching query engine statistics")
        
        try:
            retriever_stats = self.retriever.get_stats()
        except Exception as e:
            logger.error(f"Failed to get retriever stats: {e}")
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
        
        logger.debug(f"Engine stats: {stats}")
        return stats