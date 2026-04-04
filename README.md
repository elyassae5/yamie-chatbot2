# YamieBot

An AI-powered internal knowledge assistant for a multi-brand Dutch restaurant group. Staff ask questions via WhatsApp and the bot answers from the company's Notion knowledge base using RAG (Retrieval-Augmented Generation).

**Brands supported:** Yamie Pastabar · Flamin'wok · Smokey Joe's

---

## Table of Contents

- [How It Works](#how-it-works)
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
Staff (WhatsApp) → Twilio → FastAPI Backend → QueryEngine → Pinecone + GPT-4o → Answer
```

1. A staff member sends a question via WhatsApp
2. Twilio forwards the message to the FastAPI webhook
3. The backend checks the phone number against the whitelist (Supabase)
4. A `Momentje... ⏳` acknowledgment is sent immediately to avoid Twilio's 15-second timeout
5. The question is processed in a background task:
   - If the user has conversation history, the question is classified as a follow-up or new topic. Follow-ups are rewritten into standalone queries; new topics are left unchanged.
   - The QueryEngine retrieves the top 10 most relevant chunks from all 5 Pinecone namespaces simultaneously
   - Chunks below the similarity threshold (0.35) are filtered out
   - GPT-4o generates a grounded answer based on the remaining chunks
   - Markdown is converted to WhatsApp format (`**bold**` → `*bold*`), source references are stripped
6. The answer is sent back via the Twilio API
7. The full interaction (including all retrieved chunks and debug data) is logged to Supabase

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| RAG Framework | LlamaIndex | Document ingestion and retrieval orchestration |
| Vector Database | Pinecone (`yamie-knowledge`) | Stores document embeddings, semantic search |
| LLM | GPT-4o | Answer generation |
| Embeddings | text-embedding-3-large (3072d) | Converts text to vectors |
| Conversation Memory | Redis Cloud | Per-user history (30 min TTL, 4 turns) |
| Chatbot Backend | FastAPI + Uvicorn (port 8000) | REST API, WhatsApp webhook |
| Admin Backend | FastAPI + Uvicorn (port 8001) | Admin dashboard API, sync endpoints |
| Admin Frontend | React 18 + Vite + TypeScript (port 5173) | Admin UI |
| Logging & Analytics | Supabase + structlog | Query logs, sync logs, whitelist management |
| WhatsApp | Twilio Sandbox | Receives and sends WhatsApp messages |
| Hosting (Backends) | Railway | Chatbot backend + admin backend |
| Hosting (Frontend) | Vercel | Admin dashboard UI |
| Knowledge Source | Notion | All company documents and content |

---

## Project Structure

```
yamie-chatbot2-main/
│
├── CLAUDE.md                         # Project memory for Claude Code (AI dev context)
├── docs/
│   ├── backlog.md                    # Prioritized feature backlog
│   └── session-log.md               # Session history (what was done when)
│
├── backend/                          # Chatbot FastAPI app (port 8000)
│   ├── main.py                       # App entry point, CORS, rate limiter, lifespan
│   ├── config.py                     # Backend-specific config
│   ├── engine.py                     # Shared QueryEngine singleton
│   └── routes/
│       ├── query.py                  # POST /api/query (API key auth, debug data to Supabase)
│       ├── health.py                 # GET /api/health + /api/stats
│       └── webhook.py                # POST /api/webhook/whatsapp (Twilio handler)
│
├── src/                              # Core RAG system
│   ├── config.py                     # Main config (API keys, chunk size, top_k, etc.)
│   ├── ingestion/
│   │   ├── notion_loader.py          # Recursively loads Notion pages + embedded PDFs/DOCX
│   │   ├── notion_pipeline.py        # Notion sources registry + ingestion pipeline
│   │   ├── sync_service.py           # Incremental sync engine (deterministic IDs, orphan detection)
│   │   ├── chunker.py                # Splits documents into overlapping chunks
│   │   ├── vector_store.py           # Pinecone storage context
│   │   ├── loader.py                 # Legacy DOCX loader (deprecated)
│   │   └── pipeline.py               # Legacy DOCX pipeline (deprecated)
│   ├── query/
│   │   ├── engine.py                 # Main query orchestrator (input → retrieval → answer)
│   │   ├── retriever.py              # Multi-namespace Pinecone retriever
│   │   ├── responder.py              # LLM answer generation with retry logic
│   │   ├── prompts.py                # Prompt construction (system + user prompt)
│   │   ├── system_prompt.py          # Bot personality and rules (v2.1, Dutch, grounded)
│   │   └── models.py                 # QueryRequest / QueryResponse dataclasses
│   ├── memory/
│   │   └── conversation_memory.py    # Redis-backed per-user conversation history
│   ├── database/
│   │   └── supabase_client.py        # Query logging to Supabase
│   └── logging_config.py             # structlog setup (JSON format)
│
├── admin_dashboard/
│   ├── backend/                      # Admin FastAPI app (port 8001)
│   │   ├── main.py                   # Admin app entry point
│   │   ├── config.py                 # Admin config (JWT, CORS, credentials)
│   │   ├── auth/
│   │   │   └── jwt_handler.py        # JWT creation and verification
│   │   └── routes/
│   │       ├── auth.py               # POST /api/auth/login, GET /api/auth/me
│   │       ├── whitelist.py          # CRUD for whitelisted_numbers (Supabase)
│   │       ├── logs.py               # Paginated query logs viewer
│   │       ├── sync.py               # Content sync endpoints (trigger, status, history)
│   │       └── system.py             # Pinecone + Redis + config status
│   └── frontend/                     # React admin UI (port 5173)
│       └── src/
│           ├── App.tsx               # Routing + protected routes
│           ├── components/
│           │   └── Layout.tsx        # Navigation (desktop + mobile bottom nav)
│           ├── pages/
│           │   ├── LoginPage.tsx     # JWT login form
│           │   ├── DashboardPage.tsx # Live stat cards
│           │   ├── WhitelistPage.tsx # Manage WhatsApp numbers
│           │   ├── LogsPage.tsx      # Query logs with debug view (chunks, scores)
│           │   ├── SyncPage.tsx      # Content sync UI (trigger, history, details)
│           │   └── SystemPage.tsx    # System health overview
│           └── lib/
│               ├── api.ts            # Axios client with auto token injection
│               └── auth.ts           # Login/logout helpers
│
├── scripts/                          # Utility and ingestion scripts
│   ├── run_notion_ingestion.py       # CLI: ingest Notion sources into Pinecone (legacy)
│   ├── debug_query.py                # Inspect retrieval chunks and sources for a query
│   ├── system_status.py              # Check Pinecone, Redis, Supabase health
│   ├── test_query.py                 # Run a test query end-to-end
│   ├── inspect_redis.py              # View conversation memory in Redis
│   ├── test_redis.py                 # Test Redis connection
│   └── test_notion_connection.py     # Test Notion API access
│
├── .env.example                      # Template for all required environment variables
├── requirements.txt                  # Python dependencies (all pinned to exact versions)
├── Procfile                          # Railway deployment: uvicorn backend.main:app
└── run_backend.py                    # Start the chatbot backend locally
```

---

## Knowledge Base (Pinecone)

**Index:** `yamie-knowledge`
**Total vectors:** ~551
**All content sourced from Notion**
**Vector ID format:** `{notion_page_id}::chunk::{index:04d}` (deterministic)

| Namespace | Vectors | Content |
|---|---|---|
| `yamie-pastabar` | ~294 | 17 city locations, embedded PDFs (visit reports, training docs, quality checks) |
| `flaminwok` | ~151 | 10 city locations, embedded PDFs |
| `operations-department` | ~78 | SOPs, weekly reports, franchise procedures |
| `officiele-documenten` | ~18 | Menu cards, allergen lists, recipe cards, franchise handbook |
| `smokey-joes` | ~10 | 3 locations (low content) |

The query engine searches **all 5 namespaces simultaneously** and merges results. Chunks below the similarity threshold (0.35) are filtered out before being sent to the LLM.

### Deterministic Vector IDs

All vectors use the format `{notion_page_id}::chunk::{index:04d}`. This enables:
- **Targeted deletion** when a page changes (delete old chunks by ID, upsert new ones)
- **Incremental sync** without clearing entire namespaces
- **Orphan detection** to clean up vectors for deleted Notion pages

---

## Content Sync (Notion → Pinecone)

The sync system keeps Pinecone in sync with Notion content. It detects changes, additions, and deletions automatically.

### How It Works

1. **Enumerate** all pages in each Notion source tree (lightweight, no content loading)
2. **Compare** `last_edited_time` against the last successful sync timestamp (stored in Supabase `sync_logs`)
3. **Re-ingest** only changed pages with deterministic vector IDs
4. **Orphan detection** — compares Pinecone page IDs against Notion page IDs, deletes vectors for pages that no longer exist
5. **Safety checks** — aborts orphan cleanup if >50% of pages look orphaned (prevents accidental mass deletion)

### Usage

**Via Admin Dashboard (recommended):**
Go to the Sync page → click "Sync Nu". The dashboard shows sync history with per-source and per-page breakdowns.

**Via API:**
```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Incremental sync (only changed pages)
curl -X POST http://localhost:8001/api/sync/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"force_full": false}'

# Full sync (re-ingest everything — use for recovery only)
curl -X POST http://localhost:8001/api/sync/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"force_full": true}'
```

**Legacy ingestion script (fallback only):**
```bash
python scripts/run_notion_ingestion.py --all --clear
```
> Note: The legacy script uses random vector IDs. After using it, a full sync is needed to restore deterministic IDs.

---

## Local Development Setup

**Prerequisites:** Python 3.11+, Node.js 18+, Git Bash (Windows)

```bash
# 1. Clone the repository
git clone <repo-url>
cd yamie-chatbot2-main

# 2. Create and activate virtual environment (Git Bash on Windows)
python -m venv venv
source venv/Scripts/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and fill in all API keys (see Environment Variables section)

# 5. Install frontend dependencies (for admin dashboard)
cd admin_dashboard/frontend
npm install
cd ../..
```

---

## Running the Services

Three services need to run for full local functionality:

**Terminal 1 — Chatbot backend (port 8000)**
```bash
source venv/Scripts/activate
python run_backend.py
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

**Admin login credentials:**
Stored in Supabase `admin_users` table (bcrypt-hashed passwords). Managed via database, not hardcoded in code.

---

## Utility Scripts

```bash
# Check overall system health (Pinecone, Redis, Supabase)
python scripts/system_status.py

# Run a test query and see the full response
python scripts/test_query.py

# Inspect retrieved chunks for a specific query (for debugging answer quality)
python scripts/debug_query.py

# View conversation memory stored in Redis for a user
python scripts/inspect_redis.py

# Test Redis connection
python scripts/test_redis.py

# Test Notion API connection and accessible pages
python scripts/test_notion_connection.py
```

---

## Admin Dashboard

The admin dashboard is deployed on Vercel (frontend) and Railway (backend). It provides a management interface for non-technical users.

**Live URL:** [yamie-chatbot2.vercel.app](https://yamie-chatbot2.vercel.app)

### Pages

| Page | Description |
|---|---|
| **Login** | JWT authentication |
| **Dashboard** | Live stats: total queries, queries today |
| **Telefoonnummers** | Add/remove/activate/deactivate WhatsApp numbers |
| **Vragen Overzicht** | Query logs with search, filters, and detail modal with retrieval debug view |
| **Sync** | Trigger Notion → Pinecone sync, view history with per-source/per-page breakdown |
| **Systeem** | Pinecone namespace vector counts, Redis status, live config |

### Query Debug View

When viewing a query in the Vragen page, the detail modal includes a **"Bronnen & context"** panel showing:
- All chunks that were **used for the answer** (passed threshold) with similarity scores, source paths, and expandable full text
- All chunks that were **filtered out** (below threshold)
- The similarity threshold used

This data is saved to Supabase for every query (both API and WhatsApp).

### Supabase Tables

| Table | Purpose | RLS |
|---|---|---|
| `whitelisted_numbers` | WhatsApp phone numbers allowed to use the bot | ✅ Enabled |
| `query_logs` | Full query history with debug data | ✅ Enabled |
| `admin_users` | Dashboard login credentials (bcrypt hashes) | ✅ Enabled |
| `sync_logs` | Content sync history and results | ✅ Enabled |
| `sync_lock` | Atomic sync lock (single-row, 30-min auto-expiry) | ✅ Enabled |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values.

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=yamie-knowledge
PINECONE_NAMESPACE=operations-department

# Redis Cloud (conversation memory)
REDIS_HOST=...
REDIS_PORT=6379
REDIS_PASSWORD=...

# Supabase (query logging + whitelist)
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Notion (needed for ingestion and sync)
NOTION_API_KEY=ntn_...

# API Security
API_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=development  # Set to "production" on Railway to disable Swagger docs

# Admin Dashboard
ADMIN_JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

---

## Production Deployment

### Chatbot Backend (Railway)

**Live URL:** `yamie-chatbot2-production.up.railway.app`

**Procfile:**
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Admin Backend (Railway)

**Live URL:** `yamiebot-admin-backend-production.up.railway.app`

### Admin Frontend (Vercel)

**Live URL:** `yamie-chatbot2.vercel.app`

### Deployment

All services auto-deploy on push to GitHub:
1. Push to `main` branch
2. Railway auto-deploys both backends
3. Vercel auto-deploys the frontend

**Twilio webhook URL (set in Twilio console):**
```
https://yamie-chatbot2-production.up.railway.app/api/webhook/whatsapp
```

> ⚠️ Twilio Sandbox expires every 72 hours. Users must rejoin by sending `join let-were` to the Twilio number. The permanent fix is Phase 7 (WhatsApp Business API).

---

## API Endpoints

### Chatbot Backend (port 8000)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API info |
| `POST` | `/api/query` | Ask a question (`{"question": "...", "user_id": "...", "debug": true}`) |
| `GET` | `/api/health` | Health check (Pinecone, Redis, Supabase) |
| `GET` | `/api/stats` | System statistics |
| `POST` | `/api/webhook/whatsapp` | Twilio WhatsApp webhook |

### Admin Backend (port 8001)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/auth/login` | Login, returns JWT token | ❌ |
| `GET` | `/api/auth/me` | Current user info | ✅ |
| `GET` | `/api/whitelist/` | List all whitelisted numbers | ✅ |
| `POST` | `/api/whitelist/` | Add a number | ✅ |
| `PATCH` | `/api/whitelist/{id}` | Activate/deactivate a number | ✅ |
| `DELETE` | `/api/whitelist/{id}` | Delete a number | ✅ |
| `GET` | `/api/logs/` | Paginated query logs (with filters) | ✅ |
| `GET` | `/api/logs/{id}` | Single log detail | ✅ |
| `GET` | `/api/logs/stats/summary` | Query count stats | ✅ |
| `POST` | `/api/sync/run` | Trigger sync (`{"force_full": false}`) | ✅ |
| `GET` | `/api/sync/status` | Sync status per source | ✅ |
| `GET` | `/api/sync/history` | Paginated sync history | ✅ |
| `GET` | `/api/system/status` | Overall system health | ✅ |
| `GET` | `/api/system/pinecone` | Pinecone namespace stats | ✅ |
| `GET` | `/api/system/redis` | Redis connection status | ✅ |

---

## Configuration Reference

All core settings live in `src/config.py`.

| Setting | Value | Description |
|---|---|---|
| `llm_model` | `gpt-4o` | OpenAI model for answer generation |
| `llm_temperature` | `0.3` | Low = factual, grounded answers |
| `llm_max_tokens` | `500` | Max response length (keeps answers WhatsApp-friendly) |
| `embedding_model` | `text-embedding-3-large` | OpenAI embedding model |
| `embedding_dimensions` | `3072` | Vector dimensions |
| `chunk_size` | `1000` | Characters per chunk |
| `chunk_overlap` | `200` | Overlap between consecutive chunks |
| `query_top_k` | `10` | Chunks retrieved per query |
| `query_similarity_threshold` | `0.35` | Minimum similarity score to pass to LLM |
| `conversation_ttl_seconds` | `1800` | Redis memory expires after 30 minutes |
| `max_conversation_turns` | `4` | Q&A pairs kept in memory |
| `openai_timeout_seconds` | `30` | Max time for OpenAI API calls |
| `pinecone_timeout_seconds` | `10` | Max time for Pinecone queries |
| `redis_timeout_seconds` | `5` | Max time for Redis operations |

---

## System Prompt

The bot uses a single active system prompt (`src/query/system_prompt.py`, version `v2.1`). Key behaviors:

- **Identity:** YamieBot, internal assistant for the Yamie-groep (Yamie Pastabar, Flamin'wok, Smokey Joe's)
- **Tone:** Friendly but professional, uses je/jij, conversational
- **Language:** Matches the user's language (Dutch → Dutch, English → English)
- **Grounding:** Only uses information from retrieved document chunks. Never fabricates information.
- **Greetings:** Introduces itself and offers help. Does not search documents for greetings.
- **Word limit:** Answers stay under 200 words (optimized for WhatsApp readability)
- **No technical jargon:** Never mentions "documentfragmenten", "fragmenten", "kennisbank" or other internal terms to users
- **No source references:** Source citations are not included in WhatsApp messages (tracked in admin dashboard instead)
- **Cross-document safety:** Does not combine information from unrelated documents into a single answer

---

## Project Roadmap

| Phase | Status | Description |
|---|---|---|
| **Phase 1** — Core RAG System | ✅ Complete | Pinecone, LlamaIndex, GPT-4o, multi-namespace retriever |
| **Phase 2** — Notion Ingestion | ✅ Complete | NotionLoader, NotionIngestionPipeline, 5 namespaces |
| **Phase 3** — WhatsApp Integration | ✅ Complete | Twilio webhook, background processing, Redis memory, whitelist |
| **Phase 4** — Admin Dashboard | ✅ Complete | FastAPI backend + React frontend, mobile responsive, 6 pages |
| **Phase 5** — Deploy Admin Dashboard | ✅ Complete | Admin backend on Railway, frontend on Vercel |
| **Phase 6** — Incremental Sync | ✅ Complete | Deterministic vector IDs, incremental sync, orphan detection with safety checks |
| **Phase 7** — WhatsApp Business API | 🔲 Upcoming | Switch from Twilio sandbox to real WhatsApp number (Meta approval required) |

### Backlog (Priority Order)

**RAG Quality:**
- Re-ranker integration (Cohere Rerank) — retrieve more chunks, re-rank with cross-encoder
- Hybrid search (vector + keyword/BM25) — fixes name lookups like "Wie is Daoud?"
- Evaluation pipeline — systematic testing across different settings and models

**Admin Dashboard:**
- System prompt viewer — show/edit active prompt from dashboard
- Advanced analytics — charts, per-user stats, trends over time
- Answer quality rating — owners rate answers to tune the system
- Ticket/feedback system

**Infrastructure:**
- Scheduled auto-sync (background job every X hours)
- Response caching in Redis
- Deprecate legacy ingestion script once sync is proven stable long-term