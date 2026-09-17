# Month 2 → Month 3 Migration Plan

## Status of Month 2 source

Before writing any Month 3 architecture, this project's working agreement (see the
top-level project instructions) required inspecting the existing Month 2 codebase
(T17 Function Calling, T18 ReAct Agent, T19 Tool Error Handling, T20 Evaluation,
T21 Hybrid Search, T22 Reranking, T23 Multi-hop RAG, T25 Model Evaluation, T26
LoRA/Fine-tuning, T29 Observability, T30 Prompt Versioning, T31 Security/Guardrails,
T32 Prototype) before reusing or replacing anything from it.

That inspection was attempted at the start of this build. Result: **no Month 2
source code was available in this environment** — this cloud workspace started
empty, and the session was not linked to Satish's computer. Satish confirmed
directly that no real Month 2 code exists to migrate from.

**Decision (confirmed with Satish): this is a fresh build.** Month 3 is designed
and implemented standalone. The T17–T32 topic list is treated as *prior art /
conceptual scope* — i.e. "these capabilities existed conceptually in Month 2 and
must appear, properly integrated, in Month 3" — rather than as literal code to
port. Nothing below claims code reuse that did not happen.

## What this means concretely, task by task

| Month 2 topic | Month 3 treatment |
|---|---|
| T17 Function Calling | Rebuilt as the Tool Gateway (`backend/app/tools/gateway.py`) — schema-validated, allowlisted, timeout-bounded. |
| T18 ReAct Agent | Rebuilt, deliberately *not* as an open ReAct loop — as the bounded Adaptive Orchestrator (`backend/app/agents/orchestrator.py`) with an explicit router and a hard step cap, per Feature 1's "do not create an uncontrolled autonomous agent" requirement. |
| T19 Tool Error Handling | Rebuilt into `backend/app/core/errors.py` (error classification) and `backend/app/core/resilience.py` (retry/fallback), used uniformly by every tool and, in Phase 2, every RAG/LLM call. |
| T20 Evaluation | To be rebuilt in Phase 3 as the executable evaluation suite (Feature 2) under `backend/app/evaluation/` and `evaluation/`. |
| T21 Hybrid Search | To be rebuilt in Phase 2 under `backend/app/rag/` (BM25 + dense retrieval via `sentence-transformers/all-MiniLM-L6-v2`). |
| T22 Reranking | To be rebuilt in Phase 2 (`cross-encoder/ms-marco-MiniLM-L-6-v2`), with a fallback path per Feature 4 if the reranker is unavailable. |
| T23 Multi-hop RAG | Router already recognizes multi-hop-shaped queries (`RoutePath.MULTI_HOP`); the retrieval loop itself lands in Phase 2. |
| T25 Model Evaluation | Folds into Phase 3 evaluation suite alongside T20. |
| T26 LoRA/Fine-tuning | Out of scope for the production copilot unless a concrete accuracy gap justifies it — documented as "remains experimental, not production," consistent with the instruction not to force it into production for its own sake. Revisit only if Phase 3 evaluation shows a gap fine-tuning would actually close. |
| T29 Observability | Rebuilt as `backend/app/core/logging.py` (structured JSON logs, request-id propagation) + `ObservabilityEvent` table + `/observability` endpoint. Already recording router_decision, tool_selected, latency in Phase 1. |
| T30 Prompt Versioning | Rebuilt as `backend/app/prompts/registry.py` — real create/activate/rollback semantics, DB-backed, five seed prompts, already tested and running. |
| T31 Security/Guardrails | Rebuilt as the Security Gateway (`backend/app/security/`) — PII detection, prompt-injection detection, input/output validation. Already blocking injection and redacting PII in Phase 1. |
| T32 Prototype | Superseded entirely by this repository. |

## What was NOT ported (because nothing existed to port)

Nothing. There is no discard/replace list because there was no working Month 2
implementation to evaluate line by line. If Satish attaches real Month 2 files or
links this session to his computer later, this document will be revised with an
actual reuse/refactor/discard table per file, and any Phase 1 module above that
duplicates something already-working will be reconciled rather than left
duplicated.

## Phase plan going forward

- **Phase 1 (this delivery):** repo scaffold, config, structured logging, error
  classification + resilience helpers, security gateway (PII + injection),
  prompt registry (seeded, tested), tool gateway + calculator tool, orchestrator
  router, `/health` `/chat` `/prompts` `/security/events` `/observability`
  endpoints, SQLite models, 22 passing pytest tests, CI skeleton.
- **Phase 2:** document ingestion (PDF/DOCX/TXT), hybrid retrieval (BM25 + dense),
  reranking, Gemini integration for real RAG answers, knowledge-base and
  structured-DB tools wired into the tool gateway, multi-hop retrieval loop.
- **Phase 3:** evaluation suite + regression detection, prompt-version-vs-version
  benchmarking, React frontend, CI/CD hardening, load testing, security review
  (OWASP LLM Top 10), full documentation set (T33–T48).
