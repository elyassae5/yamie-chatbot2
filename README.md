# YamieBot - Production-Ready RAG Assistant

AI-powered chatbot for Yamie PastaBar franchise staff in the Netherlands. Get instant answers about company policies, procedures, and operations from internal documents via WhatsApp (coming soon) or web interface.

## What It Does

Staff ask questions about franchise operations through a web interface (Gradio) or REST API. YamieBot searches internal documents and provides accurate, cited answers instantly with full conversation memory.

**Example:**
```
Q: "Wie is Daoud en wat doet hij?"
A: "Daoud is verantwoordelijk voor managementondersteuning en wordt ingeschakeld 
    bij personeels- of managementproblemen. 📄 [smokey_joes_interne_franchisehandleiding.docx]"
```

**Features:**
- ✅ Conversation memory (remembers context for 30 minutes)
- ✅ Source citations (always shows where info came from)
- ✅ No hallucinations (strict document grounding)
- ✅ Production-grade logging (Supabase query tracking)
- ✅ Rate limiting & security (FastAPI + Redis)
- ✅ Configuration tracking (A/B testing ready)
- ✅ System prompt versioning (optimize based on data)

---

## Current Status

**Phase**: Production Features Complete ✅  
**Progress**: ~80% complete  
**Next**: WhatsApp integration + Deployment

### Completed ✅
- ✅ Document ingestion
- ✅ Vector search (Pinecone Serverless)
- ✅ Answer generation (GPT-4o-mini)
- ✅ Conversation memory (Redis Cloud)
- ✅ Context-aware follow-up questions
- ✅ **Structured logging (structlog with JSON output)**
- ✅ **Query logging to Supabase (comprehensive analytics)**
- ✅ **Rate limiting (20/min per user, 60/min per IP)**
- ✅ **Retry logic (automatic recovery from transient failures)**
- ✅ **Input sanitization (500 char limit, injection protection)**
- ✅ **Configuration tracking (A/B testing infrastructure)**
- ✅ **System prompt versioning (v1.1-short active)**
- ✅ **FastAPI REST API with auto-generated docs**
- ✅ **Gradio web interface**

### Next Steps 🚧
- ⏳ WhatsApp integration (Twilio) ← **MAIN PRIORITY**
- ⏳ Production deployment (Railway/Render)
- ⏳ Redis query caching (optional optimization)
- ⏳ Analytics dashboard (optional)

---

## Tech Stack

**Core RAG:**
- **Framework**: LlamaIndex (production RAG framework)
- **Embeddings**: OpenAI text-embedding-3-large (3072 dims)
- **Vector DB**: Pinecone Serverless
- **LLM**: GPT-4o-mini (fast + cheap)
- **Memory**: Redis Cloud (conversation history)
- **Chunking**: 500 chars, 150 overlap

**Backend & API:**
- **API**: FastAPI (async, production-ready)
- **Rate Limiting**: fastapi-limiter + Redis
- **Retry Logic**: tenacity (3 attempts, exponential backoff)
- **Logging**: structlog (JSON output for log aggregators)
- **Query Logging**: Supabase PostgreSQL (analytics & monitoring)

**Frontend:**
- **Web UI**: Gradio (internal testing + demos)
- **Future**: WhatsApp via Twilio (production interface)

**Configuration:**
- Top-k retrieval: 7 chunks
- Temperature: 0.1 (factual)
- Max tokens: 400
- Conversation memory: 5 turns displayed, 5 stored, 30min TTL
- System prompt: v1.1-short (conversational, context-aware)

---

## Quick Start

### 1. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Set Up Environment
Create `.env` file with:
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=yamie-test

# Redis Cloud (conversation memory + rate limiting)
REDIS_HOST=redis-xxxxx.ec2.cloud.redislabs.com
REDIS_PORT=10098
REDIS_PASSWORD=your_redis_password

# Supabase (query logging)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
```

### 3. Add Documents
```bash
# Place DOCX files in data/ folder
cp your_document.docx data/
```

### 4. Ingest Documents
```bash
python scripts/run_ingestion.py
```

### 5. Start the System

**Option A: Full Stack (Recommended)**
```bash
# Terminal 1: Start backend API
python run_backend.py
# Backend runs at: http://localhost:8000
# API docs at: http://localhost:8000/docs

# Terminal 2: Start Gradio frontend
python run_frontend.py
# Gradio UI at: http://localhost:7860
```

**Option B: Backend Only (API testing)**
```bash
python run_backend.py
# Test with curl or API clients
```

**Option C: Terminal Testing (Quick tests)**
```bash
python scripts/test_query.py
# Interactive mode, doesn't log to Supabase
```

---

## Project Structure
```
yamie-chatbot/
├── data/                           # Documents to ingest
│   └── *.docx
├── src/
│   ├── config.py                   # Central configuration
│   ├── logging_config.py           # Structured logging setup (structlog)
│   ├── ingestion/                  # Document processing (LlamaIndex)
│   │   ├── loader.py              # Document loading
│   │   ├── chunker.py             # Text chunking
│   │   ├── pipeline.py            # Ingestion orchestration
│   │   └── vector_store.py        # Pinecone integration
│   ├── query/                      # RAG query system
│   │   ├── engine.py              # Main orchestrator + memory
│   │   ├── retriever.py           # Vector search (LlamaIndex + Pinecone)
│   │   ├── responder.py           # Answer generation (OpenAI + retry logic)
│   │   ├── prompts.py             # Prompt construction
│   │   ├── system_prompt.py       # Bot behavior (EDIT THIS!)
│   │   └── models.py              # Data models
│   ├── memory/                     # Conversation memory
│   │   └── conversation_memory.py # Redis integration
│   └── database/                   # Query logging
│       ├── supabase_client.py     # Supabase integration
│       └── __init__.py
├── backend/                        # FastAPI REST API
│   ├── main.py                    # FastAPI app + lifespan management
│   ├── config.py                  # Backend configuration
│   ├── models/                    # API request/response models
│   └── routes/
│       ├── query.py               # Query endpoint + Supabase logging
│       └── health.py              # Health check endpoint
├── frontend/                       # Web interfaces
│   ├── gradio_app.py              # Main Gradio interface
│   └── gradio_app_share.py        # Shareable Gradio interface
├── scripts/
│   ├── run_ingestion.py           # Ingest documents
│   ├── test_query.py              # Interactive testing (no logging)
│   ├── inspect_redis.py           # View/clear conversations
│   └── system_status.py           # Health check
├── run_backend.py                  # Start FastAPI server
├── run_frontend.py                 # Start Gradio interface
├── .env                            # API keys (create this!)
├── requirements.txt                # Dependencies
└── README.md                       # This file
```

---

## Usage

### Production Flow (Web Interface)

1. **Start Backend:**
```bash
   python run_backend.py
```

2. **Start Frontend:**
```bash
   python run_frontend.py
```

3. **Ask Questions:**
   - Open Gradio at `http://localhost:7860`
   - Type questions naturally
   - Bot remembers context for 30 minutes
   - All queries logged to Supabase

### API Usage (Direct)
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Wie is Daoud?",
    "user_id": "employee_123",
    "debug": true
  }'
```

**Response:**
```json
{
  "question": "Wie is Daoud?",
  "answer": "Daoud is verantwoordelijk voor managementondersteuning...",
  "sources": [...],
  "has_answer": true,
  "response_time_seconds": 1.24,
  "user_id": "employee_123",
  "timestamp": "2026-01-08T13:25:35.311483+00:00",
  "debug_info": {
    "transformed_question": null,
    "chunks_retrieved": 7,
    "top_chunks": [...]
  }
}
```

### API Documentation

**Interactive docs:** `http://localhost:8000/docs` (Swagger UI)  
**Alternative docs:** `http://localhost:8000/redoc` (ReDoc)

**Endpoints:**
- `POST /api/query` - Process a question
- `GET /api/stats` - Get system statistics
- `GET /api/health` - Health check

### Terminal Testing (Development)
```bash
python scripts/test_query.py

# Commands:
# - Type questions normally
# - Type 'reset' to clear conversation memory
# - Type 'quit' to exit
```

**Note:** Terminal testing bypasses FastAPI and doesn't log to Supabase.

### Redis/Memory Management
```bash
# View stored conversations
python scripts/inspect_redis.py

# Clear all conversations (prompts for confirmation)
python scripts/inspect_redis.py
# Type: yes
```

---

## Configuration

### Application Settings (`src/config.py`)
```python
# Chunking (affects retrieval quality)
chunk_size: int = 500           # Characters per chunk
chunk_overlap: int = 150        # Overlap between chunks

# Retrieval (affects answer quality)
query_top_k: int = 7            # Number of chunks to retrieve
query_similarity_threshold: float = 0.0  # Minimum similarity score

# LLM (affects response quality & cost)
llm_model: str = "gpt-4o-mini"  # Fast + cheap model
llm_temperature: float = 0.1    # Low = factual, high = creative
llm_max_tokens: int = 400       # Response length

# Memory (affects conversation context)
max_conversation_turns: int = 5         # Turns shown in context
conversation_ttl_seconds: int = 1800    # 30 minutes

# Embeddings
embedding_model: str = "text-embedding-3-large"
embedding_dimensions: int = 3072
```

### System Prompt Management (`src/query/system_prompt.py`)

**Current Active:** `v1.1-short` (conversational, context-aware)

**Available Prompts:**
- `SYSTEM_PROMPT_FULL` (v1.0-full) - Verbose with examples
- `SYSTEM_PROMPT_SHORT` (v1.1-short) - **ACTIVE** - Conversational
- `SYSTEM_PROMPT_STRICT` (v1.0-strict) - Ultra-strict, minimal

**To switch prompts:**
```python
# Edit these 2 lines in system_prompt.py:
ACTIVE_SYSTEM_PROMPT = SYSTEM_PROMPT_SHORT  # Change this
ACTIVE_SYSTEM_PROMPT_VERSION = SYSTEM_PROMPT_SHORT_VERSION  # And this
```

**All prompt changes are automatically tracked in Supabase logs!**

---

## Production Features

### 1. Structured Logging (structlog)

**All logs output as JSON for easy parsing:**
```json
{"event": "query_received", "user_id": "employee_123", "timestamp": "2026-01-08T13:25:35Z"}
{"event": "retrieval_completed", "chunks_retrieved": 7, "query": "Wie is Daoud?"}
{"event": "query_processed", "has_answer": true, "response_time_seconds": 1.24}
{"event": "query_logged_to_supabase", "system_prompt_version": "v1.1-short"}
```

**Benefits:** Easy to search, parse, and analyze in log aggregators (Datadog, CloudWatch, etc.)

### 2. Query Logging (Supabase)

**Every query logs:**
- Question (original + transformed)
- Answer + success/failure
- Response time, token usage
- Sources used
- User ID, IP address
- **Configuration snapshot** (top_k, chunk_size, temperature, etc.)
- **System prompt version** (track A/B test results)

**View logs:** Supabase Dashboard → Table Editor → `query_logs`

**Analytics queries:**
```sql
-- Which prompt version performs best?
SELECT system_prompt_version, AVG(CASE WHEN has_answer THEN 1.0 ELSE 0.0 END) * 100 as success_rate
FROM query_logs GROUP BY system_prompt_version;

-- Which configuration gives best results?
SELECT config_top_k, AVG(response_time_ms) as avg_ms, COUNT(*) as queries
FROM query_logs GROUP BY config_top_k;
```

### 3. Rate Limiting (fastapi-limiter + Redis)

**Limits:**
- Per user: 20 queries/minute
- Per IP: 60 queries/minute
- Prevents abuse and runaway costs

**Custom error messages** when limits exceeded.

### 4. Retry Logic (tenacity)

**Automatic retries on transient failures:**
- OpenAI API: 3 attempts, exponential backoff (2s, 4s, 8s)
- Pinecone API: 3 attempts, exponential backoff
- Only retries network errors, timeouts, rate limits
- Never retries authentication errors

**User experience:** Seamless - failures are invisible when retries succeed.

### 5. Input Sanitization

**Protection against:**
- Questions >500 characters (cost control)
- HTML/script tags (XSS prevention)
- SQL injection patterns (security)

**Allows:** Emojis, URLs, normal language

---

## Architecture

### How It Works
```
User asks question (Gradio/API/WhatsApp)
    ↓
FastAPI endpoint receives request
    ↓
Rate limiting check (fastapi-limiter + Redis)
    ↓
Input sanitization (500 char limit, injection protection)
    ↓
QueryEngine.query()
    │
    ├─→ [1] Load conversation history (Redis)
    │        Last 5 turns for context
    │
    ├─→ [2] Transform vague questions
    │        "What about that?" → "What about vacation days?"
    │        Uses GPT-4o-mini + conversation context
    │
    ├─→ [3] Retrieve relevant chunks (Pinecone + LlamaIndex)
    │        Top 7 chunks via vector similarity search
    │        Automatic retry on failures
    │
    ├─→ [4] Generate answer (GPT-4o-mini)
    │        Uses: chunks + conversation history + system prompt
    │        Automatic retry on failures
    │
    └─→ [5] Save to memory (Redis)
             Auto-expires after 30 minutes
    ↓
Log to Supabase (configuration + metrics + prompt version)
    ↓
Return answer with citations
```

### Conversation Memory Flow

**How it works:**
- Each user gets unique conversation ID
- Stores last 5 Q&A pairs in Redis
- Uses last 5 for context generation
- Auto-deletes after 30 minutes of inactivity

**Example:**
```
Turn 1: "Wie is Daoud?" → Bot explains
         [Saved to Redis]

Turn 2: "Wat zijn zijn taken?" → Bot knows "zijn" = Daoud
         [Context: previous Q&A used]

Turn 3: "Vertel me meer" → Bot knows what "more" refers to
         [Context: last 5 turns used]

[After 30 minutes of inactivity]
         [Redis auto-deletes conversation]
```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check environment variables
→ Verify all keys in .env file
→ Test: python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('OPENAI_API_KEY'))"

# Supabase connection errors
→ Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
→ Test in Supabase dashboard: Settings → API

# Redis connection errors
→ Check REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
→ Test: python scripts/inspect_redis.py
```

### Query Quality Issues
```bash
# "I don't know" when it should know
→ Check if info exists in documents
→ Try increasing config_top_k (7 → 10 in config.py)
→ Check system prompt strictness (try SYSTEM_PROMPT_SHORT)

# Poor follow-up question handling
→ Check Redis memory (python scripts/inspect_redis.py)
→ Verify conversation_ttl hasn't expired (30 min default)
→ Clear stale conversations: python scripts/inspect_redis.py

# Hallucinations or made-up info
→ Current prompt is strict, shouldn't happen
→ Check Supabase logs to see which chunks were retrieved
→ Report issue with query + response for investigation
```

### Performance Issues
```bash
# Slow responses (>3 seconds)
→ First query is always slower (cold start)
→ Check OpenAI API status: https://status.openai.com
→ Check Pinecone status: https://status.pinecone.io
→ Review response_time_ms in Supabase logs

# Rate limit errors
→ Default: 20/min per user, 60/min per IP
→ Adjust in backend/routes/query.py if needed
→ Check legitimate usage patterns in Supabase
```

### Supabase Logging Issues
```bash
# Queries not appearing in Supabase
→ Check if using test_query.py (it doesn't log)
→ Verify SUPABASE credentials in .env
→ Check backend logs for "supabase_logging_failed"
→ Test direct API call: curl http://localhost:8000/api/query

# Table doesn't exist
→ Re-run table creation SQL in Supabase SQL Editor
→ Check RLS policies allow service_role access
```

---

## Analytics & Monitoring

### Query Analytics (Supabase)

**View recent queries:**
```sql
SELECT created_at, user_id, question, has_answer, response_time_ms
FROM query_logs
ORDER BY created_at DESC
LIMIT 100;
```

**Success rate by configuration:**
```sql
SELECT 
    config_top_k,
    config_temperature,
    COUNT(*) as queries,
    AVG(CASE WHEN has_answer THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
    AVG(response_time_ms) as avg_response_ms
FROM query_logs
GROUP BY config_top_k, config_temperature
ORDER BY success_rate DESC;
```

**Most asked questions:**
```sql
SELECT question, COUNT(*) as count
FROM query_logs
GROUP BY question
ORDER BY count DESC
LIMIT 20;
```

**User activity:**
```sql
SELECT user_id, COUNT(*) as queries, MAX(created_at) as last_query
FROM query_logs
GROUP BY user_id
ORDER BY queries DESC;
```

### System Health
```bash
# Check all components
python scripts/system_status.py

# Check specific components
curl http://localhost:8000/api/health  # Backend health
curl http://localhost:8000/api/stats   # System statistics
```

---

## Cost Tracking

### Current Costs (Real Data)

**Per Query Average:**
- Embedding: ~$0.0001 (cached in Pinecone)
- LLM (GPT-4o-mini): ~$0.0002-0.0004
- Pinecone: $0 (free tier)
- Redis: $0 (free tier)
- Supabase: $0 (free tier)
- **Total: ~$0.0003-0.0005 per query**

**Monthly (1000 queries/restaurant, 40 restaurants):**
- OpenAI API: €15-25/month
- Pinecone: €0 (free tier covers 40K restaurants)
- Redis: €0 (free tier sufficient)
- Supabase: €0-5 (free tier probably sufficient)
- Twilio WhatsApp: €10-15/month (future)
- Hosting: €5-10/month (future)
- **Total: €20-30/month current, €40-60/month with WhatsApp**

**Track costs in Supabase:**
```sql
-- Estimated OpenAI cost per query
SELECT 
    AVG((prompt_tokens * 0.15 + completion_tokens * 0.60) / 1000000) as avg_cost_usd,
    SUM((prompt_tokens * 0.15 + completion_tokens * 0.60) / 1000000) as total_cost_usd
FROM query_logs
WHERE prompt_tokens IS NOT NULL;
```

---

## Development Roadmap

### ✅ Phase 1-3: Foundation (Complete)
- [x] Document ingestion (DOCX via LlamaIndex)
- [x] Vector storage (Pinecone Serverless)
- [x] RAG query system (LlamaIndex + custom orchestration)
- [x] Conversation memory (Redis Cloud)
- [x] Context-aware questions (question transformation)
- [x] Speed optimization (GPT-4o-mini)

### ✅ Phase 4: Production Features (Complete)
- [x] Structured logging (structlog with JSON output)
- [x] Query logging to Supabase (comprehensive analytics)
- [x] Configuration tracking (A/B testing infrastructure)
- [x] System prompt versioning (v1.1-short active)
- [x] Rate limiting (20/min user, 60/min IP)
- [x] Retry logic (automatic recovery from failures)
- [x] Input sanitization (security + cost control)
- [x] FastAPI REST API (production-ready)
- [x] Gradio web interface (testing + demos)

### ⏳ Phase 5: WhatsApp Integration (Next - 4-6 hours)
- [ ] Twilio account setup
- [ ] Webhook endpoint (/api/webhook)
- [ ] Message handling & formatting
- [ ] User authentication (phone whitelist)
- [ ] Testing with real phone numbers

### ⏳ Phase 6: Production Deployment (After WhatsApp - 2-3 hours)
- [ ] Deploy to Railway/Render
- [ ] Environment variables setup
- [ ] SSL/HTTPS configuration
- [ ] Domain setup (optional)
- [ ] Monitoring & alerts

### 🔮 Phase 7: Scale & Polish (Optional)
- [ ] Redis query caching (40-60% cost reduction)
- [ ] Multi-restaurant support (separate namespaces)
- [ ] Analytics dashboard (Streamlit/React)
- [ ] Admin panel (user management)
- [ ] Full rollout (40 restaurants)

---

## Key Design Decisions

1. **LlamaIndex over pure OpenAI**: Industry-standard RAG framework, battle-tested
2. **GPT-4o-mini over GPT-4o**: 16x cheaper, 5x faster, quality sufficient for our use case
3. **Supabase over custom DB**: Auto-generated API, RLS security, free tier generous
4. **structlog over basic logging**: JSON output, production-ready, easy to parse
5. **FastAPI over Flask**: Async support, auto-generated docs, modern Python
6. **Redis over in-memory**: Persistent, multi-user, auto-cleanup, rate limiting support
7. **Retry logic over fail-fast**: Better UX, handles transient failures gracefully
8. **Configuration tracking**: Essential for A/B testing and optimization
9. **System prompt versioning**: Track which prompt performs best with real data

---

## Important Files to Edit

**To change bot behavior:**
- `src/query/system_prompt.py` - Edit prompts and switch active version

**To tune performance:**
- `src/config.py` - Adjust chunk_size, top_k, temperature, etc.

**To add documents:**
- `data/` folder - Add .docx files
- Run: `python scripts/run_ingestion.py`

**To modify API:**
- `backend/routes/query.py` - Add endpoints or modify logic
- `backend/main.py` - Configure CORS, middleware, lifespan

**To customize frontend:**
- `frontend/gradio_app.py` - Modify Gradio interface

---

## Testing

### Unit Testing (Future)
```bash
pytest tests/
```

### Integration Testing
```bash
# Test full pipeline
python scripts/test_query.py

# Test API endpoints
curl http://localhost:8000/api/health
curl http://localhost:8000/api/stats
```

### Load Testing (Future)
```bash
# Use locust or similar
locust -f tests/load_test.py
```

---

## Security

**Implemented:**
- ✅ Input sanitization (500 char limit, injection protection)
- ✅ Rate limiting (abuse prevention)
- ✅ Supabase RLS (row-level security)
- ✅ Service role key (server-side only, never exposed)
- ✅ Environment variables (no hardcoded secrets)
- ✅ CORS configuration (controlled access)

**Recommendations for production:**
- Use HTTPS (SSL/TLS)
- Rotate API keys regularly
- Monitor Supabase logs for suspicious activity
- Set up alerts for rate limit violations
- Use WhatsApp phone whitelist (only authorized numbers)

---

## Support & Maintenance

**Logs:**
- Backend logs: Console output (JSON format)
- Query logs: Supabase → Table Editor → `query_logs`
- Redis conversations: `python scripts/inspect_redis.py`

**Common Maintenance Tasks:**
- Add documents: Place in `data/` → run `python scripts/run_ingestion.py`
- Update prompt: Edit `system_prompt.py` → change `ACTIVE_SYSTEM_PROMPT`
- Clear conversations: `python scripts/inspect_redis.py` → confirm yes
- Analyze performance: Query Supabase `query_logs` table

---

## License

Internal use only - Yamie PastaBar Franchise

---

## Changelog

**v0.8.0 (2026-01-08) - Production Features Complete**
- ✅ Added Supabase query logging with configuration tracking
- ✅ Implemented system prompt versioning (v1.1-short active)
- ✅ Added rate limiting (fastapi-limiter)
- ✅ Implemented retry logic (tenacity)
- ✅ Enhanced input sanitization
- ✅ Structured logging with structlog
- ✅ FastAPI REST API with auto-generated docs
- ✅ Gradio web interface

**v0.6.0 (2025-01-07) - Conversation Memory**
- ✅ Redis Cloud integration
- ✅ Context-aware follow-up questions
- ✅ Question transformation with conversation history

**v0.5.0 (2024-12-31) - Speed Optimization**
- ✅ Switched to GPT-4o-mini (5x faster, 16x cheaper)
- ✅ Response time: ~1.3 seconds

**v0.4.0 (2024-12-28) - LlamaIndex Integration**
- ✅ Migrated to LlamaIndex framework
- ✅ Improved retrieval quality

**v0.1.0 (2024-12-20) - Initial Core**
- ✅ Document ingestion (DOCX)
- ✅ Vector storage (Pinecone)
- ✅ Basic RAG pipeline

---

**Last Updated:** January 8, 2026  
**Status:** Production features complete, ready for WhatsApp integration  
**Next Milestone:** WhatsApp integration via Twilio 🚀  
**Current Version:** v0.8.0