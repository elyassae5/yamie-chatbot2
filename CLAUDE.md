# YamieBot — AI Knowledge Assistant for Dutch Restaurant Group

## What This Is
RAG chatbot for Yamie Pastabar, Flamin'wok, and Smokey Joe's. Staff ask questions via WhatsApp, answers come from the company's Notion knowledge base. Built for non-technical restaurant owners (my uncle is co-owner).

## How I Work — Read This First
- I'm building this as a serious production project. Everything must be solid, not hacked together.
- **Step by step only.** Never give me 10 things to implement at once. One step, I confirm it works, then the next. If I'm confused at step 3, everything after is useless.
- **Be completely honest.** If something in the codebase is bad or there's a better way, say it directly. Be my most experienced, capable, and honest dev buddy.
- **Explain the "why"** before the "what." I want to understand what we're doing and why, not just blindly paste code.
- **Always research before recommending** — use WebSearch to find the current best-in-class tech. Knowledge cutoff is not an excuse. April 2026 moves fast.
- **No fear of big refactors.** Quality > cost/time/effort. Everything is on the table.
- I work on Windows 11 with Git Bash in VS Code. Terminal commands should use Git Bash syntax.
- At the end of each session: update this CLAUDE.md and create a new session log with today's date and session order (in case of multiple sessions per day) in `docs/sessions/`.
- The GitHub codebase is the source of truth. Session summaries and docs capture where we left off.

## Tech Stack
- **Backend**: FastAPI (port 8000 chatbot, port 8001 admin)
- **Frontend**: React 18 + Vite + TypeScript (admin dashboard)
- **Agent**: Claude Sonnet 4.6 via Anthropic SDK (`anthropic==0.92.0`) — agentic RAG loop
- **Embeddings**: OpenAI text-embedding-3-large (3072d) — must match Pinecone index, cannot change without full re-ingest
- **Vector DB**: Pinecone (`yamie-knowledge` index, 5 namespaces) — direct SDK calls, no LlamaIndex in query path
- **Memory**: Redis Cloud (30 min TTL, 5 turns) — stores conversation as turns, passed as native Anthropic messages array
- **Logging**: Supabase (query_logs, sync_logs, whitelisted_numbers, admin_users, sync_lock)
- **Ingestion**: LlamaIndex (used ONLY for Notion → Pinecone sync — not in the query/agent path)
- **WhatsApp**: Twilio sandbox (not yet Business API — expires every 72h, rejoin with "join let-were")
- **Hosting**: Railway (both backends), Vercel (frontend)

## Architecture
```
WhatsApp → Twilio → FastAPI → YamieAgent (agentic loop)
                                 ↓ tool use
                              Pinecone (direct SDK) ← OpenAI embeddings
                                 ↑ results
                              Claude Sonnet 4.6 → Answer

Notion → SyncService (LlamaIndex) → Chunker → Embeddings → Pinecone (deterministic IDs)
Admin Dashboard → FastAPI admin backend → Supabase
```

## Agentic RAG — How It Works
Classical RAG (old): hardcoded pipeline — embed → Pinecone → filter → LLM → answer.

Agentic RAG (current): Claude is in control.
1. Claude receives question + conversation history (as native Anthropic messages)
2. Claude decides whether to call `search_knowledge_base` tool (skips for greetings/smalltalk)
3. If it searches: Pinecone returns top chunks, Claude reads them
4. Claude may search again with refined terms if first result is weak
5. Claude generates the final answer grounded in what the tool returned
6. Only the final Q→A pair is saved to Redis (not intermediate tool calls)

Key improvements over classical:
- Follow-up questions resolved natively via message history (no separate GPT-4o-mini transform step)
- Claude can search multiple times with different queries per question
- No search for greetings/smalltalk (Claude decides)
- Namespace targeting: Claude picks the right namespace for the question

## Key Conventions
- All user-facing text is **Dutch**
- Bot never mentions "zoektool", "fragmenten", "kennisbank", "namespace" to users
- Vector IDs are deterministic: `{notion_page_id}::chunk::{index:04d}`
- Commit messages: `fix:`, `feat:`, `cleanup:` prefixes
- Never deploy destructive operations without dry-run mode + safety checks
- Always pin dependencies to exact versions
- Dev environment: Windows 11, Git Bash, VS Code
- Run test script: `python -X utf8 scripts/test_agent.py`

## Pinecone Namespaces (5 total, ~551 vectors)
- `operations-department` (~78) — SOPs, reports, franchise procedures
- `yamie-pastabar` (~294) — 17 locations, embedded PDFs
- `flaminwok` (~151) — 10 locations, embedded PDFs
- `smokey-joes` (~10) — 3 locations (low content)
- `officiele-documenten` (~18) — menus, allergen lists, handbook

## Agent Config
- similarity_threshold: 0.35
- top_k: 10 per namespace (Claude decides which namespaces to search)
- max_tool_calls: 5 per query (safety ceiling)
- llm_model: claude-sonnet-4-6 (constant in src/agent/agent.py)
- llm_max_tokens: 1500 (covers tool_use blocks + answer)
- llm_temperature: 0.3
- system_prompt: v3.0 (src/agent/system_prompt.py)

## System Prompt (v3.0)
- Bot identifies as YamieBot, internal assistant of the Yamie-groep
- Friendly but professional tone (je/jij)
- Answers capped at 200 words (WhatsApp-friendly)
- Claude-controlled search: tool description in Dutch guides when/how to search
- Handles greetings without searching
- Never fabricates info, never mixes unrelated chunks
- No markdown double asterisks (WhatsApp uses single)
- No source references in answers (tracked in admin dashboard)

## Current State (last updated: April 9, 2026, Session 1)

### What's Working
- **Agentic RAG live on Railway** — Claude Sonnet 4.6 controls retrieval via tool use
- Multi-search: Claude searches multiple times with refined queries when needed
- Follow-up handling: native via Anthropic message history (Redis turns → messages array)
- Greetings: no Pinecone search triggered
- Chatbot + admin dashboard live (Railway + Vercel)
- Incremental sync from Notion → Pinecone via admin dashboard "Sync Nu" button
- Orphan detection with 50% safety threshold
- Deterministic vector IDs
- Query debug view in admin dashboard — "Bronnen & context" panel
- WhatsApp formatting: markdown converted, source refs stripped, friendly truncation
- "Momentje... ⏳" acknowledgment
- All debug data saved to Supabase for every query
- API key auth on /api/query and /api/stats
- Swagger/ReDoc disabled in production
- Shared YamieAgent singleton via backend/engine.py
- Database-level sync lock, Postgres RPC for stats, search input sanitization
- Security hardened: CORS locked, JWT fails hard, errors don't leak, deps pinned
- Supabase RLS enabled on all 5 tables

### Known Issues / Limitations
- **Twilio sandbox expires every 72h** — users must rejoin with "join let-were". Fix: Phase 8 (WhatsApp Business API)
- **Name lookups fail** (e.g. "Wie is Daoud?") — pure vector search has no keyword matching. Fix: hybrid search (Phase 5 of master plan)
- **Latency varies** — 7-20s typical, occasional spikes to 50s (Claude API). Acceptable for WhatsApp (async processing). Monitor in production.
- **OpenAI credits** — still needed for embeddings. If balance hits $0, bot stops. Keep topped up.
- **src/query/ still in codebase** — kept as fallback until new agent is confirmed stable. Delete after 1-2 weeks of clean production.

### Not Yet Done (in priority order)
- Evaluation pipeline (Phase 0 of master plan) — 25-30 real Q&A pairs with scoring baseline. Prerequisite for measuring all future improvements.
- Hybrid search / BM25 (Phase 5) — fixes name/address exact-match lookups. High priority.
- Embedding model research — current: text-embedding-3-large (OpenAI). Newer options (Voyage AI, etc.) may be better but require full Pinecone re-ingest.
- Markdown-aware chunking (Phase 2) — header-aware splitting for Notion pages
- Re-ranker (Phase 1 of old plan — partially addressed by agentic multi-search, but a cross-encoder would still help)
- Dashboard chat feature
- Auto-onboarding WhatsApp message when adding a number
- Notion structure review with uncle (Phase 6)
- **Embedded forms gap** — Notion pages have embedded Google Forms PDFs, invisible to bot. Migrating to Tally (better for n8n automations). Not yet done.
- Form triggers / workflow automation (Tally → n8n)
- System prompt viewer in admin dashboard
- WhatsApp Business API (Phase 8)
- Scheduled auto-sync
- Delete src/query/ once agentic agent is confirmed stable in production

## File Structure Quick Reference
- `src/config.py` — All settings (model, top_k, threshold, ANTHROPIC_API_KEY, etc.)
- `src/agent/agent.py` — YamieAgent: the agentic loop (main entry point)
- `src/agent/tools.py` — KnowledgeBaseSearcher + SEARCH_KNOWLEDGE_BASE_TOOL schema
- `src/agent/system_prompt.py` — Bot personality and rules (v3.0)
- `src/agent/models.py` — QueryRequest/QueryResponse (stable contract for all downstream)
- `src/ingestion/sync_service.py` — Incremental sync engine + orphan detection
- `src/ingestion/notion_loader.py` — Notion API loader, enumerate_pages(), load_single_page()
- `src/memory/conversation_memory.py` — Redis-backed conversation history
- `backend/engine.py` — Shared YamieAgent singleton (imported by all routes)
- `backend/routes/webhook.py` — WhatsApp webhook (formatting, truncation, debug logging)
- `backend/routes/query.py` — API query endpoint (API key auth, debug data saved to Supabase)
- `admin_dashboard/backend/routes/auth.py` — Login endpoint
- `admin_dashboard/backend/routes/sync.py` — Sync API endpoints
- `admin_dashboard/backend/routes/whitelist.py` — Whitelist CRUD
- `admin_dashboard/frontend/src/pages/LogsPage.tsx` — Query logs + debug view
- `admin_dashboard/frontend/src/pages/DashboardPage.tsx` — Dashboard
- `admin_dashboard/frontend/src/pages/WhitelistPage.tsx` — Whitelist management
- `admin_dashboard/frontend/src/pages/SyncPage.tsx` — Sync UI
- `scripts/test_agent.py` — End-to-end agent test against real Pinecone (run with python -X utf8)

## References
- `docs/master-plan.md` — Phase-by-phase roadmap (phases renumbered — see current state above for updated priority order)
- `docs/backlog.md` — Full prioritized backlog
- `docs/sessions/` — Individual session logs (YYYY-MM-DD-session-N.md)
- `docs/codebase-review-2026-04-04.md` — Deep codebase analysis (pre-agentic refactor)
- `README.md` — Full project documentation
