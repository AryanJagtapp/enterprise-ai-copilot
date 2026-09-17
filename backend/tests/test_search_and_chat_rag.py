import io


def test_search_endpoint_returns_results_after_upload(client):
    files = {"file": ("search_test_doc.txt", io.BytesIO(b"Our FinOps quarterly review covers Azure reserved instance savings."), "text/plain")}
    client.post("/api/v1/documents/upload", files=files, data={"document_type": "runbook", "business_unit": "FD"})

    resp = client.post("/api/v1/search", json={"query": "Azure reserved instance savings", "top_k": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"]
    assert any("reserved instance" in r["text"].lower() for r in body["results"])


def test_chat_rag_path_returns_grounded_fallback_answer(client):
    files = {"file": ("rag_chat_doc.txt", io.BytesIO(b"The onboarding checklist requires a laptop request within 24 hours of joining."), "text/plain")}
    client.post("/api/v1/documents/upload", files=files, data={"document_type": "policy", "business_unit": "shared"})

    resp = client.post("/api/v1/chat", json={"message": "What does the onboarding checklist require for a laptop?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["router_decision"] == "RAG"
    assert body["fallback_triggered"] is True  # no real Gemini key in this environment
    assert any("Gemini" in r for r in body["fallback_reasons"])
    assert body["citations"]


def test_chat_respects_authorization_over_metadata_filter(client):
    files = {"file": ("restricted_doc.txt", io.BytesIO(b"The restricted merger negotiation terms include a 90 day exclusivity clause."), "text/plain")}
    client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"document_type": "contract", "business_unit": "shared", "confidentiality_level": "Restricted"},
    )

    resp = client.post(
        "/api/v1/search",
        json={"query": "exclusivity clause merger negotiation terms", "top_k": 5},
        headers={"X-User-Clearance": "Internal"},
    )
    assert resp.status_code == 200
    assert all("exclusivity" not in r["text"].lower() for r in resp.json()["results"])
