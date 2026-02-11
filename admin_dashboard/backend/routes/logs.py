"""
Query Logs Routes - View chatbot query history from Supabase
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
import structlog

from admin_dashboard.backend.config import get_admin_config
from admin_dashboard.backend.auth.jwt_handler import get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()

# Get config
config = get_admin_config()


# ========== REQUEST/RESPONSE MODELS ==========

class QueryLogEntry(BaseModel):
    """A single query log entry."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    question: Optional[str] = None
    transformed_question: Optional[str] = None
    answer: Optional[str] = None
    has_answer: Optional[bool] = None
    sources: Optional[Any] = None  # jsonb
    chunks_retrieved: Optional[int] = None
    response_time_seconds: Optional[float] = None
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    debug_info: Optional[Any] = None  # jsonb
    config_top_k: Optional[int] = None
    config_chunk_size: Optional[int] = None
    config_chunk_overlap: Optional[int] = None
    config_similarity_threshold: Optional[float] = None
    config_temperature: Optional[float] = None
    config_max_tokens: Optional[int] = None
    config_embedding_model: Optional[str] = None
    system_prompt_version: Optional[str] = None


class QueryLogsResponse(BaseModel):
    """Response containing query logs and metadata."""
    logs: List[QueryLogEntry]
    total_count: int
    page: int
    page_size: int


# ========== ROUTES ==========

@router.get("/", response_model=QueryLogsResponse)
async def get_query_logs(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(50, ge=1, le=500, description="Number of logs per page"),
    user_id: Optional[str] = Query(None, description="Filter by user ID (phone number)"),
    search: Optional[str] = Query(None, description="Search in questions and answers"),
    username: str = Depends(get_current_user_simple)
):
    """
    Get query logs from Supabase with pagination and optional filtering.
    
    Requires authentication.
    """
    logger.info(
        "query_logs_fetch",
        requested_by=username,
        page=page,
        page_size=page_size,
        user_id=user_id,
        search=search
    )
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Build query
        query = supabase_logger.client.table("query_logs").select("*")
        
        # Apply filters
        if user_id:
            query = query.eq("user_id", user_id)
        
        if search:
            # Search in question OR answer
            query = query.or_(f"question.ilike.%{search}%,answer.ilike.%{search}%")
        
        # Order by most recent first
        query = query.order("created_at", desc=True)
        
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Apply pagination
        query = query.range(offset, offset + page_size - 1)
        
        # Execute query
        response = query.execute()
        
        # Get total count (for pagination metadata)
        count_query = supabase_logger.client.table("query_logs").select("*", count="exact")
        if user_id:
            count_query = count_query.eq("user_id", user_id)
        if search:
            count_query = count_query.or_(f"question.ilike.%{search}%,answer.ilike.%{search}%")
        
        count_response = count_query.execute()
        total_count = count_response.count if hasattr(count_response, 'count') else len(response.data)
        
        logger.info(
            "query_logs_fetched",
            requested_by=username,
            logs_returned=len(response.data),
            total_count=total_count,
            page=page
        )
        
        return QueryLogsResponse(
            logs=response.data,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(
            "query_logs_fetch_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch query logs: {str(e)}"
        )


@router.get("/{log_id}", response_model=QueryLogEntry)
async def get_single_log(
    log_id: int,
    username: str = Depends(get_current_user_simple)
):
    """
    Get a single query log entry by ID.
    
    Useful for viewing full details including all sources/chunks.
    Requires authentication.
    """
    logger.info("single_log_fetch", log_id=log_id, requested_by=username)
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Fetch single log
        response = supabase_logger.client.table("query_logs").select("*").eq("id", log_id).execute()
        
        if not response.data or len(response.data) == 0:
            logger.warning("log_not_found", log_id=log_id)
            raise HTTPException(
                status_code=404,
                detail=f"Query log with ID {log_id} not found"
            )
        
        logger.info("single_log_fetched", log_id=log_id, requested_by=username)
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "single_log_fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
            log_id=log_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch query log: {str(e)}"
        )


@router.get("/stats/summary")
async def get_logs_summary(
    username: str = Depends(get_current_user_simple)
):
    """
    Get summary statistics about query logs.
    
    Returns:
    - Total queries
    - Average response time
    - Success rate
    - Most common questions
    
    Requires authentication.
    """
    logger.info("logs_summary_requested", requested_by=username)
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Get all logs (we'll calculate stats in Python)
        # For production, you'd want to do this with SQL aggregations
        response = supabase_logger.client.table("query_logs").select("*").execute()
        
        logs = response.data
        total_queries = len(logs)
        
        if total_queries == 0:
            return {
                "total_queries": 0,
                "average_response_time": 0,
                "success_rate": 0,
                "total_users": 0
            }
        
        # Calculate stats
        total_response_time = sum(log.get("response_time_seconds", 0) for log in logs)
        avg_response_time = total_response_time / total_queries
        
        successful_queries = sum(1 for log in logs if log.get("has_answer", False))
        success_rate = (successful_queries / total_queries) * 100
        
        unique_users = len(set(log.get("user_id") for log in logs if log.get("user_id")))
        
        logger.info("logs_summary_generated", requested_by=username, total_queries=total_queries)
        
        return {
            "total_queries": total_queries,
            "average_response_time": round(avg_response_time, 2),
            "success_rate": round(success_rate, 2),
            "total_users": unique_users,
            "successful_queries": successful_queries,
            "failed_queries": total_queries - successful_queries
        }
        
    except Exception as e:
        logger.error(
            "logs_summary_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )