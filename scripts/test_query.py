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
    question = "What is the maximum weight limit for employees when lifting heavy boxes in the storage room?"
    
    print(f"\n🔍 Testing question: '{question}'\n")
    
    try:
        response = engine.query(question)
        
        # Display result
        print(response)  # Uses our __str__ method from QueryResponse

        """
         # 🔍 DEBUG: Show retrieved chunks
        print("\n" + "="*80)
        print("🔍 DEBUG: RETRIEVED CHUNKS")
        print("="*80)
        
        if response.sources:
            for i, chunk in enumerate(response.sources, 1):
                print(f"\n--- Chunk {i} ---")
                print(f"Source: {chunk.source}")
                print(f"Category: {chunk.category}")
                print(f"Similarity Score: {chunk.similarity_score:.4f}")
                print(f"\nText Preview (first 300 chars):")
                print(chunk.text[:300])
                print(f"\nFull Text:")
                print(chunk.text)
                print("-" * 80)
        else:
            print("\n⚠️ NO CHUNKS RETRIEVED!")
            print("This means the retrieval step failed completely.")
        """  
    except Exception as e:
        print(f"❌ Error during query: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()