"""
Content Sync Routes — Trigger and monitor Notion → Pinecone sync.

Endpoints:
- POST /api/sync/run         — Trigger a sync (incremental or full)
- GET  /api/sync/status       — Get last sync times per source
- GET  /api/sync/history      — Get paginated sync log history
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from admin_dashboard.backend.auth.jwt_handler import get_current_user_simple

logger = structlog.get_logger(__name__)
router = APIRouter()


# ========== RESPONSE MODELS ==========

class SyncRunRequest(BaseModel):
    """Request body for triggering a sync."""
    force_full: bool = False  # If True, re-ingest all pages regardless of edit time
    source_keys: Optional[List[str]] = None  # Specific sources, or None for all


class SyncRunResponse(BaseModel):
    """Response after a sync completes."""
    status: str
    sources_checked: int
    sources_with_changes: int
    total_pages_changed: int
    total_chunks_upserted: int
    duration_seconds: float
    source_details: List[Dict[str, Any]]


class SyncStatusResponse(BaseModel):
    """Current sync status per source."""
    sources: Dict[str, Any]


class SyncHistoryEntry(BaseModel):
    """A single sync log entry."""
    id: str
    status: str
    trigger: str
    sources_checked: int
    sources_with_changes: int
    total_pages_changed: int
    total_chunks_upserted: int
    duration_seconds: float
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SyncHistoryResponse(BaseModel):
    """Paginated sync history."""
    logs: List[SyncHistoryEntry]
    total: int
    page: int
    page_size: int


# ========== DATABASE LOCK HELPERS ==========

def _acquire_lock(username: str) -> bool:
    """
    Attempt to acquire the sync lock atomically via Postgres.
    
    Returns True if lock acquired, False if another sync is running.
    Also auto-releases stale locks older than 30 minutes.
    """
    try:
        from src.database.supabase_client import get_supabase_client
        client = get_supabase_client()
        
        response = client.rpc("acquire_sync_lock", {"p_started_by": username}).execute()
        
        # RPC returns True if the UPDATE matched a row, None/empty if not
        if response.data is True:
            return True
        return False
        
    except Exception as e:
        logger.error("sync_lock_acquire_failed", error=str(e), error_type=type(e).__name__)
        return False


def _release_lock():
    """Release the sync lock."""
    try:
        from src.database.supabase_client import get_supabase_client
        client = get_supabase_client()
        
        client.rpc("release_sync_lock").execute()
        
    except Exception as e:
        logger.error("sync_lock_release_failed", error=str(e), error_type=type(e).__name__)


def _is_sync_running() -> Dict[str, Any]:
    """Check current lock status (for the status endpoint)."""
    try:
        from src.database.supabase_client import get_supabase_client
        client = get_supabase_client()
        
        response = client.table("sync_lock").select("*").eq("id", 1).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return {
                "is_running": row.get("is_running", False),
                "started_by": row.get("started_by"),
                "started_at": row.get("started_at"),
            }
        return {"is_running": False}
        
    except Exception as e:
        logger.error("sync_lock_check_failed", error=str(e), error_type=type(e).__name__)
        return {"is_running": False}


# ========== ROUTES ==========

@router.post("/run", response_model=SyncRunResponse)
async def run_sync(
    request: SyncRunRequest,
    username: str = Depends(get_current_user_simple),
):
    """
    Trigger a content sync from Notion to Pinecone.

    By default runs incrementally — only pages edited since last sync.
    Set force_full=true to re-ingest everything (needed once for migration
    to deterministic vector IDs).

    Uses a database-level lock to prevent concurrent syncs across all workers.

    Requires authentication.
    """
    # Attempt to acquire database lock (atomic — safe across multiple workers)
    if not _acquire_lock(username):
        raise HTTPException(
            status_code=409,
            detail="A sync is already in progress. Please wait for it to finish.",
        )

    logger.info(
        "sync_triggered",
        requested_by=username,
        force_full=request.force_full,
        source_keys=request.source_keys,
    )

    try:
        from src.ingestion.sync_service import ContentSyncService

        service = ContentSyncService()
        result = service.sync_all(
            trigger="manual",
            force_full=request.force_full,
            source_keys=request.source_keys,
        )

        source_details = [
            {
                "source_key": sr.source_key,
                "namespace": sr.namespace,
                "status": sr.status,
                "pages_checked": sr.pages_checked,
                "pages_changed": sr.pages_changed,
                "pages_synced": sr.pages_synced,
                "pages_failed": sr.pages_failed,
                "chunks_upserted": sr.total_chunks_upserted,
                "duration_seconds": sr.duration_seconds,
                "error": sr.error,
            }
            for sr in result.source_results
        ]

        logger.info(
            "sync_completed",
            requested_by=username,
            status=result.status,
            pages_changed=result.total_pages_changed,
            duration=result.duration_seconds,
        )

        return SyncRunResponse(
            status=result.status,
            sources_checked=result.sources_checked,
            sources_with_changes=result.sources_with_changes,
            total_pages_changed=result.total_pages_changed,
            total_chunks_upserted=result.total_chunks_upserted,
            duration_seconds=result.duration_seconds,
            source_details=source_details,
        )

    except Exception as e:
        logger.error(
            "sync_failed",
            requested_by=username,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Sync failed. Check server logs for details.",
        )

    finally:
        # Always release the lock, even if sync fails
        _release_lock()


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    username: str = Depends(get_current_user_simple),
):
    """
    Get the current sync status: last sync time per source and
    whether a sync is currently running.

    Requires authentication.
    """
    logger.info("sync_status_requested", requested_by=username)

    try:
        from src.ingestion.sync_service import ContentSyncService

        service = ContentSyncService()
        status = service.get_sync_status()

        # Add lock status from database
        lock_status = _is_sync_running()
        status["_sync_in_progress"] = lock_status["is_running"]
        if lock_status["is_running"]:
            status["_current_sync"] = {
                "status": "running",
                "started_by": lock_status.get("started_by"),
                "started_at": lock_status.get("started_at"),
            }

        return SyncStatusResponse(sources=status)

    except Exception as e:
        logger.error("sync_status_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get sync status.",
        )


@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    page: int = 1,
    page_size: int = 10,
    username: str = Depends(get_current_user_simple),
):
    """
    Get paginated sync history from Supabase.

    Requires authentication.
    """
    logger.info("sync_history_requested", requested_by=username, page=page)

    try:
        from src.database import get_supabase_logger

        supabase_logger = get_supabase_logger()

        # Get total count
        count_response = (
            supabase_logger.client
            .table("sync_logs")
            .select("id", count="exact")
            .execute()
        )
        total = count_response.count or 0

        # Get paginated results
        offset = (page - 1) * page_size
        response = (
            supabase_logger.client
            .table("sync_logs")
            .select("*")
            .order("completed_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        logs = [
            SyncHistoryEntry(
                id=str(row.get("id", "")),
                status=row.get("status", "unknown"),
                trigger=row.get("trigger", "unknown"),
                sources_checked=row.get("sources_checked", 0),
                sources_with_changes=row.get("sources_with_changes", 0),
                total_pages_changed=row.get("total_pages_changed", 0),
                total_chunks_upserted=row.get("total_chunks_upserted", 0),
                duration_seconds=row.get("duration_seconds", 0.0),
                started_at=row.get("started_at"),
                completed_at=row.get("completed_at"),
                details=row.get("details"),
            )
            for row in (response.data or [])
        ]

        return SyncHistoryResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error("sync_history_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get sync history.",
        )