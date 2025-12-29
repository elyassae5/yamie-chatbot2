# YamieBot - Internal RAG Assistant

Production-grade RAG chatbot for Smokey Joe's franchise staff in the Netherlands.

## What It Does

Staff ask questions about franchise operations, training protocols, procedures, and company policies. YamieBot answers instantly using the internal franchise manual - no waiting for managers or trainers.

**Example**:
- Q: "Wie is Daoud en wat doet hij?"
- A: "Daoud is verantwoordelijk voor managementondersteuning en is betrokken bij personeel of managementkwesties. 📄 [smokey_joes_interne_franchisehandleiding.docx]"

## Current Status

**Phase**: Core system complete ✅ - Ready for feature additions  
**Progress**: ~50% complete (5/10 phases)  
**Timeline**: 3-4 weeks to WhatsApp rollout

### Completed ✅
- ✅ Document ingestion (DOCX support)
- ✅ Vector retrieval system (Pinecone)
- ✅ Answer generation (GPT-4o)
- ✅ Production-ready logging
- ✅ Code refactored and optimized
- ✅ Real franchise data ingested

### Next Steps 🎯
1. Add query logging (database tracking)
2. Implement Redis caching (40-60% cost reduction)
3. Add conversation memory
4. Build WhatsApp integration
5. Deploy to production

## Tech Stack

**Core RAG:**
- **Embeddings**: OpenAI text-embedding-3-large (3072 dims)
- **Vector DB**: Pinecone Serverless (cosine similarity)
- **LLM**: GPT-4o (temp: 0.2)
- **Chunking**: 500 tokens, 150 overlap

**Infrastructure:**
- **Language**: Python 3.10+
- **Framework**: LlamaIndex (query) + Custom (ingestion)
- **Logging**: Structured logging with file rotation
- **Config**: Dataclasses + dotenv

**Configuration:**
- Chunk size: 500 tokens (optimized for franchise manual)
- Chunk overlap: 150 tokens
- Top-k retrieval: 7 chunks
- Temperature: 0.2 (factual responses)
- Max tokens: 600

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment
```bash
cp .env.example .env
# Add your API keys to .env:
# - OPENAI_API_KEY=your_key_here
# - PINECONE_API_KEY=your_key_here
# - PINECONE_INDEX_NAME=yamie-test
```

### 3. Add Documents
```bash
# Place your DOCX/PDF files in the data/ folder
cp your_document.docx data/
```

### 4. Ingest Documents
```bash
python scripts/run_ingestion.py
# Logs saved to: logs/yamiebot_YYYYMMDD_HHMMSS.log
```

### 5. Test the System
```bash
python scripts/test_query.py
# Choose option 2 for interactive mode
# Type 'debug' to see retrieved chunks
```

## Project Structure
```
yamie-chatbot/
├── data/                           # Document storage
│   └── *.docx
├── logs/                           # Application logs (auto-generated)
│   └── yamiebot_YYYYMMDD_HHMMSS.log
├── src/
│   ├── config.py                   # Central configuration
│   ├── logging_config.py           # Logging setup
│   ├── ingestion/                  # Document processing
│   │   ├── loader.py              # DOCX/PDF loading
│   │   ├── chunker.py             # Text chunking
│   │   ├── vector_store.py        # Pinecone integration
│   │   └── pipeline.py            # Ingestion orchestrator
│   └── query/                      # RAG query system
│       ├── models.py              # Data models
│       ├── prompts.py             # LLM prompts
│       ├── retriever.py           # Vector search
│       ├── responder.py           # LLM generation
│       └── engine.py              # Query orchestrator
├── scripts/
│   ├── run_ingestion.py           # Ingest documents
│   ├── test_query.py              # Interactive testing
│   ├── test_suite.py              # Batch testing
│   └── system_status.py           # Health check
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Usage

### Ingestion (When Documents Change)
```bash
# Ingest new documents
python scripts/run_ingestion.py

# View system health
python scripts/system_status.py

# Run with debug logging
# Edit scripts/run_ingestion.py: level="DEBUG"
```

### Querying (Testing)
```bash
# Interactive mode (recommended)
python scripts/test_query.py
# Choose option 2, ask questions, type 'quit' to exit

# Batch testing
python scripts/test_suite.py
# Note: Update TEST_QUESTIONS in the script first

# Single query test
python scripts/test_query.py
# Choose option 1 for preset question
```

### Logging
```bash
# Logs are automatically saved to logs/ directory
# View latest log:
ls -lt logs/ | head -n 1

# Change log level:
# Edit scripts/run_ingestion.py or scripts/test_query.py
# Set: level="DEBUG"  (verbose) or level="INFO" (normal)
```

## Configuration

Edit `src/config.py` to tune the system:
```python
# Chunking (affects retrieval quality)
chunk_size: int = 500           # Tokens per chunk
chunk_overlap: int = 150        # Overlap between chunks

# Retrieval (affects answer quality)
query_top_k: int = 7            # Chunks to retrieve
query_similarity_threshold: float = 0.0  # Min similarity

# LLM (affects answer generation)
llm_model: str = "gpt-4o"       # OpenAI model
llm_temperature: float = 0.2    # 0=factual, 1=creative
llm_max_tokens: int = 600       # Max response length
```

## Roadmap

### Phase 1-2: Foundation ✅ (Weeks 1-4)
- [x] Project setup
- [x] Document ingestion (DOCX/PDF)
- [x] Vector storage (Pinecone)
- [x] Basic RAG query system

### Phase 3: Production Refactor ✅ (Week 5)
- [x] Real franchise data ingestion
- [x] Production-ready logging
- [x] Code refactoring (all modules)
- [x] Error handling improvements

### Phase 4: Essential Features ⏳ (Weeks 6-7)
- [ ] Query logging (PostgreSQL/Supabase)
- [ ] Redis caching (cost + speed)
- [ ] Input sanitization
- [ ] Conversation memory

### Phase 5: Integration (Weeks 8-9)
- [ ] WhatsApp integration (Twilio)
- [ ] User authentication (phone whitelist)
- [ ] Rate limiting (prevent abuse)

### Phase 6: Deployment (Week 10)
- [ ] Production deployment (Railway/AWS)
- [ ] Monitoring (Sentry)
- [ ] Backup strategy

### Phase 7: Launch (Week 11+)
- [ ] Pilot testing (5-10 staff)
- [ ] Full rollout (all restaurants)
- [ ] Ongoing maintenance

## Cost Estimate

**Development (Current)**: ~$10/month
- OpenAI API: ~$5/month (testing)
- Pinecone: Free tier

**Production (Estimated)**: ~$120-140/month
- OpenAI API: $25-35/month (500 queries/day)
- Pinecone: $50/month (serverless)
- Database: $10/month (PostgreSQL)
- Redis: $5/month (caching)
- Hosting: $15/month (Railway/AWS)
- Twilio: $15/month (WhatsApp)

**Cost Optimizations Planned:**
- Redis caching → 40-60% reduction
- Smaller embedding model → 6.5x cheaper
- Aggressive caching → Additional 20% reduction

## Development

### Testing
```bash
# Health check
python scripts/system_status.py

# Interactive testing
python scripts/test_query.py

# Batch testing (update questions first)
python scripts/test_suite.py

# Test logging system
python -m src.logging_config
```

### Debugging
```bash
# Enable debug logs
# Edit script file, change: level="DEBUG"

# View retrieval chunks
# In test_query.py interactive mode, type: debug

# Check Pinecone stats
python scripts/system_status.py
```

## Troubleshooting

### Ingestion Issues
```bash
# Error: "No documents found"
→ Check files are in data/ folder
→ Verify file extensions (.docx, .pdf)

# Error: "Pinecone namespace empty"
→ Run: python scripts/run_ingestion.py
→ Wait for completion

# Error: "Vector ID must be ASCII"
→ Rename files to remove special characters
```

### Query Issues
```bash
# Error: "Index not found"
→ Run ingestion first

# Error: "No chunks retrieved"
→ Check namespace in config.py matches ingestion
→ Verify documents were ingested successfully

# Poor answers
→ Increase top_k in config.py
→ Adjust chunk_size (try 512 or 768)
→ Check if information actually in documents
```

## Support

- **Issues**: Check logs/ directory for error details
- **Questions**: Review this README and QUICK_REFERENCE.md
- **Logs**: All operations logged to logs/ with timestamps

## License

Internal use only - Smokey Joe's Franchise