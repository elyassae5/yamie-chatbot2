"""
Supabase client for query logging.
Handles connection and logging of all queries to the database.
"""

import os
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client, Client

logger = structlog.get_logger(__name__)


class SupabaseLogger:
    """
    Handles logging of queries to Supabase database.
    
    This class provides a clean interface for logging all query data
    including questions, answers, performance metrics, and errors.
    """
    
    def __init__(self):
        """Initialize Supabase client with credentials from environment."""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logger.error(
                "supabase_credentials_missing",
                has_url=bool(self.supabase_url),
                has_key=bool(self.supabase_key)
            )
            raise ValueError(
                "Missing Supabase credentials. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env"
            )
        
        try:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info(
                "supabase_client_initialized",
                url=self.supabase_url[:20] + "..."  # Log partial URL for security
            )
        except Exception as e:
            logger.error(
                "supabase_client_initialization_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    
    def log_query(
        self,
        user_id: str,
        question: str,
        answer: str,
        has_answer: bool,
        response_time_seconds: float,
        sources: Optional[List[Dict[str, Any]]] = None,
        transformed_question: Optional[str] = None,
        chunks_retrieved: Optional[int] = None,
        client_ip: Optional[str] = None,
        model: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
        # NEW: Configuration parameters
        config_top_k: Optional[int] = None,
        config_chunk_size: Optional[int] = None,
        config_chunk_overlap: Optional[int] = None,
        config_similarity_threshold: Optional[float] = None,
        config_temperature: Optional[float] = None,
        config_max_tokens: Optional[int] = None,
        config_embedding_model: Optional[str] = None,
        system_prompt_version: Optional[str] = None,
    ) -> bool:
        """
        Log a query to Supabase.
        
        Args:
            user_id: User identifier
            question: Original question asked
            answer: Generated answer
            has_answer: Whether a valid answer was generated
            response_time_seconds: Time taken to respond
            sources: List of source chunks used (optional)
            transformed_question: Question after conversation context (optional)
            chunks_retrieved: Number of chunks retrieved (optional)
            client_ip: Client IP address (optional)
            model: LLM model used (optional)
            prompt_tokens: Tokens in prompt (optional)
            completion_tokens: Tokens in completion (optional)
            total_tokens: Total tokens used (optional)
            error: Error message if any (optional)
            error_type: Type of error (optional)
            debug_info: Additional debug information (optional)
            
            # Configuration parameters (for A/B testing and optimization)
            config_top_k: Number of chunks retrieved (top-k parameter)
            config_chunk_size: Size of document chunks
            config_chunk_overlap: Overlap between chunks
            config_similarity_threshold: Minimum similarity score
            config_temperature: LLM temperature setting
            config_max_tokens: Maximum tokens in response
            config_embedding_model: Embedding model used
            system_prompt_version: Version of system prompt used
            
        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            # Prepare data for insertion
            log_data = {
                "user_id": user_id,
                "question": question,
                "answer": answer,
                "has_answer": has_answer,
                "response_time_ms": int(response_time_seconds * 1000),
                "created_at": datetime.utcnow().isoformat(),
            }
            
            # Add optional fields if provided
            if transformed_question:
                log_data["transformed_question"] = transformed_question
            
            if chunks_retrieved is not None:
                log_data["chunks_retrieved"] = chunks_retrieved
            
            if client_ip:
                log_data["client_ip"] = client_ip
            
            if model:
                log_data["model"] = model
            
            if prompt_tokens is not None:
                log_data["prompt_tokens"] = prompt_tokens
            
            if completion_tokens is not None:
                log_data["completion_tokens"] = completion_tokens
            
            if total_tokens is not None:
                log_data["total_tokens"] = total_tokens
            
            if error:
                log_data["error"] = error
                log_data["error_type"] = error_type
            
            if config_top_k is not None:
                log_data["config_top_k"] = config_top_k
            
            if config_chunk_size is not None:
                log_data["config_chunk_size"] = config_chunk_size
            
            if config_chunk_overlap is not None:
                log_data["config_chunk_overlap"] = config_chunk_overlap
            
            if config_similarity_threshold is not None:
                log_data["config_similarity_threshold"] = config_similarity_threshold
            
            if config_temperature is not None:
                log_data["config_temperature"] = config_temperature
            
            if config_max_tokens is not None:
                log_data["config_max_tokens"] = config_max_tokens
            
            if config_embedding_model:
                log_data["config_embedding_model"] = config_embedding_model
            
            if system_prompt_version:
                log_data["system_prompt_version"] = system_prompt_version
            
            # Convert sources to JSONB format
            if sources:
                log_data["sources"] = [
                    {
                        "source": s.get("source", "unknown"),
                        "category": s.get("category", "general"),
                        "similarity_score": s.get("similarity_score", 0.0),
                    }
                    for s in sources
                ]
            
            # Add debug info if provided
            if debug_info:
                log_data["debug_info"] = debug_info
            
            # Insert into Supabase
            response = self.client.table("query_logs").insert(log_data).execute()
            
            logger.info(
                "query_logged_to_supabase",
                user_id=user_id,
                has_answer=has_answer,
                response_time_ms=log_data["response_time_ms"],
                config_top_k=config_top_k,
                record_id=response.data[0]["id"] if response.data else None
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "supabase_logging_failed",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id,
                question=question[:50] + "..."
            )
            return False

    def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent query logs (for debugging/monitoring).
        
        Args:
            limit: Number of logs to retrieve
            
        Returns:
            List of log entries
        """
        try:
            response = (
                self.client.table("query_logs")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            logger.debug(
                "recent_logs_fetched",
                count=len(response.data) if response.data else 0
            )
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(
                "fetch_recent_logs_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            return []
    
    def get_user_query_count(self, user_id: str, hours: int = 24) -> int:
        """
        Get number of queries from a user in the last N hours.
        Useful for rate limiting or analytics.
        
        Args:
            user_id: User identifier
            hours: Time window in hours
            
        Returns:
            Number of queries
        """
        try:
            from datetime import timedelta
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            response = (
                self.client.table("query_logs")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .gte("created_at", cutoff_time)
                .execute()
            )
            
            count = response.count if response.count else 0
            
            logger.debug(
                "user_query_count_fetched",
                user_id=user_id,
                count=count,
                hours=hours
            )
            
            return count
            
        except Exception as e:
            logger.error(
                "user_query_count_failed",
                error=str(e),
                error_type=type(e).__name__,
                user_id=user_id
            )
            return 0


# Singleton instance (initialized once)
_supabase_logger: Optional[SupabaseLogger] = None


def get_supabase_logger() -> SupabaseLogger:
    """
    Get the singleton Supabase logger instance.
    
    Returns:
        SupabaseLogger instance
    """
    global _supabase_logger
    
    if _supabase_logger is None:
        _supabase_logger = SupabaseLogger()
    
    return _supabase_logger


def get_supabase_client() -> Client:
    """
    Get the raw Supabase client for direct database access.
    
    Returns:
        Supabase Client instance
    """
    logger_instance = get_supabase_logger()
    return logger_instance.client