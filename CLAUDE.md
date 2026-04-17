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
- system_prompt: v3.1 (src/agent/system_prompt.py)

## System Prompt (v3.1)
- Bot identifies as YamieBot, internal assistant of the Yamie-groep
- Friendly but professional tone (je/jij)
- Answers capped at 200 words (WhatsApp-friendly)
- Claude-controlled search: tool description in Dutch guides when/how to search
- Handles greetings without searching
- Never fabricates info, never mixes unrelated chunks
- No markdown double asterisks (WhatsApp uses single asterisks)
- No source references in answers (tracked in admin dashboard)
- When PDF form fields are unreadable: says specifically what it can't see, refers to Notion
- When asked for files/links: "Het originele document staat in Notion — vraag je manager" (not "ik kan geen bestanden delen")

## Current State (last updated: April 10, 2026, Session 1)

### What's Working
- **Agentic RAG live on Railway** — Claude Sonnet 4.6 controls retrieval via tool use
- **Multiple tool_use blocks handled** — Claude can return parallel searches in one response, all are executed correctly
- Multi-search: Claude searches multiple times with refined queries when needed
- Follow-up handling: native via Anthropic message history (Redis turns → messages array)
- Greetings: no Pinecone search triggered
- Chatbot + admin dashboard live (Railway + Vercel)
- **Admin dashboard chat** — full YamieBot chat in the browser, JWT protected, memory isolated per admin
- Incremental sync from Notion → Pinecone via admin dashboard "Sync Nu" button
- Orphan detection with 50% safety threshold
- Deterministic vector IDs
- Query debug view in admin dashboard — "Bronnen & context" panel
- WhatsApp formatting: markdown converted, source refs stripped, friendly truncation
- "Momentje... ⏳" acknowledgment
- All debug data saved to Supabase for every query (WhatsApp + API — not admin chat)
- API key auth on /api/query and /api/stats
- Swagger/ReDoc disabled in production
- Shared YamieAgent singleton via backend/engine.py
- Database-level sync lock, Postgres RPC for stats, search input sanitization
- Security hardened: CORS locked, JWT fails hard, errors don't leak, deps pinned
- Supabase RLS enabled on all 5 tables
- **Mobile UI** — hamburger drawer nav, no overflow anywhere, bold rendering in chat

### Known Issues / Limitations
- **Twilio sandbox expires every 72h** — users must rejoin with "join let-were". Fix: Phase 8 (WhatsApp Business API)
- **Name lookups fail** (e.g. "Wie is Daoud?") — pure vector search has no keyword matching. Fix: hybrid search (Phase 5)
- **PDF form fields invisible** — pypdf reads text layer only, AcroForm checkbox values not captured. Fix: Tally → Notion pipeline
- **Latency varies** — 7-20s typical, occasional spikes. Acceptable for WhatsApp (async). Monitor in production.
- **OpenAI credits** — still needed for embeddings. Keep topped up.

### Not Yet Done (in priority order)
1. **Evaluation pipeline** — 25-30 real Q&A pairs with scoring baseline. Prerequisite for measuring all future improvements.
2. **Hybrid search / BM25** — fixes name/address exact-match lookups
3. **Notion cleanup** — prerequisite for form automation work
4. **Google Forms → Sheets → n8n → Notion** — existing forms, no migration needed (link to Sheet, n8n writes to Notion)
5. **Tally migration** — for new forms. $29/month Pro, native Notion integration. Go/No-Go form is best pilot. See `docs/tally-n8n-migration.md`
6. **n8n automations** — GO/NO-GO WhatsApp alert, NO-GO task creation, HACCP reminder, weekly summary
7. Embedding model research (text-embedding-3-large is ~18 months old)
8. Markdown-aware chunking
9. Admin chat Supabase logging (decide: log or not log)
10. Auto-onboarding WhatsApp message when adding a number
11. WhatsApp Business API (Phase 8)
12. Scheduled auto-sync

## File Structure Quick Reference
- `src/config.py` — All settings (model, top_k, threshold, ANTHROPIC_API_KEY, etc.)
- `src/agent/agent.py` — YamieAgent: the agentic loop (main entry point)
- `src/agent/tools.py` — KnowledgeBaseSearcher + SEARCH_KNOWLEDGE_BASE_TOOL schema
- `src/agent/system_prompt.py` — Bot personality and rules (v3.1)
- `src/agent/models.py` — QueryRequest/QueryResponse (stable contract for all downstream)
- `src/ingestion/sync_service.py` — Incremental sync engine + orphan detection
- `src/ingestion/notion_loader.py` — Notion API loader, enumerate_pages(), load_single_page()
- `src/memory/conversation_memory.py` — Redis-backed conversation history
- `backend/engine.py` — Shared YamieAgent singleton (imported by all routes)
- `backend/routes/webhook.py` — WhatsApp webhook (formatting, truncation, debug logging)
- `backend/routes/query.py` — API query endpoint (API key auth, debug data saved to Supabase)
- `admin_dashboard/backend/routes/auth.py` — Login endpoint
- `admin_dashboard/backend/routes/chat.py` — Dashboard chat endpoint (JWT, no Supabase logging)
- `admin_dashboard/backend/routes/sync.py` — Sync API endpoints
- `admin_dashboard/backend/routes/whitelist.py` — Whitelist CRUD
- `admin_dashboard/frontend/src/components/Layout.tsx` — Nav (hamburger drawer on mobile)
- `admin_dashboard/frontend/src/pages/ChatPage.tsx` — Dashboard chat UI
- `admin_dashboard/frontend/src/pages/LogsPage.tsx` — Query logs + debug view
- `admin_dashboard/frontend/src/pages/DashboardPage.tsx` — Dashboard
- `admin_dashboard/frontend/src/pages/WhitelistPage.tsx` — Whitelist management
- `admin_dashboard/frontend/src/pages/SyncPage.tsx` — Sync UI
- `scripts/test_agent.py` — End-to-end agent test against real Pinecone (run with python -X utf8)
- `scripts/system_status.py` — Full system health check
- `scripts/inspect_redis.py` — Debug Redis conversations
- `scripts/run_notion_ingestion.py` — Manual full re-ingest pipeline

## References
- `docs/master-plan.md` — Phase-by-phase roadmap
- `docs/backlog.md` — Full prioritized backlog
- `docs/tally-n8n-migration.md` — Full Dutch explanation of Tally + n8n workflow (for owners)
- `docs/sessions/` — Individual session logs (YYYY-MM-DD-session-N.md)
- `docs/codebase-review-2026-04-04.md` — Deep codebase analysis (pre-agentic refactor)
- `README.md` — Full project documentation
