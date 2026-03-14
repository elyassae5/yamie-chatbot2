"""
Admin Dashboard Backend Configuration
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AdminConfig:
    """Configuration for the admin dashboard backend."""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001  # Different port from main chatbot backend (8000)
    reload: bool = True  # Auto-reload during development
    
    # CORS settings
    cors_enabled: bool = True
    cors_origins: list = None
    
    # JWT Authentication
    jwt_secret_key: str = os.getenv("ADMIN_JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24  # 24 hours
    
    def __post_init__(self):
        if not self.jwt_secret_key:
            raise ValueError(
                "ADMIN_JWT_SECRET environment variable is not set. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
                "https://yamie-chatbot2.vercel.app",
            ]

def get_admin_config() -> AdminConfig:
    """Get admin configuration singleton."""
    return AdminConfig()