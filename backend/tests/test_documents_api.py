import io


def test_upload_list_delete_document(client):
    files = {"file": ("api_test_doc.txt", io.BytesIO(b"This is a unique API test document about onboarding."), "text/plain")}
    data = {"document_type": "policy", "business_unit": "shared", "confidentiality_level": "Internal", "tags": "hr,onboarding"}
    resp = client.post("/api/v1/documents/upload", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "indexed"
    document_id = body["document"]["document_id"]
    assert body["document"]["tags"] == ["hr", "onboarding"]

    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    assert any(d["document_id"] == document_id for d in list_resp.json())

    delete_resp = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] == document_id

    list_resp_after = client.get("/api/v1/documents")
    assert not any(d["document_id"] == document_id for d in list_resp_after.json())


def test_upload_rejects_unsupported_extension(client):
    files = {"file": ("bad.exe", io.BytesIO(b"not allowed"), "application/octet-stream")}
    resp = client.post("/api/v1/documents/upload", files=files, data={})
    assert resp.status_code == 422


def test_upload_duplicate_returns_conflict(client):
    content = b"Duplicate detection test content, unique string 12345."
    files1 = {"file": ("dup1.txt", io.BytesIO(content), "text/plain")}
    files2 = {"file": ("dup2.txt", io.BytesIO(content), "text/plain")}
    first = client.post("/api/v1/documents/upload", files=files1, data={})
    assert first.status_code == 200
    second = client.post("/api/v1/documents/upload", files=files2, data={})
    assert second.status_code == 409
