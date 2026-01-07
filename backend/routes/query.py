"""
Query Route - Main endpoint for asking questions

POST /api/query
GET /api/stats
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi_limiter.depends import RateLimiter
from datetime import datetime
import structlog

from backend.models import QueryRequest, QueryResponse, ErrorResponse, Source
from src.query import QueryEngine
from src.config import get_config

logger = structlog.get_logger(__name__)

router = APIRouter()

# Initialize QueryEngine (singleton - reused across requests)
logger.info("query_engine_initialization_started")
try:
    engine = QueryEngine(config=get_config())
    logger.info("query_engine_initialized", status="success")
except Exception as e:
    logger.error(
        "query_engine_initialization_failed",
        error=str(e),
        error_type=type(e).__name__
    )
    engine = None


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        200: {"description": "Query processed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        429: {"description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Server error"},
    }
)
async def query(
    request: QueryRequest,
    http_request: Request,
    rate_limit_user: None = Depends(RateLimiter(times=20, seconds=60)),
    rate_limit_ip: None = Depends(RateLimiter(times=60, seconds=60))
) -> QueryResponse:
    """
    Process a question and return an answer.

    Rate limits:
    - Per user: 20 requests per minute
    - Per IP: 60 requests per minute (allows multiple users from same location)
    
    This endpoint:
    1. Validates the input
    2. Checks conversation memory (Redis)
    3. Searches relevant documents (Pinecone)
    4. Generates answer (OpenAI GPT-4o-mini)
    5. Returns structured response
    
    **Example Request:**
```json
    {
        "question": "Wie is Daoud?",
        "user_id": "gradio_user",
        "debug": true
    }
```
    
    **Example Response:**
```json
    {
        "question": "Wie is Daoud?",
        "answer": "Daoud is verantwoordelijk voor...",
        "sources": [...],
        "has_answer": true,
        "response_time_seconds": 1.23,
        "debug_info": {
            "transformed_question": "Wie is Daoud en wat zijn zijn taken?",
            "chunks_retrieved": 7,
            "top_chunks": [...]
        }
    }
```
    """
    
    # Check if engine is initialized
    if engine is None:
        logger.error("query_rejected", reason="engine_not_initialized")
        raise HTTPException(
            status_code=500,
            detail="Query engine not initialized. Check server logs."
        )
    
    # Log incoming request with IP address
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    logger.info(
        "query_received",
        user_id=request.user_id,
        client_ip=client_ip,
        debug_mode=request.debug,
        top_k=request.top_k
    )
    logger.debug("query_question", question=request.question)
    
    start_time = datetime.utcnow()
    
    try:
        # Store original question for debug info
        original_question = request.question
        
        # Process query using QueryEngine
        response = engine.query(
            question=request.question,
            user_id=request.user_id,
            top_k=request.top_k,
        )
        
        # Build debug info if requested
        debug_info = None
        if request.debug:
            debug_info = {
                "original_question": original_question,
                "transformed_question": response.question if response.question != original_question else None,
                "chunks_retrieved": len(response.sources),
                "top_chunks": [
                    {
                        "source": chunk.source,
                        "category": chunk.category,
                        "score": round(chunk.similarity_score, 3),
                        "text_preview": chunk.text[:300] + "..." if len(chunk.text) > 300 else chunk.text
                    }
                    for chunk in response.sources[:3]  # Top 3 chunks
                ],
                "all_sources": [
                    {
                        "source": chunk.source,
                        "score": round(chunk.similarity_score, 3)
                    }
                    for chunk in response.sources
                ]
            }
            logger.debug(
                "debug_info_generated",
                chunks_retrieved=len(response.sources),
                top_chunks_count=min(3, len(response.sources))
            )
        
        # Convert to API response model
        api_response = QueryResponse(
            question=response.question,
            answer=response.answer,
            sources=[
                Source(
                    source=chunk.source,
                    category=chunk.category,
                    similarity_score=chunk.similarity_score,
                    text=chunk.text if hasattr(chunk, 'text') else None
                )
                for chunk in response.sources
            ],
            has_answer=response.has_answer,
            response_time_seconds=response.response_time_seconds,
            user_id=request.user_id,
            timestamp=datetime.utcnow(),
            debug_info=debug_info  # ← Include debug info!
        )
        
        logger.info(
            "query_processed",
            response_time_seconds=round(response.response_time_seconds, 2),
            has_answer=response.has_answer,
            sources_count=len(response.sources),
            user_id=request.user_id
        )
        
        # TODO: Log to Supabase here (Phase 3)
        
        return api_response
        
    except ValueError as e:
        # Invalid input (e.g., empty question)
        logger.warning(
            "invalid_query",
            error=str(e),
            user_id=request.user_id
        )
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # Unexpected error
        logger.error(
            "query_processing_failed",
            error=str(e),
            error_type=type(e).__name__,
            user_id=request.user_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    Get query engine statistics.
    
    Returns information about the system:
    - Vector store stats (total documents, namespace, etc.)
    - Configuration settings
    - Memory stats
    """
    
    if engine is None:
        logger.error("stats_rejected", reason="engine_not_initialized")
        raise HTTPException(status_code=500, detail="Query engine not initialized")
    
    try:
        logger.debug("stats_request_received")
        stats = engine.get_stats()
        logger.info("stats_retrieved", stats_available=True)
        return {
            "status": "ok",
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(
            "stats_retrieval_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(status_code=500, detail=str(e))