"""
Authentication Routes - Login/Logout for admin dashboard
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
import structlog

from admin_dashboard.backend.config import get_admin_config
from admin_dashboard.backend.auth.jwt_handler import (
    create_access_token, 
    get_current_user_simple,
    verify_password
)
from src.database.supabase_client import get_supabase_client

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
    email: str | None = None
    role: str
    message: str


class UserInfo(BaseModel):
    """Current user information."""
    username: str
    email: str | None = None
    role: str
    authenticated: bool = True


# ========== ROUTES ==========

@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Login endpoint - validates credentials against Supabase database.
    
    Checks admin_users table for username and verifies bcrypt password hash.
    """
    logger.info("login_attempt", username=credentials.username)
    
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query admin_users table for this username
        response = supabase.table("admin_users").select("*").eq("username", credentials.username).execute()
        
        # Check if user exists
        if not response.data or len(response.data) == 0:
            logger.warning("login_failed", username=credentials.username, reason="user_not_found")
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )
        
        user = response.data[0]
        
        # Check if user is active
        if not user.get("is_active", True):
            logger.warning("login_failed", username=credentials.username, reason="user_inactive")
            raise HTTPException(
                status_code=401,
                detail="User account is disabled"
            )
        
        # Verify password using bcrypt
        password_hash = user.get("password_hash", "")
        if not verify_password(credentials.password, password_hash):
            logger.warning("login_failed", username=credentials.username, reason="invalid_password")
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )
        
        # Password is correct! Create JWT token
        token = create_access_token(
            username=credentials.username,
            secret_key=config.jwt_secret_key,
            algorithm=config.jwt_algorithm,
            expiration_minutes=config.jwt_expiration_minutes,
        )
        
        # Update last_login timestamp
        try:
            supabase.table("admin_users").update({
                "last_login": datetime.utcnow().isoformat()
            }).eq("username", credentials.username).execute()
        except Exception as e:
            logger.warning("last_login_update_failed", username=credentials.username, error=str(e))
        
        logger.info("login_success", username=credentials.username, role=user.get("role"))
        
        return LoginResponse(
            access_token=token,
            username=credentials.username,
            email=user.get("email"),
            role=user.get("role", "admin"),
            message="Login successful"
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (like 401)
        raise
    except Exception as e:
        logger.error("login_error", username=credentials.username, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error during login"
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(username: str = Depends(get_current_user_simple)):
    """
    Get current authenticated user information from database.
    
    This endpoint requires a valid JWT token in the Authorization header.
    """
    logger.debug("user_info_requested", username=username)
    
    try:
        # Get user info from database
        supabase = get_supabase_client()
        response = supabase.table("admin_users").select("username, email, role, is_active").eq("username", username).execute()
        
        if not response.data or len(response.data) == 0:
            logger.warning("user_info_failed", username=username, reason="user_not_found")
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        user = response.data[0]
        
        return UserInfo(
            username=user.get("username"),
            email=user.get("email"),
            role=user.get("role", "admin"),
            authenticated=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("user_info_error", username=username, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch user information"
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