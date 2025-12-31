# YamieBot - Internal RAG Assistant

AI-powered chatbot for Yamie PastaBar franchise staff in the Netherlands. Get instant answers about company policies, procedures, and operations from internal documents.

## What It Does

Staff ask questions about franchise operations via WhatsApp (future) or command-line (current). YamieBot searches internal documents and provides accurate, cited answers instantly.

**Example:**
```
Q: "Wie is Daoud en wat doet hij?"
A: "Daoud is verantwoordelijk voor managementondersteuning en wordt ingeschakeld 
    bij personeels- of managementproblemen. 📄 [smokey_joes_interne_franchisehandleiding.docx]"
```

**Features:**
- ✅ Conversation memory (remembers context for 30 minutes)
- ✅ Multi-language support (Dutch/English)
- ✅ Source citations (always shows where info came from)
- ✅ Fast responses (~1-2 seconds)
- ✅ No hallucinations (strict document grounding)

---

## Current Status

**Phase**: Core complete + Conversation memory ✅  
**Progress**: ~65% complete  
**Next**: WhatsApp integration

### Completed ✅
- ✅ Document ingestion (DOCX support)
- ✅ Vector search (Pinecone)
- ✅ Answer generation (GPT-4o-mini)
- ✅ Conversation memory (Redis Cloud)
- ✅ Context-aware follow-up questions
- ✅ Production logging
- ✅ Optimized for speed & cost

### In Progress 🚧
- ⏳ Query logging to database
- ⏳ WhatsApp integration (Twilio)
- ⏳ Redis caching for speed
- ⏳ Production deployment

---

## Tech Stack

**Core RAG:**
- **Embeddings**: OpenAI text-embedding-3-large (3072 dims)
- **Vector DB**: Pinecone Serverless
- **LLM**: GPT-4o-mini (fast + cheap)
- **Memory**: Redis Cloud (conversation history)
- **Chunking**: 600 chars, 200 overlap

**Configuration:**
- Top-k retrieval: 6 chunks
- Temperature: 0.1 (factual)
- Max tokens: 400
- Response time: ~1.3 seconds
- Conversation memory: 10 turns, 30min TTL

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

# Redis Cloud (conversation memory)
REDIS_HOST=redis-xxxxx.ec2.cloud.redislabs.com
REDIS_PORT=10098
REDIS_PASSWORD=your_redis_password
```

### 3. Add Documents
```bash
# Place DOCX files in data/ folder
cp your_document.docx data/
```

### 4. Ingest Documents
```bash
python scripts/ingest.py
```

### 5. Test the Bot
```bash
# Interactive testing (recommended)
python scripts/test_query.py
# Choose option 2 for interactive mode
# Type 'reset' to clear conversation memory
# Type 'quit' to exit
```

---

## Project Structure

```
yamie-chatbot/
├── data/                           # Documents to ingest
│   └── *.docx
├── logs/                           # Application logs
├── src/
│   ├── config.py                   # Central configuration
│   ├── logging_config.py           # Logging setup
│   ├── ingestion/                  # Document processing
│   │   ├── document_processor.py  # DOCX processing
│   │   └── vector_store.py        # Pinecone integration
│   ├── query/                      # RAG query system
│   │   ├── engine.py              # Main orchestrator + memory
│   │   ├── retriever.py           # Vector search
│   │   ├── responder.py           # Answer generation
│   │   ├── prompts.py             # Prompt construction
│   │   ├── system_prompt.py       # Bot behavior (EDIT THIS!)
│   │   └── models.py              # Data models
│   └── memory/                     # Conversation memory
│       └── conversation_memory.py # Redis integration
├── scripts/
│   ├── ingest.py                  # Ingest documents
│   ├── test_query.py              # Interactive testing
│   ├── inspect_redis.py           # View conversations
│   └── system_status.py           # Health check
├── .env                            # API keys (create this!)
├── requirements.txt                # Dependencies
└── README.md                       # This file
```

---

## Usage

### Testing (Interactive Mode)
```bash
python scripts/test_query.py

# Commands available:
# - Type your question normally
# - Type 'reset' to clear conversation memory
# - Type 'quit' to exit
```

**Example conversation:**
```
Your question: Wie is Daoud?
Bot: Daoud is verantwoordelijk voor managementondersteuning...

Your question: Wat zijn zijn taken?
Bot: [Understands "zijn" refers to Daoud from context]

Your question: reset
Bot: [Conversation memory cleared]
```

### Ingestion (When Documents Change)
```bash
# Re-ingest all documents
python scripts/ingest.py

# Check system health
python scripts/system_status.py
```

### Redis/Memory Management
```bash
# View stored conversations
python scripts/inspect_redis.py

# Clear all conversations
python scripts/inspect_redis.py
# Type: yes (when prompted)
```

---

## Configuration

Edit `src/config.py` to tune performance:

```python
# Chunking (affects retrieval quality)
chunk_size: int = 600           # Characters per chunk
chunk_overlap: int = 200        # Overlap between chunks

# Retrieval (affects answer quality)
query_top_k: int = 6            # Number of chunks to retrieve

# LLM (affects response quality)
llm_model: str = "gpt-4o-mini"  # Fast + cheap model
llm_temperature: float = 0.1    # Low = factual
llm_max_tokens: int = 400       # Response length

# Memory (affects conversation context)
max_conversation_turns: int = 10        # Turns to store
conversation_ttl_seconds: int = 1800    # 30 minutes
```

### System Prompt (Bot Behavior)

Edit `src/query/system_prompt.py` to change how the bot responds:
```python
SYSTEM_PROMPT_SHORT = """Your instructions here..."""
```

**This file controls:**
- How the bot interprets questions
- When it says "I don't know"
- How it handles follow-up questions
- Citation behavior

---

## Architecture

### How It Works

```
User asks question
    ↓
[1] Load conversation history (Redis)
    ↓
[2] Transform vague questions into clear queries
    Example: "What about that?" → "What about vacation days?"
    ↓
[3] Search document chunks (Pinecone)
    Retrieves top 6 most relevant chunks
    ↓
[4] Generate answer with context (GPT-4o-mini)
    Uses: conversation history + retrieved chunks + original question
    ↓
[5] Save Q&A to memory (Redis)
    Auto-expires after 30 minutes
    ↓
Return answer with source citations
```

### Conversation Memory

**How it works:**
- Each user gets unique conversation (by `user_id`)
- Stores last 10 Q&A pairs
- Auto-deletes after 30 minutes of inactivity
- Used for context-aware follow-ups

**Example:**
```
Turn 1: "Wie is Daoud?" → Bot explains
Turn 2: "Wat zijn zijn taken?" → Bot knows "zijn" = Daoud's
Turn 3: "Vertel me meer" → Bot knows what "more" refers to
```

---

## Troubleshooting

### Ingestion Issues
```bash
# No documents found
→ Check files are in data/ folder
→ Verify .docx extension

# Pinecone errors
→ Check PINECONE_API_KEY in .env
→ Verify index exists (check Pinecone dashboard)
```

### Query Issues
```bash
# "Index not found"
→ Run ingestion first: python scripts/ingest.py

# Poor quality answers
→ Increase query_top_k in config.py (try 8-10)
→ Check if info actually exists in documents

# "I don't know" when it should know
→ Try rephrasing question
→ Check system_prompt.py (might be too strict)
```

### Redis/Memory Issues
```bash
# Connection errors
→ Check REDIS_HOST, REDIS_PORT, REDIS_PASSWORD in .env
→ Test: python scripts/inspect_redis.py

# Conversations not saving
→ Check Redis connection
→ Verify user_id is being passed correctly

# Old conversations interfering
→ Run: python scripts/inspect_redis.py
→ Clear all conversations when prompted
```

---

## Development Roadmap

### Phase 1-3: Foundation ✅ (Complete)
- [x] Document ingestion (DOCX)
- [x] Vector storage (Pinecone)
- [x] RAG query system
- [x] Conversation memory (Redis)
- [x] Context-aware questions
- [x] Speed optimization (GPT-4o-mini)

### Phase 4: Essential Features ⏳ (Current)
- [ ] Query logging (database tracking)
- [ ] Redis caching (speed + cost)
- [ ] Input sanitization
- [ ] Rate limiting

### Phase 5: WhatsApp Integration (Next)
- [ ] Twilio webhook setup
- [ ] Message handling
- [ ] Phone number routing
- [ ] User authentication

### Phase 6: Production Deployment
- [ ] Deploy to Railway/Render
- [ ] Environment setup
- [ ] Monitoring (Sentry)
- [ ] SSL/HTTPS

### Phase 7: Scale & Polish
- [ ] Multi-restaurant support
- [ ] Analytics dashboard
- [ ] Admin panel
- [ ] Full rollout (20 restaurants)

---

## Cost Estimate

**Current (Development):** ~€5/month
- OpenAI API: ~€3/month
- Pinecone: Free tier
- Redis: Free tier

**Production (20 Restaurants, 1000 queries/restaurant/month):**
- OpenAI API: €15-25/month
- Pinecone: €0-70/month (likely free tier)
- Redis Cloud: €0/month (free tier)
- Twilio WhatsApp: €10-15/month
- Hosting: €5-15/month
- **Total: €40-60/month realistic**
- **Per restaurant: €2-3/month**
- **Per query: €0.002-0.005**

**Optimization opportunities:**
- Redis caching → 40-60% cost reduction
- Aggressive prompt caching → 20% additional reduction

---

## Testing Commands

```bash
# Interactive testing (main use)
python scripts/test_query.py

# Check system health
python scripts/system_status.py

# View Redis conversations
python scripts/inspect_redis.py

# Re-ingest documents
python scripts/ingest.py
```

---

## Performance

**Current Metrics:**
- Response time: ~1.3 seconds (query processing only)
- First query: ~3s (cold start, one-time)
- Subsequent queries: ~1.5s (warm connections)
- Quality: No hallucinations with current prompt
- Context retention: 10 turns, 30 minutes

**Optimization Status:**
- ✅ Model: GPT-4o-mini (16x cheaper than GPT-4o)
- ✅ Embeddings: text-embedding-3-large (best quality)
- ✅ Chunking: Optimized (600 chars, 200 overlap)
- ⏳ Caching: Not yet implemented

---

## Key Design Decisions

1. **GPT-4o-mini over GPT-4o**: 16x cheaper, 5x faster, quality sufficient
2. **Redis over in-memory**: Persistent, multi-user, auto-cleanup
3. **Custom code over LangChain**: Full control, easier debugging
4. **Terminal testing over UI**: No caching issues, production-like
5. **Separate system_prompt.py**: Easy iteration without breaking code

---

## Important Files to Edit

**To change bot behavior:**
- `src/query/system_prompt.py` - Edit `SYSTEM_PROMPT_SHORT`

**To tune performance:**
- `src/config.py` - Adjust chunk_size, top_k, temperature, etc.

**To add documents:**
- `data/` folder - Add .docx files, then run `python scripts/ingest.py`

---

## Support

- **Logs**: Check `logs/` directory for detailed error info
- **Issues**: Review troubleshooting section above
- **Redis**: Use `inspect_redis.py` to debug conversations

---

## License

Internal use only - Yamie PastaBar Franchise

---

**Last Updated:** December 31, 2024  
**Status:** Core system complete, conversation memory working  
**Next Milestone:** WhatsApp integration 🚀