"""
Orchestrator + /chat integration coverage for the structured_db_search
path added in Phase 3 (priority #2/#3): confirms the router actually
distinguishes a structured-database question from RAG/tool/multi-hop,
and that the /chat endpoint actually executes it end-to-end through the
Tool Gateway rather than leaving the route unhandled.
"""
import io

from app.agents.orchestrator import RoutePath, decide_route


def test_structured_db_query_routes_to_structured_db_tool():
    decision = decide_route("How many policy documents do we have for CD?")
    assert decision.path == RoutePath.TOOL
    assert decision.tool_name == "structured_db_search"


def test_structured_db_query_does_not_get_misrouted_to_rag_or_multi_hop():
    decision = decide_route("List all contracts for the shared business unit")
    assert decision.path == RoutePath.TOOL
    assert decision.tool_name == "structured_db_search"


def test_chat_endpoint_structured_db_search_path(client):
    # Upload a document tagged CD/policy so the structured search has
    # something real to find.
    files = {"file": ("cd_structured_test.txt", io.BytesIO(b"CD policy content for structured db routing test."), "text/plain")}
    data = {"document_type": "policy", "business_unit": "CD", "confidentiality_level": "Internal"}
    upload_resp = client.post("/api/v1/documents/upload", files=files, data=data)
    assert upload_resp.status_code == 200

    resp = client.post("/api/v1/chat", json={"message": "How many policies do we have for CD?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["router_decision"] == "TOOL"
    assert "structured_db_search" in body["tools_used"]
    assert "cd_structured_test.txt" in body["answer"] or "Found" in body["answer"]


def test_chat_endpoint_structured_db_search_no_match_is_graceful(client):
    resp = client.post("/api/v1/chat", json={"message": "How many runbooks do we have for a nonexistent client XYZ123?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["router_decision"] == "TOOL"
    assert "structured_db_search" in body["tools_used"]
    # No crash, no 500 — either a real hit or the graceful "no match" message.
    assert body["answer"]


def test_chat_never_exposes_raw_chain_of_thought(client):
    """The response schema only ever carries safe structured metadata
    (route/citations/tools_used/etc.), never a raw model 'reasoning' or
    'thoughts' field — this is the hidden-chain-of-thought guarantee
    Phase 3 priority #3 asks to be verified."""
    resp = client.post("/api/v1/chat", json={"message": "What is our company leave policy?"})
    assert resp.status_code == 200
    body = resp.json()
    for forbidden_key in ("reasoning", "thoughts", "chain_of_thought", "internal_notes"):
        assert forbidden_key not in body
