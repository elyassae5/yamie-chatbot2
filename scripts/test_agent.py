"""
Test the new YamieAgent end-to-end against real Pinecone + Notion data.

Run from project root:
    python -X utf8 scripts/test_agent.py
    python -X utf8 scripts/test_agent.py --forms-only   # forms tool only
    python -X utf8 scripts/test_agent.py --kb-only      # KB tool only

Tests a mix of question types:
- KB (search_knowledge_base): factual / name / address / procedure / greetings
- FORMS (query_forms_data): counts, rankings, lists, severity filters
- HYBRID: questions Claude should split between both tools
- Multi-turn follow-up
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.agent import YamieAgent
from src.config import get_config

# (label, question, user_id, group)
# group values: 'kb' (knowledge base only), 'forms' (forms tool only),
#               'hybrid' (likely both), 'meta' (greeting/out-of-scope)
QUESTIONS = [
    # KB-only
    ("greeting",       "Hoi! Wie ben jij?",                                        "test_user_1", "meta"),
    ("name_lookup",    "Wie is Daoud?",                                             "test_user_2", "kb"),
    ("procedure",      "Wat is de procedure bij ziekteverzuim?",                    "test_user_3", "kb"),
    ("allergens",      "Welke allergenen zitten er in de pasta carbonara?",         "test_user_4", "kb"),
    ("address",        "Wat is het adres van Flamin'wok Utrecht?",                  "test_user_5", "kb"),
    ("out_of_scope",   "Wat is het weer morgen in Amsterdam?",                      "test_user_6", "meta"),

    # FORMS-only
    ("forms_count_all",
        "Hoeveel formulier-inzendingen zijn er ingediend in de afgelopen 30 dagen?",
        "test_user_8", "forms"),
    ("forms_brand_kritiek",
        "Hoeveel kritieke bevindingen had Yamie in totaal?",
        "test_user_9", "forms"),
    ("forms_score",
        "Welke vestiging scoort het slechtst op basis van de inzendingen?",
        "test_user_10", "forms"),
    ("forms_recent_voorbezoek",
        "Laat me de 3 laatste voorbezoeken zien.",
        "test_user_11", "forms"),

    # HYBRID — Claude should ideally pick BOTH tools in the same turn
    ("hybrid_sop_plus_data",
        "Wat zegt het beleid over hygiene-controles, en welke vestigingen hebben "
        "daar problemen mee gehad?",
        "test_user_12", "hybrid"),

    # Multi-turn: same user_id across two questions
    ("followup_q1",    "Wat zijn de openingstijden van Yamie Pastabar Amsterdam?",  "test_user_7", "kb"),
    ("followup_q2",    "En op zondag?",                                             "test_user_7", "kb"),
]

SEPARATOR = "-" * 70


def _filter_questions(argv: list[str]) -> list[tuple]:
    """Optional CLI flags to scope which test groups run."""
    if "--forms-only" in argv:
        return [q for q in QUESTIONS if q[3] == "forms"]
    if "--kb-only" in argv:
        return [q for q in QUESTIONS if q[3] in ("kb", "meta")]
    if "--hybrid-only" in argv:
        return [q for q in QUESTIONS if q[3] == "hybrid"]
    if "--smoke" in argv:
        # Minimum-viable smoke: one of each kind.
        wanted = {"greeting", "name_lookup", "forms_count_all", "hybrid_sop_plus_data"}
        return [q for q in QUESTIONS if q[0] in wanted]
    return QUESTIONS


def run():
    print(f"\n{'='*70}")
    print("  YamieAgent — End-to-End Test (KB + Forms tools)")
    print(f"{'='*70}\n")

    questions = _filter_questions(sys.argv)
    print(f"Running {len(questions)} question(s).")
    print()

    print("Initializing agent (connects to Pinecone + Redis + Notion)...")
    try:
        agent = YamieAgent(config=get_config())
        print("Agent initialized.\n")
    except Exception as e:
        print(f"FAILED to initialize agent: {e}")
        sys.exit(1)

    summary: list[dict] = []

    for label, question, user_id, group in questions:
        print(SEPARATOR)
        print(f"[{label.upper()}] group={group} user_id={user_id}")
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

            summary.append({
                "label": label,
                "group": group,
                "elapsed_s": round(elapsed, 1),
                "chunks": len(response.sources),
                "has_answer": response.has_answer,
                "ok": True,
            })

        except Exception as e:
            print(f"ERROR: {e}")
            summary.append({
                "label": label,
                "group": group,
                "elapsed_s": round(time.time() - start, 1),
                "chunks": 0,
                "has_answer": False,
                "ok": False,
                "error": str(e),
            })

        print()

    print(SEPARATOR)
    print("Summary")
    print(SEPARATOR)
    for s in summary:
        status = "OK " if s["ok"] else "ERR"
        chunks = f"{s['chunks']:>3}"
        print(
            f"  {status}  [{s['group']:<6}] {s['label']:<28}  "
            f"{s['elapsed_s']:>5.1f}s  chunks={chunks}  has_answer={s['has_answer']}"
        )
    print()
    print("Test complete.")
    print()


if __name__ == "__main__":
    run()
