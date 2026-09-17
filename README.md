# Enterprise AI Knowledge & Workflow Copilot

Month 3 capstone project — Fulcrum Digital AI/ML Internship.

An enterprise-style AI assistant: upload company documents, search
organizational knowledge, ask questions and get grounded, cited answers, use
controlled tools, query approved structured data, and handle multi-hop
questions — with the system also monitoring its own quality, security, and
reliability. Built as one integrated application, not a set of independent
mini-projects; T33–T48 are its acceptance criteria (see `docs/TASK_STATUS.md`).

> **Status:** Phase 1 of 3. The security gateway, prompt registry, tool
> gateway, orchestrator router, and API skeleton are implemented, tested (22
> passing pytest tests), and verified against a live running server.
> Document ingestion, hybrid RAG, evaluation, the React frontend, CI/CD
> execution, and load testing are Phase 2/3 — see
> `MONTH_2_TO_MONTH_3_MIGRATION_PLAN.md` and `docs/TASK_STATUS.md` for exactly
> what is and isn't built yet.

## Why this exists

Most of this cohort's Month 3 submissions will be T33–T48 done as separate
tutorials. This one is a single production-oriented application with four
deliberate differentiators layered on top:

1. **Adaptive Agentic Orchestration** — a bounded router decides RAG vs. tool
   vs. multi-hop vs. clarify vs. refuse per query, instead of running the
   same pipeline for everything.
2. **Continuous AI Evaluation + Regression Detection** — the system measures
   its own answer quality, groundedness, and reliability, and can detect and
   roll back a prompt-version regression.
3. **Enterprise AI Security Gateway** — every request passes through a single
   explicit security/policy layer (PII detection, prompt-injection detection,
   input/output validation, tool authorization) before it ever reaches an LLM
   or a tool.
4. **Failure Recovery & Fallback Architecture** — component failures (Gemini
   rate limits, a down reranker, a down vector store) degrade gracefully and
   say so, instead of failing hard or silently.

## Architecture

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

Full design rationale: `docs/T33_Technical_Design_Document_v1.md`.

## Technology stack

**Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 + SQLite,
Google Gemini (no OpenAI), `sentence-transformers/all-MiniLM-L6-v2` (dense
embeddings), `rank-bm25` (sparse retrieval), `cross-encoder/ms-marco-MiniLM-L-6-v2`
(reranking), pytest.

**Frontend:** React + Vite (Phase 3). No Streamlit anywhere in this project.

## Project structure

```
enterprise-ai-copilot/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # health, chat, prompts, security, observability
│   │   ├── core/              # config, structured logging, errors, resilience
│   │   ├── models/            # SQLAlchemy models (documents, prompts, evaluations, security/observability events)
│   │   ├── security/          # PII detection, prompt-injection detection, gateway
│   │   ├── tools/             # tool gateway, schemas, calculator
│   │   ├── agents/            # orchestrator / router
│   │   ├── prompts/           # prompt registry (versioning)
│   │   ├── rag/                # Phase 2
│   │   ├── evaluation/         # Phase 3
│   │   ├── observability/      # Phase 2+ (tracing helpers)
│   │   └── main.py
│   ├── tests/                  # 22 passing pytest tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # Phase 3
├── evaluation/                 # Phase 3 benchmark datasets
├── load_tests/                 # Phase 3 (Locust)
├── docs/                        # T33–T48 documentation set
├── scripts/
├── .github/workflows/ci.yml
├── .env.example
├── docker-compose.yml
├── MONTH_2_TO_MONTH_3_MIGRATION_PLAN.md
└── README.md
```

## Setup (Windows / PowerShell)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt
copy ..\.env.example .env
# edit .env and set GEMINI_API_KEY
```

If `.\venv\Scripts\Activate.ps1` is blocked by execution policy, skip
activation and call the venv's python/pip directly as shown above.

## Running the backend

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/docs for interactive Swagger/OpenAPI.

## Running tests

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -v
```

Expected: 22 passed (Phase 1 baseline — grows every phase).

## Environment variables

See `.env.example` at the repo root. Never commit a real `.env` file — it is
git-ignored. No API keys, secrets, or credentials appear anywhere in this
repository.

## API (Phase 1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| POST | `/api/v1/chat` | Security gateway → orchestrator → (tool \| placeholder) → response |
| GET | `/api/v1/prompts` | List prompt versions |
| POST | `/api/v1/prompts` | Create a new prompt version |
| POST | `/api/v1/prompts/{id}/activate?version=N` | Activate a version |
| POST | `/api/v1/prompts/{id}/rollback?version=N` | Roll back to a previous version |
| GET | `/api/v1/security/events` | Security Center data (PII/injection/policy events) |
| GET | `/api/v1/observability` | Request-level observability events |

Document upload/search, evaluation, and the full endpoint set from the spec
land in Phase 2/3 (`docs/TASK_STATUS.md` tracks exactly what's done).

## Security posture (Phase 1)

- Prompt-injection and PII scanning on every `/chat` request before it
  reaches any downstream logic.
- Retrieved/external content is always wrapped as `<untrusted_data>` before
  reaching a prompt template (Phase 2), so a document can never pose as an
  instruction.
- No arbitrary code execution anywhere: the calculator tool uses Python's
  `ast` module with a strict node-type allowlist, not `eval()`.
- All tool calls go through a single Tool Gateway: allowlisted, schema
  validated, timeout-bounded, capped at `max_agent_steps` per request.
- Every security decision is persisted as a `SecurityEvent`, visible via
  `/api/v1/security/events` — nothing is a hidden or fabricated check.

Full OWASP LLM Top 10 review: Phase 3 (`docs/T42_Security_Hardening_Report.md`,
not yet written).

## Observability

Structured JSON logs (`backend/app/core/logging.py`) with request-id
propagation; per-request metrics persisted to `observability_events`
(router decision, tool selected, latency, fallback flags). Retrieval/rerank/
LLM/tool-latency breakdown lands with the Phase 2 RAG pipeline.

## Deployment

Docker skeleton exists (`backend/Dockerfile`, `docker-compose.yml`) but has
not been built or deployed in this session — no deployment success is
claimed anywhere in this repository.

## Troubleshooting

- **`ModuleNotFoundError: app`** — run pytest/uvicorn from the `backend/`
  directory; `pytest.ini` sets `pythonpath = .` relative to it.
- **PowerShell activation blocked** — use `.\venv\Scripts\python.exe` /
  `.\venv\Scripts\pip.exe` directly instead of `Activate.ps1`.
- **SQLite "database is locked"** — only one process should hold
  `data/app.db` at a time in local dev; stop any previously running
  `uvicorn` instance first.

## T33–T48 mapping

See `docs/TASK_STATUS.md` for the live, honest status of every task —
Implemented / Tested / Evidence Captured / Complete, with no task marked
Complete on documentation alone.

---
⚠️ Internal capstone project for Fulcrum Digital. AI-generated content in
this repository (documentation, code comments, design rationale) should be
validated by a qualified engineer before being treated as a stakeholder-ready
deliverable. Questions on data handling or security posture: CISO@fulcrumdigital.com.
