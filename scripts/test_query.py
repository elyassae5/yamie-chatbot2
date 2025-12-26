"""
Quick test script for the query engine.
Tests basic functionality with a simple question.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.query import QueryEngine


def main():
    print("\n" + "="*80)
    print("🧪 YamieBot Query Engine - Quick Test")
    print("="*80 + "\n")
    
    # Initialize engine
    try:
        engine = QueryEngine()
    except Exception as e:
        print(f"❌ Failed to initialize engine: {e}")
        return
    
    # Test question
    question = "Welke wijnen hebben jullie?"
    
    print(f"\n🔍 Testing question: '{question}'\n")
    
    try:
        response = engine.query(question)
        
        # Display result
        print(response)  # Uses our __str__ method from QueryResponse
        
    except Exception as e:
        print(f"❌ Error during query: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()