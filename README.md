# YamieBot

An AI-powered internal knowledge assistant for a multi-brand Dutch restaurant group. Staff ask questions via WhatsApp and the bot answers from the company's Notion knowledge base using RAG (Retrieval-Augmented Generation).

**Brands supported:** Yamie Pastabar · Flamin'wok · Smokey Joe's

---

## Table of Contents

- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Knowledge Base (Pinecone)](#knowledge-base-pinecone)
- [Local Development Setup](#local-development-setup)
- [Running the Services](#running-the-services)
- [Ingesting Notion Content](#ingesting-notion-content)
- [Utility Scripts](#utility-scripts)
- [Admin Dashboard](#admin-dashboard)
- [Environment Variables](#environment-variables)
- [Production Deployment (Railway)](#production-deployment-railway)
- [API Endpoints](#api-endpoints)
- [Configuration Reference](#configuration-reference)
- [Project Roadmap](#project-roadmap)

---

## How It Works

```
Staff (WhatsApp) → Twilio → FastAPI Backend → QueryEngine → Pinecone + OpenAI → Answer
```

1. A staff member sends a question via WhatsApp
2. Twilio forwards the message to the FastAPI webhook
3. The backend checks the phone number against the whitelist (Supabase)
4. A `🤔 Denken...` acknowledgment is sent immediately to avoid Twilio's 15-second timeout
5. The question is processed in a background task:
   - If the user has conversation history, the question is transformed into a standalone query (resolves pronouns like "hij", "dat", "die locatie")
   - The QueryEngine retrieves the top 15 most relevant chunks from all 5 Pinecone namespaces simultaneously
   - GPT-4o-mini generates a grounded answer in the user's language
6. The answer is sent back via the Twilio API
7. The full interaction is logged to Supabase

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| RAG Framework | LlamaIndex | Document ingestion and retrieval orchestration |
| Vector Database | Pinecone (`yamie-knowledge`) | Stores document embeddings, semantic search |
| LLM | GPT-4o-mini | Answer generation |
| Embeddings | text-embedding-3-large (3072d) | Converts text to vectors |
| Conversation Memory | Redis Cloud | Per-user history (30 min TTL, 4 turns) |
| Chatbot Backend | FastAPI + Uvicorn (port 8000) | REST API, WhatsApp webhook |
| Admin Backend | FastAPI + Uvicorn (port 8001) | Admin dashboard API |
| Admin Frontend | React 18 + Vite + TypeScript (port 5173) | Admin UI |
| Logging & Analytics | Supabase + structlog | Query logs, whitelist management |
| WhatsApp | Twilio API | Receives and sends WhatsApp messages |
| Hosting | Railway | Production deployment (chatbot backend) |
| Knowledge Source | Notion | All company documents and content |

---

## Project Structure

```
yamie-chatbot2-main/
│
├── backend/                          # Chatbot FastAPI app (port 8000)
│   ├── main.py                       # App entry point, CORS, rate limiter, lifespan
│   ├── config.py                     # Backend-specific config
│   └── routes/
│       ├── query.py                  # POST /api/query
│       ├── health.py                 # GET /api/health + /api/stats
│       └── webhook.py                # POST /api/webhook/whatsapp (Twilio handler)
│
├── src/                              # Core RAG system
│   ├── config.py                     # Main config (API keys, chunk size, top_k, etc.)
│   ├── ingestion/
│   │   ├── notion_loader.py          # Recursively loads Notion pages + embedded PDFs/DOCX
│   │   ├── notion_pipeline.py        # Notion → chunks → embeddings → Pinecone pipeline
│   │   ├── chunker.py                # Splits documents into overlapping chunks
│   │   ├── vector_store.py           # Pinecone storage context
│   │   ├── loader.py                 # Legacy DOCX loader (no longer used)
│   │   └── pipeline.py               # Legacy DOCX pipeline (no longer used)
│   ├── query/
│   │   ├── engine.py                 # Main query orchestrator (input → retrieval → answer)
│   │   ├── retriever.py              # Multi-namespace Pinecone retriever
│   │   ├── responder.py              # LLM answer generation
│   │   ├── prompts.py                # Prompt construction
│   │   ├── system_prompt.py          # Bot personality and rules (Dutch, grounded)
│   │   └── models.py                 # QueryRequest / QueryResponse Pydantic models
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
│   │       └── system.py             # Pinecone + Redis + config status
│   └── frontend/                     # React admin UI (port 5173)
│       └── src/
│           ├── App.tsx               # Routing + protected routes
│           ├── components/
│           │   └── Layout.tsx        # Navigation (desktop + mobile bottom nav)
│           ├── pages/
│           │   ├── LoginPage.tsx     # JWT login form
│           │   ├── DashboardPage.tsx # Live stat cards (total queries, whitelist, today)
│           │   ├── WhitelistPage.tsx # Add/delete/activate/deactivate numbers
│           │   ├── LogsPage.tsx      # Paginated logs with search + detail modal
│           │   └── SystemPage.tsx    # Pinecone namespaces, Redis, config display
│           └── lib/
│               ├── api.ts            # Axios client with auto token injection
│               └── auth.ts           # Login/logout helpers
│
├── scripts/                          # Utility and ingestion scripts
│   ├── run_notion_ingestion.py       # CLI: ingest Notion sources into Pinecone
│   ├── debug_query.py                # Inspect retrieval chunks and sources for a query
│   ├── system_status.py              # Check Pinecone, Redis, Supabase health
│   ├── test_query.py                 # Run a test query end-to-end
│   ├── inspect_redis.py              # View conversation memory in Redis
│   ├── test_redis.py                 # Test Redis connection
│   └── test_notion_connection.py     # Test Notion API access
│
├── .env.example                      # Template for all required environment variables
├── requirements.txt                  # Python dependencies
├── Procfile                          # Railway deployment: uvicorn backend.main:app
└── run_backend.py                    # Start the chatbot backend locally
```

---

## Knowledge Base (Pinecone)

**Index:** `yamie-knowledge`  
**Total vectors:** 1,090  
**All content sourced from Notion**

| Namespace | Vectors | Content |
|---|---|---|
| `yamie-pastabar` | 529 | 17 city locations, 50+ embedded PDFs (visit reports, training docs, quality checks) |
| `flaminwok` | 302 | 10 city locations, 34 embedded PDFs |
| `operations-department` | 204 | SOPs, weekly reports, franchise procedures |
| `smokey-joes` | 24 | 3 locations (incl. multi-concept at Ijmuiden + Amsterdam Zuidoost)  |
| `officiele-documenten` | 31 | Menu cards, allergen lists, recipe cards, franchise handbook |

The query engine searches **all 5 namespaces simultaneously** and merges + re-ranks results. The `top_k=15` setting was determined through testing to be the optimal balance between coverage and accuracy.

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

Three services need to run for full local functionality. Open three separate terminal windows.

**Terminal 1 — Chatbot backend (port 8000)**
```bash
source venv/Scripts/activate
python run_backend.py
# Available at: http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Terminal 2 — Admin dashboard backend (port 8001)**
```bash
source venv/Scripts/activate
python -m admin_dashboard.backend.main
# Available at: http://localhost:8001
# API docs: http://localhost:8001/docs
```

**Terminal 3 — Admin dashboard frontend (port 5173)**
```bash
cd admin_dashboard/frontend
npm run dev
# Available at: http://localhost:5173
```

**Admin login credentials:**
```
Username: admin
Password: changeme123
```
> ⚠️ These are currently hardcoded. Must be moved to environment variables before production handoff.

---

## Ingesting Notion Content

All knowledge comes from Notion. The ingestion pipeline loads Notion pages recursively, extracts text from embedded PDFs and DOCX files, chunks the content, embeds it with `text-embedding-3-large`, and stores it in Pinecone.

**Re-ingest a single namespace (e.g. after Notion content changes):**
```bash
python scripts/run_notion_ingestion.py --source yamie-pastabar --clear
```

**Dry-run (preview without embedding — shows doc count, chunk count, estimated cost):**
```bash
python scripts/run_notion_ingestion.py --source yamie-pastabar --dry-run
```

**Re-ingest all 5 namespaces:**
```bash
python scripts/run_notion_ingestion.py --clear
```

**List all registered sources:**
```bash
python scripts/run_notion_ingestion.py --list
```

**Available source keys:**
- `operations-department`
- `yamie-pastabar`
- `flaminwok`
- `smokey-joes`
- `officiele-documenten`

> **Note:** `NOTION_API_KEY` must be set in `.env` and the Notion integration must be connected to the relevant teamspaces in Notion's UI.

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

The admin dashboard is a separate application that runs alongside the chatbot. It provides a management interface for non-technical users.

**Pages:**

| Page | Description |
|---|---|
| **Login** | JWT authentication |
| **Dashboard** | Live stats: total queries, whitelisted numbers, queries today |
| **Telefoonnummers** | Add/remove/activate/deactivate WhatsApp numbers. Managers type `+31612345678` — the `whatsapp:` prefix is added automatically |
| **Vragen Overzicht** | Paginated query log with search, click-to-detail modal |
| **Systeem Status** | Pinecone namespace vector counts, Redis status, live config |

The frontend is fully mobile-responsive with a bottom navigation bar on mobile and a card-based layout for tables on small screens.

**Supabase tables used:**

- `whitelisted_numbers` — columns: `phone_number`, `name`, `department`, `added_at`, `is_active`, `notes`, `id`
- `query_logs` — columns: `id`, `created_at`, `user_id`, `question`, `transformed_question`, `answer`, `has_answer`, `response_time_seconds`, `sources`, `chunks_retrieved`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `error`, `config_top_k`, `config_chunk_size`, `config_temperature`, and more

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

# Redis Cloud (conversation memory + rate limiting)
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

# Notion (only needed when running ingestion)
NOTION_API_KEY=ntn_...

# Admin Dashboard (optional — defaults shown)
ADMIN_JWT_SECRET=your-secret-key-change-in-production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme123
```

---

## Production Deployment (Railway)

The chatbot backend is deployed and live on Railway.

**Live URL:** `yamie-chatbot2-production.up.railway.app`

**Procfile (startup command):**
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Deployment steps for any new changes:**
1. Push to GitHub
2. Railway auto-deploys from the connected repository
3. Set or update environment variables in the Railway dashboard under the service's Variables tab

**Twilio webhook URL (must be set in Twilio console):**
```
https://yamie-chatbot2-production.up.railway.app/api/webhook/whatsapp
```

> ⚠️ The admin dashboard backend and frontend are **not yet deployed** — this is the next priority (Phase 5).

---

## API Endpoints

### Chatbot Backend (port 8000)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API info |
| `POST` | `/api/query` | Ask a question (JSON body: `{"question": "...", "user_id": "..."}`) |
| `GET` | `/api/health` | Health check (Pinecone, Redis, Supabase) |
| `GET` | `/api/stats` | System statistics |
| `POST` | `/api/webhook/whatsapp` | Twilio WhatsApp webhook (form data) |

### Admin Backend (port 8001)

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/auth/login` | Login, returns JWT token | ❌ |
| `GET` | `/api/auth/me` | Current user info | ✅ |
| `GET` | `/api/whitelist/` | List all whitelisted numbers | ✅ |
| `POST` | `/api/whitelist/` | Add a number | ✅ |
| `PATCH` | `/api/whitelist/{id}` | Activate/deactivate a number | ✅ |
| `DELETE` | `/api/whitelist/{id}` | Delete a number | ✅ |
| `GET` | `/api/logs/` | Paginated query logs | ✅ |
| `GET` | `/api/logs/{id}` | Single log detail | ✅ |
| `GET` | `/api/logs/stats/summary` | Query count stats | ✅ |
| `GET` | `/api/system/status` | Overall system health | ✅ |
| `GET` | `/api/system/pinecone` | Pinecone namespace stats | ✅ |
| `GET` | `/api/system/redis` | Redis connection status | ✅ |

---

## Configuration Reference

All core settings live in `src/config.py`.

| Setting | Value | Description |
|---|---|---|
| `llm_model` | `gpt-4o-mini` | OpenAI model for answer generation |
| `llm_temperature` | `0.3` | Low = factual, grounded answers |
| `llm_max_tokens` | `450` | Max answer length |
| `embedding_model` | `text-embedding-3-large` | OpenAI embedding model |
| `embedding_dimensions` | `3072` | Vector dimensions |
| `chunk_size` | `500` | Characters per chunk |
| `chunk_overlap` | `150` | Overlap between consecutive chunks |
| `query_top_k` | `15` | Chunks retrieved per query (optimized for multi-namespace balance) |
| `conversation_ttl_seconds` | `1800` | Redis memory expires after 30 minutes of inactivity |
| `max_conversation_turns` | `4` | How many Q&A pairs are kept in memory |
| `openai_timeout_seconds` | `30` | Max time for OpenAI API calls |
| `pinecone_timeout_seconds` | `10` | Max time for Pinecone queries |
| `redis_timeout_seconds` | `5` | Max time for Redis operations |

---

## Project Roadmap

| Phase | Status | Description |
|---|---|---|
| **Phase 1** — Core RAG System | ✅ Complete | Pinecone, LlamaIndex, GPT-4o-mini, multi-namespace retriever |
| **Phase 2** — Notion Ingestion | ✅ Complete | NotionLoader, NotionIngestionPipeline, 5 namespaces, 1,090 vectors |
| **Phase 3** — WhatsApp Integration | ✅ Complete | Twilio webhook, background processing, Redis memory, whitelist, Railway |
| **Phase 4** — Admin Dashboard | ✅ Complete | FastAPI backend (14 endpoints) + React frontend, mobile responsive |
| **Phase 5** — Deploy Admin Dashboard | 🔲 Next | Deploy admin backend + frontend to Railway/Vercel, move credentials to env vars |
| **Phase 6** — Content Completion | 🔲 Upcoming | Expand Smokey Joe's (only 24 vectors), re-ingest if Notion has changed |
| **Phase 7** — WhatsApp Business API | 🔲 Upcoming | Switch from Twilio sandbox to real WhatsApp number (Meta approval required) |
| **Backlog** | 🔲 Future | Auto re-ingestion on Notion changes, Redis response caching, cost monitoring dashboard, analytics |