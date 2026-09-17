# Task Completion Tracker

Status model: Not Started → In Progress → Implemented → Tested → Evidence Captured → Complete.
A markdown document alone never counts as Complete.

## Phase 1 (unchanged from prior delivery)

| Task | Requirement | Status | Location |
|---|---|---|---|
| T33 | Technical Design Document v1 | Complete | `docs/T33_Technical_Design_Document_v1.md` |
| — | Month 2→3 migration plan | Complete | `MONTH_2_TO_MONTH_3_MIGRATION_PLAN.md` |
| — | Repo scaffold, config, structured logging, error/resilience helpers | Complete | `backend/app/core/` |

## Phase 2 (this delivery)

| Task | Requirement | Implementation | Test/Evidence | Status | Location |
|---|---|---|---|---|---|
| — | Flexible document metadata schema | 11 fields incl. extensible `tags`/`extra_metadata` JSON | `test_ingestion.py` | Tested | `backend/app/models/db.py::Document` |
| T37 (ingestion) | PDF/DOCX/TXT ingestion, validation, dedup | pypdf/python-docx/plain parsers, sha256 dedup, size/type validation | 5 tests, live curl (2 docs uploaded) | Tested | `backend/app/services/ingestion.py` |
| T37 (chunking) | Chunking + metadata | Paragraph-aware sliding window with overlap | 4 tests | Tested | `backend/app/rag/chunking.py` |
| T37 (dense) | Dense retrieval, Hugging Face embeddings | `sentence-transformers/all-MiniLM-L6-v2`, flat numpy vector store | 3 vector-store tests + live retrieval | Tested | `backend/app/rag/embeddings.py`, `vector_store.py` |
| T21 | BM25 + hybrid retrieval | `rank-bm25` + Reciprocal Rank Fusion | 3 tests + live retrieval | Tested | `backend/app/rag/sparse_index.py`, `hybrid_retrieval.py` |
| T22 | Cross-encoder reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2`, with fallback on load failure | 3 tests incl. simulated failure | Tested | `backend/app/rag/reranker.py` |
| — | Metadata filtering (relevance, not security) | business_unit/document_type/client_name/tags filter | 2 tests | Tested | `hybrid_retrieval.py::build_metadata_filter_set` |
| — | Authorization (separate from metadata filtering) | Clearance-vs-confidentiality enforcement, independent of search filters | 4 tests + live curl proving header-based bypass attempt fails | Tested | `backend/app/security/authorization.py` |
| T23 | Multi-hop retrieval | Gemini-planned (heuristic fallback), capped at 4 hops, merged pool | 2 tests | Tested | `backend/app/agents/multi_hop.py` |
| — | Gemini answer synthesis + citations | Real Gemini call path + genuine extractive fallback (no real key in this env, so fallback path is what actually runs) | 3 tests + live curl | Tested | `backend/app/rag/answer_synthesis.py`, `services/gemini_client.py` |
| Feature 1 | Adaptive orchestrator fully wired to RAG/TOOL/MULTI_HOP/CLARIFY/REFUSE | `/chat` now runs the real pipeline per path, not placeholders | 5 router tests + 3 chat integration tests + live curl | Tested | `backend/app/api/routes/chat.py` |
| Feature 3 | KB search + structured DB search tools registered | Tool Gateway now exposes 3 tools, schema-validated, allowlisted | Exercised via `/chat` KB path indirectly; direct tool tests pending Phase 3 | Implemented | `backend/app/tools/gateway.py` |
| Feature 4 | Fallback paths (embedding, reranker, Gemini, multi-hop planner) | Every one of the four fails gracefully with a recorded reason, never silently | 6+ tests exercise real failure paths (no real Gemini key) | Tested | across `rag/`, `agents/`, `services/` |
| T38 | `/documents/upload`, `/documents`, `/documents/{id}` DELETE, `/search` | Implemented | 6 tests + live curl | Tested | `backend/app/api/routes/documents.py`, `search.py` |
| T39 | Executable evaluation suite | Real benchmark (3 QA cases, 3 safety cases, 2 tool cases) against real pipeline, not fabricated numbers | 5 tests + live curl (`safety_case_pass_rate: 1.0`, `citation_presence_rate: 1.0` on this run) | Tested | `backend/app/evaluation/` |
| T39/Feature 2 | Regression detection + rollback workflow | `compare_runs` + `evaluate_prompt_change` (auto-rollback via PromptRegistry) | 4 tests (regression flagged on worse candidate, on slower latency, not flagged on improvement) | Tested | `backend/app/evaluation/regression.py` |
| T42 (draft) | OWASP LLM Top 10-oriented review | All 10 categories addressed with explicit known-gaps section | Written; reflects code actually in this repo | In Progress (real security review still pending) | `docs/T42_Security_Hardening_Report.md` |
| — | React frontend (Vite) | Dashboard, Chat, Documents, Prompt Registry, Security Center, Observability, Evaluation — all wired to the real API, no mock data | `npm run build` succeeds; live screenshots taken of all 4 core views interacting with real backend data | Tested | `frontend/` |
| T41 | Load testing | Locust script covering health/chat/search/documents | NOT yet run under real concurrency in this session — explicitly marked pending, no numbers fabricated | Implemented (not yet executed) | `load_tests/locustfile.py` |
| T43 | CI | Same skeleton as Phase 1; still not run on real GitHub Actions (no repo pushed) | — | Implemented (not yet executed) | `.github/workflows/ci.yml` |
| T44–T48 | Runbook, demo prep, retrospective, KT doc | Not started | — | Not Started | Phase 3 |

## Test suite summary (reproducible)

```
cd backend
.\venv\Scripts\python.exe -m pytest -v
```

61 passed, 0 failed (Phase 2 baseline — up from 22 in Phase 1). Every RAG/
security/evaluation test in this count exercises real code paths (real
embedding + reranker model downloads happen in CI/local runs; no
network access = those specific tests would need HF Hub reachability,
same as any other ML dependency).

## Genuine blockers requiring Satish's input

1. **No real GEMINI_API_KEY has been provided.** The system is fully wired
   to call Gemini and gracefully falls back to extractive synthesis when
   it can't — this is real, tested behavior, not a stub — but real
   generative answers (vs. extractive fallback) require a real key in
   `backend/.env`.
2. **Load testing (T41) has not been executed under real concurrency.**
   The Locust script is ready; running it against a live instance and
   capturing real throughput/latency/error-rate numbers needs to happen
   on Satish's machine or a staging environment, per the "no fabricated
   measurements" rule.
3. **CI has not run on real GitHub Actions** — no repo has been pushed to
   GitHub yet from this session.
4. **Authorization is header-based (`X-User-Clearance`), not backed by a
   real identity provider.** Documented as a known gap in
   `docs/T42_Security_Hardening_Report.md`; wiring real auth (e.g. Azure
   AD) is a decision Satish should make deliberately, not something to
   improvise.

**Fabrication check:** no mentor feedback, peer review, deployment,
load-test measurements, or stakeholder attendance are claimed anywhere in
this repository. Every "Tested" row above was actually executed in this
session — pytest output and live curl/Playwright screenshots are
reproducible via the commands in the README.
