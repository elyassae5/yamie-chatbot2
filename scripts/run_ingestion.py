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

from src.ingestion.pipeline import IngestionPipeline

def main():
    pipeline = IngestionPipeline()

    results = pipeline.run(
        clear_existing=True,
        dry_run=False,
        inspect_chunks=False,
    )

    sys.exit(0 if results["status"] == "success" else 1)


if __name__ == "__main__":
    main()
