# YamieBot - Internal Assistant

Internal RAG-based chatbot for Yamie Pastabar staff in the Netherlands.

## What It Does

Staff ask questions about company policies, procedures, menu items, and equipment maintenance. YamieBot answers instantly using company documents - no waiting for managers.

**Example**:
- Q: "Hoe sluit ik de kassa af?"
- A: "Om de kassa af te sluiten: 1. Sluit alle tabs af, 2. Voer rapporten uit..." (Source: sop_operations.pdf)

## Status

**Current**: Production-ready RAG core ✅  
**Next**: Real data ingestion
**Timeline**: 2-3 weeks to WhatsApp rollout

## Tech Stack

- **Embeddings**: OpenAI text-embedding-3-large
- **Vector DB**: Pinecone Serverless
- **LLM**: GPT-4o
- **Chunking**: 256 tokens, 64 overlap

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add your API keys to .env

# Ingest documents
python scripts/run_ingestion.py

# Test the system
python scripts/test_query.py
```

## Project Structure
```
├── data/              # PDF documents
├── src/
│   ├── ingestion/     # Document processing
│   └── query/         # RAG query engine
├── scripts/           # Testing & demo tools
└── .env               # API keys
```

## Development

- `python scripts/system_status.py` - Check system health
- `python scripts/test_suite.py` - Run 20 test questions
- `python scripts/demo.py` - Interactive demo

## Roadmap

- [x] Document ingestion pipeline
- [x] Core RAG system
- [x] Testing infrastructure
- [ ] Real data migration 
- [ ] Conversation memory
- [ ] WhatsApp integration
- [ ] Production deployment

## License

Internal use only - Yamie Pastabar