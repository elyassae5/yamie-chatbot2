# YamieBot

An AI-powered internal knowledge assistant for a multi-brand Dutch restaurant group. Staff ask questions via WhatsApp and the bot answers from the company's Notion knowledge base using **agentic RAG** — Claude Sonnet 4.6 controls retrieval via tool use and can issue multiple refined searches per question.

**Brands supported:** Yamie Pastabar · Flamin'wok · Smokey Joe's

---

## Table of Contents

- [How It Works](#how-it-works)
- [Agentic RAG Architecture](#agentic-rag-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Knowledge Base (Pinecone)](#knowledge-base-pinecone)
- [Content Sync (Notion → Pinecone)](#content-sync-notion--pinecone)
- [Local Development Setup](#local-development-setup)
- [Running the Services](#running-the-services)
- [Utility Scripts](#utility-scripts)
- [Admin Dashboard](#admin-dashboard)
- [Environment Variables](#environment-variables)
- [Production Deployment](#production-deployment)
- [API Endpoints](#api-endpoints)
- [Configuration Reference](#configuration-reference)
- [System Prompt](#system-prompt)
- [Project Roadmap](#project-roadmap)

---

## How It Works

```
Staff (WhatsApp) → Twilio → FastAPI → YamieAgent (agentic loop)
                                        ↓
                              Claude Sonnet 4.6 (tool use)
                                        ↓ search_knowledge_base
                              Pinecone (direct SDK) ← OpenAI embeddings
                                        ↑ results
                              Claude writes final answer → back to user
```

1. A staff member sends a question via WhatsApp
2. Twilio forwards the message to the FastAPI webhook
3. The webhook verifies the Twilio signature and checks the phone number against a Supabase whitelist
4. A `Momentje... ⏳` acknowledgment is sent immediately to avoid Twilio's 15-second timeout
5. The question is processed in a FastAPI background task:
   - Conversation history is loaded from Redis and converted into a native Anthropic `messages` array
   - Claude Sonnet 4.6 receives the messages along with a `search_knowledge_base` tool
   - **Claude decides** whether to search. Greetings and smalltalk → no search. Factual questions → Claude picks the query string and target namespaces and calls the tool
   - The searcher embeds the query with OpenAI `text-embedding-3-large` (3072d), queries Pinecone namespaces, filters by similarity threshold (0.35), and returns chunks
   - Claude may issue a refined follow-up search in the same turn if the first result is weak
   - Claude writes the final answer grounded in what the tool returned
   - Only the final Q→A pair is saved to Redis (not intermediate tool calls)
6. The answer is formatted for WhatsApp (`**bold**` → `*bold*`, source refs stripped, truncated if needed) and sent back via the Twilio REST API
7. The full interaction — question, answer, every retrieved chunk with scores, config version — is logged to Supabase for debugging and future evaluation

---

## Agentic RAG Architecture

This version replaces the original classical RAG pipeline (hardcoded embed → retrieve → filter → GPT-4o → answer) with an agentic loop where **Claude controls retrieval**.

### Before (classical RAG, deprecated)

Every question went through the same pipeline: embed → query all 5 Pinecone namespaces × top 10 = 50 chunks → filter by threshold → inject history as a string → GPT-4o. Follow-ups required a separate GPT-4o-mini rewrite step. Greetings still triggered full retrieval.

### After (agentic RAG, current)

```python
while True:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        tools=[SEARCH_KNOWLEDGE_BASE_TOOL],
        messages=messages,
        system=ACTIVE_SYSTEM_PROMPT,
    )
    if response.stop_reason == "end_turn":
        break                                 # Claude answered — done
    if response.stop_reason == "tool_use":
        for block in tool_use_blocks:         # Claude can emit multiple in one turn
            results = searcher.search(**block.input)
            tool_results.append({"type": "tool_result", ...})
        messages += [assistant_turn, user_turn_with_results]
```

Key improvements over classical:

- **Follow-ups resolved natively** via Anthropic message history — no separate rewrite step
- **Multi-search in one turn** — Claude can refine its query and search again without extra code
- **No search for greetings** — Claude decides; the code doesn't know what a greeting is
- **Namespace targeting** — Claude picks which of the 5 namespaces to search based on the question
- **Cleaner tool-use primitive** — `stop_reason` branching is explicit and debuggable

**No agent framework** (LangGraph / LangChain) in the query path — the loop is ~50 lines of raw Anthropic SDK. LlamaIndex is still used, but only for ingestion.

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| **Agent LLM** | Anthropic Claude Sonnet 4.6 via `anthropic==0.92.0` | Tool-use driven answer generation |
| **Embeddings** | OpenAI `text-embedding-3-large` (3072d) | Query and chunk embedding (must match ingestion) |
| **Vector DB** | Pinecone (`yamie-knowledge`, 5 namespaces) | Semantic search, direct SDK calls |
| **Ingestion** | LlamaIndex (`NotionPageReader`, `SentenceSplitter`) | Notion → chunks → Pinecone (ingestion only) |
| **Conversation Memory** | Redis Cloud | Per-user history as native Anthropic messages (30 min TTL, 5 turns) |
| **Chatbot Backend** | FastAPI + Uvicorn (port 8000) | REST API, WhatsApp webhook, background tasks |
| **Admin Backend** | FastAPI + Uvicorn (port 8001) | Admin dashboard API, sync endpoints, dashboard chat |
| **Admin Frontend** | React 18 + Vite + TypeScript (port 5173) | Admin UI, mobile-first with hamburger drawer |
| **Logging & Auth** | Supabase + structlog | Query logs, sync logs, whitelist, admin users, RLS on all tables |
| **WhatsApp** | Twilio Sandbox (Business API pending) | Inbound webhook + outbound REST |
| **Hosting (Backends)** | Railway | Chatbot backend + admin backend |
| **Hosting (Frontend)** | Vercel | Admin dashboard UI |
| **Knowledge Source** | Notion | All company documents and content |

---

## Project Structure

```
yamie-chatbot2/
│
├── CLAUDE.md                         # Project context for Claude Code sessions
├── docs/
│   ├── master-plan.md                # Phase-by-phase improvement roadmap
│   ├── backlog.md                    # Prioritized backlog
│   ├── tally-n8n-migration.md        # Forms automation plan
│   ├── interview-prep.md             # (gitignored) personal interview notes
│   └── sessions/                     # Dated session logs (YYYY-MM-DD-session-N.md)
│
├── backend/                          # Chatbot FastAPI app (port 8000)
│   ├── main.py                       # App entry, CORS, rate limiter, lifespan
│   ├── engine.py                     # Shared YamieAgent singleton
│   └── routes/
│       ├── query.py                  # POST /api/query — API key auth, logs to Supabase
│       ├── health.py                 # GET /api/health + /api/stats
│       └── webhook.py                # POST /api/webhook/whatsapp — Twilio handler + background task
│
├── src/                              # Core system
│   ├── config.py                     # All settings (API keys, thresholds, LLM config)
│   ├── agent/                        # ← agentic RAG (current query path)
│   │   ├── agent.py                  # YamieAgent: the agentic loop
│   │   ├── tools.py                  # search_knowledge_base tool + KnowledgeBaseSearcher
│   │   ├── system_prompt.py          # v3.1 Dutch system prompt
│   │   └── models.py                 # QueryResponse / RetrievedChunk (stable contract)
│   ├── ingestion/                    # Notion → Pinecone (LlamaIndex used here)
│   │   ├── notion_loader.py          # Recursive Notion loader + embedded PDF extraction
│   │   ├── notion_pipeline.py        # Notion sources registry + pipeline
│   │   ├── sync_service.py           # Incremental sync + orphan detection (50% safety)
│   │   ├── chunker.py                # SentenceSplitter wrapper
│   │   └── vector_store.py           # Pinecone storage context
│   ├── memory/
│   │   └── conversation_memory.py    # Redis-backed per-user conversation history
│   ├── database/
│   │   └── supabase_client.py        # Query logging + whitelist + sync logging
│   └── logging_config.py             # structlog setup (JSON format)
│
├── admin_dashboard/
│   ├── backend/                      # Admin FastAPI app (port 8001)
│   │   ├── main.py
│   │   ├── config.py                 # JWT secret, CORS
│   │   ├── auth/jwt_handler.py       # JWT creation + verification
│   │   └── routes/
│   │       ├── auth.py               # POST /api/auth/login, GET /api/auth/me
│   │       ├── chat.py               # POST /api/chat — dashboard chat (same agent, JWT-protected)
│   │       ├── whitelist.py          # CRUD for whitelisted_numbers
│   │       ├── logs.py               # Paginated query logs with filters
│   │       ├── sync.py               # Trigger sync, view history
│   │       └── system.py             # Pinecone + Redis + config status
│   └── frontend/                     # React admin UI (port 5173)
│       └── src/
│           ├── App.tsx               # Routing + protected routes
│           ├── components/Layout.tsx # Nav (hamburger drawer on mobile)
│           ├── pages/
│           │   ├── LoginPage.tsx
│           │   ├── DashboardPage.tsx
│           │   ├── ChatPage.tsx      # Browser chat with the bot (bold rendering, suggested Qs)
│           │   ├── WhitelistPage.tsx
│           │   ├── LogsPage.tsx      # Query logs + "Bronnen & context" debug panel
│           │   ├── SyncPage.tsx
│           │   └── SystemPage.tsx
│           └── lib/
│               ├── api.ts
│               └── auth.ts
│
├── scripts/
│   ├── test_agent.py                 # End-to-end agent test (run with: python -X utf8 scripts/test_agent.py)
│   ├── system_status.py              # Full health check: Pinecone, Redis, Supabase
│   ├── inspect_redis.py              # View conversation memory
│   └── run_notion_ingestion.py       # Manual full re-ingest (fallback)
│
├── .env.example                      # Template for all required env vars
├── requirements.txt                  # Python deps — all pinned to exact versions
├── Procfile                          # Railway: uvicorn backend.main:app
└── README.md
```

---

## Knowledge Base (Pinecone)

**Index:** `yamie-knowledge`
**Total vectors:** ~551
**Dimensions:** 3072 (OpenAI `text-embedding-3-large`)
**Source:** Notion (company workspace)
**Vector ID format:** `{notion_page_id}::chunk::{index:04d}` (deterministic — enables incremental sync)

| Namespace | Vectors | Content |
|---|---|---|
| `yamie-pastabar` | ~294 | 17 city locations, embedded PDFs (visit reports, training, QA) |
| `flaminwok` | ~151 | 10 city locations, embedded PDFs |
| `operations-department` | ~78 | SOPs, weekly reports, franchise procedures |
| `officiele-documenten` | ~18 | Menu cards, allergen lists, recipe cards, franchise handbook |
| `smokey-joes` | ~10 | 3 locations (low content) |

**Retrieval model**: Claude picks target namespaces per question (or leaves blank to search all 5). The searcher embeds the query once, queries each selected namespace with `top_k` (default 10, max 10), merges, sorts by cosine similarity, and splits at threshold 0.35 into `passed` (to Claude) and `filtered` (kept for admin logging only).

### Deterministic Vector IDs

All vectors use `{notion_page_id}::chunk::{index:04d}`. This enables:
- **Targeted deletion** when a page changes (delete old chunks by ID, upsert new)
- **Incremental sync** without clearing entire namespaces
- **Orphan detection** — compare Pinecone page IDs against current Notion page IDs, delete vectors whose page no longer exists (aborts if >50% would be deleted — safety threshold)

---

## Content Sync (Notion → Pinecone)

The sync system keeps Pinecone aligned with Notion automatically. It detects changes, additions, and deletions.

### How It Works

1. **Enumerate** all pages in each Notion source tree (lightweight — IDs and `last_edited_time` only)
2. **Compare** `last_edited_time` against the last successful sync timestamp in Supabase `sync_logs`
3. **Re-ingest** only changed pages with deterministic vector IDs (delete old chunks by ID prefix, upsert new)
4. **Orphan detection** — diff Pinecone page IDs vs current Notion page IDs, delete orphans
5. **Safety threshold** — aborts orphan cleanup if >50% of vectors would be deleted
6. **Atomic lock** — Supabase `sync_lock` table (single-row, 30-min auto-expiry) prevents concurrent syncs

### Usage

**Via Admin Dashboard (recommended):**
Go to the Sync page → click **Sync Nu**. The dashboard shows history with per-source and per-page breakdowns.

**Via API:**
```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Incremental sync
curl -X POST http://localhost:8001/api/sync/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"force_full": false}'

# Full sync (recovery only — re-ingests everything)
curl -X POST http://localhost:8001/api/sync/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"force_full": true}'
```

---

## Local Development Setup

**Prerequisites:** Python 3.11+, Node.js 18+, Git Bash (Windows)

```bash
# 1. Clone
git clone <repo-url>
cd yamie-chatbot2

# 2. Venv (Git Bash on Windows)
python -m venv venv
source venv/Scripts/activate

# 3. Python deps
pip install -r requirements.txt

# 4. Env vars
cp .env.example .env
# Edit .env — see Environment Variables section

# 5. Frontend deps
cd admin_dashboard/frontend
npm install
cd ../..
```

---

## Running the Services

Three services for full local functionality:

**Terminal 1 — Chatbot backend (port 8000)**
```bash
source venv/Scripts/activate
uvicorn backend.main:app --reload --port 8000
# http://localhost:8000 | API docs: http://localhost:8000/docs
```

**Terminal 2 — Admin dashboard backend (port 8001)**
```bash
source venv/Scripts/activate
python -m admin_dashboard.backend.main
# http://localhost:8001 | API docs: http://localhost:8001/docs
```

**Terminal 3 — Admin dashboard frontend (port 5173)**
```bash
cd admin_dashboard/frontend
npm run dev
# http://localhost:5173
```

**Admin login credentials:** stored in Supabase `admin_users` table (bcrypt-hashed). Managed via DB, not hardcoded.

---

## Utility Scripts

```bash
# End-to-end agent test against real Pinecone + Redis
python -X utf8 scripts/test_agent.py

# Overall system health (Pinecone, Redis, Supabase)
python scripts/system_status.py

# Inspect conversation memory for a user
python scripts/inspect_redis.py

# Manual full re-ingest (fallback only — sync service is the normal path)
python scripts/run_notion_ingestion.py --all --clear
```

---

## Admin Dashboard

Deployed on Vercel (frontend) and Railway (backend). Mobile-first with hamburger drawer navigation.

**Live URL:** [yamie-chatbot2.vercel.app](https://yamie-chatbot2.vercel.app)

### Pages

| Page | Description |
|---|---|
| **Login** | JWT auth |
| **Dashboard** | Live stats: total queries, queries today |
| **Chat** | Full YamieBot chat in the browser — same agent as WhatsApp, JWT-protected, memory isolated per admin |
| **Telefoonnummers** | Whitelist CRUD (add/remove/activate/deactivate) |
| **Vragen Overzicht** | Query logs with search, filters, and **Bronnen & context** debug panel |
| **Sync** | Trigger Notion → Pinecone sync, view history with per-source/per-page breakdown |
| **Systeem** | Pinecone namespace vector counts, Redis status, live config |

### Query Debug View

Every WhatsApp and API query saves full retrieval data to Supabase. The detail modal shows:
- Chunks **used for the answer** (passed threshold) with similarity scores, source paths, full text
- Chunks **filtered out** (below threshold)
- The threshold and config version used

*Dashboard chat questions are intentionally not logged to Supabase — admin test queries shouldn't pollute stats.*

### Supabase Tables

| Table | Purpose | RLS |
|---|---|---|
| `whitelisted_numbers` | WhatsApp numbers allowed to use the bot | ✅ |
| `query_logs` | Full query history + chunk-level debug data | ✅ |
| `admin_users` | Dashboard credentials (bcrypt hashes) | ✅ |
| `sync_logs` | Content sync history | ✅ |
| `sync_lock` | Atomic sync lock (single-row, auto-expires) | ✅ |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Anthropic (agent LLM)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (embeddings only — cannot change without full re-ingest)
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=yamie-knowledge
PINECONE_NAMESPACE=operations-department

# Redis Cloud (conversation memory)
REDIS_HOST=...
REDIS_PORT=6379
REDIS_PASSWORD=...

# Supabase (query logs + whitelist + admin auth)
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Notion (ingestion + sync)
NOTION_API_KEY=ntn_...

# API Security
API_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=development   # Set "production" on Railway to disable Swagger

# Admin Dashboard
ADMIN_JWT_SECRET=<python -c "import secrets; print(secrets.token_hex(32))">
```

---

## Production Deployment

| Service | Host | URL |
|---|---|---|
| Chatbot Backend | Railway | `yamie-chatbot2-production.up.railway.app` |
| Admin Backend | Railway | `yamiebot-admin-backend-production.up.railway.app` |
| Admin Frontend | Vercel | `yamie-chatbot2.vercel.app` |

**Procfile:**
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Deploy flow:** push to `main` → Railway auto-deploys both backends → Vercel auto-deploys the frontend.

**Twilio webhook URL (set in Twilio console):**
```
https://yamie-chatbot2-production.up.railway.app/api/webhook/whatsapp
```

> ⚠️ Twilio Sandbox expires every 72 hours. Users must rejoin by sending `join let-were` to the Twilio number. The permanent fix is Phase 8 (WhatsApp Business API).

---

## API Endpoints

### Chatbot Backend (port 8000)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API info |
| `POST` | `/api/query` | Ask a question (`{"question": "...", "user_id": "...", "debug": true}`) — API key auth |
| `GET` | `/api/health` | Health check (Pinecone, Redis, Supabase) |
| `GET` | `/api/stats` | System statistics |
| `POST` | `/api/webhook/whatsapp` | Twilio WhatsApp webhook (Twilio-signature verified) |

### Admin Backend (port 8001)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/auth/login` | Login, returns JWT | ❌ |
| `GET` | `/api/auth/me` | Current user | ✅ |
| `POST` | `/api/chat` | Dashboard chat with the agent | ✅ |
| `GET` / `POST` / `PATCH` / `DELETE` | `/api/whitelist/...` | Whitelist CRUD | ✅ |
| `GET` | `/api/logs/` | Paginated logs with filters | ✅ |
| `GET` | `/api/logs/{id}` | Single log detail | ✅ |
| `GET` | `/api/logs/stats/summary` | Query count stats | ✅ |
| `POST` | `/api/sync/run` | Trigger sync | ✅ |
| `GET` | `/api/sync/status` | Sync status per source | ✅ |
| `GET` | `/api/sync/history` | Paginated sync history | ✅ |
| `GET` | `/api/system/status` | Overall system health | ✅ |
| `GET` | `/api/system/pinecone` | Pinecone namespace stats | ✅ |
| `GET` | `/api/system/redis` | Redis status | ✅ |

---

## Configuration Reference

All core settings live in `src/config.py`. The agent model is a constant in `src/agent/agent.py` (`CLAUDE_MODEL = "claude-sonnet-4-6"`).

| Setting | Value | Description |
|---|---|---|
| `llm_model` (logging) | `claude-sonnet-4-6` | Label written to Supabase for each query |
| `llm_temperature` | `0.3` | Low = factual, grounded |
| `llm_max_tokens` | `1500` | Covers tool_use blocks + final answer |
| `anthropic_timeout_seconds` | `60` | Agentic loop can take longer than a single call |
| `embedding_model` | `text-embedding-3-large` | Must match ingested vectors |
| `embedding_dimensions` | `3072` | |
| `chunk_size` / `chunk_overlap` | `1000` / `200` | Ingestion-time splitter config |
| `query_top_k` | `10` | Default per-namespace (Claude can override) |
| `query_similarity_threshold` | `0.35` | Min cosine for chunks to reach Claude |
| `MAX_TOOL_CALLS` (agent.py) | `5` | Safety ceiling on tool calls per query |
| `conversation_ttl_seconds` | `1800` | Redis memory: 30 minutes |
| `max_conversation_turns` | `5` | Q&A pairs kept in memory |

---

## System Prompt

`src/agent/system_prompt.py`, version **v3.1**. Behavior highlights:

- **Identity:** YamieBot, internal assistant for Yamie-groep
- **Tone:** Friendly but professional, uses je/jij, conversational
- **Language:** Dutch
- **Length:** Answers under 200 words (WhatsApp-friendly)
- **Grounding:** Only uses information from tool results. Never fabricates.
- **Claude-controlled search:** Tool description in Dutch guides when/how to search. Greetings skip the tool.
- **Cross-document safety:** Does not combine information from unrelated chunks into one answer
- **Markdown:** Single asterisks for bold (WhatsApp format), never double asterisks
- **PDF form fields:** When present but unreadable (AcroForm checkboxes invisible to pypdf), says specifically "De ingevulde vakjes zijn voor mij niet zichtbaar" and refers to Notion
- **File/link requests:** Responds "Het originele document staat in Notion — vraag je manager" instead of "I can't share files"
- **No internal jargon:** Never says "zoektool", "fragmenten", "kennisbank", "namespace", "database"

---

## Project Roadmap

| Phase | Status | Description |
|---|---|---|
| **Phase 1** — Core RAG System | ✅ Complete | Pinecone, LlamaIndex ingestion, multi-namespace retrieval |
| **Phase 2** — Notion Ingestion | ✅ Complete | Recursive Notion loader, 5 namespaces, embedded PDFs |
| **Phase 3** — WhatsApp Integration | ✅ Complete | Twilio webhook + background tasks, Redis memory, whitelist |
| **Phase 4** — Admin Dashboard | ✅ Complete | FastAPI + React, 7 pages, mobile-first |
| **Phase 5** — Deploy Admin Dashboard | ✅ Complete | Railway + Vercel |
| **Phase 6** — Incremental Sync | ✅ Complete | Deterministic IDs, orphan detection with 50% safety |
| **Phase 7** — Agentic RAG Refactor | ✅ Complete | Anthropic SDK + Claude Sonnet 4.6 + tool use (April 2026) |
| **Phase 8** — Evaluation Pipeline | 🔲 Next | 25-30 Q&A pairs + scoring baseline (prerequisite for all quality work) |
| **Phase 9** — Hybrid Search (BM25 + dense) | 🔲 | Fixes name/address exact-match lookups |
| **Phase 10** — WhatsApp Business API | 🔲 | Replaces 72-hour sandbox with real number |

### Backlog (Priority Order)

**RAG Quality:**
- Evaluation pipeline — 25-30 real Q&A pairs, automated scoring on correctness / grounding / format
- Hybrid search (dense + BM25) — Pinecone sparse vectors, fixes "Wie is Daoud?" type questions
- Re-ranker integration (Cohere Rerank or local cross-encoder)
- Markdown-aware chunking (header-based splitter)
- Embedding model research (text-embedding-3-large is ~18 months old)

**Infrastructure:**
- Langfuse integration for production tracing
- Response caching in Redis
- Scheduled auto-sync (background job every 6-12 h)
- Deprecate legacy `scripts/run_notion_ingestion.py` once sync is proven stable

**Product:**
- Auto-onboarding WhatsApp message when a new number is whitelisted
- Tally + n8n pipeline for forms (replaces unreadable PDF checklists — see [docs/tally-n8n-migration.md](docs/tally-n8n-migration.md))
- Dashboard chat Supabase logging (decide: log or not log admin test questions)
