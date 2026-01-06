"""
Entry point for running the ingestion pipeline.
Usage:
    python scripts/run_ingestion.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging
from src.ingestion.pipeline import IngestionPipeline
import structlog

logger = structlog.get_logger(__name__)


def main():
    """Run the document ingestion pipeline with proper logging."""
    
    # Set up logging FIRST (before anything else)
    setup_logging(
        log_level="INFO",                    # Change to "DEBUG" for more detailed logs
        log_file="logs/ingestion.log"        # Save logs to file
    )
    
    logger.info("ingestion_script_started")
    logger.info("script_message", message="YAMIEBOT INGESTION SCRIPT")
    
    try:
        # Initialize and run pipeline
        pipeline = IngestionPipeline()
        
        logger.info(
            "pipeline_run_configuration",
            clear_existing=True,
            dry_run=False,
            inspect_chunks=False
        )
        
        results = pipeline.run(
            clear_existing=True,      # Clear old vectors before adding new ones
            dry_run=False,            # Set to True for test run (no embedding/storage)
            inspect_chunks=False,     # Set to True to see sample chunks
        )
        
        # Check result
        if results["status"] == "success":
            logger.info("ingestion_successful", message="✅ INGESTION SUCCESSFUL!")
            logger.info(
                "ingestion_results",
                documents=results['documents'],
                chunks=results['chunks'],
                duration_seconds=results['duration_seconds']
            )
        elif results["status"] == "dry_run":
            logger.info("dry_run_completed", message="✅ DRY RUN COMPLETE")
            logger.info(
                "dry_run_results",
                chunks_would_create=results['chunks'],
                estimated_cost_usd=round(results.get('estimated_cost_usd', 0), 4)
            )
        else:
            logger.error("ingestion_failed", message="❌ INGESTION FAILED")
            logger.error(
                "ingestion_error",
                error=results.get('error')
            )
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("ingestion_interrupted", reason="user_keyboard_interrupt")
        sys.exit(1)
    except Exception as e:
        logger.error(
            "ingestion_unexpected_error",
            error=str(e),
            error_type=type(e).__name__
        )
        sys.exit(1)


if __name__ == "__main__":
    main()