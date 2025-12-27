"""
🧪 YamieBot Test Suite - Batch Question Testing

This script runs multiple test questions and shows the results.
You manually verify if answers are correct by checking against documents.

Features:
- Run 20 questions in batch
- See all answers clearly
- Results saved to file for review
- Add/edit questions easily

Usage:
    python scripts/test_suite.py
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.query import QueryEngine


# Test Questions - Add/edit as needed
TEST_QUESTIONS = [
    # === MENU QUESTIONS ===
    {
        "id": 1,
        "category": "menu",
        "question": "Welke pasta's hebben jullie?",
        "notes": "Should list pasta dishes"
    },
    {
        "id": 2,
        "category": "menu",
        "question": "Welke wijnen hebben jullie?",
        "notes": "Should list wines if in menu"
    },
    {
        "id": 3,
        "category": "menu",
        "question": "What are the pasta prices?",
        "notes": "Should mention prices in English"
    },
    {
        "id": 4,
        "category": "menu",
        "question": "Hoeveel kost de Carbonara?",
        "notes": "Specific dish price"
    },
    
    # === HR POLICY QUESTIONS ===
    {
        "id": 5,
        "category": "hr",
        "question": "How many sick days do I have?",
        "notes": "Should answer from HR policy"
    },
    {
        "id": 6,
        "category": "hr",
        "question": "Wat is het vakantiebeleid?",
        "notes": "Vacation policy in Dutch"
    },
    {
        "id": 7,
        "category": "hr",
        "question": "What's the employee dress code?",
        "notes": "Dress code policy"
    },
    {
        "id": 8,
        "category": "hr",
        "question": "Are schedules posted 2 weeks in advance?",
        "notes": "Work schedule policy"
    },
    
    # === SOP (OPERATIONS) QUESTIONS ===
    {
        "id": 9,
        "category": "sop",
        "question": "Hoe open ik de zaak in de ochtend?",
        "notes": "Opening procedure"
    },
    {
        "id": 10,
        "category": "sop",
        "question": "What's the closing procedure?",
        "notes": "Closing procedure"
    },
    {
        "id": 11,
        "category": "sop",
        "question": "Hoe bereid ik pasta?",
        "notes": "Pasta preparation SOP"
    },
    
    # === EQUIPMENT QUESTIONS ===
    {
        "id": 12,
        "category": "equipment",
        "question": "How do I clean the espresso machine?",
        "notes": "Equipment maintenance"
    },
    {
        "id": 13,
        "category": "equipment",
        "question": "Hoe onderhoud ik de oven?",
        "notes": "Oven maintenance"
    },
    
    # === EDGE CASES (Should say "don't know") ===
    {
        "id": 14,
        "category": "edge_case",
        "question": "What pizzas do you have?",
        "notes": "Pizza not in test data - should say 'don't know'"
    },
    {
        "id": 15,
        "category": "edge_case",
        "question": "Wat is het weer vandaag?",
        "notes": "Weather - completely unrelated"
    },
    
    # === VAGUE/GENERAL QUESTIONS ===
    {
        "id": 16,
        "category": "general",
        "question": "Wat staat er op de menukaart?",
        "notes": "General menu overview"
    },
    {
        "id": 17,
        "category": "general",
        "question": "What should I know as a new employee?",
        "notes": "General onboarding - may pull from multiple docs"
    },
    
    # === MULTI-PART QUESTIONS ===
    {
        "id": 18,
        "category": "multi",
        "question": "Welke pasta's hebben jullie en hoeveel kosten ze?",
        "notes": "Should answer both: dishes + prices"
    },
    {
        "id": 19,
        "category": "multi",
        "question": "What's the sick leave policy and how do I request time off?",
        "notes": "Two-part HR question"
    },
    
    # === SPECIFIC DETAILS ===
    {
        "id": 20,
        "category": "specific",
        "question": "How often should I clean the equipment?",
        "notes": "Specific maintenance schedule"
    },
]


def run_test_suite():
    """Run all test questions and display results"""
    
    print("\n" + "=" * 80)
    print("  🧪 YAMIEBOT TEST SUITE")
    print("=" * 80)
    print(f"\nRunning {len(TEST_QUESTIONS)} test questions...")
    print("You'll manually verify if answers are correct.\n")
    
    # Initialize engine
    try:
        print("Initializing query engine...")
        engine = QueryEngine()
    except Exception as e:
        print(f"❌ Failed to initialize engine: {e}")
        print("\nMake sure you've run ingestion first:")
        print("  python scripts/run_ingestion.py")
        return
    
    print("\n" + "=" * 80)
    print("  TEST RESULTS")
    print("=" * 80 + "\n")
    
    results = []
    
    for test in TEST_QUESTIONS:
        test_id = test["id"]
        question = test["question"]
        category = test["category"]
        notes = test.get("notes", "")
        
        print(f"\n{'─' * 80}")
        print(f"Test #{test_id} [{category.upper()}]")
        print(f"{'─' * 80}")
        print(f"Question: {question}")
        if notes:
            print(f"Notes: {notes}")
        
        try:
            # Run query
            response = engine.query(question)
            
            # Store result
            result = {
                "test_id": test_id,
                "category": category,
                "question": question,
                "answer": response.answer,
                "sources": response.get_source_names(),
                "response_time": response.response_time_seconds,
            }
            results.append(result)
            
            # Display answer (show first 400 chars)
            answer_preview = response.answer[:400]
            if len(response.answer) > 400:
                answer_preview += "..."
            
            print(f"\nAnswer:")
            print(f"{answer_preview}")
            print(f"\nSources: {', '.join(response.get_source_names())}")
            print(f"Response time: {response.response_time_seconds:.2f}s")
                
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            results.append({
                "test_id": test_id,
                "question": question,
                "error": str(e),
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("  📊 SUMMARY")
    print("=" * 80)
    
    print(f"\n  Total questions tested: {len(TEST_QUESTIONS)}")
    
    # Category breakdown
    print("\n  Questions by category:")
    categories = {}
    for result in results:
        cat = result.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items()):
        print(f"    {cat:15} {count}")
    
    # Average response time
    times = [r["response_time"] for r in results if "response_time" in r]
    if times:
        avg_time = sum(times) / len(times)
        print(f"\n  Average response time: {avg_time:.2f}s")
    
    
    print("\n  ✅ Review the answers above and check against your documents")
    print("     to verify accuracy.\n")
    
    print("=" * 80 + "\n")
    
    return results


def main():
    try:
        results = run_test_suite()
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
