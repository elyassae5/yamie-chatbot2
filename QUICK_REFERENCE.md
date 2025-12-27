# ⚡ YamieBot Quick Reference Guide

**Your "Oh Shit" Manual - Everything You Need in One Place**

---

## 🎯 QUICK START (Right Now)

### 1️⃣ Check Current System Status
```bash
python scripts/system_status.py
```
**Shows**: What PDFs are loaded, how many vectors in Pinecone, config settings

### 2️⃣ Test the Chatbot
```bash
# Single question test
python scripts/test_query.py

# Full test suite (20 questions)
python scripts/test_suite.py
```

### 3️⃣ Demo for Uncle
```bash
python scripts/demo.py
# Choose option 1 (Uncle Demo)
```

---

## 📁 FILE LOCATIONS (Where Everything Lives)

```
yamie-chatbot-main/
│
├── 📂 data/                    ← PUT PDFS HERE
│   └── *.pdf                   ← Your documents
│
├── 📂 src/
│   ├── config.py               ← CHANGE SETTINGS HERE
│   │   • Line 25-26: Chunk size/overlap
│   │   • Line 29-30: Retrieval settings (top_k)
│   │   • Line 33-35: LLM settings (model, temp, tokens)
│   │
│   └── query/
│       └── prompts.py          ← CHANGE SYSTEM PROMPT HERE
│           • Line 18-52: System prompt (bilingual)
│           • Line 148-155: Confidence thresholds
│
├── 📂 scripts/
│   ├── system_status.py        ← Check system health
│   ├── run_ingestion.py        ← Ingest PDFs → Pinecone
│   ├── test_query.py           ← Test single question
│   ├── test_suite.py           ← Test 20 questions
│   └── demo.py                 ← Demo for uncle
│
└── .env                        ← API KEYS HERE (create from .env.example)
    OPENAI_API_KEY=sk-...
    PINECONE_API_KEY=...
    PINECONE_INDEX_NAME=yamie-test
```

---

## 🔧 COMMON TASKS

### ✅ Add New PDFs
1. Copy PDFs to `data/` folder
2. Run: `python scripts/run_ingestion.py`
3. Wait ~1 minute per PDF
4. Verify: `python scripts/system_status.py`

### ✅ Replace All Data (Test → Real)
1. Delete all files in `data/` folder
2. Copy real PDFs to `data/` folder
3. Run: `python scripts/run_ingestion.py`
4. Test: `python scripts/test_query.py`

### ✅ Test a Question
```python
# Edit scripts/test_query.py line 29
question = "Your question here"

# Run
python scripts/test_query.py
```

### ✅ Change System Prompt
1. Open `src/query/prompts.py`
2. Edit lines 18-52 (SYSTEM_PROMPT variable)
3. No need to re-ingest, just re-run queries
4. Test: `python scripts/test_query.py`

### ✅ Adjust Retrieval Settings
```python
# src/config.py

# Retrieve more chunks (if answers are incomplete)
query_top_k: int = 10  # Default: 5

# Lower similarity threshold (if getting "don't know" too often)
query_similarity_threshold: float = 0.0  # Default: 0.0 (disabled)
```

---

## 🚨 TROUBLESHOOTING

### ❌ "OPENAI_API_KEY missing"
**Fix**: Create `.env` file in project root:
```
OPENAI_API_KEY=sk-proj-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=yamie-test
```

### ❌ "No documents found in ./data"
**Fix**: Make sure PDFs are in `data/` folder
```bash
# Check if files exist
ls data/

# Should show .pdf files
```

### ❌ "Pinecone index 'yamie-test' not found"
**Fix**: Run ingestion to create it:
```bash
python scripts/run_ingestion.py
```

### ❌ "Namespace 'documents' is empty (0 vectors)"
**Fix**: Run ingestion to populate:
```bash
python scripts/run_ingestion.py
```

### ❌ Answers are wrong or "I don't know" too often
**Causes**:
1. PDFs are scanned images (not searchable text)
2. Retrieval not finding right chunks
3. Chunks too small/large
4. Similarity threshold too high

**Fixes**:
```bash
# 1. Check PDF text
# Open PDF, try to copy text. If you can't → scanned image

# 2. Increase top_k to retrieve more chunks
# Edit src/config.py line 29
query_top_k: int = 10

# 3. Check what chunks are being retrieved
# Use inspect mode (we'll create this)
```

### ❌ Answers are hallucinating (making stuff up)
**Fix**: Check system prompt is strong enough:
```python
# src/query/prompts.py should have:
"NEVER make up information"
"NEVER use knowledge outside the provided context"
"If answer not in documents, say you don't know"
```

### ❌ Slow responses (>5 seconds)
**Causes**:
1. Large chunk size → slow embedding
2. Too many chunks retrieved (top_k too high)
3. OpenAI API slow

**Fixes**:
```python
# Reduce top_k
query_top_k: int = 3  # From 5

# Use smaller embedding model (trade quality for speed)
embedding_model: str = "text-embedding-3-small"  # From 3-large
```

---

## ⚙️ KEY CONFIGURATION SETTINGS

### Location: `src/config.py`

| Setting | Default | What It Does | When to Change |
|---------|---------|--------------|----------------|
| `chunk_size` | 1024 | Tokens per chunk | If chunks cut off mid-thought (increase) or too long (decrease) |
| `chunk_overlap` | 250 | Overlap between chunks | If context is lost across chunks (increase) |
| `query_top_k` | 5 | Chunks retrieved per query | If answers incomplete (increase to 10) |
| `llm_temperature` | 0.1 | Creativity (0=factual, 1=creative) | Keep at 0.1 for factual answers |
| `llm_max_tokens` | 500 | Max answer length | If answers cut off (increase to 800) |

---

## 📊 UNDERSTANDING OUTPUT

### Query Response Fields
```python
response = engine.query("What pasta do you have?")

response.answer           # The actual answer text
response.has_answer       # True/False - did it find answer?
response.confidence       # "high", "medium", "low"
response.sources          # List of chunks used
response.response_time    # How long it took (seconds)
```
---

## 🎬 DEMO CHECKLIST (For Uncle)

### Before Demo
- [ ] Run `python scripts/system_status.py` - verify all OK
- [ ] Run `python scripts/test_suite.py` - check pass rate >60%
- [ ] Test 3-5 questions manually
- [ ] Know which questions work well
- [ ] Have backup plan if something breaks

### During Demo
1. Start: `python scripts/demo.py` → Choose option 1
2. Let it run through 5 pre-loaded questions
3. Explain each answer and source citation
4. Show conversation log after

### What to Highlight
- ✅ "Works in both Dutch and English"
- ✅ "Always cites which document it used"
- ✅ "Says 'I don't know' if info not in docs (no making stuff up)"
- ✅ "Fast responses (<2 seconds)"
- ✅ "Can handle menu, HR, operations, equipment questions"

---

## 🔄 WORKFLOW SUMMARY

### Daily Use (After Production)
```
1. User asks question (WhatsApp)
2. System retrieves relevant chunks from Pinecone
3. GPT-4o generates answer based on chunks
4. User gets answer with sources
```

### Adding New Documents
```
1. Put PDF in data/ folder
2. Run: python scripts/run_ingestion.py
3. New data instantly available for queries
```

### Testing Changes
```
1. Make change (prompt, config, etc.)
2. Run: python scripts/test_query.py
3. If good → commit
4. If bad → revert
```

---

## 💾 BACKUP STRATEGY

### Before Making Changes
```bash
# 1. Backup current PDFs
mkdir -p backups
cp data/*.pdf backups/

# 2. Save current status
python scripts/system_status.py > backups/status.txt

# 3. Make changes

# 4. If it breaks, restore:
cp backups/*.pdf data/
python scripts/run_ingestion.py
```

---

## 📞 EMERGENCY CONTACTS

### If API Stops Working
1. Check OpenAI status: https://status.openai.com/
2. Check Pinecone status: https://status.pinecone.io/
3. Check API key is valid
4. Check billing (OpenAI requires credits)

### If Everything Breaks
```bash
# Nuclear option: Start from scratch
rm -rf data/*.pdf
cp backups/test_data/*.pdf data/
python scripts/run_ingestion.py
python scripts/test_query.py
```

---

## 🎓 KEY CONCEPTS

### What is RAG?
**R**etrieval **A**ugmented **G**eneration
1. Retrieve relevant chunks from your documents
2. Augment the question with those chunks
3. Generate answer using LLM (GPT-4o)

### Why Not Fine-Tuning?
- Fine-tuning = Expensive, slow, needs lots of data
- RAG = Flexible, fast, works with small datasets
- You can update docs instantly without retraining

### What Are Embeddings?
- Turn text into numbers (vectors)
- Similar meanings → similar numbers
- "Pasta Carbonara" and "Carbonara pasta" have similar embeddings
- That's how we find relevant chunks

### What is Pinecone?
- Database for storing embeddings
- Finds similar vectors super fast (milliseconds)
- Like Google for your documents

---

## 📝 NOTES FOR LATER

### Phase 2 (After Uncle Approves)
- [ ] Add conversation memory (multi-turn dialogue)
- [ ] Implement user management (phone whitelist)
- [ ] WhatsApp integration
- [ ] Logging to database
- [ ] Monitoring

### Phase 3 (Production)
- [ ] Deploy to Railway/AWS
- [ ] Set up monitoring
- [ ] Add rate limiting
- [ ] Train staff on usage
- [ ] Collect feedback

---

## ✅ FINAL CHECKLIST (Before Meeting Uncle)

**System Health**:
- [ ] `system_status.py` shows all green
- [ ] At least 3 PDFs in `data/` folder
- [ ] Pinecone has vectors
- [ ] Test query works

**Testing**:
- [ ] Ran test suite (pass rate >60%)
- [ ] Tested 5 questions manually
- [ ] Know which questions work best
- [ ] Demo script ready

**Preparation**:
- [ ] Know how to explain RAG in simple terms
- [ ] Can show answer + sources clearly
- [ ] Have backup plan if demo breaks
- [ ] Saved conversation log for review

---

**Remember**: Keep it simple. Uncle doesn't need to know about embeddings or Pinecone. Just show:
1. Ask question → Get answer → See source
2. Works in Dutch and English
3. Fast and accurate
4. Safe (no hallucinations)

**You got this!** 🚀
