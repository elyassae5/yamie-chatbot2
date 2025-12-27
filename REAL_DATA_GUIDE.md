# 🔄 Real Data Migration Guide

**When**: Your uncle gives you real PDFs  
**Goal**: Replace test data with real data safely  
**Time**: ~10 minutes

---

## 📋 CHECKLIST

### ✅ Before You Start
- [ ] You have the real PDFs from your uncle
- [ ] Your .env file has valid API keys
- [ ] You've tested the system with test data (run `python scripts/system_status.py`)

### ✅ After Migration
- [ ] Real PDFs are in `data/` folder
- [ ] Pinecone has new vectors (check with `system_status.py`)
- [ ] Test queries work with real data
- [ ] Save test results for your uncle

---

## 🚀 STEP-BY-STEP PROCESS

### **Step 1: Backup Current State** (Optional but recommended)

```bash
# Create backup folder
mkdir -p backups/test_data

# Copy current test PDFs
cp data/*.pdf backups/test_data/

# Save current Pinecone stats
python scripts/system_status.py > backups/test_data/status_before.txt
```

**Why**: In case something goes wrong, you can restore test data.

---

### **Step 2: Clear Test Data from `data/` Folder**

```bash
# Windows (PowerShell)
Remove-Item data\*.pdf

# Or manually:
# Go to yamie-chatbot-main/data/
# Delete all PDF files with (1) in the name:
#   - menu (1).pdf
#   - hr_policy (1).pdf
#   - equipment_maintenance (1).pdf
#   - sop_operations.pdf
```

**Result**: `data/` folder is empty.

---

### **Step 3: Add Real PDFs**

**Copy the real PDFs your uncle gives you into the `data/` folder.**

**Naming Tips**:
- Use descriptive names: `menu_amsterdam.pdf`, `hr_policy_2024.pdf`
- No spaces in filenames (use `_` instead)
- Keep `.pdf` extension
- Category keywords help (menu, hr, sop, equipment)

**Example structure**:
```
data/
├── menu_main.pdf              # Menu items, prices
├── hr_policy_2024.pdf         # HR policies, leave, sick days
├── sop_kitchen_operations.pdf # Standard operating procedures
├── equipment_maintenance.pdf  # Equipment manuals, cleaning
└── staff_handbook.pdf         # General staff info
```

**Critical**: Make sure PDFs are **searchable text** (not scanned images).

**How to check**:
- Open PDF in browser
- Try to select/copy text
- If you can copy text → ✅ Good
- If you can't copy text → ❌ Scanned image (needs OCR)

---

### **Step 4: Clear Old Vectors from Pinecone**

**Why**: Remove test data vectors so they don't mix with real data.

**Option A: Clear via Script** (Easiest)

```bash
# This will ask for confirmation before clearing
python scripts/run_ingestion.py
# When prompted, it will clear the namespace automatically
```

The script has `clear_existing=True` which wipes the namespace before ingesting.

**Option B: Manual Clear** (if needed)

```python
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("yamie-test")  # Your index name
index.delete(delete_all=True, namespace="documents")  # Your namespace

print("✅ Namespace cleared")
```

---

### **Step 5: Ingest Real PDFs**

```bash
# Run ingestion with real data
python scripts/run_ingestion.py
```

**What this does**:
1. Reads all PDFs from `data/` folder
2. Splits them into chunks (256 tokens each)
3. Generates embeddings for each chunk
4. Uploads to Pinecone

**Expected output**:
```
Starting YamieBot ingestion pipeline

 Config:
  Data dir: ./data
  Embedding model: text-embedding-3-large
  Chunk size: 256
  ...

 Loading documents from ./data
 Loaded 5 valid documents

Created 147 chunks

Clearing namespace 'documents'
Initializing Pinecone index: yamie-test

Embedding and storing vectors...
100%|████████████████| 147/147 [00:45<00:00,  3.22it/s]

Ingestion complete
Documents processed: 5
Chunks created: 147
Duration: 47.32s
```

**Troubleshooting**:
- **Error: "No documents found"** → Check PDFs are in `data/` folder
- **Error: "Empty documents"** → PDFs might be scanned images (need OCR)
- **Error: "OpenAI API error"** → Check API key and credit balance

---

### **Step 6: Verify Real Data is Loaded**

```bash
# Check system status
python scripts/system_status.py
```

**Look for**:
- ✅ New PDFs listed under "DATA FILES"
- ✅ Vector count increased in Pinecone
- ✅ Estimated documents matches number of PDFs

**Expected**:
```
📁 DATA FILES

Found 5 PDF files:

  1. menu_main.pdf
     Size: 45.2 KB
  ...

🗄️  PINECONE VECTOR DATABASE

Index name: yamie-test
Namespace: documents
✅ Index exists

📊 Statistics:
   Total vectors (all namespaces): 147
   Vectors in 'documents': 147
   Dimension: 3072
   
   Estimated documents: ~10 (based on avg 15 chunks/doc)
```

---

### **Step 7: Test with Real Questions**

```bash
# Run quick test
python scripts/test_query.py
```

**Modify the question** in `scripts/test_query.py` first:
```python
# Line 29 - change to a real question about your data
question = "What's on the menu?"  # Or in Dutch: "Wat staat er op de menukaart?"
```

**Or run full test suite** (recommended):
```bash
python scripts/test_suite.py
```

This tests 20 questions and generates a report.

---

### **Step 8: Create Questions for Your Uncle**

Based on the real data, create 5-10 questions you'll ask to demo:

**Example** (adjust based on real PDFs):
```
1. "What pasta dishes do you have?"
2. "How much is the Carbonara?"
3. "What's the sick leave policy?"
4. "How do I open the restaurant in the morning?"
5. "How often should I clean the espresso machine?"
```

**Save these** in a file for the demo.

---

## 🎯 DEMO PREPARATION

### Create Demo Script

We'll create `scripts/demo.py` to make it easy to show your uncle:

```bash
# I'll create this for you next if you want
python scripts/demo.py
```

This will:
- Show a clean interface
- Ask questions interactively
- Display answers with sources
- Save conversation log

---

## ⚠️ COMMON ISSUES

### **Issue 1: "No documents found"**
**Cause**: PDFs not in `data/` folder  
**Fix**: Check `data/` path, make sure PDFs are there

### **Issue 2: "Empty documents skipped"**
**Cause**: PDFs are scanned images, not text  
**Fix**: Tell your uncle you need searchable PDFs or use OCR

### **Issue 3: "Pinecone index not found"**
**Cause**: Index doesn't exist  
**Fix**: The script will create it automatically, just run again

### **Issue 4: Answers are wrong**
**Cause**: Could be many things:
- Chunks are too small/large
- Retrieval not finding right chunks
- Prompt needs tuning

**Fix**: Use `scripts/inspect_query.py` (we'll create this) to debug

---

## 🔄 IF SOMETHING GOES WRONG

### Restore Test Data

```bash
# Copy test PDFs back
cp backups/test_data/*.pdf data/

# Re-run ingestion
python scripts/run_ingestion.py
```

### Start Fresh

```bash
# Clear everything
Remove-Item data\*.pdf

# Copy test PDFs back
cp backups/test_data/*.pdf data/

# Re-ingest
python scripts/run_ingestion.py
```

---

## 📝 CHECKLIST FOR DEMO

Before showing your uncle:

- [ ] Real PDFs ingested successfully
- [ ] `system_status.py` shows correct vector count
- [ ] Test suite passes (>70% accuracy)
- [ ] You've tested 5-10 real questions manually
- [ ] You know which questions work well
- [ ] You have answers ready if something doesn't work

---

## 🎓 KEY POINTS TO EXPLAIN TO YOUR UNCLE

1. **How it works**:
   - "We take your PDFs and split them into chunks"
   - "Each chunk gets a 'meaning number' (embedding)"
   - "When you ask a question, we find the most similar chunks"
   - "Then GPT-4 answers based only on those chunks"

2. **What it can do**:
   - "Answer questions about menu, prices, policies, procedures"
   - "Works in Dutch and English"
   - "Always cites which document the answer came from"

3. **What it can't do**:
   - "Can't answer questions not in the documents"
   - "Can't make up information"
   - "If it doesn't know, it says so"

4. **Why it's safe**:
   - "Only authorized phone numbers can use it"
   - "All questions are logged"
   - "Data stays in your control (Pinecone + OpenAI)"

---

## ⏭️ NEXT STEPS

After successful demo:
1. Collect feedback from your uncle
2. Identify missing information in documents
3. Add more documents if needed
4. Tune prompts based on real questions
5. Move to WhatsApp integration (Phase 2)

---

**Questions?** Run `python scripts/system_status.py` anytime to check current state.
