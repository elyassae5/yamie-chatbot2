"""
Health Check Route

GET /api/health - Check if the system is healthy
"""

from fastapi import APIRouter
from datetime import datetime
import logging

from backend.models import HealthResponse
from backend import __version__

logger = logging.getLogger(__name__)

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
    
    components = {}
    overall_status = "healthy"
    
    # Check QueryEngine
    try:
        from backend.routes.query import engine
        if engine is not None:
            components["query_engine"] = "healthy"
            
            # Check Redis (via memory)
            if hasattr(engine, 'memory') and engine.memory:
                if engine.memory.health_check():
                    components["redis"] = "healthy"
                else:
                    components["redis"] = "unhealthy"
                    overall_status = "degraded"
            else:
                components["redis"] = "not_configured"
            
            # Check Pinecone (via retriever)
            if hasattr(engine, 'retriever') and engine.retriever:
                try:
                    stats = engine.retriever.get_stats()
                    if stats and stats.get('total_vectors', 0) > 0:
                        components["pinecone"] = "healthy"
                    else:
                        components["pinecone"] = "no_data"
                        overall_status = "degraded"
                except Exception as e:
                    logger.warning(f"Pinecone health check failed: {e}")
                    components["pinecone"] = "unhealthy"
                    overall_status = "degraded"
            else:
                components["pinecone"] = "not_configured"
                overall_status = "unhealthy"
        else:
            components["query_engine"] = "unhealthy"
            overall_status = "unhealthy"
            
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        components["query_engine"] = "error"
        overall_status = "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=__version__,
        components=components
    )