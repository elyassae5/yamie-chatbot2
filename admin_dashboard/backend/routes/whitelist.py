"""
Whitelist Management Routes - CRUD operations for phone number whitelist
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import structlog

from admin_dashboard.backend.config import get_admin_config
from admin_dashboard.backend.auth.jwt_handler import get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()

# Get config
config = get_admin_config()


# ========== REQUEST/RESPONSE MODELS ==========

class WhitelistEntry(BaseModel):
    """A whitelisted phone number entry."""
    phone_number: str = Field(..., description="Phone number in format 'whatsapp:+31612345678'")
    name: str = Field(..., description="Name of the user")
    department: Optional[str] = Field(None, description="Department (e.g., Owner/Manager, Developer)")
    added_at: Optional[datetime] = None
    is_active: bool = Field(default=True, description="Whether this number is active")
    notes: Optional[str] = Field(None, description="Optional notes about this user")


class AddWhitelistRequest(BaseModel):
    """Request to add a new whitelisted number."""
    phone_number: str = Field(..., description="Phone number in format 'whatsapp:+31612345678'")
    name: str = Field(..., description="Name of the user")
    notes: Optional[str] = None


class UpdateWhitelistRequest(BaseModel):
    """Request to update a whitelisted number."""
    name: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ========== ROUTES ==========

@router.get("/", response_model=List[WhitelistEntry])
async def get_all_whitelisted_numbers(
    username: str = Depends(get_current_user_simple)
):
    """
    Get all whitelisted phone numbers.
    
    Requires authentication.
    """
    logger.info("whitelist_fetch_all", requested_by=username)
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Fetch all entries from Supabase
        response = supabase_logger.client.table("whitelisted_numbers").select("*").order("added_at", desc=True).execute()
        
        logger.info("whitelist_fetched", count=len(response.data), requested_by=username)
        
        return response.data
        
    except Exception as e:
        logger.error("whitelist_fetch_failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch whitelist: {str(e)}"
        )


@router.post("/", response_model=WhitelistEntry, status_code=201)
async def add_whitelisted_number(
    entry: AddWhitelistRequest,
    username: str = Depends(get_current_user_simple)
):
    """
    Add a new phone number to the whitelist.
    
    Requires authentication.
    """
    logger.info(
        "whitelist_add_attempt",
        phone_number=entry.phone_number[:18] + "***",
        name=entry.name,
        requested_by=username
    )
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Check if number already exists
        existing = supabase_logger.client.table("whitelisted_numbers").select("*").eq("phone_number", entry.phone_number).execute()
        
        if existing.data and len(existing.data) > 0:
            logger.warning(
                "whitelist_add_failed",
                reason="already_exists",
                phone_number=entry.phone_number[:18] + "***"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Phone number {entry.phone_number} is already whitelisted"
            )
        
        # Insert new entry
        new_entry = {
            "phone_number": entry.phone_number,
            "name": entry.name,
            "is_active": True,
            "notes": entry.notes,
        }
        
        response = supabase_logger.client.table("whitelisted_numbers").insert(new_entry).execute()
        
        logger.info(
            "whitelist_add_success",
            phone_number=entry.phone_number[:18] + "***",
            name=entry.name,
            requested_by=username
        )
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "whitelist_add_failed",
            error=str(e),
            error_type=type(e).__name__,
            phone_number=entry.phone_number[:18] + "***"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add number to whitelist: {str(e)}"
        )


@router.patch("/{entry_id}", response_model=WhitelistEntry)
async def update_whitelisted_number(
    entry_id: int,
    update: UpdateWhitelistRequest,
    username: str = Depends(get_current_user_simple)
):
    """
    Update a whitelisted number entry.
    
    Typically used to activate/deactivate numbers.
    Requires authentication.
    """
    logger.info(
        "whitelist_update_attempt",
        entry_id=entry_id,
        requested_by=username
    )
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Build update dict (only include non-None values)
        update_data = {}
        if update.name is not None:
            update_data["name"] = update.name
        if update.is_active is not None:
            update_data["is_active"] = update.is_active
        if update.notes is not None:
            update_data["notes"] = update.notes
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields to update"
            )
        
        # Update in Supabase
        response = supabase_logger.client.table("whitelisted_numbers").update(update_data).eq("id", entry_id).execute()
        
        if not response.data or len(response.data) == 0:
            logger.warning("whitelist_update_failed", reason="not_found", entry_id=entry_id)
            raise HTTPException(
                status_code=404,
                detail=f"Whitelist entry with ID {entry_id} not found"
            )
        
        logger.info("whitelist_update_success", entry_id=entry_id, requested_by=username)
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "whitelist_update_failed",
            error=str(e),
            error_type=type(e).__name__,
            entry_id=entry_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update whitelist entry: {str(e)}"
        )


@router.delete("/{entry_id}", status_code=204)
async def delete_whitelisted_number(
    entry_id: int,
    username: str = Depends(get_current_user_simple)
):
    """
    Delete a whitelisted number entry.
    
    NOTE: This permanently deletes the entry. Consider using PATCH to set is_active=False instead.
    Requires authentication.
    """
    logger.info(
        "whitelist_delete_attempt",
        entry_id=entry_id,
        requested_by=username
    )
    
    try:
        # Import Supabase client
        from src.database.supabase_client import get_supabase_logger
        
        supabase_logger = get_supabase_logger()
        
        # Delete from Supabase
        response = supabase_logger.client.table("whitelisted_numbers").delete().eq("id", entry_id).execute()
        
        if not response.data or len(response.data) == 0:
            logger.warning("whitelist_delete_failed", reason="not_found", entry_id=entry_id)
            raise HTTPException(
                status_code=404,
                detail=f"Whitelist entry with ID {entry_id} not found"
            )
        
        logger.info("whitelist_delete_success", entry_id=entry_id, requested_by=username)
        
        return None  # 204 No Content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "whitelist_delete_failed",
            error=str(e),
            error_type=type(e).__name__,
            entry_id=entry_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete whitelist entry: {str(e)}"
        )