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
    
    from src.query.retriever import create_multi_namespace_retriever
    retriever = create_multi_namespace_retriever(
        namespaces=[
            "operations-department",
            "yamie-pastabar",
            "flaminwok",
            "smokey-joes",
            "officiele-documenten",
        ],
        config=config
    )
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
    
    # Retriever returns ALL top_k chunks (no threshold filtering)
    # Threshold filtering happens in the query engine before sending to LLM
    all_chunks = retriever.retrieve(request)
    
    # Split into passed vs filtered using the configured threshold
    threshold = config.query_similarity_threshold
    passed_chunks = [c for c in all_chunks if c.similarity_score >= threshold]
    filtered_chunks = [c for c in all_chunks if c.similarity_score < threshold]
    
    print(f"\n  Top-K: {request.top_k}")
    print(f"  Similarity Threshold: {threshold}")
    print(f"\n  ✅ Retrieved {len(all_chunks)} total chunks")
    print(f"     ├── {len(passed_chunks)} passed threshold (→ sent to LLM)")
    print(f"     └── {len(filtered_chunks)} below threshold (→ filtered out)")
    
    # Display each chunk in detail
    print_subheader("3. RETRIEVED CHUNKS — PASSED THRESHOLD (sent to LLM)")
    
    chunks_data = []
    
    def display_chunk(chunk, index, total, label=""):
        """Display a single chunk with full detail."""
        print(f"\n{'━' * 80}")
        print(f"  {label}CHUNK {index}/{total}")
        print(f"{'━' * 80}")
        
        print(f"\n  📁 SOURCE PATH:")
        print(f"     {chunk.source}")
        
        print(f"\n  📋 METADATA:")
        print(f"     Namespace: {chunk.metadata.get('namespace', 'N/A')}")
        print(f"     Source Type: {chunk.metadata.get('source_type', 'N/A')}")
        print(f"     Page Title: {chunk.metadata.get('page_title', 'N/A')}")
        print(f"     Category: {chunk.category}")
        
        print(f"\n  📊 SIMILARITY SCORE: {chunk.similarity_score:.4f}")
        
        print(f"\n  📄 FULL CHUNK TEXT ({len(chunk.text)} chars):")
        print(f"  {'─' * 76}")
        for line in chunk.text.split('\n'):
            print(f"     {line}")
        print(f"  {'─' * 76}")
    
    if passed_chunks:
        for i, chunk in enumerate(passed_chunks, 1):
            display_chunk(chunk, i, len(passed_chunks), "✅ ")
            chunks_data.append({
                "rank": i,
                "source_path": chunk.source,
                "similarity_score": chunk.similarity_score,
                "category": chunk.category,
                "text": chunk.text,
                "text_length": len(chunk.text),
                "passed_threshold": True,
                "metadata": {
                    "namespace": chunk.metadata.get('namespace'),
                    "source_type": chunk.metadata.get('source_type'),
                    "page_title": chunk.metadata.get('page_title'),
                    "page_id": chunk.metadata.get('page_id'),
                    "page_url": chunk.metadata.get('page_url'),
                }
            })
    else:
        print(f"\n  ⚠️ No chunks passed the similarity threshold ({threshold})")
    
    # Show filtered chunks
    print_subheader(f"4. FILTERED CHUNKS — BELOW THRESHOLD < {threshold} (NOT sent to LLM)")
    
    if filtered_chunks:
        for i, chunk in enumerate(filtered_chunks, 1):
            display_chunk(chunk, i, len(filtered_chunks), "❌ ")
            chunks_data.append({
                "rank": len(passed_chunks) + i,
                "source_path": chunk.source,
                "similarity_score": chunk.similarity_score,
                "category": chunk.category,
                "text": chunk.text,
                "text_length": len(chunk.text),
                "passed_threshold": False,
                "metadata": {
                    "namespace": chunk.metadata.get('namespace'),
                    "source_type": chunk.metadata.get('source_type'),
                    "page_title": chunk.metadata.get('page_title'),
                    "page_id": chunk.metadata.get('page_id'),
                    "page_url": chunk.metadata.get('page_url'),
                }
            })
    else:
        print(f"\n  ✅ All chunks passed the threshold — nothing filtered out")
    
    # Show what would be sent to LLM
    print_subheader("5. CONTEXT FOR LLM")
    
    context_text = "\n\n---\n\n".join([
        f"[Source: {c.source}]\n{c.text}" 
        for c in passed_chunks
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
    print_subheader("6. SUMMARY")
    
    passed_sources = list(set(c.source for c in passed_chunks))
    all_sources = list(set(c.source for c in all_chunks))
    avg_passed = sum(c.similarity_score for c in passed_chunks) / len(passed_chunks) if passed_chunks else 0
    avg_all = sum(c.similarity_score for c in all_chunks) / len(all_chunks) if all_chunks else 0
    
    print(f"\n  Total Retrieved: {len(all_chunks)}")
    print(f"  Passed Threshold: {len(passed_chunks)}")
    print(f"  Filtered Out: {len(filtered_chunks)}")
    print(f"  Threshold: {threshold}")
    print(f"  Avg Score (passed): {avg_passed:.4f}")
    print(f"  Avg Score (all): {avg_all:.4f}")
    if all_chunks:
        print(f"  Score Range (all): {min(c.similarity_score for c in all_chunks):.4f} - {max(c.similarity_score for c in all_chunks):.4f}")
    
    if passed_sources:
        print(f"\n  📁 Sources Sent to LLM:")
        for src in passed_sources:
            print(f"     • {src}")
    else:
        print(f"\n  ⚠️ No chunks passed threshold ({threshold}) — LLM received no context")
    
    # Build export data
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "config": {
            "index": config.pinecone_index_name,
            "namespaces": stats.get('active_namespaces', []),
            "top_k": request.top_k,
            "similarity_threshold": threshold,
            "embedding_model": config.embedding_model,
        },
        "results": {
            "total_retrieved": len(all_chunks),
            "passed_threshold": len(passed_chunks),
            "filtered_out": len(filtered_chunks),
            "sources_sent_to_llm": passed_sources,
            "all_sources": all_sources,
            "avg_score_passed": avg_passed,
            "avg_score_all": avg_all,
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