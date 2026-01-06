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
import structlog

logger = structlog.get_logger(__name__)


def main():
    """Run query engine tests with proper logging."""
    
    # Set up logging (FIXED: Updated parameters)
    setup_logging(
        log_level="INFO",  # Change to "DEBUG" for detailed logs
        log_file="logs/test_query.log"  # Optional: specify log file path
    )
    
    logger.info("test_started", script="test_query.py")
    logger.info("separator", message="="*80)
    logger.info("test_title", title="YAMIEBOT QUERY ENGINE - QUICK TEST")
    logger.info("separator", message="="*80)
    
    # Initialize engine
    try:
        from src.query import QueryEngine
        engine = QueryEngine()
    except Exception as e:
        logger.error(
            "engine_initialization_failed",
            error=str(e),
            error_type=type(e).__name__
        )
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


def run_preset_test(engine):
    """Run a single preset test question."""
    
    # Test question (you can change this)
    question = "Wie is Daoud en wat doet hij?"
    user_id = "test_user"  # User ID for conversation memory
    
    logger.info(
        "preset_test_started",
        question=question,
        user_id=user_id
    )
    
    try:
        response = engine.query(question, user_id=user_id)
        
        # Display result using the QueryResponse __str__ method
        print("\n" + "="*80)
        print("RESULT")
        print("="*80)
        print(response)
        
        logger.info(
            "preset_test_completed",
            has_answer=response.has_answer,
            response_time=response.response_time_seconds
        )
        
        # Optional: Show chunk details (uncomment if needed)
        # _display_chunk_details(response)
        
    except Exception as e:
        logger.error(
            "preset_test_failed",
            error=str(e),
            error_type=type(e).__name__
        )


def run_interactive_mode(engine):
    """Run in interactive mode - user can ask multiple questions."""
    
    logger.info("interactive_mode_started")
    
    print("\n" + "="*80)
    print("INTERACTIVE MODE")
    print("="*80)
    print("Ask questions to test the chatbot.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'debug' to toggle chunk details.")
    print("Type 'reset' to clear conversation memory.")
    print("="*80 + "\n")
    
    show_chunks = False
    user_id = "test_user"  # User ID for conversation memory
    
    while True:
        try:
            # Get question from user
            question = input("\n💬 Your question: ").strip()
            
            if not question:
                continue
            
            # Check for commands
            if question.lower() in ['quit', 'exit', 'q']:
                logger.info("interactive_mode_exited", reason="user_command")
                break
            
            if question.lower() == 'debug':
                show_chunks = not show_chunks
                status = "enabled" if show_chunks else "disabled"
                print(f"\n✓ Chunk details {status}")
                logger.info("debug_mode_toggled", status=status)
                continue
            
            if question.lower() == 'reset':
                # Clear conversation memory
                if hasattr(engine, 'memory') and engine.memory:
                    engine.memory.clear_conversation(user_id)
                    print(f"\n✓ Conversation memory cleared!")
                    logger.info("conversation_memory_cleared", user_id=user_id)
                else:
                    print(f"\n⚠️ Memory not available")
                    logger.warning("memory_not_available")
                continue
            
            # Process question
            logger.info("user_question", question=question, user_id=user_id)
            
            response = engine.query(question, user_id=user_id)
            
            # Display result
            print("\n" + "="*80)
            print("RESULT")
            print("="*80)
            print(response)
            
            logger.info(
                "query_result",
                has_answer=response.has_answer,
                response_time=response.response_time_seconds,
                sources_count=len(response.sources)
            )
            
            # Optionally show chunk details
            if show_chunks:
                _display_chunk_details(response)
            
        except KeyboardInterrupt:
            logger.info("interactive_mode_interrupted", reason="ctrl_c")
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(
                "query_error",
                error=str(e),
                error_type=type(e).__name__
            )
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