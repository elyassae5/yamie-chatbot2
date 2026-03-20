"""
Shared QueryEngine singleton.

Both the /api/query route and the WhatsApp webhook route
import the engine from here so they share one instance
(one set of Pinecone connections, one Redis memory client).
"""

import structlog
from src.query import QueryEngine
from src.config import get_config

logger = structlog.get_logger(__name__)

# Initialize QueryEngine once — shared across all routes
logger.info("query_engine_initialization_started")
try:
    engine = QueryEngine(config=get_config())
    logger.info("query_engine_initialized", status="success")
except Exception as e:
    logger.error(
        "query_engine_initialization_failed",
        error=str(e),
        error_type=type(e).__name__
    )
    engine = None