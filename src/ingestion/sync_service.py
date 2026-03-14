"""
Content Sync Service — Incremental Notion → Pinecone sync.

Instead of re-ingesting everything, this service:
1. Enumerates all pages in each Notion source tree
2. Compares last_edited_time against the last sync timestamp
3. Re-ingests only changed pages with deterministic vector IDs
4. Logs sync results to Supabase

Usage:
    from src.ingestion.sync_service import ContentSyncService

    service = ContentSyncService()

    # Sync all sources (incremental — only changed pages)
    result = service.sync_all()

    # Sync a single source
    result = service.sync_source("operations-department")

    # Force full re-ingestion with new deterministic IDs
    result = service.sync_all(force_full=True)
"""

import structlog
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding

from src.config import Config, get_config
from src.ingestion.notion_loader import NotionLoader
from src.ingestion.notion_pipeline import NOTION_SOURCES, NotionSource
from src.ingestion.chunker import DocumentChunker

logger = structlog.get_logger(__name__)


# Max chunks we expect per page — used for deletion.
# Pinecone silently ignores IDs that don't exist, so overshooting is safe.
MAX_CHUNKS_PER_PAGE = 200


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class PageSyncResult:
    """Result of syncing a single Notion page."""
    page_id: str
    title: str
    status: str  # "updated", "skipped", "failed"
    chunks_upserted: int = 0
    vectors_deleted: int = 0
    error: Optional[str] = None


@dataclass
class SourceSyncResult:
    """Result of syncing one Notion source (namespace)."""
    source_key: str
    namespace: str
    status: str  # "success", "partial", "failed", "no_changes"
    pages_checked: int = 0
    pages_changed: int = 0
    pages_synced: int = 0
    pages_failed: int = 0
    total_chunks_upserted: int = 0
    total_vectors_deleted: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    page_results: List[PageSyncResult] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a full sync run across all sources."""
    status: str  # "success", "partial", "failed", "no_changes"
    trigger: str  # "manual", "scheduled"
    sources_checked: int = 0
    sources_with_changes: int = 0
    total_pages_changed: int = 0
    total_chunks_upserted: int = 0
    total_vectors_deleted: int = 0
    duration_seconds: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    source_results: List[SourceSyncResult] = field(default_factory=list)


# =============================================================================
# CONTENT SYNC SERVICE
# =============================================================================

class ContentSyncService:
    """
    Handles incremental sync of Notion content to Pinecone.

    Key design decisions:
    - Deterministic vector IDs: {page_id}::chunk::{index:04d}
      This allows targeted deletion when a page changes.
    - Uses Pinecone client directly (not LlamaIndex VectorStoreIndex)
      for full control over IDs and batch operations.
    - Tracks sync timestamps in Supabase for incremental detection.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

        # Initialize components
        self.notion_loader = NotionLoader()
        self.chunker = DocumentChunker(self.config)

        # Pinecone client (used for deletion only — upsert goes through LlamaIndex)
        self._pc = Pinecone(api_key=self.config.pinecone_api_key)
        self._index = self._pc.Index(self.config.pinecone_index_name)

        # LlamaIndex embedding model (same one used by the existing pipeline)
        self._embed_model = OpenAIEmbedding(
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dimensions,
            embed_batch_size=self.config.embedding_batch_size,
        )

        # Supabase client for sync tracking
        self._supabase = None
        try:
            from src.database import get_supabase_logger
            self._supabase = get_supabase_logger()
        except Exception as e:
            logger.warning("supabase_not_available_for_sync", error=str(e))

        logger.info("sync_service_initialized")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def sync_all(
        self,
        trigger: str = "manual",
        force_full: bool = False,
        source_keys: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync all registered Notion sources (incremental by default).

        Args:
            trigger: "manual" (button press) or "scheduled" (background job)
            force_full: If True, re-ingest all pages regardless of edit time.
                        Required once after switching to deterministic IDs.
            source_keys: Specific sources to sync (defaults to all)

        Returns:
            SyncResult with detailed statistics
        """
        start_time = datetime.now(timezone.utc)

        keys = source_keys or list(NOTION_SOURCES.keys())

        logger.info(
            "sync_all_started",
            sources=keys,
            trigger=trigger,
            force_full=force_full,
        )

        source_results = []
        total_pages_changed = 0
        total_chunks = 0
        total_deleted = 0
        sources_with_changes = 0

        for source_key in keys:
            result = self.sync_source(
                source_key=source_key,
                force_full=force_full,
            )
            source_results.append(result)
            total_pages_changed += result.pages_changed
            total_chunks += result.total_chunks_upserted
            total_deleted += result.total_vectors_deleted
            if result.pages_changed > 0:
                sources_with_changes += 1

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        completed_at = datetime.now(timezone.utc).isoformat()

        # Determine overall status
        failed = sum(1 for r in source_results if r.status == "failed")
        if failed == len(source_results):
            status = "failed"
        elif failed > 0:
            status = "partial"
        elif total_pages_changed == 0:
            status = "no_changes"
        else:
            status = "success"

        sync_result = SyncResult(
            status=status,
            trigger=trigger,
            sources_checked=len(keys),
            sources_with_changes=sources_with_changes,
            total_pages_changed=total_pages_changed,
            total_chunks_upserted=total_chunks,
            total_vectors_deleted=total_deleted,
            duration_seconds=round(duration, 2),
            started_at=start_time.isoformat(),
            completed_at=completed_at,
            source_results=source_results,
        )

        # Log to Supabase
        self._log_sync_result(sync_result)

        logger.info(
            "sync_all_completed",
            status=status,
            sources_checked=len(keys),
            pages_changed=total_pages_changed,
            chunks_upserted=total_chunks,
            duration_seconds=round(duration, 2),
        )

        return sync_result

    def sync_source(
        self,
        source_key: str,
        force_full: bool = False,
    ) -> SourceSyncResult:
        """
        Sync a single Notion source (incremental by default).

        Args:
            source_key: Key from NOTION_SOURCES registry
            force_full: If True, re-ingest all pages in this source

        Returns:
            SourceSyncResult with per-page details
        """
        start_time = datetime.now(timezone.utc)

        if source_key not in NOTION_SOURCES:
            return SourceSyncResult(
                source_key=source_key,
                namespace="unknown",
                status="failed",
                error=f"Source '{source_key}' not found",
            )

        source = NOTION_SOURCES[source_key]

        logger.info(
            "sync_source_started",
            source=source_key,
            namespace=source.namespace,
            force_full=force_full,
        )

        try:
            # Step 1: Enumerate all pages in this source tree
            all_pages = self.notion_loader.enumerate_pages(source.page_id)

            logger.info(
                "pages_enumerated",
                source=source_key,
                total_pages=len(all_pages),
            )

            # Step 2: Determine which pages changed
            if force_full:
                changed_pages = all_pages
            else:
                last_sync = self._get_last_sync_time(source_key)
                changed_pages = self._filter_changed_pages(all_pages, last_sync)

            logger.info(
                "changes_detected",
                source=source_key,
                pages_checked=len(all_pages),
                pages_changed=len(changed_pages),
            )

            if not changed_pages:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return SourceSyncResult(
                    source_key=source_key,
                    namespace=source.namespace,
                    status="no_changes",
                    pages_checked=len(all_pages),
                    pages_changed=0,
                    duration_seconds=round(duration, 2),
                )

            # Step 3: Sync each changed page
            page_results = []
            total_chunks = 0
            total_deleted = 0
            failed = 0

            for i, page_info in enumerate(changed_pages, 1):
                logger.info(
                    "syncing_page",
                    page=page_info["title"],
                    progress=f"{i}/{len(changed_pages)}",
                )

                result = self._sync_single_page(
                    page_id=page_info["page_id"],
                    title=page_info["title"],
                    parent_path=page_info["parent_path"],
                    namespace=source.namespace,
                )

                page_results.append(result)
                total_chunks += result.chunks_upserted
                total_deleted += result.vectors_deleted
                if result.status == "failed":
                    failed += 1

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Determine status
            if failed == len(changed_pages):
                status = "failed"
            elif failed > 0:
                status = "partial"
            else:
                status = "success"

            return SourceSyncResult(
                source_key=source_key,
                namespace=source.namespace,
                status=status,
                pages_checked=len(all_pages),
                pages_changed=len(changed_pages),
                pages_synced=len(changed_pages) - failed,
                pages_failed=failed,
                total_chunks_upserted=total_chunks,
                total_vectors_deleted=total_deleted,
                duration_seconds=round(duration, 2),
                page_results=page_results,
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(
                "sync_source_failed",
                source=source_key,
                error=str(e),
                error_type=type(e).__name__,
            )
            return SourceSyncResult(
                source_key=source_key,
                namespace=source.namespace,
                status="failed",
                error=str(e),
                duration_seconds=round(duration, 2),
            )

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get the current sync status for all sources.
        Returns last sync times and basic stats.
        """
        status = {}
        for source_key in NOTION_SOURCES:
            last_sync = self._get_last_sync_time(source_key)
            status[source_key] = {
                "name": NOTION_SOURCES[source_key].name,
                "namespace": NOTION_SOURCES[source_key].namespace,
                "last_sync": last_sync.isoformat() if last_sync else None,
            }
        return status

    # =========================================================================
    # INTERNAL: SINGLE PAGE SYNC
    # =========================================================================

    def _sync_single_page(
        self,
        page_id: str,
        title: str,
        parent_path: str,
        namespace: str,
    ) -> PageSyncResult:
        """
        Sync a single page: delete old vectors, load content, chunk, embed, upsert.
        Uses LlamaIndex VectorStoreIndex for upsert to keep metadata format
        identical to the existing pipeline (retriever compatibility).
        """
        try:
            # Step A: Delete old vectors for this page
            deleted = self._delete_vectors_for_page(page_id, namespace)

            # Step B: Load page content (single page, no recursion)
            documents = self.notion_loader.load_single_page(
                page_id=page_id,
                namespace=namespace,
                parent_path=parent_path,
                include_files=True,
            )

            if not documents:
                logger.info("page_empty_after_load", page_id=page_id, title=title)
                return PageSyncResult(
                    page_id=page_id,
                    title=title,
                    status="updated",
                    vectors_deleted=deleted,
                )

            # Step C: Chunk documents
            nodes = self.chunker.chunk(documents)

            # Step D: Assign deterministic IDs
            for i, node in enumerate(nodes):
                node.id_ = self._make_vector_id(page_id, i)
                node.metadata["notion_page_id"] = page_id

            # Step E: Upsert via LlamaIndex (handles embedding + Pinecone metadata format)
            vector_store = PineconeVectorStore(
                pinecone_index=self._index,
                namespace=namespace,
            )
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                embed_model=self._embed_model,
                show_progress=False,
            )

            logger.info(
                "page_synced",
                page_id=page_id,
                title=title,
                chunks=len(nodes),
                deleted=deleted,
            )

            return PageSyncResult(
                page_id=page_id,
                title=title,
                status="updated",
                chunks_upserted=len(nodes),
                vectors_deleted=deleted,
            )

        except Exception as e:
            logger.error(
                "page_sync_failed",
                page_id=page_id,
                title=title,
                error=str(e),
                error_type=type(e).__name__,
            )
            return PageSyncResult(
                page_id=page_id,
                title=title,
                status="failed",
                error=str(e),
            )

    # =========================================================================
    # INTERNAL: PINECONE OPERATIONS
    # =========================================================================

    def _make_vector_id(self, page_id: str, chunk_index: int) -> str:
        """
        Generate a deterministic vector ID for a chunk.
        Format: {page_id}::chunk::{index:04d}
        """
        return f"{page_id}::chunk::{chunk_index:04d}"

    def _delete_vectors_for_page(self, page_id: str, namespace: str) -> int:
        """
        Delete all vectors belonging to a specific Notion page.
        Uses deterministic ID pattern — generates IDs and bulk-deletes.
        Pinecone silently ignores IDs that don't exist.
        """
        ids_to_delete = [
            self._make_vector_id(page_id, i)
            for i in range(MAX_CHUNKS_PER_PAGE)
        ]

        try:
            # Pinecone delete accepts up to 1000 IDs per call
            self._index.delete(ids=ids_to_delete, namespace=namespace)
            logger.debug(
                "vectors_deleted_for_page",
                page_id=page_id,
                namespace=namespace,
                ids_attempted=len(ids_to_delete),
            )
            return len(ids_to_delete)  # We don't know exact count deleted
        except Exception as e:
            logger.error(
                "vector_deletion_failed",
                page_id=page_id,
                error=str(e),
            )
            return 0

    # =========================================================================
    # INTERNAL: SYNC TRACKING (SUPABASE)
    # =========================================================================

    def _get_last_sync_time(self, source_key: str) -> Optional[datetime]:
        """
        Get the last successful sync time for a specific source from Supabase.

        Checks the details JSONB column to find a sync that actually
        included this source_key (not just any successful sync globally).
        Returns None if never synced (triggers full sync).
        """
        if not self._supabase:
            return None

        try:
            # Fetch recent successful/no_changes syncs with their details
            response = (
                self._supabase.client
                .table("sync_logs")
                .select("completed_at, details")
                .in_("status", ["success", "no_changes"])
                .order("completed_at", desc=True)
                .limit(10)
                .execute()
            )

            if not response.data:
                return None

            # Find the most recent sync that included this source
            for row in response.data:
                details = row.get("details") or {}
                source_results = details.get("source_results", [])

                for sr in source_results:
                    if sr.get("source_key") == source_key and sr.get("status") != "failed":
                        timestamp_str = row["completed_at"]
                        logger.debug(
                            "last_sync_time_found",
                            source_key=source_key,
                            completed_at=timestamp_str,
                        )
                        return datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )

            # No sync found that included this source
            logger.info(
                "no_previous_sync_for_source",
                source_key=source_key,
            )
            return None

        except Exception as e:
            logger.warning(
                "get_last_sync_time_failed",
                source_key=source_key,
                error=str(e),
            )
            return None

    def _log_sync_result(self, result: SyncResult) -> None:
        """Log sync result to Supabase sync_logs table."""
        if not self._supabase:
            return

        try:
            self._supabase.client.table("sync_logs").insert({
                "status": result.status,
                "trigger": result.trigger,
                "sources_checked": result.sources_checked,
                "sources_with_changes": result.sources_with_changes,
                "total_pages_changed": result.total_pages_changed,
                "total_chunks_upserted": result.total_chunks_upserted,
                "total_vectors_deleted": result.total_vectors_deleted,
                "duration_seconds": result.duration_seconds,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "details": {
                    "source_results": [
                        {
                            "source_key": sr.source_key,
                            "namespace": sr.namespace,
                            "status": sr.status,
                            "pages_checked": sr.pages_checked,
                            "pages_changed": sr.pages_changed,
                            "pages_synced": sr.pages_synced,
                            "pages_failed": sr.pages_failed,
                            "chunks_upserted": sr.total_chunks_upserted,
                            "error": sr.error,
                        }
                        for sr in result.source_results
                    ]
                },
            }).execute()

            logger.info("sync_result_logged_to_supabase")

        except Exception as e:
            logger.warning("sync_result_logging_failed", error=str(e))

    # =========================================================================
    # INTERNAL: CHANGE DETECTION
    # =========================================================================

    def _filter_changed_pages(
        self,
        pages: List[Dict[str, Any]],
        last_sync: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        """
        Filter pages to only those edited after the last sync.
        If last_sync is None (never synced), returns ALL pages.
        """
        if last_sync is None:
            logger.info("no_previous_sync_found", action="syncing_all_pages")
            return pages

        changed = []
        for page in pages:
            edited_str = page.get("last_edited_time", "")
            if not edited_str:
                # No edit time available — include to be safe
                changed.append(page)
                continue

            try:
                edited_time = datetime.fromisoformat(
                    edited_str.replace("Z", "+00:00")
                )
                if edited_time > last_sync:
                    changed.append(page)
            except (ValueError, TypeError):
                # Can't parse timestamp — include to be safe
                changed.append(page)

        return changed