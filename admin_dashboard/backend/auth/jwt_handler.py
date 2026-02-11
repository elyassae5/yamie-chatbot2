"""
JWT Token Handler - For admin authentication
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger(__name__)

# Security scheme for FastAPI
security = HTTPBearer()


def create_access_token(username: str, secret_key: str, algorithm: str, expiration_minutes: int) -> str:
    """
    Create a JWT access token.
    
    Args:
        username: Username to encode in token
        secret_key: Secret key for signing
        algorithm: JWT algorithm (e.g., "HS256")
        expiration_minutes: Token expiration time in minutes
        
    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(minutes=expiration_minutes)
    
    payload = {
        "sub": username,  # Subject (username)
        "exp": expire,    # Expiration time
        "iat": datetime.utcnow(),  # Issued at
    }
    
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    
    logger.info(
        "jwt_token_created",
        username=username,
        expires_in_minutes=expiration_minutes
    )
    
    return token


def verify_access_token(
    credentials: HTTPAuthorizationCredentials,
    secret_key: str,
    algorithm: str
) -> str:
    """
    Verify a JWT access token and return the username.
    
    Args:
        credentials: HTTP Authorization credentials from request
        secret_key: Secret key for verification
        algorithm: JWT algorithm
        
    Returns:
        Username from token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username = payload.get("sub")
        
        if username is None:
            logger.warning("jwt_verification_failed", reason="no_username_in_token")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
        
        logger.debug("jwt_verified", username=username)
        return username
        
    except jwt.ExpiredSignatureError:
        logger.warning("jwt_verification_failed", reason="token_expired")
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning("jwt_verification_failed", reason="invalid_token", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )


def create_get_current_user_dependency(secret_key: str, algorithm: str):
    """
    Factory function to create a get_current_user dependency with config injected.
    
    This allows us to pass config values into the dependency function.
    """
    def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
        """
        Dependency to get the current authenticated user.
        
        Use this in route dependencies to protect endpoints.
        """
        return verify_access_token(credentials, secret_key, algorithm)
    
    return get_current_user


# Helper to avoid repeating config imports in routes
def get_current_user_simple(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Simple version that gets config automatically.
    Use this in routes for cleaner code.
    """
    from admin_dashboard.backend.config import get_admin_config
    config = get_admin_config()
    return verify_access_token(credentials, config.jwt_secret_key, config.jwt_algorithm)