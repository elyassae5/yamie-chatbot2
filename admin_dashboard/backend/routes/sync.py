"""
Content Sync Routes — Trigger and monitor Notion → Pinecone sync.

Endpoints:
- POST /api/sync/run         — Trigger a sync (incremental or full)
- GET  /api/sync/status       — Get last sync times per source
- GET  /api/sync/history      — Get paginated sync log history
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
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


# Track whether a sync is currently running
_sync_in_progress = False
_current_sync_status: Optional[Dict[str, Any]] = None


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

    Requires authentication.
    """
    global _sync_in_progress, _current_sync_status

    if _sync_in_progress:
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

    _sync_in_progress = True
    _current_sync_status = {"status": "running", "started_by": username}

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
        _sync_in_progress = False
        _current_sync_status = None


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

        # Add in-progress flag
        status["_sync_in_progress"] = _sync_in_progress
        if _current_sync_status:
            status["_current_sync"] = _current_sync_status

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