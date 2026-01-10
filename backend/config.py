"""
Backend Configuration

FastAPI-specific settings that extend the core config.
Imports and reuses src.config.Config for core RAG settings.
"""

import os
from dataclasses import dataclass
from typing import List
from src.config import Config as CoreConfig

@dataclass
class BackendConfig:
    """
    Backend-specific configuration for FastAPI server.
    
    This config handles FastAPI/server settings.
    Core RAG settings come from src.config.Config
    """
    
    # Server settings
    host: str = "0.0.0.0"   # Listen on all network interfaces
    port: int = 8000
    reload: bool = False  # Set True for development
    
    # CORS settings (allow frontend to connect)
    cors_enabled: bool = True
    cors_origins: List[str] = None
    
    # Supabase settings (for query logging)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # Logging
    log_queries: bool = True  # Log all queries to Supabase
    log_errors: bool = True   # Log errors
    
    def __post_init__(self):
        """Set defaults after initialization."""
        if self.cors_origins is None:
            # Allow all origins for development
            # TODO: Restrict in production!
            self.cors_origins = ["*"]
    
    # Core RAG configuration (reuse existing!)
    @property
    def core(self) -> CoreConfig:
        """Get core RAG configuration."""
        return CoreConfig()


def get_backend_config() -> BackendConfig:
    """Get backend configuration instance."""
    return BackendConfig()