#!/usr/bin/env python3
"""
YamieBot System Status - Full health check for the production system.

Shows:
- API key status
- Pinecone index + all namespace vector counts
- Redis connection + memory stats
- Supabase connection + log count
- Notion API connection
- Current RAG configuration

Usage:
    python scripts/system_status.py
"""

import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging
setup_logging(log_level="WARNING")  # Suppress JSON logs for clean output

from src.config import get_config
from src.ingestion.notion_pipeline import NOTION_SOURCES


def section(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def ok(label: str, value: str = ""):
    print(f"  ✅  {label}{f'  →  {value}' if value else ''}")


def warn(label: str, value: str = ""):
    print(f"  ⚠️   {label}{f'  →  {value}' if value else ''}")


def err(label: str, value: str = ""):
    print(f"  ❌  {label}{f'  →  {value}' if value else ''}")


def info(label: str, value: str = ""):
    print(f"  ℹ️   {label}{f':  {value}' if value else ''}")


# ─────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────
def check_api_keys(config):
    section("🔐  API KEYS")
    keys = {
        "OpenAI":         config.openai_api_key,
        "Pinecone":       config.pinecone_api_key,
        "Redis":          config.redis_password,
        "Supabase URL":   config.supabase_url,
        "Supabase Key":   config.supabase_service_role_key,
    }
    all_ok = True
    for name, value in keys.items():
        if value:
            ok(name)
        else:
            err(name, "MISSING — add to .env")
            all_ok = False

    # Notion (optional, only needed for ingestion)
    if config.notion_api_key:
        ok("Notion API Key")
    else:
        warn("Notion API Key", "not set — only needed for ingestion")

    return all_ok


# ─────────────────────────────────────────────
# PINECONE
# ─────────────────────────────────────────────
def check_pinecone(config):
    section("📦  PINECONE — yamie-knowledge")
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=config.pinecone_api_key)
        index = pc.Index(config.pinecone_index_name)
        stats = index.describe_index_stats()

        total = stats.get("total_vector_count", 0)
        namespaces = stats.get("namespaces", {})
        dimension = stats.get("dimension", "?")

        ok(f"Connected to index '{config.pinecone_index_name}'")
        info("Dimension", str(dimension))
        info("Total vectors", str(total))

        print()
        print(f"  {'Namespace':<30} {'Vectors':>8}  Status")
        print(f"  {'─'*30} {'─'*8}  {'─'*10}")

        for source_key, source in NOTION_SOURCES.items():
            ns = source.namespace
            count = namespaces.get(ns, {}).get("vector_count", 0)
            status = "✅ OK" if count > 50 else ("⚠️  LOW" if count > 0 else "❌ EMPTY")
            print(f"  {ns:<30} {count:>8}  {status}")

        # Check for namespaces in Pinecone not in our registry
        registered = {s.namespace for s in NOTION_SOURCES.values()}
        for ns, ns_stats in namespaces.items():
            if ns not in registered:
                count = ns_stats.get("vector_count", 0)
                print(f"  {ns:<30} {count:>8}  ⚠️  UNKNOWN (not in registry)")

        print()
        info("Last checked", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
        return True

    except Exception as e:
        err("Could not connect to Pinecone", str(e))
        return False


# ─────────────────────────────────────────────
# REDIS
# ─────────────────────────────────────────────
def check_redis(config):
    section("🔴  REDIS — Conversation Memory")
    try:
        import redis
        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password,
            socket_connect_timeout=5,
            decode_responses=True,
        )
        r.ping()

        info_data = r.info()
        used_memory = info_data.get("used_memory_human", "?")
        connected_clients = info_data.get("connected_clients", "?")

        # Count conversation keys
        conv_keys = len(r.keys("conversation:*"))

        ok(f"Connected  →  {config.redis_host}:{config.redis_port}")
        info("Memory used", used_memory)
        info("Connected clients", str(connected_clients))
        info("Active conversations", str(conv_keys))
        info("TTL per session", f"{config.conversation_ttl_seconds // 60} min")
        info("Max turns kept", str(config.max_conversation_turns))
        return True

    except Exception as e:
        err("Could not connect to Redis", str(e))
        return False


# ─────────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────────
def check_supabase(config):
    section("🗄️   SUPABASE — Logging & Whitelist")
    try:
        from supabase import create_client
        client = create_client(config.supabase_url, config.supabase_service_role_key)

        # Query logs count
        logs_res = client.table("query_logs").select("*", count="exact").limit(1).execute()
        log_count = logs_res.count if hasattr(logs_res, "count") else "?"

        # Query whitelist
        wl_res = client.table("whitelisted_numbers").select("*").execute()
        wl_active = sum(1 for e in wl_res.data if e.get("is_active"))
        wl_total = len(wl_res.data)

        ok(f"Connected  →  {config.supabase_url[:40]}...")
        info("Total query logs", str(log_count))
        info("Whitelisted numbers", f"{wl_active} active / {wl_total} total")

        print()
        if wl_res.data:
            print(f"  {'Name':<20} {'Number':<25} Status")
            print(f"  {'─'*20} {'─'*25} {'─'*8}")
            for entry in wl_res.data:
                status = "✅ Actief" if entry.get("is_active") else "⏸  Inactief"
                number = entry.get("phone_number", "").replace("whatsapp:", "")
                print(f"  {entry.get('name','?'):<20} {number:<25} {status}")

        return True

    except Exception as e:
        err("Could not connect to Supabase", str(e))
        return False


# ─────────────────────────────────────────────
# NOTION
# ─────────────────────────────────────────────
def check_notion(config):
    section("📝  NOTION — Knowledge Sources")
    if not config.notion_api_key:
        warn("Notion API key not set — skipping connection test")
        warn("Only needed when running ingestion, not for the chatbot")
        return True

    try:
        import requests
        headers = {
            "Authorization": f"Bearer {config.notion_api_key.strip()}",
            "Notion-Version": "2022-06-01",
            "Content-Type": "application/json",
        }
        # Use a known page ID from the registry to verify the token works
        first_source = next(iter(NOTION_SOURCES.values()))
        res = requests.get(
            f"https://api.notion.com/v1/pages/{first_source.page_id}",
            headers=headers,
            timeout=5,
        )

        if res.status_code == 200:
            ok("Connected — integration token valid")
        elif res.status_code == 403:
            warn("Token valid but page not shared with integration — check Notion permissions")
        else:
            warn(f"Could not verify token (HTTP {res.status_code}) — may still work for ingestion")

        # Show all registered sources
        print()
        print(f"  {'Source Key':<28} {'Namespace':<28} Page ID")
        print(f"  {'─'*28} {'─'*28} {'─'*12}")
        for key, source in NOTION_SOURCES.items():
            print(f"  {key:<28} {source.namespace:<28} {source.page_id[:8]}...")

        return True  # Non-blocking — ingestion handles its own auth

    except Exception as e:
        err("Could not reach Notion API", str(e))
        return False


# ─────────────────────────────────────────────
# RAG CONFIG
# ─────────────────────────────────────────────
def show_rag_config(config):
    section("⚙️   RAG CONFIGURATION")
    print()
    print(f"  {'Setting':<30} Value")
    print(f"  {'─'*30} {'─'*20}")

    rows = [
        ("LLM model",           config.llm_model),
        ("LLM temperature",     str(config.llm_temperature)),
        ("LLM max tokens",      str(config.llm_max_tokens)),
        ("Embedding model",     config.embedding_model),
        ("Embedding dimensions",str(config.embedding_dimensions)),
        ("Chunk size",          str(config.chunk_size)),
        ("Chunk overlap",       str(config.chunk_overlap)),
        ("Query top-k",         str(config.query_top_k)),
        ("Similarity threshold",str(config.query_similarity_threshold)),
    ]
    for label, value in rows:
        print(f"  {label:<30} {value}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + "  🤖  YAMIEBOT SYSTEM STATUS".center(58) + "║")
    print("║" + datetime.utcnow().strftime("  %Y-%m-%d %H:%M UTC").ljust(58) + "║")
    print("╚" + "═" * 58 + "╝")

    try:
        config = get_config()
    except ValueError as e:
        print(f"\n❌ Config error: {e}")
        sys.exit(1)

    results = {}
    results["api_keys"]  = check_api_keys(config)
    results["pinecone"]  = check_pinecone(config)
    results["redis"]     = check_redis(config)
    results["supabase"]  = check_supabase(config)
    results["notion"]    = check_notion(config)
    show_rag_config(config)

    # Summary
    section("📋  SUMMARY")
    all_ok = True
    checks = {
        "API Keys":  results["api_keys"],
        "Pinecone":  results["pinecone"],
        "Redis":     results["redis"],
        "Supabase":  results["supabase"],
        "Notion":    results["notion"],
    }
    for name, passed in checks.items():
        if passed:
            ok(name)
        else:
            err(name)
            all_ok = False

    print()
    if all_ok:
        print("  🟢  All systems operational. Ready to ingest or query.")
    else:
        print("  🔴  Some checks failed. Fix the issues above before proceeding.")

    print()


if __name__ == "__main__":
    main()