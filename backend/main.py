"""
YamieBot Backend - Main FastAPI Application

Production-ready REST API that wraps the QueryEngine.
Supports multiple frontends (Gradio, WhatsApp, React, etc.)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from backend.config import get_backend_config
from backend.routes import query, health
from backend import __version__

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info("="*80)
    logger.info("🚀 YAMIEBOT BACKEND STARTING")
    logger.info("="*80)
    logger.info(f"Version: {__version__}")
    
    # Initialize QueryEngine (happens in routes, but we log here)
    logger.info("Initializing components...")
    
    yield
    
    # Shutdown
    logger.info("="*80)
    logger.info("👋 YAMIEBOT BACKEND SHUTTING DOWN")
    logger.info("="*80)


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
    logger.info(f"✓ CORS enabled for origins: {config.cors_origins}")

# Include routers
app.include_router(query.router, prefix="/api", tags=["Query"])
app.include_router(health.router, prefix="/api", tags=["Health"])

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information."""
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
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {config.host}:{config.port}")
    
    uvicorn.run(
        "backend.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info"
    )