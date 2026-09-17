# T41 — Load Test Report

Status: **script ready, not yet executed under real concurrency.** No
throughput, latency-under-load, concurrency, or bottleneck numbers are
recorded in this document, because none have been genuinely measured in
this development environment (no daemon/staging environment with the
network conditions load testing requires is available here, and this
project's standing rule is to never fabricate performance measurements).
Every number below is a placeholder for Satish to fill in after he
actually runs this.

## What exists

`load_tests/locustfile.py` — a Locust script exercising the four
highest-traffic endpoints in realistic proportion: `/chat` (weight 5,
covering RAG/tool/multi-hop paths via randomized sample queries),
`/search` (weight 2), `/documents` listing (weight 1), and `/health`
(weight 3, as a baseline).

## Exact commands to run this yourself

```powershell
cd backend
.\venv\Scripts\pip.exe install locust
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

In a second terminal:

```powershell
cd load_tests
..\backend\venv\Scripts\python.exe -m locust -f locustfile.py --host http://localhost:8000
```

Open `http://localhost:8089`, set the number of users and spawn rate, and
start the run. Locust's web UI gives you requests/sec, response-time
percentiles, and failure rate live, and can export a CSV report
(`--csv=report` flag on the command line, or the "Download Data" button
in the UI).

## Results

**[Satish: paste real results here after running the above — number of
concurrent users, spawn rate, duration, requests/sec, p50/p95/p99 latency
per endpoint, failure rate, and any bottleneck observed (e.g. reranker
CPU-bound, SQLite write contention under concurrent document uploads).]**

## Known theoretical bottlenecks (reasoned about, not measured)

These are architectural predictions based on reading the code, explicitly
labeled as such — not measurements:

- The flat-file vector store (`app/rag/vector_store.py`) loads its full
  numpy matrix into the single backend process's memory; concurrent
  `/chat` requests share it read-only, so this is unlikely to bottleneck
  reads, but it does mean the whole index must fit in one process's RAM.
- SQLite's single-writer model means concurrent document uploads
  (each a write transaction) could serialize under high concurrency —
  worth watching for in the real load test's `/documents/upload` numbers
  if that endpoint is included in a future run.
- The cross-encoder reranker and embedding model both run on CPU in this
  environment (no GPU); latency under concurrent `/chat` load is the
  single most important number to actually measure here.

---
⚠️ AI-generated. No performance numbers are claimed until Satish runs the
above and records real results.
