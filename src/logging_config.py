"""
Production-grade logging configuration using structlog.

This provides JSON-structured logs that are:
- Parseable by log aggregators (Datadog, CloudWatch, etc.)
- Searchable and queryable
- Include context (user_id, request_id, etc.)
- Production-ready
"""

import logging
import sys
import structlog
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """
    Configure structured logging for production.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logs (default: None, logs to console)
    
    Example:
        >>> setup_logging(log_level="INFO")
        >>> logger = structlog.get_logger()
        >>> logger.info("user_logged_in", user_id="user_123", ip="192.168.1.1")
    """
    
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure structlog processors (the pipeline that processes each log)
    structlog.configure(
        processors=[
            # Add log level to log entry
            structlog.stdlib.add_log_level,
            # Add logger name to log entry
            structlog.stdlib.add_logger_name,
            # Add timestamp in ISO format
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # If exception occurred, format it nicely
            structlog.processors.format_exc_info,
            # Decode unicode (handle special characters)
            structlog.processors.UnicodeDecoder(),
            # Render as JSON (production-ready format)
            structlog.processors.JSONRenderer()
        ],
        # Context is stored in a dict
        context_class=dict,
        # Use standard library logging
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache logger on first use (performance optimization)
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging (structlog builds on top of this)
    handlers = []
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    handlers.append(console_handler)
    
    # File handler (optional, if log_file specified)
    if log_file:
        # Ensure logs directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        format="%(message)s",  # structlog handles formatting
        level=numeric_level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Get a logger and log that setup is complete
    logger = structlog.get_logger()
    logger.info(
        "logging_configured",
        log_level=log_level,
        log_file=log_file if log_file else "console_only",
        structured=True
    )


def get_logger(name: str = None):
    """
    Get a structured logger instance.
    
    Args:
        name: Optional logger name (typically __name__ of the module)
    
    Returns:
        Structured logger that outputs JSON
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("query_completed", user_id="user_123", response_time_ms=1250)
        {"event": "query_completed", "user_id": "user_123", "response_time_ms": 1250, ...}
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


# Convenience function for testing
if __name__ == "__main__":
    # Test the logging setup
    setup_logging(log_level="INFO")
    
    logger = get_logger("test")
    
    print("\n" + "="*80)
    print("TESTING STRUCTURED LOGGING")
    print("="*80 + "\n")
    
    # Test different log levels
    logger.debug("debug_message", detail="This is debug info")
    logger.info("info_message", user_id="user_123", action="login")
    logger.warning("warning_message", attempts=3, max_attempts=5)
    logger.error("error_message", error_code="E001", error_msg="Something went wrong")
    
    # Test with context
    logger.info(
        "query_completed",
        user_id="employee_daoud",
        question="Wie is Daoud?",
        response_time_ms=1240,
        has_answer=True,
        chunks_retrieved=7,
        model="gpt-4o-mini"
    )
    
    print("\n" + "="*80)
    print("✓ Structured logging working! Each log is valid JSON.")
    print("="*80 + "\n")