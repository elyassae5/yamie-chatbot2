#!/usr/bin/env python3
"""
Notion Ingestion Script - Ingest Notion content into Pinecone.

Usage:
    # Ingest a specific registered source
    python scripts/run_notion_ingestion.py --source operations-department
    
    # Ingest all registered sources
    python scripts/run_notion_ingestion.py --all
    
    # Dry run (no embedding/storage, just test loading + chunking)
    python scripts/run_notion_ingestion.py --source operations-department --dry-run
    
    # Clear existing vectors before ingesting
    python scripts/run_notion_ingestion.py --source operations-department --clear
    
    # Ingest a custom page (not in registry)
    python scripts/run_notion_ingestion.py --page-id YOUR_PAGE_ID --namespace custom-ns --name "My Custom Source"
    
    # List available sources
    python scripts/run_notion_ingestion.py --list

Author: YamieBot Team
Last Updated: February 2026
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging
from src.ingestion.notion_pipeline import (
    NotionIngestionPipeline,
    NOTION_SOURCES,
    IngestionResult,
    PipelineResult,
)
import structlog

logger = structlog.get_logger(__name__)


def print_banner():
    """Print the script banner."""
    print()
    print("=" * 70)
    print("🚀 YAMIEBOT NOTION INGESTION")
    print("=" * 70)
    print()


def print_sources(pipeline: NotionIngestionPipeline):
    """Print available sources."""
    print("📋 Available Notion Sources:")
    print("-" * 50)
    
    sources = pipeline.list_sources()
    
    if not sources:
        print("  No sources registered yet.")
        print("  Add sources in src/ingestion/notion_pipeline.py")
        return
    
    for key, info in sources.items():
        print(f"\n  📁 {key}")
        print(f"     Name: {info['name']}")
        print(f"     Namespace: {info['namespace']}")
        if info['description']:
            print(f"     Description: {info['description']}")
        print(f"     Page ID: {info['page_id'][:20]}...")
    
    print()


def print_result(result: IngestionResult):
    """Print a single ingestion result."""
    status_icons = {
        "success": "✅",
        "failed": "❌",
        "skipped": "⏭️",
        "dry_run": "🧪",
    }
    
    icon = status_icons.get(result.status, "❓")
    
    print(f"\n{icon} {result.source_name}")
    print(f"   Status: {result.status}")
    print(f"   Namespace: {result.namespace}")
    
    if result.status in ("success", "dry_run"):
        print(f"   Documents: {result.documents_loaded}")
        print(f"   Chunks: {result.chunks_created}")
        print(f"   Duration: {result.duration_seconds:.1f}s")
        
        if result.details.get("estimated_cost_usd"):
            print(f"   Estimated Cost: ${result.details['estimated_cost_usd']:.4f}")
    
    if result.error:
        print(f"   Error: {result.error}")


def print_pipeline_result(result: PipelineResult):
    """Print overall pipeline results."""
    status_icons = {
        "success": "✅",
        "partial": "⚠️",
        "failed": "❌",
    }
    
    icon = status_icons.get(result.status, "❓")
    
    print("\n" + "=" * 70)
    print(f"{icon} INGESTION COMPLETE")
    print("=" * 70)
    
    print(f"\n📊 Summary:")
    print(f"   Status: {result.status}")
    print(f"   Sources Processed: {result.sources_processed}")
    print(f"   Sources Failed: {result.sources_failed}")
    print(f"   Total Documents: {result.total_documents}")
    print(f"   Total Chunks: {result.total_chunks}")
    print(f"   Duration: {result.duration_seconds:.1f}s")
    
    if result.results:
        print(f"\n📋 Per-Source Results:")
        for r in result.results:
            print_result(r)


def print_namespace_stats(pipeline: NotionIngestionPipeline, namespace: str):
    """Print stats for a namespace after ingestion."""
    print(f"\n📈 Verifying namespace '{namespace}'...")
    stats = pipeline.get_namespace_stats(namespace)
    
    if stats.get("error"):
        print(f"   ⚠️  Could not fetch stats: {stats['error']}")
    elif stats.get("exists"):
        print(f"   ✅ Vectors in namespace: {stats['vector_count']}")
    else:
        print(f"   ⚠️  Namespace not found (may need a moment to propagate)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest Notion content into Pinecone vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest operations department
  python scripts/run_notion_ingestion.py --source operations-department
  
  # Dry run to test without storing
  python scripts/run_notion_ingestion.py --source operations-department --dry-run
  
  # Clear existing and re-ingest
  python scripts/run_notion_ingestion.py --source operations-department --clear
  
  # Ingest all sources
  python scripts/run_notion_ingestion.py --all
  
  # Custom page
  python scripts/run_notion_ingestion.py --page-id abc123 --namespace my-ns --name "My Source"
        """
    )
    
    # Source selection (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--source", "-s",
        help="Registered source key to ingest (e.g., 'operations-department')"
    )
    source_group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Ingest all registered sources"
    )
    source_group.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available sources and exit"
    )
    
    # Custom page options
    parser.add_argument(
        "--page-id",
        help="Notion page ID for custom ingestion (use with --namespace)"
    )
    parser.add_argument(
        "--namespace",
        help="Pinecone namespace for custom ingestion"
    )
    parser.add_argument(
        "--name",
        default="Custom Source",
        help="Name for custom source (for logging)"
    )
    
    # Ingestion options
    parser.add_argument(
        "--clear", "-c",
        action="store_true",
        help="Clear existing vectors in namespace before ingesting"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Load and chunk only, don't embed or store"
    )
    parser.add_argument(
        "--no-nested",
        action="store_true",
        help="Don't recursively load nested pages"
    )
    parser.add_argument(
        "--no-files",
        action="store_true",
        help="Don't extract embedded PDF/DOCX files"
    )
    
    # Logging
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(
        log_level=log_level,
        log_file="logs/notion_ingestion.log"
    )
    
    print_banner()
    
    # Initialize pipeline
    try:
        pipeline = NotionIngestionPipeline()
    except Exception as e:
        print(f"❌ Failed to initialize pipeline: {e}")
        sys.exit(1)
    
    # Handle --list
    if args.list:
        print_sources(pipeline)
        sys.exit(0)
    
    # Handle custom page
    if args.page_id:
        if not args.namespace:
            print("❌ Error: --page-id requires --namespace")
            sys.exit(1)
        
        print(f"📄 Ingesting custom page: {args.name}")
        print(f"   Page ID: {args.page_id}")
        print(f"   Namespace: {args.namespace}")
        print(f"   Clear existing: {args.clear}")
        print(f"   Dry run: {args.dry_run}")
        print()
        
        result = pipeline.ingest_page(
            page_id=args.page_id,
            namespace=args.namespace,
            name=args.name,
            clear_existing=args.clear,
            dry_run=args.dry_run,
            include_nested=not args.no_nested,
            include_files=not args.no_files,
        )
        
        print_result(result)
        
        if result.status == "success":
            print_namespace_stats(pipeline, args.namespace)
        
        sys.exit(0 if result.status in ("success", "dry_run") else 1)
    
    # Handle --all
    if args.all:
        print(f"📚 Ingesting ALL registered sources")
        print(f"   Sources: {list(NOTION_SOURCES.keys())}")
        print(f"   Clear existing: {args.clear}")
        print(f"   Dry run: {args.dry_run}")
        print()
        
        result = pipeline.ingest_all(
            clear_existing=args.clear,
            dry_run=args.dry_run,
        )
        
        print_pipeline_result(result)
        
        sys.exit(0 if result.status == "success" else 1)
    
    # Handle --source
    if args.source:
        if args.source not in NOTION_SOURCES:
            print(f"❌ Error: Unknown source '{args.source}'")
            print(f"   Available sources: {list(NOTION_SOURCES.keys())}")
            print(f"   Use --list to see details")
            sys.exit(1)
        
        source = NOTION_SOURCES[args.source]
        
        print(f"📁 Ingesting source: {source.name}")
        print(f"   Key: {args.source}")
        print(f"   Namespace: {source.namespace}")
        print(f"   Clear existing: {args.clear}")
        print(f"   Dry run: {args.dry_run}")
        print()
        
        result = pipeline.ingest_source(
            source_key=args.source,
            clear_existing=args.clear,
            dry_run=args.dry_run,
        )
        
        print_result(result)
        
        if result.status == "success":
            print_namespace_stats(pipeline, source.namespace)
        
        print()
        sys.exit(0 if result.status in ("success", "dry_run") else 1)
    
    # No action specified
    print("❌ No action specified. Use one of:")
    print("   --source <name>  : Ingest a specific source")
    print("   --all            : Ingest all sources")
    print("   --list           : List available sources")
    print("   --page-id <id>   : Ingest a custom page")
    print()
    print("Run with --help for full usage information.")
    sys.exit(1)


if __name__ == "__main__":
    main()