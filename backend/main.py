"""
YamieBot Backend - Main FastAPI Application

Production-ready REST API that wraps the QueryEngine.
Supports multiple frontends (Gradio, WhatsApp, React, etc.)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog

from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from backend.config import get_backend_config
from backend.routes import query, health, webhook
from backend import __version__

# Setup structured logging
from src.logging_config import setup_logging

# Initialize structured logging for the backend
setup_logging(log_level="INFO")
logger = structlog.get_logger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info("backend_startup_started", version=__version__)
    logger.info("backend_startup_message", message="🚀 YAMIEBOT BACKEND STARTING")
    logger.info("backend_version", version=__version__)
    logger.info("components_initialization", status="starting")
    
    # Initialize rate limiter with Redis
    try:
        # Import config to get Redis credentials
        from src.config import get_config
        src_config = get_config()
        
        logger.info(
            "rate_limiter_initialization_started",
            redis_host=src_config.redis_host,
            redis_port=src_config.redis_port
        )
        
        # Create async Redis connection
        redis_connection = redis.from_url(
            f"redis://:{src_config.redis_password}@{src_config.redis_host}:{src_config.redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize FastAPILimiter
        await FastAPILimiter.init(redis_connection)
        
        logger.info(
            "rate_limiter_initialized",
            status="success",
            redis_host=src_config.redis_host
        )
        
    except Exception as e:
        logger.error(
            "rate_limiter_initialization_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise RuntimeError(f"Rate limiter initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("backend_shutdown_started")
    
    # Close rate limiter
    try:
        await FastAPILimiter.close()
        logger.info("rate_limiter_closed")
    except Exception as e:
        logger.warning(
            "rate_limiter_close_failed",
            error=str(e)
        )
    
    logger.info("backend_shutdown_message", message="👋 YAMIEBOT BACKEND SHUTTING DOWN")
    logger.info("backend_shutdown_completed")



# Create FastAPI app
app = FastAPI(
    title="YamieBot API",
    description="REST API for YamieBot - AI Assistant for Yamie PastaBar",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI at /docs
    redoc_url="/redoc",  # ReDoc at /redoc
)

# Get configuration
config = get_backend_config()

# Setup CORS (allow frontends to connect)
if config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(
        "cors_enabled",
        origins=config.cors_origins,
        allow_credentials=True
    )

# Include routers
app.include_router(query.router, prefix="/api", tags=["Query"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(webhook.router, prefix="/api", tags=["WhatsApp"])


logger.info(
    "routers_registered",
    routers=["query", "health"],
    prefix="/api"
)

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information."""
    logger.debug("root_endpoint_accessed")
    return {
        "name": "YamieBot API",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "query": "/api/query",
            "health": "/api/health",
            "stats": "/api/stats"
        }
    }

# Rate limit exception handler
@app.exception_handler(HTTPException)
async def rate_limit_handler(request, exc: HTTPException):
    """Handle rate limit exceptions with better messages."""
    
    # Check if it's a rate limit error (429)
    if exc.status_code == 429:
        logger.warning(
            "rate_limit_exceeded",
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
            detail=str(exc.detail)
        )
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "You've made too many requests. Please wait a moment before trying again.",
                "limit": "20 requests per minute",
                "retry_after_seconds": 60,
                "tip": "Normal usage is 2-4 queries per minute. If you're testing, please slow down."
            }
        )
    
    # Not a rate limit error, return as-is
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all uncaught exceptions."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "server_starting",
        host=config.host,
        port=config.port,
        reload=config.reload
    )
    
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info"
    )