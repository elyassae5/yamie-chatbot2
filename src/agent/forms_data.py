"""
Forms data querier for YamieBot.

Second tool alongside the knowledge base searcher. Where search_knowledge_base
does semantic retrieval over Notion KB pages (procedures, SOPs, handbook),
THIS module answers structured operational questions about the 7 form
submission databases.

Why a second tool instead of expanding the Pinecone index:
- Form submissions are STRUCTURED data (franchise × date × form_type ×
  kritiek_count × inwerker × ...). Vector search collapses that into "find
  pages mentioning koelketen" which makes aggregation impossible.
- Questions like "welke vestiging scoort het slechtst op kritieke
  bevindingen deze maand?" need GROUP BY + COUNT, not nearest-neighbour.
- The Notion API has native filter primitives that handle this cleanly.

Schema reality:
- 6 forms (Voorbezoek, Leveranciers, Personeelstraining, Rapport, Nabezoek,
  Quality check) share the "forms_pipeline" schema written by
  /projects/forms-pipeline/backend/.
- 1 form (Go/No-Go) uses an older "gonogo" schema written by
  /projects/gonogo-pipeline/. Different column names, different status
  vocab, no Concept field. Querier branches per-form.

Production-grade considerations:
- All Notion API calls wrapped in tenacity retries (matches existing
  KnowledgeBaseSearcher pattern).
- Pagination follows next_cursor with a hard 500-row cap so the agent
  never hangs on huge result sets.
- Defensive property parsing — Notion returns shape-shifty payloads where
  any property can be missing or null.
- Empty results return a clear Dutch message; Claude must never hallucinate
  data that the tool didn't return.
- Errors return graceful Dutch fallback so the agent loop continues.
- Hard cap of 50 on `limit`. The schema enforces it but the code defends
  too.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from notion_client import Client
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Config, get_config

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Hard cap on how many rows we will pull across pagination per query.
# Notion returns 100/page; this caps at 5 pages. Larger queries should be
# refined with date/severity filters rather than blindly paginated.
MAX_ROWS_PER_QUERY = 500

# Notion's per-page maximum.
NOTION_PAGE_SIZE = 100

# Default limit for list-style aggregations if Claude doesn't specify.
DEFAULT_LIST_LIMIT = 10
MAX_LIST_LIMIT = 50

# ─────────────────────────────────────────────────────────────────────────────
# FORM REGISTRY
# Maps the slug Claude uses to (a) the Notion DB ID, (b) the schema flavour,
# (c) per-form column overrides.
#
# `concept_property_type` is critical for the brand filter: Notion's filter API
# rejects mismatched shapes (a 'select' filter against a 'multi_select' column
# returns 400). Values:
#   "select"        — Concept is a single-select column
#   "multi_select"  — Concept is a multi-select column
#   None            — form has no Concept column at all; brand filter must
#                     skip this form entirely (otherwise it would return all
#                     rows when the user wanted only Yamie)
# Verified against the actual Notion DB schemas on 2026-05-09.
# ─────────────────────────────────────────────────────────────────────────────

FORM_REGISTRY: dict[str, dict[str, Any]] = {
    "voorbezoek": {
        "db_id": "5468ac9e5975425491dce172ec13705a",
        "label": "Voorbezoek",
        "schema": "forms_pipeline",
        # Voorbezoek uses 'Datum voorbezoek' instead of the standard 'Datum'.
        "date_property": "Datum voorbezoek",
        "concept_property_type": "select",
    },
    "leveranciers": {
        "db_id": "a9a627b3125441d79aeb00577f4cf04f",
        "label": "Leveranciers- en Voorraadcontrole",
        "schema": "forms_pipeline",
        "date_property": "Datum",
        "concept_property_type": "select",
    },
    "personeelstraining": {
        "db_id": "a63896f7a8ec4ecbb36ce5d36922bcb8",
        "label": "Personeelstraining",
        "schema": "forms_pipeline",
        "date_property": "Datum",
        # Personeelstraining is concept-agnostic — same training applies
        # across all three brands. No Concept column.
        "concept_property_type": None,
    },
    "gonogo": {
        "db_id": "849959b48c1f451ba0a759ec56f5976c",
        "label": "Go/No-Go",
        "schema": "gonogo",
        "date_property": "Ingediend op",
        "concept_property_type": None,
    },
    "rapport": {
        "db_id": "ca52cded1a21418a9c9b343224b99409",
        "label": "Rapport van bevindingen",
        "schema": "forms_pipeline",
        "date_property": "Datum",
        "concept_property_type": "multi_select",
    },
    "nabezoek": {
        "db_id": "c2ccc4aac019436fbd17af8ab41e07e6",
        "label": "Nabezoek",
        "schema": "forms_pipeline",
        "date_property": "Datum",
        # Nabezoek inherits the inwerker's earlier vestiging context; no
        # Concept column on the DB.
        "concept_property_type": None,
    },
    "quality_check": {
        "db_id": "d3845ed663af46898ecfad4155ec344f",
        "label": "Quality check",
        "schema": "forms_pipeline",
        "date_property": "Datum",
        "concept_property_type": "multi_select",
    },
}

ALL_FORM_SLUGS = list(FORM_REGISTRY.keys())

# Concept (brand) normalisation matches the pipeline writer mappings.
_BRAND_TO_CONCEPT: dict[str, str] = {
    "yamie": "Yamie",
    "flamin": "Flamin",
    "smokey": "Smokey",
}

# Severity vocab Claude provides → forms_pipeline 'Status' select option.
_SEVERITY_TO_FORMS_PIPELINE_STATUS: dict[str, str] = {
    "kritiek": "Kritiek",
    "aandachtspunten": "Aandachtspunten",
    "voltooid": "Voltooid",
}

# Severity vocab → gonogo 'Ernst' select option.
_SEVERITY_TO_GONOGO_ERNST: dict[str, str] = {
    "kritiek": "critical",
    "aandachtspunten": "warning",
    "voltooid": "ok",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATE RANGE RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_date_range(date_range: str) -> Optional[str]:
    """Resolve a date_range enum into an ISO date string for 'on_or_after' filter.

    Returns None for 'all_time' (no date filter applied).
    """
    if not date_range or date_range == "all_time":
        return None

    today = datetime.now(timezone.utc).date()

    if date_range == "last_7_days":
        return (today - timedelta(days=7)).isoformat()
    if date_range == "last_30_days":
        return (today - timedelta(days=30)).isoformat()
    if date_range == "last_90_days":
        return (today - timedelta(days=90)).isoformat()
    if date_range == "this_month":
        return today.replace(day=1).isoformat()

    # Unknown value — log and treat as no filter (defensive).
    logger.warning("unknown_date_range_value", value=date_range)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DEFENSIVE PROPERTY EXTRACTION
# Notion's API returns differently-shaped payloads per property type, with
# liberal use of empty arrays and nulls. Every accessor here must handle a
# missing key, a present-but-empty value, and an unexpected type.
# ─────────────────────────────────────────────────────────────────────────────

def _prop_title(props: dict, name: str) -> str:
    prop = props.get(name) or {}
    arr = prop.get("title") or []
    if not arr:
        return ""
    text = arr[0].get("plain_text") or ""
    return text.strip()


def _prop_rich_text(props: dict, name: str) -> str:
    prop = props.get(name) or {}
    arr = prop.get("rich_text") or []
    if not arr:
        return ""
    return "".join(item.get("plain_text", "") for item in arr).strip()


def _prop_select(props: dict, name: str) -> str:
    prop = props.get(name) or {}
    sel = prop.get("select")
    if not sel:
        return ""
    return sel.get("name", "").strip()


def _prop_multi_select(props: dict, name: str) -> list[str]:
    prop = props.get(name) or {}
    arr = prop.get("multi_select") or []
    return [item.get("name", "").strip() for item in arr if item.get("name")]


def _prop_number(props: dict, name: str) -> int:
    prop = props.get(name) or {}
    val = prop.get("number")
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _prop_email(props: dict, name: str) -> str:
    prop = props.get(name) or {}
    return (prop.get("email") or "").strip()


def _prop_date_start(props: dict, name: str) -> str:
    prop = props.get(name) or {}
    date_obj = prop.get("date")
    if not date_obj:
        return ""
    return (date_obj.get("start") or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL SUBMISSION ROW
# Each Notion page gets normalised into this shape so downstream formatting
# code doesn't care which schema it came from.
# ─────────────────────────────────────────────────────────────────────────────

class SubmissionRow:
    """Canonical normalised view of one submission, agnostic of source schema."""

    __slots__ = (
        "form_slug",
        "form_label",
        "datum",
        "vestiging",
        "concept",
        "inwerker",
        "status",
        "kritiek_count",
        "aandacht_count",
        "samenvatting",
        "submission_id",
        "page_url",
    )

    def __init__(
        self,
        form_slug: str,
        form_label: str,
        datum: str,
        vestiging: str,
        concept: str,
        inwerker: str,
        status: str,
        kritiek_count: int,
        aandacht_count: int,
        samenvatting: str,
        submission_id: str,
        page_url: str,
    ):
        self.form_slug = form_slug
        self.form_label = form_label
        self.datum = datum
        self.vestiging = vestiging
        self.concept = concept
        self.inwerker = inwerker
        self.status = status
        self.kritiek_count = kritiek_count
        self.aandacht_count = aandacht_count
        self.samenvatting = samenvatting
        self.submission_id = submission_id
        self.page_url = page_url

    @property
    def has_findings(self) -> bool:
        return self.kritiek_count > 0 or self.aandacht_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# QUERIER
# ─────────────────────────────────────────────────────────────────────────────

class FormsDataQuerier:
    """
    Queries the 7 form submission Notion DBs and returns formatted Dutch text
    for the agent's tool_result.

    Public entry point: query(form_type, brand, vestiging, date_range,
    severity, aggregation, limit) -> str.

    The returned string is fed directly to Claude as the tool_result content.
    Claude then composes the final Dutch answer for the user.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

        # Fail-soft init: if NOTION_API_KEY is missing or the Notion client
        # cannot be constructed, log it and disable the tool. The agent can
        # still answer KB-only questions. Hard-raising here would crash the
        # whole YamieAgent startup, which would in turn 500 every WhatsApp
        # webhook and admin chat call. Production-grade demands graceful
        # degradation when a single subsystem can't initialise.
        self._enabled: bool = False
        self._init_error: Optional[str] = None
        self._client: Optional[Client] = None

        if not self.config.notion_api_key:
            self._init_error = "NOTION_API_KEY missing"
            logger.warning(
                "forms_querier_disabled",
                reason=self._init_error,
            )
            return

        try:
            self._client = Client(auth=self.config.notion_api_key)
            self._enabled = True
            logger.info(
                "forms_data_querier_initialized",
                forms_registered=len(FORM_REGISTRY),
                max_rows_cap=MAX_ROWS_PER_QUERY,
            )
        except Exception as e:
            self._init_error = f"{type(e).__name__}: {e}"
            logger.error(
                "forms_querier_disabled",
                reason=self._init_error,
            )
            return

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ── Public API ────────────────────────────────────────────────────────────

    def query(
        self,
        form_type: str,
        aggregation: str,
        brand: Optional[str] = None,
        vestiging: Optional[str] = None,
        date_range: str = "last_30_days",
        severity: str = "all",
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> str:
        """
        Query the form databases and return Dutch tool_result text.

        Args:
            form_type:    'voorbezoek', 'leveranciers', 'personeelstraining',
                          'gonogo', 'rapport', 'nabezoek', 'quality_check', or 'all'.
            aggregation:  'count', 'list_submissions', 'list_findings_summary',
                          'score_per_franchise'.
            brand:        Optional 'yamie' / 'flamin' / 'smokey'. Only applied
                          on forms_pipeline schema (gonogo has no Concept).
            vestiging:    Optional substring to match the Vestiging column.
            date_range:   'last_7_days' / 'last_30_days' / 'last_90_days' /
                          'this_month' / 'all_time'. Default 'last_30_days'.
            severity:     'kritiek' / 'aandachtspunten' / 'any_findings' /
                          'voltooid' / 'all'. Default 'all'.
            limit:        For list aggregations. Capped at MAX_LIST_LIMIT.

        Returns:
            Dutch text formatted for Claude's tool_result.
        """
        # If init fail-soft'd, return a clear Dutch message so Claude can
        # still produce a graceful answer for the user.
        if not self._enabled:
            logger.warning(
                "forms_query_called_while_disabled",
                init_error=self._init_error,
            )
            return (
                "Sorry, ik kan de formulier-data nu niet ophalen "
                "(de koppeling met Notion is tijdelijk niet beschikbaar). "
                "Probeer het later opnieuw of neem contact op met je manager."
            )

        # Defensive normalisation.
        limit = max(1, min(limit or DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT))
        date_range = date_range or "last_30_days"
        severity = severity or "all"

        try:
            slugs = self._resolve_form_slugs(form_type)
        except ValueError as e:
            logger.warning("forms_query_invalid_form_type", form_type=form_type)
            return f"Sorry, ik herken het formuliertype '{form_type}' niet. {e}"

        date_floor = _resolve_date_range(date_range)

        logger.info(
            "forms_query_started",
            form_type=form_type,
            slugs=slugs,
            aggregation=aggregation,
            brand=brand,
            vestiging=vestiging,
            date_range=date_range,
            severity=severity,
            limit=limit,
        )

        # Pull rows from each requested form, normalised.
        rows: list[SubmissionRow] = []
        per_form_errors: list[str] = []
        for slug in slugs:
            try:
                rows.extend(
                    self._fetch_rows_for_form(
                        slug=slug,
                        brand=brand,
                        vestiging=vestiging,
                        date_floor=date_floor,
                        severity=severity,
                    )
                )
            except Exception as e:
                # One form failing doesn't tank the whole query — degrade
                # gracefully and tell Claude what we couldn't reach.
                logger.error(
                    "forms_query_form_fetch_failed",
                    slug=slug,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                per_form_errors.append(FORM_REGISTRY[slug]["label"])

        logger.info(
            "forms_query_fetch_complete",
            total_rows=len(rows),
            forms_failed=len(per_form_errors),
        )

        # Format the result based on aggregation.
        formatted = self._format_aggregation(
            rows=rows,
            aggregation=aggregation,
            limit=limit,
            filters_summary=self._describe_filters(
                form_type=form_type,
                brand=brand,
                vestiging=vestiging,
                date_range=date_range,
                severity=severity,
            ),
        )

        if per_form_errors:
            formatted += (
                f"\n\nLet op: ik kon de volgende formulieren nu niet ophalen: "
                f"{', '.join(per_form_errors)}."
            )

        return formatted

    def get_stats(self) -> dict:
        """Lightweight stats for the admin dashboard / debugging."""
        return {
            "enabled": self._enabled,
            "init_error": self._init_error,
            "forms_registered": len(FORM_REGISTRY),
            "max_rows_per_query": MAX_ROWS_PER_QUERY,
            "default_list_limit": DEFAULT_LIST_LIMIT,
        }

    # ── Form resolution ───────────────────────────────────────────────────────

    def _resolve_form_slugs(self, form_type: str) -> list[str]:
        if not form_type:
            raise ValueError("form_type is verplicht.")
        ft = form_type.strip().lower()
        if ft == "all":
            return list(ALL_FORM_SLUGS)
        if ft in FORM_REGISTRY:
            return [ft]
        # Soft alias support — Claude sometimes spells things slightly off.
        aliases = {
            "go-no-go": "gonogo",
            "go/no-go": "gonogo",
            "qualitycheck": "quality_check",
            "quality": "quality_check",
        }
        if ft in aliases:
            return [aliases[ft]]
        raise ValueError(
            f"Onbekend formuliertype. Geldig: {', '.join(ALL_FORM_SLUGS)} of 'all'."
        )

    # ── Per-form fetch ────────────────────────────────────────────────────────

    def _fetch_rows_for_form(
        self,
        *,
        slug: str,
        brand: Optional[str],
        vestiging: Optional[str],
        date_floor: Optional[str],
        severity: str,
    ) -> list[SubmissionRow]:
        spec = FORM_REGISTRY[slug]
        schema = spec["schema"]
        concept_type = spec.get("concept_property_type")

        # Universal: if a brand filter was requested but this form has no
        # Concept column, skip it entirely. Returning all rows would lie to
        # the user; returning nothing tells the aggregator there's no
        # brand-scoped data here.
        if brand and concept_type is None:
            logger.info(
                "forms_query_skipping_form_no_concept",
                slug=slug,
                brand=brand,
            )
            return []

        if schema == "forms_pipeline":
            filter_obj = self._build_filter_forms_pipeline(
                date_property=spec["date_property"],
                date_floor=date_floor,
                brand=brand,
                concept_type=concept_type,
                vestiging=vestiging,
                severity=severity,
            )
        elif schema == "gonogo":
            filter_obj = self._build_filter_gonogo(
                date_property=spec["date_property"],
                date_floor=date_floor,
                vestiging=vestiging,
                severity=severity,
            )
        else:
            raise RuntimeError(f"Unknown schema flavour: {schema}")

        pages = self._paginate_query(
            db_id=spec["db_id"],
            filter_obj=filter_obj,
            sort_property=spec["date_property"],
        )

        # Normalise per schema.
        if schema == "forms_pipeline":
            return [self._normalise_forms_pipeline(p, slug, spec["label"]) for p in pages]
        return [self._normalise_gonogo(p, slug, spec["label"]) for p in pages]

    # ── Filter construction ───────────────────────────────────────────────────

    def _build_filter_forms_pipeline(
        self,
        *,
        date_property: str,
        date_floor: Optional[str],
        brand: Optional[str],
        concept_type: Optional[str],
        vestiging: Optional[str],
        severity: str,
    ) -> Optional[dict]:
        clauses: list[dict] = []

        if date_floor:
            clauses.append({
                "property": date_property,
                "date": {"on_or_after": date_floor},
            })

        # Brand filter shape MUST match the actual Concept property type per
        # form. Notion 400s on mismatched shapes (verified 2026-05-09 — see
        # the registry comment for which form is which type).
        if brand:
            concept = _BRAND_TO_CONCEPT.get(brand.lower())
            if concept and concept_type == "select":
                clauses.append({"property": "Concept", "select": {"equals": concept}})
            elif concept and concept_type == "multi_select":
                clauses.append(
                    {"property": "Concept", "multi_select": {"contains": concept}}
                )
            # If concept_type is None the caller already short-circuited.

        if vestiging:
            clauses.append({
                "property": "Vestiging",
                "rich_text": {"contains": vestiging.strip()},
            })

        sev_clause = self._severity_clause_forms_pipeline(severity)
        if sev_clause:
            clauses.append(sev_clause)

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"and": clauses}

    def _severity_clause_forms_pipeline(self, severity: str) -> Optional[dict]:
        sev = (severity or "all").lower()
        if sev in ("all", ""):
            return None
        if sev == "any_findings":
            return {
                "or": [
                    {"property": "Status", "select": {"equals": "Kritiek"}},
                    {"property": "Status", "select": {"equals": "Aandachtspunten"}},
                ]
            }
        target = _SEVERITY_TO_FORMS_PIPELINE_STATUS.get(sev)
        if not target:
            return None
        return {"property": "Status", "select": {"equals": target}}

    def _build_filter_gonogo(
        self,
        *,
        date_property: str,
        date_floor: Optional[str],
        vestiging: Optional[str],
        severity: str,
    ) -> Optional[dict]:
        # Gonogo has no Concept column. The caller in _fetch_rows_for_form
        # already short-circuits when a brand filter was requested, so we
        # only get here for unbranded queries.
        clauses: list[dict] = []

        if date_floor:
            clauses.append({
                "property": date_property,
                "date": {"on_or_after": date_floor},
            })

        if vestiging:
            # Gonogo uses 'Naam vestiging' as the title column.
            clauses.append({
                "property": "Naam vestiging",
                "title": {"contains": vestiging.strip()},
            })

        sev_clause = self._severity_clause_gonogo(severity)
        if sev_clause:
            clauses.append(sev_clause)

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"and": clauses}

    def _severity_clause_gonogo(self, severity: str) -> Optional[dict]:
        sev = (severity or "all").lower()
        if sev in ("all", ""):
            return None
        if sev == "any_findings":
            return {
                "or": [
                    {"property": "Ernst", "select": {"equals": "warning"}},
                    {"property": "Ernst", "select": {"equals": "critical"}},
                ]
            }
        target = _SEVERITY_TO_GONOGO_ERNST.get(sev)
        if not target:
            return None
        return {"property": "Ernst", "select": {"equals": target}}

    # ── Notion API call with pagination ───────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _query_one_page(
        self,
        *,
        db_id: str,
        filter_obj: Optional[dict],
        sort_property: str,
        start_cursor: Optional[str],
    ) -> dict:
        """One Notion databases.query call. Wrapped in tenacity retries."""
        body: dict[str, Any] = {
            "database_id": db_id,
            "page_size": NOTION_PAGE_SIZE,
            "sorts": [{"property": sort_property, "direction": "descending"}],
        }
        if filter_obj:
            body["filter"] = filter_obj
        if start_cursor:
            body["start_cursor"] = start_cursor
        return self._client.databases.query(**body)

    def _paginate_query(
        self,
        *,
        db_id: str,
        filter_obj: Optional[dict],
        sort_property: str,
    ) -> list[dict]:
        """Pull pages until no next_cursor or until MAX_ROWS_PER_QUERY hit."""
        rows: list[dict] = []
        cursor: Optional[str] = None
        page_count = 0

        while True:
            page_count += 1
            try:
                response = self._query_one_page(
                    db_id=db_id,
                    filter_obj=filter_obj,
                    sort_property=sort_property,
                    start_cursor=cursor,
                )
            except Exception as e:
                # If sort by date fails (e.g. property doesn't exist on this
                # DB), retry once without the sort.
                logger.warning(
                    "notion_query_failed_retrying_unsorted",
                    db_id=db_id,
                    sort_property=sort_property,
                    error=str(e),
                )
                response = self._client.databases.query(
                    database_id=db_id,
                    page_size=NOTION_PAGE_SIZE,
                    filter=filter_obj or {},
                    start_cursor=cursor or None,
                ) if filter_obj else self._client.databases.query(
                    database_id=db_id,
                    page_size=NOTION_PAGE_SIZE,
                    start_cursor=cursor or None,
                )

            results = response.get("results") or []
            rows.extend(results)

            if len(rows) >= MAX_ROWS_PER_QUERY:
                logger.warning(
                    "forms_query_row_cap_hit",
                    db_id=db_id,
                    cap=MAX_ROWS_PER_QUERY,
                    pages_pulled=page_count,
                )
                rows = rows[:MAX_ROWS_PER_QUERY]
                break

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
            if not cursor:
                break

        return rows

    # ── Normalisation per schema ──────────────────────────────────────────────

    def _normalise_forms_pipeline(
        self, page: dict, slug: str, label: str,
    ) -> SubmissionRow:
        props = page.get("properties") or {}
        spec = FORM_REGISTRY[slug]
        date_prop = spec["date_property"]

        # Concept can be select or multi_select depending on the form.
        concept = _prop_select(props, "Concept")
        if not concept:
            concept_multi = _prop_multi_select(props, "Concept")
            if concept_multi:
                concept = ", ".join(concept_multi)

        return SubmissionRow(
            form_slug=slug,
            form_label=label,
            datum=_prop_date_start(props, date_prop) or _safe_created_time(page),
            vestiging=_prop_rich_text(props, "Vestiging"),
            concept=concept,
            inwerker=_prop_select(props, "Inwerker"),
            status=_prop_select(props, "Status"),
            kritiek_count=_prop_number(props, "Aantal kritieke punten"),
            aandacht_count=_prop_number(props, "Aantal aandachtspunten"),
            samenvatting=_prop_rich_text(props, "Samenvatting"),
            submission_id=_prop_rich_text(props, "Submission ID"),
            page_url=page.get("url", ""),
        )

    def _normalise_gonogo(
        self, page: dict, slug: str, label: str,
    ) -> SubmissionRow:
        props = page.get("properties") or {}
        spec = FORM_REGISTRY[slug]
        date_prop = spec["date_property"]

        # Map gonogo 'Ernst' onto the forms_pipeline status vocab so that
        # downstream formatters see a single shape.
        ernst = _prop_select(props, "Ernst").lower()
        status_label = {
            "critical": "Kritiek",
            "warning": "Aandachtspunten",
            "ok": "Voltooid",
        }.get(ernst, ernst.capitalize() if ernst else "")

        return SubmissionRow(
            form_slug=slug,
            form_label=label,
            datum=_prop_date_start(props, date_prop) or _safe_created_time(page),
            vestiging=_prop_title(props, "Naam vestiging"),
            concept="",  # gonogo has no Concept column
            inwerker=_prop_select(props, "Naam inwerker"),
            status=status_label,
            kritiek_count=_prop_number(props, "Aantal Nee"),
            aandacht_count=0,  # gonogo doesn't track warnings separately
            samenvatting=_prop_select(props, "Eindbeoordeling"),  # 'GO' / 'NO-GO'
            submission_id=_prop_rich_text(props, "Submission ID"),
            page_url=page.get("url", ""),
        )

    # ── Aggregation / formatting ──────────────────────────────────────────────

    def _format_aggregation(
        self,
        *,
        rows: list[SubmissionRow],
        aggregation: str,
        limit: int,
        filters_summary: str,
    ) -> str:
        agg = (aggregation or "count").lower()

        if not rows:
            return (
                f"Geen inzendingen gevonden voor deze filters ({filters_summary}). "
                "Probeer een ruimere periode of andere filterwaarden."
            )

        if agg == "count":
            return self._format_count(rows, filters_summary)
        if agg == "list_submissions":
            return self._format_list(rows, limit, filters_summary, with_findings_text=False)
        if agg == "list_findings_summary":
            return self._format_list(rows, limit, filters_summary, with_findings_text=True)
        if agg == "score_per_franchise":
            return self._format_score_per_franchise(rows, limit, filters_summary)

        # Unknown aggregation — fall back to count.
        logger.warning("unknown_aggregation_falling_back_to_count", aggregation=aggregation)
        return self._format_count(rows, filters_summary)

    def _format_count(self, rows: list[SubmissionRow], filters_summary: str) -> str:
        n = len(rows)
        kritiek = sum(1 for r in rows if r.status == "Kritiek")
        aandacht = sum(1 for r in rows if r.status == "Aandachtspunten")
        voltooid = sum(1 for r in rows if r.status == "Voltooid")
        andere = n - kritiek - aandacht - voltooid

        total_kritiek_punten = sum(r.kritiek_count for r in rows)
        total_aandacht_punten = sum(r.aandacht_count for r in rows)

        lines = [
            f"Totaal {n} inzending(en) gevonden ({filters_summary}).",
            f"Status-verdeling: {kritiek} kritiek, {aandacht} aandachtspunten, "
            f"{voltooid} voltooid"
            + (f", {andere} overig." if andere else "."),
            f"Som van bevindingen: {total_kritiek_punten} kritieke punten, "
            f"{total_aandacht_punten} aandachtspunten over alle inzendingen.",
        ]
        return "\n".join(lines)

    def _format_list(
        self,
        rows: list[SubmissionRow],
        limit: int,
        filters_summary: str,
        *,
        with_findings_text: bool,
    ) -> str:
        showing = rows[:limit]
        header = (
            f"Gevonden {len(rows)} inzending(en) ({filters_summary}). "
            f"Toon de {len(showing)} meest recente:\n"
        )
        parts = [header]
        for i, r in enumerate(showing, 1):
            line = (
                f"{i}. [{r.datum or '?'}] {r.form_label} | "
                f"{r.vestiging or 'onbekende vestiging'}"
                f"{' | ' + r.concept if r.concept else ''}"
                f" | Status: {r.status or 'n.v.t.'}"
                f" | Kritiek: {r.kritiek_count}, Aandacht: {r.aandacht_count}"
                f"{' | Inwerker: ' + r.inwerker if r.inwerker else ''}"
            )
            parts.append(line)
            if with_findings_text and r.samenvatting:
                parts.append(f"   Samenvatting: {r.samenvatting}")
        return "\n".join(parts)

    def _format_score_per_franchise(
        self, rows: list[SubmissionRow], limit: int, filters_summary: str,
    ) -> str:
        # Aggregate per vestiging (skip rows with empty vestiging).
        buckets: dict[str, dict[str, Any]] = {}
        for r in rows:
            key = r.vestiging or "(onbekende vestiging)"
            b = buckets.setdefault(
                key,
                {"submissions": 0, "kritiek": 0, "aandacht": 0, "concept": r.concept},
            )
            b["submissions"] += 1
            b["kritiek"] += r.kritiek_count
            b["aandacht"] += r.aandacht_count
            if not b["concept"] and r.concept:
                b["concept"] = r.concept

        # Lower kritiek = better. Ties broken by lower aandacht, then more
        # submissions (more data = more confidence).
        ranked = sorted(
            buckets.items(),
            key=lambda kv: (kv[1]["kritiek"], kv[1]["aandacht"], -kv[1]["submissions"]),
        )

        showing = ranked[:limit]
        header = (
            f"Ranking per vestiging op basis van bevindingen "
            f"(laagste kritiek = beste). Filter: {filters_summary}.\n"
        )
        lines = [header]
        for i, (vestiging, b) in enumerate(showing, 1):
            concept_part = f" ({b['concept']})" if b["concept"] else ""
            lines.append(
                f"{i}. {vestiging}{concept_part} — "
                f"{b['kritiek']} kritiek, {b['aandacht']} aandachtspunten, "
                f"over {b['submissions']} inzending(en)."
            )
        if len(ranked) > limit:
            lines.append(f"\n(Nog {len(ranked) - limit} vestiging(en) niet getoond.)")
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _describe_filters(
        self,
        *,
        form_type: str,
        brand: Optional[str],
        vestiging: Optional[str],
        date_range: str,
        severity: str,
    ) -> str:
        bits: list[str] = []
        bits.append(f"formuliertype: {form_type}")
        if brand:
            bits.append(f"merk: {brand}")
        if vestiging:
            bits.append(f"vestiging bevat '{vestiging}'")
        bits.append(f"periode: {date_range}")
        if severity and severity != "all":
            bits.append(f"ernst: {severity}")
        return ", ".join(bits)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper kept module-level (used by both normalisers).
# ─────────────────────────────────────────────────────────────────────────────

def _safe_created_time(page: dict) -> str:
    """Fall back to Notion's system created_time if the configured date column
    is missing on a page (e.g. very old rows or schema drift)."""
    raw = page.get("created_time") or ""
    # Notion returns RFC3339 like '2026-04-30T12:34:56.000Z'. We want the date
    # part for display.
    return raw[:10] if raw else ""
