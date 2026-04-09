"""
Test the new YamieAgent end-to-end against real Pinecone data.

Run from project root:
    python scripts/test_agent.py

Tests a mix of question types:
- Factual lookups (menu, allergens)
- Name/person lookups (known to fail with pure vector)
- Address/location lookups
- Procedure questions
- Greetings (should NOT trigger a search)
- Out-of-scope (bot should admit it doesn't know)
- Follow-up (multi-turn)
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent import YamieAgent
from src.config import get_config

QUESTIONS = [
    # (label, question, user_id)
    ("greeting",       "Hoi! Wie ben jij?",                                        "test_user_1"),
    ("name_lookup",    "Wie is Daoud?",                                             "test_user_2"),
    ("procedure",      "Wat is de procedure bij ziekteverzuim?",                    "test_user_3"),
    ("allergens",      "Welke allergenen zitten er in de pasta carbonara?",         "test_user_4"),
    ("address",        "Wat is het adres van Flamin'wok Utrecht?",                  "test_user_5"),
    ("out_of_scope",   "Wat is het weer morgen in Amsterdam?",                      "test_user_6"),
    # Multi-turn: send two questions with the same user_id
    ("followup_q1",    "Wat zijn de openingstijden van Yamie Pastabar Amsterdam?",  "test_user_7"),
    ("followup_q2",    "En op zondag?",                                             "test_user_7"),  # follow-up
]

SEPARATOR = "-" * 70


def run():
    print(f"\n{'='*70}")
    print("  YamieAgent — End-to-End Test")
    print(f"{'='*70}\n")

    print("Initializing agent (connects to Pinecone + Redis)...")
    try:
        agent = YamieAgent(config=get_config())
        print("Agent initialized.\n")
    except Exception as e:
        print(f"FAILED to initialize agent: {e}")
        sys.exit(1)

    for label, question, user_id in QUESTIONS:
        print(SEPARATOR)
        print(f"[{label.upper()}] user_id={user_id}")
        print(f"Question: {question}")
        print()

        start = time.time()
        try:
            response = agent.query(question=question, user_id=user_id)
            elapsed = time.time() - start

            print(f"Answer ({elapsed:.1f}s):")
            print(f"  {response.answer}")
            print()
            print(f"  has_answer:      {response.has_answer}")
            print(f"  chunks used:     {len(response.sources)}")
            print(f"  chunks filtered: {len(response.filtered_chunks)}")

            if response.sources:
                print(f"  sources:")
                seen = set()
                for c in response.sources:
                    if c.source not in seen:
                        print(f"    - {c.source} (score: {c.similarity_score:.3f})")
                        seen.add(c.source)

        except Exception as e:
            print(f"ERROR: {e}")

        print()

    print(SEPARATOR)
    print("Test complete.")
    print()


if __name__ == "__main__":
    run()
