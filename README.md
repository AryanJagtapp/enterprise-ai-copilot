# Enterprise AI Knowledge & Workflow Copilot

Month 3 capstone project — Fulcrum Digital AI/ML Internship.

An enterprise-style AI assistant: upload company documents, search
organizational knowledge, ask questions and get grounded, cited answers, use
controlled tools, query approved structured data, and handle multi-hop
questions — with the system also monitoring its own quality, security, and
reliability. Built as one integrated application, not a set of independent
mini-projects; T33–T48 are its acceptance criteria (see `docs/TASK_STATUS.md`).

> **Status:** Phase 2 of 3. Document ingestion, hybrid retrieval (BM25 +
> dense embeddings), cross-encoder reranking, multi-hop retrieval, Gemini
> answer synthesis (with a real, tested extractive fallback since this
> environment has no real Gemini key), metadata filtering, a separate
> authorization layer, an executable evaluation + regression-detection
> suite, and a working React frontend are all implemented, tested (61
> passing pytest tests), and verified against a live running server —
> including real Playwright screenshots of the UI driving the real API.
> Load testing under real concurrency, CI execution on GitHub, and the
> remaining T44–T48 documents are Phase 3 — see `docs/TASK_STATUS.md` for
> exactly what is and isn't done.

## Why this exists

Most of this cohort's Month 3 submissions will be T33–T48 done as separate
tutorials. This one is a single production-oriented application with four
deliberate differentiators layered on top:

1. **Adaptive Agentic Orchestration** — a bounded router decides RAG vs. tool
   vs. multi-hop vs. clarify vs. refuse per query, instead of running the
   same pipeline for everything.
2. **Continuous AI Evaluation + Regression Detection** — the system measures
   its own answer quality, groundedness, and reliability, and can detect and
   roll back a prompt-version regression automatically.
3. **Enterprise AI Security Gateway** — every request passes through a single
   explicit security/policy layer (PII detection, prompt-injection detection,
   input/output validation, tool authorization), and document access is
   enforced by a **separate authorization layer**, not by search filters.
4. **Failure Recovery & Fallback Architecture** — component failures (no
   Gemini key, a down reranker, a down embedding model) degrade gracefully
   and say so, instead of failing hard or silently.

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
Hybrid Search  Tool Gateway  Retrieval (iterated, ≤4 hops)
      |            |            |
  Reranker    DB/Calculator   Reranker
      |____________|____________|
                   |
          Authorization filter  (clearance vs. confidentiality_level)
                   |
               Gemini LLM  (or extractive fallback if unavailable)
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
Security posture: `docs/T42_Security_Hardening_Report.md`.

## Technology stack

**Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0 + SQLite,
Google Gemini (no OpenAI), `sentence-transformers/all-MiniLM-L6-v2` (dense
embeddings), `rank-bm25` (sparse retrieval), `cross-encoder/ms-marco-MiniLM-L-6-v2`
(reranking), pypdf + python-docx (parsing), pytest.

**Frontend:** React + Vite, no UI framework dependency beyond React itself
(kept deliberately light so it installs and builds reliably). No Streamlit
anywhere in this project.

## Project structure

```
enterprise-ai-copilot/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # health, chat, documents, search, prompts, security, observability, evaluation
│   │   ├── core/              # config, structured logging, errors, resilience
│   │   ├── models/            # SQLAlchemy models (documents, chunks, prompts, evaluations, security/observability events)
│   │   ├── security/          # PII detection, prompt-injection detection, gateway, authorization
│   │   ├── tools/             # tool gateway, schemas, calculator, KB search, structured DB search
│   │   ├── agents/            # orchestrator router, multi-hop planner
│   │   ├── prompts/           # prompt registry (versioning)
│   │   ├── rag/                # chunking, embeddings, vector store, BM25, hybrid retrieval, reranker, answer synthesis
│   │   ├── evaluation/         # benchmark datasets, executable runner, regression detection
│   │   ├── services/           # ingestion pipeline, Gemini client wrapper
│   │   ├── observability/      # (tracing helpers — Phase 3)
│   │   └── main.py
│   ├── tests/                  # 61 passing pytest tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React + Vite — Dashboard, Chat, Documents, Evaluation, Observability, Security, Prompts
├── evaluation/                 # (reserved for external benchmark data files)
├── load_tests/                 # Locust script (not yet executed under real concurrency)
├── docs/                        # T33–T48 documentation set
├── scripts/
├── .github/workflows/ci.yml
├── .env.example
├── docker-compose.yml
├── MONTH_2_TO_MONTH_3_MIGRATION_PLAN.md
└── README.md
```

## Setup (Windows / PowerShell)

### Backend

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

The first request that uses embeddings or reranking will download the
Hugging Face models (`sentence-transformers/all-MiniLM-L6-v2` and
`cross-encoder/ms-marco-MiniLM-L-6-v2`, a few hundred MB total) — this
needs outbound internet access once, then they're cached locally.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` to
`http://localhost:8000`, so start the backend first.

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

Expected: **61 passed**. This includes tests that genuinely exercise the
Gemini-unavailable fallback path (no real API key is configured in this
environment, so those tests prove the fallback works, not that Gemini
answered) — see `tests/test_gemini_fallback.py`.

## Environment variables

See `.env.example` at the repo root. Never commit a real `.env` file — it is
git-ignored. No API keys, secrets, or credentials appear anywhere in this
repository.

## API (Phase 2)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| POST | `/api/v1/chat` | Full pipeline: security gateway → orchestrator → RAG/tool/multi-hop → authorization → synthesis → response |
| POST | `/api/v1/search` | Raw hybrid retrieval + rerank, no LLM synthesis (debugging / evaluation) |
| POST | `/api/v1/documents/upload` | Upload + ingest a PDF/DOCX/TXT with enterprise metadata |
| GET | `/api/v1/documents` | List documents (filterable by status/business_unit) |
| DELETE | `/api/v1/documents/{id}` | Remove a document and its chunks/vectors |
| GET | `/api/v1/prompts` | List prompt versions |
| POST | `/api/v1/prompts` | Create a new prompt version |
| POST | `/api/v1/prompts/{id}/activate?version=N` | Activate a version |
| POST | `/api/v1/prompts/{id}/rollback?version=N` | Roll back to a previous version |
| GET | `/api/v1/security/events` | Security Center data (PII/injection/policy events) |
| GET | `/api/v1/observability` | Request-level observability events with latency breakdown |
| POST | `/api/v1/evaluate` | Run the executable benchmark suite, write metrics |
| POST | `/api/v1/evaluate/compare` | Compare two runs, flag regressions |
| POST | `/api/v1/evaluate/prompt-change` | Benchmark a candidate prompt version vs. the active one, auto-rollback on regression |
| GET | `/api/v1/metrics` | Evaluation metric history |

`X-User-Clearance` header (`Public`/`Internal`/`Confidential`/`Restricted`,
defaults to `Internal`) controls document authorization on `/chat` and
`/search` — see the security posture section below for why this is a
placeholder, not real authentication.

## Security posture

Full OWASP LLM Top 10-oriented review: `docs/T42_Security_Hardening_Report.md`.
Summary:

- Prompt-injection and PII scanning on every `/chat` request, plus on every
  retrieved document chunk before it reaches a prompt template.
- Retrieved/external content is always wrapped as `<untrusted_data>` so a
  document can never pose as an instruction.
- No arbitrary code execution anywhere: the calculator tool uses Python's
  `ast` module with a strict node-type allowlist; the structured-DB-search
  tool only queries an explicit table allowlist, never raw SQL.
- All tool calls go through a single Tool Gateway: allowlisted, schema
  validated, timeout-bounded, capped at `max_agent_steps` per request.
- **Authorization is a separate concern from metadata filtering.** A
  document's `confidentiality_level` is enforced by
  `app/security/authorization.py` on every retrieval, regardless of what
  business-unit/document-type filter (if any) the caller requested — a
  broad or missing filter can never leak a Restricted document. Verified
  live: a `search` request with `X-User-Clearance: Internal` cannot see a
  Restricted document even when it is the best-matching result.
- Known, documented gap: clearance is read from a request header with no
  real identity provider behind it yet (see the security report).

## Observability

Structured JSON logs with request-id propagation; per-request metrics
persisted to `observability_events`, including the full latency breakdown
(retrieval / rerank / LLM / tool), router decision, retrieval strategy,
prompt version used, and fallback flag + reason. Visible live in the
frontend's Observability tab or via `GET /api/v1/observability`.

## Evaluation & regression detection

`POST /api/v1/evaluate` runs a real benchmark (3 QA cases against seeded
sample documents, 3 safety cases including real injection strings, 2 tool
cases) through the actual pipeline and writes genuine metric values —
nothing here is a static table. `POST /api/v1/evaluate/prompt-change`
benchmarks a candidate prompt version against the currently active one and
automatically rolls back via the Prompt Registry if the decisive metric
regresses beyond a threshold. See `docs/TASK_STATUS.md` for the actual
metric values this repository produced in this session.

## Deployment

Docker skeleton exists (`backend/Dockerfile`, `docker-compose.yml`) but has
not been built or deployed in this session — no deployment success is
claimed anywhere in this repository. A frontend Dockerfile + compose service
is Phase 3.

## Load testing

`load_tests/locustfile.py` is ready (health/chat/search/documents tasks)
but has **not been run under real concurrency** in this session — per the
project's "no fabricated measurements" rule, that requires Satish to run it
against a real instance:

```powershell
pip install locust
locust -f load_tests\locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 to configure concurrency and start.

## Troubleshooting

- **`ModuleNotFoundError: app`** — run pytest/uvicorn from the `backend/`
  directory; `pytest.ini` sets `pythonpath = .` relative to it.
- **PowerShell activation blocked** — use `.\venv\Scripts\python.exe` /
  `.\venv\Scripts\pip.exe` directly instead of `Activate.ps1`.
- **SQLite "database is locked"** — only one process should hold
  `data/app.db` at a time in local dev; stop any previously running
  `uvicorn` instance first.
- **Embedding/reranker model download fails** — these need one-time
  outbound internet access to huggingface.co; if your network blocks it,
  retrieval falls back to BM25-only automatically (and says so), but for
  full hybrid search you'll need that access at least once.
- **Frontend shows a network error** — make sure the backend is running on
  port 8000 before `npm run dev`; the dev server proxies `/api` there.

## T33–T48 mapping

See `docs/TASK_STATUS.md` for the live, honest status of every task —
Implemented / Tested / Evidence Captured / Complete, with no task marked
Complete on documentation alone, and an explicit list of genuine blockers
that need Satish's input (a real Gemini key, running the load test, pushing
to GitHub for real CI, and a decision on real authentication).

---
⚠️ Internal capstone project for Fulcrum Digital. AI-generated content in
this repository (documentation, code comments, design rationale) should be
validated by a qualified engineer before being treated as a stakeholder-ready
deliverable. Questions on data handling or security posture: CISO@fulcrumdigital.com.
