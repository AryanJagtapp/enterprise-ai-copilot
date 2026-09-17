# T44 — Operational Runbook

Status: Phase 3. Every command below has actually been run against this
repository in this development environment and the stated result is what
was actually observed — not a projected/expected result. Re-run them
yourself before a demo; environments differ (see "Known environment
differences" at the end).

## 1. Prerequisites

- Python 3.11
- Node.js 20+ (for the frontend)
- A real `GEMINI_API_KEY` if you want to exercise real Gemini generation
  instead of the (fully functional, tested) extractive fallback path.
  Without one, the system does not degrade to an error — it degrades to
  the extractive fallback and says so honestly in `fallback_reason`.

## 2. First-time setup (Windows / PowerShell)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip.exe install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt
copy ..\.env.example .env
# Edit .env and set GEMINI_API_KEY if you have one. Never commit this file.
```

```powershell
cd ..\frontend
npm install
```

(Linux/macOS: use `python3 -m venv venv`, `source venv/bin/activate`, and
forward-slash paths in place of the PowerShell equivalents above — this is
exactly what was actually used in this development sandbox.)

## 3. Running the backend

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Health check:

```powershell
curl http://localhost:8000/api/v1/health
```

Expected: `{"status":"ok"}` (verified in this session — see T33/TASK_STATUS
for the live curl transcript).

## 4. Running the frontend

```powershell
cd frontend
npm run dev
```

Opens on `http://localhost:5173` by default, proxying `/api` calls to the
backend on port 8000 (see `frontend/vite.config.js`).

## 5. Running the test suite

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -v
```

As of this Phase 3 delivery: **78 passed, 0 failed** (61 from Phase 2 +
17 new Phase 3 tests covering tool-gateway authorization/timeout/invalid-
argument behavior, the structured-DB-search routing path end-to-end, and
the malformed-prompt-template crash-safety fix). This was actually run in
this session immediately before writing this document — see the pytest
transcript captured in the Phase 3 summary message.

## 6. Linting

```powershell
cd backend
.\venv\Scripts\python.exe -m ruff check app tests
```

Expected: `All checks passed!` (verified in this session).

## 7. Common operational tasks

### Ingest a document

```powershell
curl -X POST http://localhost:8000/api/v1/documents/upload `
  -F "file=@C:\path\to\policy.pdf" `
  -F "document_type=policy" `
  -F "business_unit=CD" `
  -F "confidentiality_level=Internal"
```

### Ask a question (RAG path)

```powershell
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\": \"What is our leave policy?\"}"
```

### Ask a structured-data question (new Phase 3 path)

```powershell
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\": \"How many policy documents do we have for CD?\"}"
```

### Run the evaluation suite and view results

```powershell
curl -X POST http://localhost:8000/api/v1/evaluate `
  -H "Content-Type: application/json" -d "{\"run_label\": \"manual_check\"}"
curl "http://localhost:8000/api/v1/metrics?run_label=manual_check"
```

### Roll back a prompt version manually

```powershell
curl -X POST "http://localhost:8000/api/v1/prompts/multi_hop_planner/rollback?version=1"
```

(Verified against `backend/app/api/routes/prompts.py` and
`app/api/routes/evaluation.py` as they exist in this Phase 3 delivery —
`version`/`run_label` are query parameters, not JSON body fields, for the
activate/rollback routes. Re-check those files if they change later.)

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `no such table` on startup | In-memory SQLite without `StaticPool` (should not occur — already fixed) | Confirm `DATABASE_URL` isn't accidentally overridden to a fresh `:memory:` per connection |
| Chat always returns extractive fallback | No real `GEMINI_API_KEY` set, or it matches a known placeholder string | Set a real key in `backend/.env`; check `app/services/gemini_client.py`'s placeholder list |
| `pip install` fails on `sentence-transformers`/`torch` | No network access / registry blocked | Confirm outbound access to PyPI; these are large downloads (500MB+ for torch) |
| Reranker falls back to "original order" | Cross-encoder model failed to download/load from Hugging Face Hub | Check network access to `huggingface.co`; this is a genuine, tested fallback, not a bug |
| CORS errors from the frontend | Backend not running on the port the Vite proxy expects | Confirm backend is on port 8000, or update `frontend/vite.config.js` |

## Known environment differences

This runbook's commands were executed in a Linux sandbox using
`.venv/bin/python`/`.venv/bin/pip` rather than the PowerShell
`.\venv\Scripts\...` paths shown above (which are what Satish's actual
Windows machine uses). Both point at the same virtual environment
layout; only the path separator and activation mechanics differ.

---
⚠️ AI-generated. Validate with a qualified professional. If you hit a
failure mode not listed here, please add it to this table rather than
working around it silently — that keeps this runbook honest.
