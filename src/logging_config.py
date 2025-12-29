"""
Centralized logging configuration for YamieBot.
Sets up structured logging with console and file outputs.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_dir: str = "logs",
    log_filename: str = None,
) -> None:
    """
    Configure logging for the entire application.
    
    This function sets up:
    - Console logging (colored output with timestamps)
    - File logging (rotating files to prevent disk space issues)
    - Proper formatting for both outputs
    - Log level filtering
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to write logs to files
        log_dir: Directory to store log files
        log_filename: Custom log filename (auto-generated if None)
        
    Example:
        >>> from src.logging_config import setup_logging
        >>> setup_logging(level="INFO", log_to_file=True)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
    
    # Clear any existing handlers (important for re-initialization)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)
    
    # ===== CONSOLE HANDLER =====
    # Shows logs in terminal with colors and clean formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Console format: simple and readable
    console_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # ===== FILE HANDLER (Optional) =====
    # Writes logs to rotating files to prevent disk space issues
    if log_to_file:
        # Generate filename if not provided
        if log_filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            log_filename = f"yamiebot_{timestamp}.log"
        
        log_file_path = log_path / log_filename
        
        # Rotating file handler: creates new file when current reaches 10MB
        # Keeps last 5 files (50MB total max)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,  # Keep last 5 files
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        
        # File format: more detailed than console
        file_format = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
        
        # Log where we're storing logs
        logging.info(f"Logging to file: {log_file_path}")
    
    # ===== SUPPRESS NOISY LIBRARIES =====
    # Some libraries are too verbose - quiet them down
    logging.getLogger('httpx').setLevel(logging.WARNING)  # HTTP client
    logging.getLogger('openai').setLevel(logging.WARNING)  # OpenAI SDK
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # URL library
    logging.getLogger('pinecone').setLevel(logging.WARNING)  # Pinecone SDK
    
    logging.info(f"Logging configured: level={level}, file_logging={log_to_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    This is a convenience function that ensures logging is set up
    and returns a properly configured logger.
    
    Args:
        name: Logger name (typically __name__ from the calling module)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> from src.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Change the logging level at runtime.
    
    Useful for temporarily enabling debug logging or reducing verbosity.
    
    Args:
        level: New logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Example:
        >>> from src.logging_config import set_log_level
        >>> set_log_level("DEBUG")  # Enable verbose logging
        >>> # ... do debugging ...
        >>> set_log_level("INFO")   # Back to normal
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    
    # Update all handlers
    for handler in logging.getLogger().handlers:
        handler.setLevel(numeric_level)
    
    logging.info(f"Log level changed to: {level}")


# ===== EXAMPLE USAGE =====
if __name__ == "__main__":
    """
    Test the logging configuration.
    Run: python -m src.logging_config
    """
    
    # Set up logging
    setup_logging(level="DEBUG", log_to_file=True)
    
    # Get a logger
    logger = logging.getLogger(__name__)
    
    # Test different log levels
    logger.debug("This is a DEBUG message - very detailed")
    logger.info("This is an INFO message - normal operation")
    logger.warning("This is a WARNING message - something unusual")
    logger.error("This is an ERROR message - something failed")
    logger.critical("This is a CRITICAL message - system failure")
    
    # Test exception logging
    try:
        x = 1 / 0
    except Exception as e:
        logger.error("An error occurred", exc_info=True)
    
    print("\n✅ Logging test complete! Check the logs/ directory for the log file.")
