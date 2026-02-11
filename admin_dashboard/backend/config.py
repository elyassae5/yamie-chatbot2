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
    jwt_secret_key: str = os.getenv("ADMIN_JWT_SECRET", "your-secret-key-change-this-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24  # 24 hours
    
    # Admin credentials (temporary - will move to database later)
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "changeme123")
    
    def __post_init__(self):
        """Set default CORS origins if not provided."""
        if self.cors_origins is None:
            self.cors_origins = [
                "http://localhost:5173",  # Vite default port
                "http://localhost:3000",  # Alternative React port
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
            ]


def get_admin_config() -> AdminConfig:
    """Get admin configuration singleton."""
    return AdminConfig()