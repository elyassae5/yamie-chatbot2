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
import logging

logger = logging.getLogger(__name__)


def main():
    """Run the document ingestion pipeline with proper logging."""
    
    # Set up logging FIRST (before anything else)
    setup_logging(
        level="INFO",           # Change to "DEBUG" for more detailed logs
        log_to_file=True,       # Save logs to file
        log_dir="logs",         # Logs directory
    )
    
    logger.info("="*80)
    logger.info("YAMIEBOT INGESTION SCRIPT")
    logger.info("="*80)
    
    try:
        # Initialize and run pipeline
        pipeline = IngestionPipeline()
        
        results = pipeline.run(
            clear_existing=True,      # Clear old vectors before adding new ones
            dry_run=False,            # Set to True for test run (no embedding/storage)
            inspect_chunks=False,     # Set to True to see sample chunks
        )
        
        # Check result
        if results["status"] == "success":
            logger.info("\n" + "="*80)
            logger.info("✅ INGESTION SUCCESSFUL!")
            logger.info("="*80)
            logger.info(f"Documents: {results['documents']}")
            logger.info(f"Chunks: {results['chunks']}")
            logger.info(f"Duration: {results['duration_seconds']}s")
        elif results["status"] == "dry_run":
            logger.info("\n" + "="*80)
            logger.info("✅ DRY RUN COMPLETE")
            logger.info("="*80)
            logger.info(f"Would have created {results['chunks']} chunks")
            logger.info(f"Estimated cost: ${results.get('estimated_cost_usd', 0):.4f}")
        else:
            logger.error("\n" + "="*80)
            logger.error("❌ INGESTION FAILED")
            logger.error("="*80)
            logger.error(f"Error: {results.get('error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n❌ Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
