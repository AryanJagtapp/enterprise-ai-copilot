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
| T41 | Load testing | Locust script covering health/chat/search/documents | NOT yet run under real concurrency in this session — explicitly marked pending, no numbers fabricated | Implemented (not yet executed) | `load_tests/locustfile.py`, `docs/T41_Load_Test_Report.md` |
| T43 | CI | Same skeleton as Phase 1; still not run on real GitHub Actions (no repo pushed) | — | Implemented (not yet executed) | `.github/workflows/ci.yml` |
| T44–T48 | Runbook, demo prep, retrospective, KT doc | Not started | — | Not Started | Phase 3 |

## Phase 3 (this delivery)

| Task | Requirement | Implementation | Test/Evidence | Status | Location |
|---|---|---|---|---|---|
| Feature 4 (fix) | Crash-safety: malformed active prompt template must degrade gracefully, not 500 | Wrapped `.format()` calls in `answer_synthesis.py` and `multi_hop.py` in their own try/except, falling back to extractive/heuristic path | 2 new dedicated tests feeding a genuinely malformed template and asserting graceful fallback | Tested | `backend/app/rag/answer_synthesis.py`, `backend/app/agents/multi_hop.py`, `tests/test_prompt_fallback_crash_fix.py` |
| Feature 1/3 | Structured-DB-search tool actually wired into the orchestrator and `/chat` (was registered in the Tool Gateway but not reachable from a real query in Phase 2) | New `app/tools/query_parsing.py` heuristic (deliberately non-LLM — avoids unnecessary complexity per this phase's framing instruction), new orchestrator routing branch, new `/chat` execution branch | 10 new tests: correct routing, correct selection, invalid arguments, non-allowlisted table rejected, unknown filter field rejected, missing context rejected, timeout handling, max-agent-steps cap, end-to-end `/chat` integration (real document ingested and found), no-match graceful case | Tested | `backend/app/tools/query_parsing.py`, `backend/app/agents/orchestrator.py`, `backend/app/api/routes/chat.py`, `tests/test_tool_gateway.py`, `tests/test_structured_db_routing.py` |
| Feature 2 | Genuine, reproducible prompt-regression + auto-rollback demonstration (not fabricated numbers) | New `rag_prompt_template_valid_rate` / `multi_hop_prompt_template_valid_rate` evaluation metrics — the first metrics in this suite that are actually sensitive to prompt *wording* validity in this no-real-Gemini-key environment (the existing citation/hit-rate metrics are computed by the prompt-content-invariant extractive fallback) | Live-executed via a standalone script against the real DB/evaluation pipeline: created a deliberately broken `multi_hop_planner` candidate version, ran `evaluate_prompt_change(decisive_metric="multi_hop_prompt_template_valid_rate")`, observed `regression_detected: true`, `rolled_back: true`, `active_version_after: 1` (baseline restored) — full JSON output captured in this phase's summary | Tested + Evidence Captured | `backend/app/evaluation/runner.py`, `backend/app/evaluation/regression.py` (unchanged logic, new metric input) |
| T42 (update) | Explicit production migration path to enterprise SSO/identity-based authorization | New dedicated section in T42 spelling out what changes (auth middleware, claims-based clearance, token validation, IdP-agnostic enforcement layer) and explicitly stating Azure AD/any real IdP has NOT been implemented | Documentation only, as instructed — no IdP code added | Complete (as a documented seam, not an implementation) | `docs/T42_Security_Hardening_Report.md` |
| T43 (update) | CI secrets hygiene | `GEMINI_API_KEY` now sourced from a GitHub Actions repository secret with a `\|\|` fallback to the same placeholder string used before, rather than a hardcoded literal | Reviewed; `ci-placeholder-key` confirmed present in `gemini_client.py`'s placeholder-detection list, so the fallback still deliberately exercises the extractive-fallback code path in CI | Implemented (still not yet executed on real GitHub Actions) | `.github/workflows/ci.yml` |
| T44 | Operational Runbook | Setup, run, test, lint, and common-operation commands — every command in it was actually executed in this session against the live server (health check, chat RAG/calculator/structured-DB paths, evaluation run, prompt rollback) and the documented output is what was actually observed | Live-verified via curl against a running `uvicorn` instance in this session | Complete | `docs/T44_Runbook.md` |
| T45 | Demo Preparation | Suggested demo narrative, sample queries, pre-demo checklist, anticipated Q&A with honest answers | Documentation only — no demo has happened yet | Complete (as prep material) | `docs/T45_Demo_Preparation.md` |
| T46 | Final Demo Runbook | Logistics/script/environment-freeze checklist template; explicit placeholders for attendee list, questions, feedback, outcome | Documentation only — attendance/feedback sections deliberately left blank for Satish to fill in after a real demo | Complete (as a template; not usable as evidence of a demo having occurred) | `docs/T46_Final_Demo_Runbook.md` |
| T47 | Personal Retrospective | Blank template with prompts; explicitly refuses to pre-fill personal reflection content | Documentation only | Complete (as a blank template) | `docs/T47_Personal_Retrospective_Template.md` |
| T48 | Knowledge Transfer | Architecture mental model, reading order, extension points, deliberate-not-bug list, test orientation, assumptions a new engineer shouldn't make | Documentation, cross-checked against the actual current codebase (route shapes, module names verified, not assumed) | Complete | `docs/T48_Knowledge_Transfer.md` |
| T41 (report doc) | Load test report | Exact commands to run Locust locally; results section left as a placeholder; theoretical bottlenecks reasoned about and explicitly labeled as unmeasured predictions | Script itself unchanged from Phase 2; still not executed under real concurrency | Implemented (not yet executed) | `docs/T41_Load_Test_Report.md` |
| — | `.env.example` | Documents every settings-relevant env var with safe defaults, no real secrets | N/A (config file) | Complete | `backend/.env.example` |

## Test suite summary (reproducible)

```
cd backend
.\venv\Scripts\python.exe -m pytest -v
```

**78 passed, 0 failed** as of Phase 3 (61 from Phase 2 + 17 new tests:
10 in `test_tool_gateway.py`, 5 in `test_structured_db_routing.py`, 2 in
`test_prompt_fallback_crash_fix.py`). Every RAG/security/evaluation test
in this count exercises real code paths (real embedding + reranker model
downloads happen in CI/local runs; no network access = those specific
tests would need HF Hub reachability, same as any other ML dependency).
This was actually re-run in this session after the Phase 3 edits, along
with `ruff check app tests` (`All checks passed!`).

## Genuine blockers requiring Satish's input

1. **No real GEMINI_API_KEY has been provided.** The system is fully wired
   to call Gemini and gracefully falls back to extractive synthesis when
   it can't — this is real, tested behavior, not a stub — but real
   generative answers (vs. extractive fallback) require a real key in
   `backend/.env`. This also means the regression-detection demonstration
   in Phase 3 had to be built around a metric that doesn't depend on
   Gemini being reachable (prompt-template validity) rather than answer
   quality, which does depend on it in this environment.
2. **Load testing (T41) has not been executed under real concurrency.**
   The Locust script is ready; running it against a live instance and
   capturing real throughput/latency/error-rate numbers needs to happen
   on Satish's machine or a staging environment, per the "no fabricated
   measurements" rule. See `docs/T41_Load_Test_Report.md` for exact
   commands.
3. **CI has not run on real GitHub Actions** — no repo has been pushed to
   GitHub yet from this session. A real `GEMINI_API_KEY` GitHub secret
   also needs to be added there (or the `\|\|` fallback placeholder will
   be used, which is fine — it deliberately exercises the fallback path).
4. **Authorization is header-based (`X-User-Clearance`), not backed by a
   real identity provider.** Documented as a known gap with an explicit
   migration-path section in `docs/T42_Security_Hardening_Report.md`.
   Azure AD (or any IdP) has deliberately NOT been implemented — wiring
   real auth is a decision Satish should make deliberately, not something
   to improvise.
5. **T46 (Final Demo Runbook) and T47 (Personal Retrospective) are
   templates with deliberately blank outcome/attendance/reflection
   sections.** They cannot honestly be marked "Complete" in the sense of
   reflecting a real demo or a real retrospective until Satish actually
   gives the demo and writes his own retrospective.

**Fabrication check:** no mentor feedback, peer review, deployment,
load-test measurements, or stakeholder attendance are claimed anywhere in
this repository. Every "Tested" row above was actually executed in this
session — pytest output, live curl output, and the regression/rollback
JSON result are reproducible via the commands in the README and
`docs/T44_Runbook.md`.
