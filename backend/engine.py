"""
Shared YamieAgent singleton.

Both the /api/query route and the WhatsApp webhook route import the engine
from here so they share one instance (one Pinecone connection, one Redis client).

Swapped from QueryEngine → YamieAgent as part of the agentic RAG migration.
The public interface is identical: engine.query(question, user_id) → QueryResponse
"""

import structlog
from src.agent import YamieAgent
from src.config import get_config

logger = structlog.get_logger(__name__)

logger.info("yamie_agent_initialization_started")
try:
    engine = YamieAgent(config=get_config())
    logger.info("yamie_agent_initialized", status="success")
except Exception as e:
    logger.error(
        "yamie_agent_initialization_failed",
        error=str(e),
        error_type=type(e).__name__,
    )
    engine = None
