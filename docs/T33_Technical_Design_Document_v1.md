# T33 — Technical Design Document v1

## Project

Enterprise AI Knowledge & Workflow Copilot — Fulcrum Digital AI/ML Internship, Month 3 Capstone.

## 1. Problem statement

Build one coherent, production-oriented enterprise AI application — not a set of
independent T33–T48 mini-projects — that lets a user upload company documents,
search organizational knowledge, ask questions and get grounded cited answers,
use controlled tools, query approved structured data, handle multi-hop
questions, and have the system observe, evaluate, secure, and recover itself.

## 2. Architecture (target — see README for the live diagram)

```
React Frontend
      |
FastAPI API Layer
      |
Security Gateway  (input validation, PII, prompt-injection, policy)
      |
Adaptive Orchestrator  (router: RAG | TOOL | MULTI_HOP | CLARIFY | REFUSE)
      |            |            |
   RAG Path    Tool Path    Multi-hop
      |            |            |
Hybrid Search  Tool Gateway  Retrieval (iterated)
      |            |            |
  Reranker    DB/Calculator   Reranker
      |____________|____________|
                   |
               Gemini LLM
                   |
           Output Validation
                   |
          Citation Validation
                   |
             Final Response
         /         |         \
  Evaluation  Observability  Security
         \         |         /
          Regression Detection
                   |
             Prompt Rollback
```

## 3. Four differentiators — design summary

1. **Adaptive Agentic Orchestration.** A bounded router (`app/agents/orchestrator.py`)
   picks exactly one path per query using explicit heuristics today, upgraded in
   Phase 2 to consult the Gemini-backed `orchestrator_router` prompt for
   genuinely ambiguous cases. Stopping criteria: `max_agent_steps` enforced by
   the Tool Gateway, not by the orchestrator re-implementing its own counter.
2. **Continuous Evaluation + Regression Detection.** `evaluations` table stores
   metric_value + baseline_value + regression_detected per run; Phase 3 adds the
   benchmark-and-compare workflow and wires a detected regression to
   `PromptRegistry.rollback()`.
3. **Enterprise AI Security Gateway.** Single choke point (`app/security/gateway.py`)
   for every inbound/outbound turn: input validation → PII scan → injection scan
   → (orchestrator) → output validation. Retrieved documents are always wrapped
   as `<untrusted_data>` before reaching a prompt template — this is the
   structural defense; the regex scan is a detection/logging layer on top of it.
4. **Failure Recovery & Fallback.** `app/core/errors.py` classifies every
   failure; `app/core/resilience.py` provides `with_retry` (bounded, backoff,
   only for errors marked retriable) and `with_fallback` (records *why* a
   fallback fired — never silent degradation).

## 4. Tech stack

Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 + SQLite, Gemini
(`google-generativeai`), `sentence-transformers/all-MiniLM-L6-v2` (dense
embeddings), `rank-bm25` (sparse), `cross-encoder/ms-marco-MiniLM-L-6-v2`
(reranking), pytest.

Frontend: React + Vite (no Streamlit).

No OpenAI anywhere in the stack.

## 5. Data model (Phase 1, implemented)

`documents`, `prompt_versions`, `evaluations`, `security_events`,
`observability_events` — see `backend/app/models/db.py`. SQLite for
local/staging; the ORM boundary means a Postgres migration later is a
connection-string change, not a rewrite.

## 6. Phase 1 scope (implemented and tested — see repo)

- Config + structured JSON logging with request-id propagation.
- Error classification + retry/fallback helpers.
- Security Gateway: regex-based PII detection + redaction, prompt-injection
  detection, input size limits, output leak-marker stripping. 6 passing tests.
- Prompt Registry: 5 seed prompts, create/activate/rollback, DB-backed. 3
  passing tests.
- Tool Gateway + Calculator tool: AST-based safe arithmetic (no eval/exec),
  schema-validated args, timeout, step cap. 5 passing tests.
- Orchestrator router: deterministic path selection. 5 passing tests, plus 2
  end-to-end `/chat` tests through the FastAPI TestClient.
- API: `/health`, `/chat`, `/prompts` (+ activate/rollback), `/security/events`,
  `/observability`. All verified live against a running uvicorn process, not
  only under TestClient.

Total: 22/22 tests passing (`pytest -v`, see repo).

## 7. Deferred to Phase 2/3 (explicitly, not silently)

Document ingestion, hybrid retrieval, reranking, multi-hop retrieval loop,
Gemini-backed answer synthesis, knowledge-base/structured-DB tools,
evaluation/regression benchmarking, React frontend, CI/CD execution, load
testing, and the full T33–T48 documentation set beyond this file and the
migration plan.

## 8. Open questions for Satish (per project instructions — asked, not assumed)

None block Phase 1. Phase 2 will surface a real decision: which document
metadata fields matter for filtering (client name, business unit CD/FD,
confidentiality level?) — needed before ingestion schema is finalized.
