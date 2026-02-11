"""
System Status Routes - Check system health and stats
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import structlog

from admin_dashboard.backend.config import get_admin_config
from admin_dashboard.backend.auth.jwt_handler import get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()

# Get config
config = get_admin_config()


# ========== RESPONSE MODELS ==========

class PineconeStats(BaseModel):
    """Pinecone vector database statistics."""
    status: str
    index_name: str
    total_vectors: int
    namespaces: Dict[str, int]  # namespace -> vector count
    dimension: Optional[int] = None


class RedisStats(BaseModel):
    """Redis cache/memory statistics."""
    status: str
    connected: bool
    error: Optional[str] = None


class SystemConfig(BaseModel):
    """Current system configuration."""
    llm_model: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    query_top_k: int
    temperature: float
    max_tokens: int


class SystemStatus(BaseModel):
    """Overall system status."""
    status: str  # "healthy", "degraded", "unhealthy"
    pinecone: PineconeStats
    redis: RedisStats
    config: SystemConfig
    admin_backend_version: str = "1.0.0"


# ========== ROUTES ==========

@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    username: str = Depends(get_current_user_simple)
):
    """
    Get comprehensive system status.
    
    Checks:
    - Pinecone connection and stats
    - Redis connection
    - Current configuration
    
    Requires authentication.
    """
    logger.info("system_status_check", requested_by=username)
    
    # Check Pinecone
    pinecone_stats = await _check_pinecone()
    
    # Check Redis
    redis_stats = await _check_redis()
    
    # Get current config
    from src.config import get_config
    src_config = get_config()
    
    system_config = SystemConfig(
        llm_model=src_config.llm_model,
        embedding_model=src_config.embedding_model,
        chunk_size=src_config.chunk_size,
        chunk_overlap=src_config.chunk_overlap,
        query_top_k=src_config.query_top_k,
        temperature=src_config.llm_temperature,
        max_tokens=src_config.llm_max_tokens,
    )
    
    # Determine overall status
    if pinecone_stats.status == "healthy" and redis_stats.status == "healthy":
        overall_status = "healthy"
    elif pinecone_stats.status == "error" or redis_stats.status == "error":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
    
    logger.info(
        "system_status_checked",
        requested_by=username,
        overall_status=overall_status,
        pinecone_status=pinecone_stats.status,
        redis_status=redis_stats.status
    )
    
    return SystemStatus(
        status=overall_status,
        pinecone=pinecone_stats,
        redis=redis_stats,
        config=system_config
    )


@router.get("/pinecone", response_model=PineconeStats)
async def get_pinecone_stats(
    username: str = Depends(get_current_user_simple)
):
    """
    Get detailed Pinecone statistics.
    
    Requires authentication.
    """
    logger.info("pinecone_stats_requested", requested_by=username)
    
    return await _check_pinecone()


@router.get("/redis", response_model=RedisStats)
async def get_redis_stats(
    username: str = Depends(get_current_user_simple)
):
    """
    Get Redis connection status.
    
    Requires authentication.
    """
    logger.info("redis_stats_requested", requested_by=username)
    
    return await _check_redis()


# ========== HELPER FUNCTIONS ==========

async def _check_pinecone() -> PineconeStats:
    """Check Pinecone connection and get stats."""
    try:
        from pinecone import Pinecone
        from src.config import get_config
        
        src_config = get_config()
        
        pc = Pinecone(api_key=src_config.pinecone_api_key)
        index = pc.Index(src_config.pinecone_index_name)
        
        # Get index stats
        stats = index.describe_index_stats()
        
        # Extract namespace stats
        namespaces = {}
        if hasattr(stats, 'namespaces') and stats.namespaces:
            for ns_name, ns_data in stats.namespaces.items():
                namespaces[ns_name] = ns_data.vector_count if hasattr(ns_data, 'vector_count') else 0
        
        total_vectors = stats.total_vector_count if hasattr(stats, 'total_vector_count') else sum(namespaces.values())
        dimension = stats.dimension if hasattr(stats, 'dimension') else None
        
        logger.info(
            "pinecone_check_success",
            total_vectors=total_vectors,
            namespaces=list(namespaces.keys())
        )
        
        return PineconeStats(
            status="healthy",
            index_name=src_config.pinecone_index_name,
            total_vectors=total_vectors,
            namespaces=namespaces,
            dimension=dimension
        )
        
    except Exception as e:
        logger.error(
            "pinecone_check_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        return PineconeStats(
            status="error",
            index_name="unknown",
            total_vectors=0,
            namespaces={}
        )


async def _check_redis() -> RedisStats:
    """Check Redis connection."""
    try:
        import redis
        from src.config import get_config
        
        src_config = get_config()
        
        # Try to connect to Redis
        r = redis.Redis(
            host=src_config.redis_host,
            port=src_config.redis_port,
            password=src_config.redis_password,
            db=src_config.redis_db,
            socket_connect_timeout=src_config.redis_timeout_seconds,
            socket_timeout=src_config.redis_timeout_seconds,
            decode_responses=True
        )
        
        # Ping to check connection
        r.ping()
        
        logger.info("redis_check_success")
        
        return RedisStats(
            status="healthy",
            connected=True
        )
        
    except Exception as e:
        logger.error(
            "redis_check_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        
        return RedisStats(
            status="error",
            connected=False,
            error=str(e)
        )