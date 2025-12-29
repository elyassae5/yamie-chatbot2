"""
Query engine - main orchestrator for the question-answering system.
Ties together retrieval, prompt building, and answer generation with
comprehensive logging and monitoring.
"""

import logging
from typing import Optional
from datetime import datetime

from src.config import Config, get_config
from src.query.models import QueryRequest, QueryResponse
from src.query.retriever import Retriever
from src.query.responder import Responder

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
            
            logger.info("="*80)
            logger.info("✓ QUERY ENGINE READY")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"Failed to initialize query engine: {e}", exc_info=True)
            raise RuntimeError(f"Query engine initialization failed: {e}")
    
    def query(
        self,
        question: str,
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
                question=question,
                chunks=chunks,
            )
        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            return self._create_error_response(
                question=question,
                error_message="Failed to generate answer. Please try again.",
                query_start=query_start
            )
        
        # Calculate total query time
        total_time = (datetime.utcnow() - query_start).total_seconds()
        
        logger.info("="*80)
        logger.info(f"✓ QUERY COMPLETED in {total_time:.2f}s")
        logger.info(f"Has answer: {response.has_answer}")
        logger.info("="*80)
        
        return response
    
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