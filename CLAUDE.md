# YamieBot — AI Knowledge Assistant for Dutch Restaurant Group

## What This Is

RAG chatbot for Yamie Pastabar, Flamin'wok, and Smokey Joe's. Staff ask questions via WhatsApp, answers come from the company's Notion knowledge base. Built for non-technical restaurant owners (my uncle is co-owner).

## How I Work — Read This First

- I'm building this as a serious production project. Everything must be solid, not hacked together.
- **Step by step only.** Never give me 10 things to implement at once. One step, I confirm it works, then the next. If I'm confused at step 3, everything after is useless.
- **Be completely honest.** If something in the codebase is bad or there's a better way, say it directly. Be my most experienced, capable, and honest dev buddy.
- **Explain the "why"** before the "what." I want to understand what we're doing and why, not just blindly paste code.
- I work on Windows 11 with Git Bash in VS Code. Terminal commands should use Git Bash syntax.
- At the end of each session: update this CLAUDE.md and create like new session log with date of today and session order incase we ahve multiple sessions a day `docs/session-log......md` with what we did.

## Tech Stack

- **Backend**: FastAPI (port 8000 chatbot, port 8001 admin)
- **Frontend**: React 18 + Vite + TypeScript (admin dashboard)
- **RAG**: LlamaIndex → Pinecone (yamie-knowledge index, 5 namespaces) → GPT-4o-mini
- **Embeddings**: text-embedding-3-large (3072d)
- **Memory**: Redis Cloud (30 min TTL, 4 turns)
- **Logging**: Supabase (query_logs, sync_logs, whitelisted_numbers)
- **WhatsApp**: Twilio sandbox (not yet Business API)
- **Hosting**: Railway (backends), Vercel (frontend)

## Architecture

```
WhatsApp → Twilio → FastAPI → QueryEngine → Pinecone + GPT-4o-mini → Answer
Notion → SyncService → Chunker → Embeddings → Pinecone (deterministic IDs)
Admin Dashboard → FastAPI admin backend → Supabase
```

## Key Conventions

- All user-facing text is **Dutch**
- Vector IDs are deterministic: `{notion_page_id}::chunk::{index:04d}`
- Commit messages: `fix:`, `feat:`, `cleanup:` prefixes
- Never deploy destructive operations without dry-run mode + safety checks
- Always pin dependencies to exact versions
- Dev environment: Windows 11, Git Bash, VS Code

## Pinecone Namespaces (5 total, ~551 vectors)

- `operations-department` — SOPs, reports, franchise procedures
- `yamie-pastabar` — 17 locations, embedded PDFs
- `flaminwok` — 10 locations, embedded PDFs
- `smokey-joes` — 3 locations (low content)
- `officiele-documenten` — menus, allergen lists, handbook

## RAG Config

- chunk_size: 1000, overlap: 200
- similarity_threshold: 0.35
- top_k: 15 (all 5 namespaces searched simultaneously)
- llm_max_tokens: 800, temperature: 0.3

## Current State (last updated: March 14, 2026)

### What's Working

- Chatbot live on Railway, admin dashboard on Vercel
- Incremental sync from Notion → Pinecone via admin dashboard "Sync Nu" button
- Deterministic vector IDs across all namespaces
- Security hardened: CORS locked, JWT fails hard, errors don't leak, deps pinned

### What's Broken / Needs Fixing

- **CRITICAL: Orphan detection DISABLED** — wiped all vectors due to ID format mismatch between `_get_pinecone_page_ids()` and `enumerate_pages()`. Code exists in `src/ingestion/sync_service.py` but is commented out. Needs: debug ID formats, add safety check (abort if >50% orphans), add dry-run mode.
- **Re-ingestion in progress** — force_full sync running to restore ~551 vectors
- **Supabase RLS disabled on `sync_logs`** — other tables (whitelisted_numbers, query_logs, admin_users) have RLS enabled. sync_logs still needs proper policies.
- **Admin credentials hardcoded** — username/password in code, must move to env vars

### Not Yet Done

- 15-question evaluation set created but never run
- Re-ranker integration (Cohere Rerank) — top RAG quality priority
- Hybrid search (vector + BM25) — fixes name lookups like "Wie is Daoud?"
- Query debug view in admin dashboard
- WhatsApp Business API (still on Twilio sandbox)

## File Structure Quick Reference

- `src/ingestion/sync_service.py` — Incremental sync engine (orphan detection here)
- `src/ingestion/notion_loader.py` — Notion API loader, enumerate_pages(), load_single_page()
- `src/query/engine.py` — Main RAG pipeline orchestrator
- `src/query/retriever.py` — Multi-namespace Pinecone retriever
- `src/config.py` — All RAG settings
- `admin_dashboard/backend/routes/sync.py` — Sync API endpoints
- `admin_dashboard/frontend/src/pages/SyncPage.tsx` — Sync UI

## References

- `docs/backlog.md` — Full prioritized backlog
- `docs/session-log.md` — Session history (what was done when)
