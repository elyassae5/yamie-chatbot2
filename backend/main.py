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

from backend.config import get_backend_config
from backend.routes import query, health
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
    
    yield
    
    # Shutdown
    logger.info("backend_shutdown_started")
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