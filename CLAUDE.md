# YamieBot — AI Knowledge Assistant for Dutch Restaurant Group

## What This Is
RAG chatbot for Yamie Pastabar, Flamin'wok, and Smokey Joe's. Staff ask questions via WhatsApp, answers come from the company's Notion knowledge base. Built for non-technical restaurant owners (my uncle is co-owner).

## How I Work — Read This First
- I'm building this as a serious production project. Everything must be solid, not hacked together.
- **Step by step only.** Never give me 10 things to implement at once. One step, I confirm it works, then the next. If I'm confused at step 3, everything after is useless.
- **Be completely honest.** If something in the codebase is bad or there's a better way, say it directly. Be my most experienced, capable, and honest dev buddy.
- **Explain the "why"** before the "what." I want to understand what we're doing and why, not just blindly paste code.
- I work on Windows 11 with Git Bash in VS Code. Terminal commands should use Git Bash syntax.
- At the end of each session: update this CLAUDE.md and create a new session log with today's date and session order (in case of multiple sessions per day) in `docs/`.
- The GitHub codebase is the source of truth. Session summaries and docs capture where we left off.

## Tech Stack
- **Backend**: FastAPI (port 8000 chatbot, port 8001 admin)
- **Frontend**: React 18 + Vite + TypeScript (admin dashboard)
- **RAG**: LlamaIndex → Pinecone (yamie-knowledge index, 5 namespaces) → GPT-4o
- **Embeddings**: text-embedding-3-large (3072d)
- **Memory**: Redis Cloud (30 min TTL, 4 turns)
- **Logging**: Supabase (query_logs, sync_logs, whitelisted_numbers, admin_users)
- **WhatsApp**: Twilio sandbox (not yet Business API — expires every 72h, rejoin with "join let-were")
- **Hosting**: Railway (both backends), Vercel (frontend)

## Architecture
```
WhatsApp → Twilio → FastAPI → QueryEngine → Pinecone + GPT-4o → Answer
Notion → SyncService → Chunker → Embeddings → Pinecone (deterministic IDs)
Admin Dashboard → FastAPI admin backend → Supabase
```

## Key Conventions
- All user-facing text is **Dutch**
- Bot never mentions "documentfragmenten", "fragmenten" or "kennisbank" to users — they know about documents but not about the technical RAG process
- Vector IDs are deterministic: `{notion_page_id}::chunk::{index:04d}`
- Commit messages: `fix:`, `feat:`, `cleanup:` prefixes
- Never deploy destructive operations without dry-run mode + safety checks
- Always pin dependencies to exact versions
- Dev environment: Windows 11, Git Bash, VS Code

## Pinecone Namespaces (5 total, ~551 vectors)
- `operations-department` (~78) — SOPs, reports, franchise procedures
- `yamie-pastabar` (~294) — 17 locations, embedded PDFs
- `flaminwok` (~151) — 10 locations, embedded PDFs
- `smokey-joes` (~10) — 3 locations (low content)
- `officiele-documenten` (~18) — menus, allergen lists, handbook

## RAG Config
- chunk_size: 1000, overlap: 200
- similarity_threshold: 0.35
- top_k: 10 (all 5 namespaces searched simultaneously)
- llm_model: gpt-4o
- llm_max_tokens: 500, temperature: 0.3

## System Prompt (v2.1)
- Bot identifies as YamieBot, internal assistant of the Yamie-groep
- Friendly but professional tone (je/jij)
- Answers capped at 200 words (WhatsApp-friendly)
- Handles greetings without document search
- Never fabricates info, never mixes unrelated document chunks
- No markdown double asterisks (WhatsApp uses single)
- No source references in answers (tracked in admin dashboard)
- Strict follow-up vs new topic classification in question transformation

## Current State (last updated: March 17, 2026)

### What's Working
- Chatbot live on Railway with GPT-4o, admin dashboard on Vercel
- Incremental sync from Notion → Pinecone via admin dashboard "Sync Nu" button
- Orphan detection with 50% safety threshold — tested end-to-end (add page → sync → delete page → sync → orphan cleaned)
- Deterministic vector IDs (no more LlamaIndex ref_doc_id prefix bug)
- Query debug view in admin dashboard — "Bronnen & context" panel with expandable full chunk text, Dutch labels
- WhatsApp formatting: markdown converted, source refs stripped, friendly truncation
- "Momentje... ⏳" acknowledgment instead of "🤔 Denken..."
- Question transformation with strict new topic vs follow-up classification
- All debug data saved to Supabase for every query (passed + filtered chunks)
- Security hardened: CORS locked, JWT fails hard, errors don't leak, deps pinned
- Supabase RLS enabled on all tables

### Known Issues / Limitations
- **Twilio sandbox expires every 72h** — users must rejoin with "join let-were". Fix: Phase 7 (WhatsApp Business API)
- **Greetings give same response** — GPT-4o sometimes repetitive despite "varieer" instruction. Minor issue.
- **Follow-up context** — "is er nog meer?" type questions re-search Pinecone and can pull unrelated chunks. System prompt has cross-document safety rule but re-ranker would properly fix this.
- **Admin credentials hardcoded** — username/password in code, must move to env vars
- **OpenAI credits** — if balance hits $0 the bot stops responding entirely. Keep credits topped up.

### Not Yet Done
- 15-question evaluation set created but never fully run
- Re-ranker integration (Cohere Rerank) — top RAG quality priority
- Hybrid search (vector + BM25) — fixes name lookups like "Wie is Daoud?"
- System prompt viewer in admin dashboard
- WhatsApp Business API (Phase 7)
- Scheduled auto-sync

## File Structure Quick Reference
- `src/config.py` — All RAG settings (model, top_k, threshold, etc.)
- `src/query/system_prompt.py` — Bot personality and rules (v2.1)
- `src/query/engine.py` — Main RAG pipeline + question transformation
- `src/query/retriever.py` — Multi-namespace Pinecone retriever
- `src/query/responder.py` — LLM answer generation with retry
- `src/ingestion/sync_service.py` — Incremental sync engine + orphan detection
- `src/ingestion/notion_loader.py` — Notion API loader, enumerate_pages(), load_single_page()
- `backend/routes/webhook.py` — WhatsApp webhook (formatting, truncation, debug logging)
- `backend/routes/query.py` — API query endpoint (debug data saved to Supabase)
- `admin_dashboard/backend/routes/sync.py` — Sync API endpoints
- `admin_dashboard/frontend/src/pages/LogsPage.tsx` — Query logs + debug view
- `admin_dashboard/frontend/src/pages/SyncPage.tsx` — Sync UI

## References
- `docs/backlog.md` — Full prioritized backlog
- `docs/session-log.md` — Session history (what was done when)
- `README.md` — Full project documentation