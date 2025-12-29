"""
Quick test script for the query engine.
Tests basic functionality with interactive or preset questions.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging
from src.query import QueryEngine
import logging

logger = logging.getLogger(__name__)


def main():
    """Run query engine tests with proper logging."""
    
    # Set up logging
    setup_logging(
        level="INFO",  # Change to "DEBUG" for detailed logs
        log_to_file=True,
        log_dir="logs",
    )
    
    logger.info("="*80)
    logger.info("YAMIEBOT QUERY ENGINE - QUICK TEST")
    logger.info("="*80)
    
    # Initialize engine
    try:
        engine = QueryEngine()
    except Exception as e:
        logger.error(f"Failed to initialize engine: {e}", exc_info=True)
        return
    
    # Ask user: preset question or interactive?
    print("\n" + "="*80)
    print("Choose test mode:")
    print("  1. Preset question (quick test)")
    print("  2. Interactive mode (ask your own questions)")
    print("="*80)
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "2":
        run_interactive_mode(engine)
    else:
        run_preset_test(engine)


def run_preset_test(engine: QueryEngine):
    """Run a single preset test question."""
    
    # Test question (you can change this)
    question = "Wie is Daoud en wat doet hij?"
    
    logger.info(f"Testing with preset question: '{question}'")
    
    try:
        response = engine.query(question)
        
        # Display result using the QueryResponse __str__ method
        print("\n" + "="*80)
        print("RESULT")
        print("="*80)
        print(response)
        
        # Optional: Show chunk details (uncomment if needed)
        # _display_chunk_details(response)
        
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)


def run_interactive_mode(engine: QueryEngine):
    """Run in interactive mode - user can ask multiple questions."""
    
    logger.info("Starting interactive mode")
    
    print("\n" + "="*80)
    print("INTERACTIVE MODE")
    print("="*80)
    print("Ask questions to test the chatbot.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'debug' to toggle chunk details.")
    print("="*80 + "\n")
    
    show_chunks = False
    
    while True:
        try:
            # Get question from user
            question = input("\n💬 Your question: ").strip()
            
            if not question:
                continue
            
            # Check for commands
            if question.lower() in ['quit', 'exit', 'q']:
                logger.info("User exited interactive mode")
                break
            
            if question.lower() == 'debug':
                show_chunks = not show_chunks
                status = "enabled" if show_chunks else "disabled"
                print(f"\n✓ Chunk details {status}")
                continue
            
            # Process question
            logger.info(f"User question: '{question}'")
            
            response = engine.query(question)
            
            # Display result
            print("\n" + "="*80)
            print("RESULT")
            print("="*80)
            print(response)
            
            # Optionally show chunk details
            if show_chunks:
                _display_chunk_details(response)
            
        except KeyboardInterrupt:
            logger.info("User interrupted with Ctrl+C")
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing question: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")


def _display_chunk_details(response):
    """Display detailed information about retrieved chunks."""
    
    print("\n" + "="*80)
    print("🔍 RETRIEVED CHUNKS (DEBUG)")
    print("="*80)
    
    if not response.sources:
        print("\n⚠️ NO CHUNKS RETRIEVED!")
        return
    
    for i, chunk in enumerate(response.sources, 1):
        print(f"\n--- Chunk {i}/{len(response.sources)} ---")
        print(f"Source: {chunk.source}")
        print(f"Category: {chunk.category}")
        print(f"Similarity Score: {chunk.similarity_score:.4f}")
        print(f"\nText Preview (first 400 chars):")
        preview = chunk.text[:400]
        if len(chunk.text) > 400:
            preview += "..."
        print(preview)
        
        # Ask if user wants to see full text
        if len(chunk.text) > 400:
            show_full = input(f"\nShow full text for chunk {i}? (y/n): ").strip().lower()
            if show_full == 'y':
                print(f"\nFull Text ({len(chunk.text)} chars):")
                print(chunk.text)
        
        print("-" * 80)


if __name__ == "__main__":
    main()