"""
Load test skeleton (Locust), per spec — T41.

Run against a live backend:
    pip install locust
    locust -f load_tests/locustfile.py --host http://localhost:8000

Then open http://localhost:8089, set concurrency, and start the run.

IMPORTANT — per project rule "do not fabricate real-world evidence":
this file has NOT been executed against a staging/production deployment
in this session. Running it and recording throughput/latency/error-rate
numbers under real concurrency is explicitly left to Satish
(docs/T41_Load_Test_Report.md marks those numbers as pending until he
runs this and pastes results in).
"""
import random

from locust import HttpUser, between, task

SAMPLE_QUERIES = [
    "What is our leave policy?",
    "How quickly must a P1 security incident be escalated?",
    "12 * 7 + 3",
    "Compare our 2023 and 2024 security policies and how they changed.",
]


class CopilotUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health(self):
        self.client.get("/api/v1/health")

    @task(5)
    def chat(self):
        self.client.post(
            "/api/v1/chat",
            json={"message": random.choice(SAMPLE_QUERIES)},
            headers={"X-User-Clearance": "Internal"},
        )

    @task(2)
    def search(self):
        self.client.post(
            "/api/v1/search",
            json={"query": random.choice(SAMPLE_QUERIES), "top_k": 5},
        )

    @task(1)
    def list_documents(self):
        self.client.get("/api/v1/documents")
