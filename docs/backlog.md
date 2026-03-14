# YamieBot — Backlog

Priority order. Updated March 14, 2026.

## Immediate (Next Session)

- [ ] Confirm re-ingestion completed (~551 vectors across 5 namespaces)
- [ ] Debug orphan detection ID format mismatch — compare Pinecone `list()` output vs `enumerate_pages()` page IDs, find the difference
- [ ] Add orphan detection safety checks: abort if orphan count > 50% of total, add dry-run mode (log what would be deleted without deleting)
- [ ] Re-enable orphan detection with safety checks
- [ ] Test chatbot with real questions via WhatsApp/API
- [ ] Run 15-question evaluation set (created March 14 Session 1, never executed)

## RAG Quality (After Sync is Stable)

- [ ] **Re-ranker integration (HIGH)** — Retrieve 20 chunks, re-rank with Cohere Rerank or cross-encoder. Fixes cases where the right chunk exists but scores low in vector search.
- [ ] **Hybrid search (MEDIUM)** — Vector + keyword/BM25. Pinecone supports sparse vectors. Fixes name lookups like "Wie is Daoud?" where pure vector search fails.
- [ ] **Markdown-aware chunking (LOW)** — Header splitter as first pass for Notion pages. Less useful for embedded PDFs.
- [ ] System prompt optimization and testing

## Admin Dashboard

- [ ] **Query debug view (HIGH)** — Click a question in Vragen page → see retrieved chunks with similarity scores, which passed threshold vs filtered, namespace distribution, what was sent to LLM. Data structure already exists in `QueryResponse` (`sources` + `filtered_chunks`). Need to verify if full debug data is saved to Supabase `query_logs`.
- [ ] **System prompt viewer (MEDIUM)** — Show active system prompt in dashboard. Allow owners to read what controls the bot.
- [ ] Advanced analytics — charts, per-user stats, trends over time
- [ ] Answer quality rating — owners rate answers to help tune system prompt
- [ ] Ticket/feedback system — owners submit feedback directly from dashboard

## Infrastructure & Security

- [ ] **Supabase RLS on `sync_logs`** — Currently disabled. Other tables have RLS enabled. Needs proper policies.
- [ ] **Admin credentials to env vars** — Username/password currently hardcoded as `admin`/`changeme123`. Must move to environment variables.
- [ ] Scheduled auto-sync — Background job every X hours as safety net
- [ ] Response caching in Redis
- [ ] Deprecate old ingestion pipeline (`scripts/run_notion_ingestion.py`) once sync is proven stable
- [ ] Explore other LLM/embedding models for better answers

## Phase 7 — WhatsApp Business API

- [ ] Switch from Twilio sandbox to real WhatsApp number
- [ ] Requires Meta Business Manager approval + KvK number
- [ ] Once approved: update Railway env vars with real Twilio credentials

## Done (Completed Items Archive)

- [x] Security hardening — CORS, error leaking, JWT secret, dependency pinning (March 14 S1)
- [x] RAG quality — threshold 0.35, chunk_size 1000, overlap 200, max_tokens 800 (March 14 S1)
- [x] Re-ingestion with new chunk size — 540→551 vectors (March 14 S1)
- [x] Pinecone race condition fix — polling wait before upsert (March 14 S1)
- [x] Code cleanup — dead DOCX config, system_prompt.py duplicates (March 14 S2)
- [x] Incremental sync feature — full system with admin dashboard UI (March 14 S2)
- [x] Deterministic vector ID migration — all 551 vectors (March 14 S2)
- [x] Bug fixes — dead category validation, per-source sync time, Dutch error messages (March 14 S3)
- [x] Dashboard stats fix — response_time_ms column name (March 14 S3)
- [x] Mobile UX — SyncPage and SystemPage responsive layouts (March 14 S3)
- [x] Sync detail view — expandable history with per-source/per-page breakdown (March 14 S3)
- [x] Orphan detection built (March 14 S3) — DISABLED due to bug, needs fix