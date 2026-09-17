# T48 — Knowledge Transfer

Status: Phase 3. Written so another engineer inheriting this codebase (or
Satish himself, months later) can get productive quickly without
re-reading every module. Cross-references `docs/T33_Technical_Design_Document_v1.md`
for the original design rationale rather than repeating it.

## 1. One-paragraph mental model

A FastAPI backend where every `/chat` request passes through one security
gateway, one router (the "adaptive orchestrator"), and lands on exactly
one of six handled paths — RAG, a calculator tool, a structured-DB-search
tool, multi-hop retrieval, a clarification response, or a refusal —
before a second security pass and an observability write. Retrieval is
hybrid (BM25 + dense embeddings, fused by RRF) with cross-encoder
reranking and a separate authorization filter that is never skippable by
a search-relevance filter. Generation goes through Gemini when a real key
is configured, and through a deterministic extractive fallback when it
isn't — the two are never confused in the response (`fallback_reason` is
always honest). Prompts are versioned in a database table, not hardcoded
strings, so a prompt edit can be evaluated and rolled back like code.

## 2. Where to start reading code, in order

1. `backend/app/api/routes/chat.py` — the entire request lifecycle in one
   file; read this first, everything else is a dependency of it.
2. `backend/app/agents/orchestrator.py` — the routing policy.
3. `backend/app/security/gateway.py` + `authorization.py` — the two
   distinct security concerns (input/output validation vs. document
   access control — do not conflate them, see the module docstrings).
4. `backend/app/rag/hybrid_retrieval.py` — retrieval; `reranker.py`;
   `answer_synthesis.py` — the RAG core.
5. `backend/app/tools/gateway.py` — the tool execution choke point.
6. `backend/app/prompts/registry.py` + `app/evaluation/regression.py` —
   the prompt-versioning and regression-detection loop.
7. `backend/app/models/db.py` — every table; read this alongside (1)-(6)
   rather than in isolation, since most modules only touch 1-2 tables.

## 3. Extension points (where to add things without fighting the architecture)

- **A new tool:** add a Pydantic schema to `app/tools/schemas.py`, a
  function to `app/tools/gateway.py`, and register it in
  `TOOL_REGISTRY`. Set `needs_context=True` only if it needs `db`/
  `request_id`/`clearance`. Never call it from anywhere except through
  `ToolGateway.call()`.
- **A new routing category:** add a heuristic to
  `app/agents/orchestrator.py::decide_route()` and a matching branch in
  `app/api/routes/chat.py`. Keep the router itself free of any actual
  execution logic — it only decides, `chat.py` executes.
- **A new evaluation metric:** add a `_xxx_metrics()` function to
  `app/evaluation/runner.py` and call it from `run_evaluation()`. It
  automatically becomes usable as a `decisive_metric` for
  `evaluate_prompt_change()` with no changes to `regression.py`.
- **A new document field:** add it to `Document` in `app/models/db.py`
  and to `to_metadata_dict()` — or, for a field that doesn't need its own
  column, use the existing `extra_metadata` JSON escape hatch instead of
  a migration.
- **Swapping the vector store for a real one (Chroma/pgvector/etc.):**
  the seam is `app/rag/vector_store.py`'s public functions
  (`add`/`search`/`delete_by_ids`) — nothing else in the codebase touches
  the storage format directly. See that module's docstring for why a
  flat-file store was chosen at this project's current scale, and what
  would justify swapping it.

## 4. Things that look like bugs but are deliberate

- Chat responses never include a "reasoning" or "chain of thought" field
  — this is intentional (Feature 1's "no hidden chain-of-thought exposed
  to the frontend" requirement), not an oversight.
- `build_metadata_filter_set()` in `hybrid_retrieval.py` looks like it
  "filters access" but does not — it only narrows search relevance.
  `authorization.py::filter_authorized_chunks()` is the real enforcement,
  applied unconditionally afterward. See T42's dedicated design note if
  this distinction isn't obvious from the code alone.
- The reranker and multi-hop planner both have working fallback paths
  that activate automatically on model/dependency failure — if you see a
  response with `fallback_triggered: true`, that's the system behaving
  correctly, not an error to chase down.
- `X-User-Clearance` is a plain, unauthenticated header. This is
  deliberate and documented (see T42's migration-path section) — do not
  "fix" it by wiring up a real identity provider without that being an
  explicit, separate decision.

## 5. Test suite orientation

`backend/tests/` mirrors `backend/app/`'s module structure one-to-one for
the most part (e.g. `test_tool_gateway.py` ↔ `app/tools/gateway.py`).
`conftest.py`'s `fresh_session()`/`db_session`/`rag_isolated` fixtures
give each test its own in-memory SQLite DB and, where needed, its own
scratch vector-store path — tests never share document state with each
other by design. As of Phase 3: 78 tests, all passing (see
`docs/TASK_STATUS.md` for the exact breakdown and the reproducible
`pytest -v` command).

## 6. What a new engineer should NOT assume

- That a real Gemini key is configured — check `backend/.env` /
  `app/services/gemini_client.py`'s placeholder-detection list before
  assuming "no generative answers" is a bug.
- That CI has actually run on GitHub — as of this document, it has only
  been validated locally (see `docs/TASK_STATUS.md`).
- That load testing has produced real numbers — it has not; the Locust
  script is ready but unexecuted under real concurrency (see
  `docs/T44_Runbook.md`).
- That the `X-User-Clearance` header is a real security boundary in any
  deployment beyond this local/staging demo.

---
⚠️ AI-generated. Validate with a qualified professional before using this
as the sole onboarding material for a new engineer.
