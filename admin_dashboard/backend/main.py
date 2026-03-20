"""
Admin Dashboard Backend - Main FastAPI Application
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from admin_dashboard.backend.config import get_admin_config

# Setup structured logging
from src.logging_config import setup_logging

setup_logging(log_level="INFO")
logger = structlog.get_logger(__name__)

# Determine environment — disable docs in production
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("admin_backend_startup", message="🔧 ADMIN DASHBOARD STARTING")
    
    yield
    
    # Shutdown
    logger.info("admin_backend_shutdown", message="👋 ADMIN DASHBOARD SHUTTING DOWN")


# Create FastAPI app — docs disabled in production
app = FastAPI(
    title="YamieBot Admin Dashboard API",
    description="Admin panel for managing YamieBot system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

# Get configuration
config = get_admin_config()

# Setup CORS
if config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("cors_enabled", origins=config.cors_origins)


# Include routers
from admin_dashboard.backend.routes import auth, whitelist, logs, system, sync

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(whitelist.router, prefix="/api/whitelist", tags=["Whitelist Management"])
app.include_router(logs.router, prefix="/api/logs", tags=["Query Logs"])
app.include_router(system.router, prefix="/api/system", tags=["System Status"])
app.include_router(sync.router, prefix="/api/sync", tags=["Content Sync"])

logger.info("routers_registered", routers=["auth", "whitelist", "logs", "system", "sync"])

logger.info(
    "docs_status",
    docs_enabled=not IS_PRODUCTION,
    environment=os.getenv("ENVIRONMENT", "development")
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "YamieBot Admin Dashboard API",
        "version": "1.0.0",
        "status": "running",
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "admin-dashboard",
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        "server_starting",
        host=config.host,
        port=config.port,
    )
    
    uvicorn.run(
        "admin_dashboard.backend.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info"
    )