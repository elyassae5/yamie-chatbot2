#!/usr/bin/env python3
"""
Debug Query Script - Shows EVERYTHING for debugging and quality control.

This script shows:
- All retrieved chunks with FULL content
- Exact source paths (Notion page hierarchy)
- Similarity scores
- Metadata (namespace, page_id, etc.)
- The exact prompt sent to the LLM
- Token usage

Perfect for:
- Debugging retrieval quality
- Understanding what the bot "sees"
- Building dashboards later
- Quality control

Usage:
    python scripts/debug_query.py
    python scripts/debug_query.py --question "your question here"
    python scripts/debug_query.py --export  # Exports results to JSON

Author: YamieBot Team
Last Updated: February 2026
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging
from src.config import get_config
from src.query.retriever import Retriever
from src.query.models import QueryRequest
import structlog

logger = structlog.get_logger(__name__)


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subheader(title: str):
    """Print a formatted subheader."""
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print("─" * 80)


def debug_query(question: str, export: bool = False) -> dict:
    """
    Run a query with full debug output.
    
    Args:
        question: The question to ask
        export: If True, returns data for JSON export
        
    Returns:
        Dictionary with all debug information
    """
    config = get_config()
    
    print_header("🔍 YAMIEBOT DEBUG QUERY")
    print(f"\n📝 Question: {question}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    # Initialize retriever
    print_subheader("1. RETRIEVER INITIALIZATION")
    
    retriever = Retriever()
    stats = retriever.get_stats()
    
    print(f"\n  Index: {config.pinecone_index_name}")
    print(f"  Active Namespaces: {stats.get('active_namespaces', [])}")
    print(f"  Multi-namespace Mode: {stats.get('multi_namespace_mode', False)}")
    print(f"  Total Vectors: {stats.get('total_vectors', 0)}")
    print(f"  Namespace Vectors: {stats.get('namespace_vectors', {})}")
    
    # Run retrieval
    print_subheader("2. RETRIEVAL")
    
    request = QueryRequest(
        question=question,
        top_k=config.query_top_k,
    )
    
    print(f"\n  Top-K: {request.top_k}")
    print(f"  Similarity Threshold: {config.query_similarity_threshold}")
    
    chunks = retriever.retrieve(request)
    
    print(f"\n  ✅ Retrieved {len(chunks)} chunks")
    
    # Display each chunk in detail
    print_subheader("3. RETRIEVED CHUNKS (FULL DETAIL)")
    
    chunks_data = []
    
    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'━' * 80}")
        print(f"  CHUNK {i}/{len(chunks)}")
        print(f"{'━' * 80}")
        
        # Source info
        print(f"\n  📁 SOURCE PATH:")
        print(f"     {chunk.source}")
        
        # Metadata
        print(f"\n  📋 METADATA:")
        print(f"     Namespace: {chunk.metadata.get('namespace', 'N/A')}")
        print(f"     Source Type: {chunk.metadata.get('source_type', 'N/A')}")
        print(f"     Page Title: {chunk.metadata.get('page_title', 'N/A')}")
        print(f"     Category: {chunk.category}")
        
        # Score
        print(f"\n  📊 SIMILARITY SCORE: {chunk.similarity_score:.4f}")
        
        # Full text
        print(f"\n  📄 FULL CHUNK TEXT ({len(chunk.text)} chars):")
        print(f"  {'─' * 76}")
        # Indent each line of the text
        for line in chunk.text.split('\n'):
            print(f"     {line}")
        print(f"  {'─' * 76}")
        
        # Collect for export
        chunks_data.append({
            "rank": i,
            "source_path": chunk.source,
            "similarity_score": chunk.similarity_score,
            "category": chunk.category,
            "text": chunk.text,
            "text_length": len(chunk.text),
            "metadata": {
                "namespace": chunk.metadata.get('namespace'),
                "source_type": chunk.metadata.get('source_type'),
                "page_title": chunk.metadata.get('page_title'),
                "page_id": chunk.metadata.get('page_id'),
                "page_url": chunk.metadata.get('page_url'),
            }
        })
    
    # Show what would be sent to LLM
    print_subheader("4. CONTEXT FOR LLM")
    
    context_text = "\n\n---\n\n".join([
        f"[Source: {c.source}]\n{c.text}" 
        for c in chunks
    ])
    
    print(f"\n  Total context length: {len(context_text)} characters")
    print(f"  Estimated tokens: ~{len(context_text.split()) * 1.3:.0f}")
    
    print(f"\n  📝 CONTEXT PREVIEW (first 1500 chars):")
    print(f"  {'─' * 76}")
    preview = context_text[:1500]
    for line in preview.split('\n'):
        print(f"     {line}")
    if len(context_text) > 1500:
        print(f"     ... [{len(context_text) - 1500} more characters]")
    print(f"  {'─' * 76}")
    
    # Summary
    print_subheader("5. SUMMARY")
    
    unique_sources = list(set(c.source for c in chunks))
    avg_score = sum(c.similarity_score for c in chunks) / len(chunks) if chunks else 0
    
    print(f"\n  Total Chunks: {len(chunks)}")
    print(f"  Unique Sources: {len(unique_sources)}")
    print(f"  Average Similarity: {avg_score:.4f}")
    print(f"  Score Range: {min(c.similarity_score for c in chunks):.4f} - {max(c.similarity_score for c in chunks):.4f}")
    
    print(f"\n  📁 Sources Used:")
    for src in unique_sources:
        print(f"     • {src}")
    
    # Build export data
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "config": {
            "index": config.pinecone_index_name,
            "namespaces": stats.get('active_namespaces', []),
            "top_k": request.top_k,
            "similarity_threshold": config.query_similarity_threshold,
            "embedding_model": config.embedding_model,
        },
        "results": {
            "chunks_retrieved": len(chunks),
            "unique_sources": len(unique_sources),
            "average_similarity": avg_score,
            "sources": unique_sources,
        },
        "chunks": chunks_data,
        "context_for_llm": {
            "total_chars": len(context_text),
            "estimated_tokens": int(len(context_text.split()) * 1.3),
            "text": context_text,
        }
    }
    
    return export_data


def run_interactive():
    """Run in interactive mode."""
    
    print_header("🔍 YAMIEBOT DEBUG QUERY - INTERACTIVE MODE")
    print("\nType your questions to see full debug output.")
    print("Commands:")
    print("  'quit' or 'q' - Exit")
    print("  'export' - Export last query to JSON")
    print()
    
    last_export_data = None
    
    while True:
        try:
            question = input("\n💬 Question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['quit', 'q', 'exit']:
                print("\n👋 Goodbye!")
                break
            
            if question.lower() == 'export':
                if last_export_data:
                    filename = f"debug_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(last_export_data, f, indent=2, ensure_ascii=False)
                    print(f"\n✅ Exported to {filename}")
                else:
                    print("\n⚠️ No query to export yet. Ask a question first.")
                continue
            
            last_export_data = debug_query(question)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Debug query tool - shows all retrieval details",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--question", "-q",
        help="Question to debug (skips interactive mode)"
    )
    
    parser.add_argument(
        "--export", "-e",
        action="store_true",
        help="Export results to JSON file"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output filename for export (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Setup logging (minimal for cleaner output)
    setup_logging(log_level="WARNING", log_file="logs/debug_query.log")
    
    if args.question:
        # Single question mode
        export_data = debug_query(args.question, export=args.export)
        
        if args.export:
            filename = args.output or f"debug_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Exported to {filename}")
    else:
        # Interactive mode
        run_interactive()


if __name__ == "__main__":
    main()