"""
Authentication Routes - Login/Logout for admin dashboard
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog

from admin_dashboard.backend.config import get_admin_config
from admin_dashboard.backend.auth.jwt_handler import create_access_token, get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()

# Get config
config = get_admin_config()


# ========== REQUEST/RESPONSE MODELS ==========

class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    username: str
    message: str


class UserInfo(BaseModel):
    """Current user information."""
    username: str
    authenticated: bool = True


# ========== ROUTES ==========

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Login endpoint - validates credentials and returns JWT token.
    
    For now, uses hardcoded admin credentials from config.
    Later, we'll check against Supabase database.
    """
    logger.info("login_attempt", username=credentials.username)
    
    # Validate credentials (temporary - hardcoded)
    if (
        credentials.username == config.admin_username
        and credentials.password == config.admin_password
    ):
        # Create JWT token
        token = create_access_token(
            username=credentials.username,
            secret_key=config.jwt_secret_key,
            algorithm=config.jwt_algorithm,
            expiration_minutes=config.jwt_expiration_minutes,
        )
        
        logger.info("login_success", username=credentials.username)
        
        return LoginResponse(
            access_token=token,
            username=credentials.username,
            message="Login successful"
        )
    
    # Invalid credentials
    logger.warning("login_failed", username=credentials.username, reason="invalid_credentials")
    raise HTTPException(
        status_code=401,
        detail="Invalid username or password"
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(username: str = Depends(get_current_user_simple)):
    """
    Get current authenticated user information.
    
    This endpoint requires a valid JWT token in the Authorization header.
    """
    logger.debug("user_info_requested", username=username)
    
    return UserInfo(
        username=username,
        authenticated=True
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    
    Since we're using stateless JWT, logout is handled client-side
    by removing the token. This endpoint is here for API completeness.
    """
    logger.info("logout_requested")
    
    return {
        "message": "Logged out successfully. Please remove your token client-side."
    }