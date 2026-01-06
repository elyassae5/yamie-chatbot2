"""
Health Check Route

GET /api/health - Check if the system is healthy
"""

from fastapi import APIRouter
from datetime import datetime
import structlog

from backend.models import HealthResponse
from backend import __version__

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the health status of all system components:
    - FastAPI server (obviously healthy if responding)
    - QueryEngine initialization status
    - Redis connection
    - Pinecone connection
    
    **Response:**
```json
    {
        "status": "healthy",
        "timestamp": "2026-01-02T16:30:00Z",
        "version": "1.0.0",
        "components": {
            "query_engine": "healthy",
            "redis": "healthy",
            "pinecone": "healthy"
        }
    }
```
    """
    
    logger.debug("health_check_started")
    
    components = {}
    overall_status = "healthy"
    
    # Check QueryEngine
    try:
        from backend.routes.query import engine
        if engine is not None:
            components["query_engine"] = "healthy"
            logger.debug("query_engine_health", status="healthy")
            
            # Check Redis (via memory)
            if hasattr(engine, 'memory') and engine.memory:
                if engine.memory.health_check():
                    components["redis"] = "healthy"
                    logger.debug("redis_health", status="healthy")
                else:
                    components["redis"] = "unhealthy"
                    overall_status = "degraded"
                    logger.warning("redis_health", status="unhealthy")
            else:
                components["redis"] = "not_configured"
                logger.debug("redis_health", status="not_configured")
            
            # Check Pinecone (via retriever)
            if hasattr(engine, 'retriever') and engine.retriever:
                try:
                    stats = engine.retriever.get_stats()
                    if stats and stats.get('total_vectors', 0) > 0:
                        components["pinecone"] = "healthy"
                        logger.debug(
                            "pinecone_health",
                            status="healthy",
                            total_vectors=stats.get('total_vectors', 0)
                        )
                    else:
                        components["pinecone"] = "no_data"
                        overall_status = "degraded"
                        logger.warning("pinecone_health", status="no_data")
                except Exception as e:
                    logger.warning(
                        "pinecone_health_check_failed",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    components["pinecone"] = "unhealthy"
                    overall_status = "degraded"
            else:
                components["pinecone"] = "not_configured"
                overall_status = "unhealthy"
                logger.warning("pinecone_health", status="not_configured")
        else:
            components["query_engine"] = "unhealthy"
            overall_status = "unhealthy"
            logger.error("query_engine_health", status="unhealthy")
            
    except Exception as e:
        logger.error(
            "health_check_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        components["query_engine"] = "error"
        overall_status = "unhealthy"
    
    logger.info(
        "health_check_completed",
        overall_status=overall_status,
        components=components
    )
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=__version__,
        components=components
    )