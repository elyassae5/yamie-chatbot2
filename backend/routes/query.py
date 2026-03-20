"""
Query Route - Main endpoint for asking questions

POST /api/query
GET /api/stats
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi_limiter.depends import RateLimiter
from datetime import datetime
import structlog

from backend.models import QueryRequest, QueryResponse, ErrorResponse, Source
from backend.engine import engine
from src.config import get_config

logger = structlog.get_logger(__name__)

router = APIRouter()


# ========== API KEY AUTHENTICATION ==========

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Verify the API key from request header.
    
    Every request to /api/query and /api/stats must include:
        X-API-Key: <your-secret-key>
    
    Raises 401 if missing or invalid.
    """
    config = get_config()
    if x_api_key != config.api_secret_key:
        logger.warning("invalid_api_key_attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")


# ========== ROUTES ==========

@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        200: {"description": "Query processed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"description": "Invalid or missing API key"},
        429: {"description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Server error"},
    }
)
async def query(
    request: QueryRequest,
    http_request: Request,
    _: None = Depends(verify_api_key),
    rate_limit_user: None = Depends(RateLimiter(times=20, seconds=60)),
    rate_limit_ip: None = Depends(RateLimiter(times=60, seconds=60))
) -> QueryResponse:
    """
    Process a question and return an answer.

    Requires X-API-Key header.

    Rate limits:
    - Per user: 20 requests per minute
    - Per IP: 60 requests per minute (allows multiple users from same location)
    
    This endpoint:
    1. Validates the API key
    2. Validates the input
    3. Checks conversation memory (Redis)
    4. Searches relevant documents (Pinecone)
    5. Generates answer (OpenAI GPT-4o)
    6. Returns structured response
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
        
        # Build debug info — ALWAYS saved to Supabase for admin debug view.
        # Includes both passed and filtered chunks so admins can see
        # the full retrieval picture for any query.
        retrieval_debug = {
            "threshold": get_config().query_similarity_threshold,
            "chunks_passed": len(response.sources),
            "chunks_filtered": len(response.filtered_chunks),
            "passed": [
                {
                    "source": chunk.source,
                    "namespace": chunk.category,
                    "score": round(chunk.similarity_score, 3),
                    "text": chunk.text,
                    "status": "passed",
                }
                for chunk in response.sources
            ],
            "filtered": [
                {
                    "source": chunk.source,
                    "namespace": chunk.category,
                    "score": round(chunk.similarity_score, 3),
                    "text": chunk.text,
                    "status": "filtered",
                }
                for chunk in response.filtered_chunks
            ],
        }
        
        # For the API response, only include debug_info if explicitly requested
        api_debug_info = retrieval_debug if request.debug else None
        
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
            debug_info=api_debug_info  # Only in API response when debug=true
        )
        
        logger.info(
            "query_processed",
            response_time_seconds=round(response.response_time_seconds, 2),
            has_answer=response.has_answer,
            sources_count=len(response.sources),
            user_id=request.user_id
        )
        
        # Log to Supabase
        try:
            from src.database import get_supabase_logger
            from src.query.system_prompt import ACTIVE_SYSTEM_PROMPT_VERSION
            
            supabase_logger = get_supabase_logger()
            
            config = get_config()
            
            supabase_logger.log_query(
                user_id=request.user_id,
                question=original_question,
                transformed_question=response.question if response.question != original_question else None,
                answer=response.answer,
                has_answer=response.has_answer,
                response_time_seconds=response.response_time_seconds,
                sources=[
                    {
                        "source": chunk.source,
                        "category": chunk.category,
                        "similarity_score": chunk.similarity_score,
                    }
                    for chunk in response.sources
                ],
                chunks_retrieved=len(response.sources),
                client_ip=client_ip,
                model=config.llm_model,
                # Configuration parameters for A/B testing
                config_top_k=request.top_k or config.query_top_k,
                config_chunk_size=config.chunk_size,
                config_chunk_overlap=config.chunk_overlap,
                config_similarity_threshold=config.query_similarity_threshold,
                config_temperature=config.llm_temperature,
                config_max_tokens=config.llm_max_tokens,
                config_embedding_model=config.embedding_model,
                system_prompt_version=ACTIVE_SYSTEM_PROMPT_VERSION,
                debug_info=retrieval_debug,  # Always save for admin debug view
            )
            
            logger.info(
                "query_logged_to_supabase",
                user_id=request.user_id,
                system_prompt_version=ACTIVE_SYSTEM_PROMPT_VERSION
            )
            
        except Exception as e:
            # Log error but don't crash the request
            logger.error(
                "supabase_logging_failed_in_endpoint",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user_id
            )
        
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
            detail="Failed to process query. Please try again later."
        )


@router.get("/stats")
async def get_stats(_: None = Depends(verify_api_key)):
    """
    Get query engine statistics.
    
    Requires X-API-Key header.
    
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
        raise HTTPException(status_code=500, detail="Failed to retrieve system stats.")