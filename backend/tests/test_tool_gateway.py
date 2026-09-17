"""
Tool Gateway verification (Phase 3 priority #2).

Covers the specific behaviors the capstone asks to be demonstrated:
correct tool selection/execution, invalid arguments rejected by schema
validation, unauthorized/non-allowlisted access refused, timeout
handling, and missing required context refused — all through the same
single choke point (ToolGateway.call), never by calling calculate()/
the DB helpers directly.
"""
import time

import pytest

from app.core.errors import ToolFailure
from app.tools.gateway import ToolContext, ToolGateway
from app.tools.query_parsing import looks_like_structured_db_query, parse_structured_db_query


def test_calculator_correct_selection_and_execution():
    gateway = ToolGateway()
    result = gateway.call("calculator", {"expression": "6 * 7"}, calls_so_far=0)
    assert result.success is True
    assert result.output == 42


def test_invalid_arguments_rejected_by_schema():
    gateway = ToolGateway()
    with pytest.raises(ToolFailure) as excinfo:
        # 'expression' is required by CalculatorArgs; omitting it must fail
        # schema validation before the tool function is ever invoked.
        gateway.call("calculator", {"not_expression": "1+1"}, calls_so_far=0)
    assert "invalid arguments" in str(excinfo.value.detail)


def test_unregistered_tool_name_is_refused():
    gateway = ToolGateway()
    with pytest.raises(ToolFailure) as excinfo:
        gateway.call("delete_all_files", {}, calls_so_far=0)
    assert "not on the allowlist" in str(excinfo.value.detail)


def test_structured_db_search_rejects_non_allowlisted_table(db_session):
    gateway = ToolGateway()
    context = ToolContext(db=db_session, request_id="test-req", clearance="Internal")
    with pytest.raises(ToolFailure) as excinfo:
        gateway.call(
            "structured_db_search",
            {"table": "users", "filters": {}, "limit": 10},
            calls_so_far=0,
            context=context,
        )
    assert "approved allowlist" in str(excinfo.value.detail)


def test_structured_db_search_rejects_unknown_filter_field(db_session):
    gateway = ToolGateway()
    context = ToolContext(db=db_session, request_id="test-req", clearance="Internal")
    with pytest.raises(ToolFailure) as excinfo:
        gateway.call(
            "structured_db_search",
            {"table": "documents", "filters": {"ssn": "123-45-6789"}, "limit": 10},
            calls_so_far=0,
            context=context,
        )
    assert "unknown filter field" in str(excinfo.value.detail)


def test_context_needing_tool_refused_without_context(db_session):
    gateway = ToolGateway()
    with pytest.raises(ToolFailure) as excinfo:
        gateway.call(
            "structured_db_search",
            {"table": "documents", "filters": {}, "limit": 5},
            calls_so_far=0,
            context=None,
        )
    assert "requires request context" in str(excinfo.value.detail)


def test_max_agent_steps_enforced():
    gateway = ToolGateway(max_calls_per_request=2)
    with pytest.raises(ToolFailure) as excinfo:
        gateway.call("calculator", {"expression": "1+1"}, calls_so_far=2)
    assert "maximum agent steps" in str(excinfo.value.detail)


def test_tool_call_timeout_is_caught_as_tool_failure():
    gateway = ToolGateway(timeout_seconds=0)

    def _slow_calc(expression: str) -> float:
        time.sleep(0.3)
        return 1.0

    from app.tools import gateway as gateway_module

    gateway_module.TOOL_REGISTRY["calculator"].fn = _slow_calc
    try:
        with pytest.raises(ToolFailure) as excinfo:
            gateway.call("calculator", {"expression": "1+1"}, calls_so_far=0)
        assert "timed out" in str(excinfo.value.detail)
        assert excinfo.value.retriable is True
    finally:
        # Restore the real implementation so other tests are unaffected.
        from app.tools.calculator import calculate

        gateway_module.TOOL_REGISTRY["calculator"].fn = lambda expression: calculate(expression)


def test_structured_db_search_end_to_end_via_gateway(db_session):
    """A genuine end-to-end call: ingest a document, then confirm the
    gateway's structured_db_search tool actually finds it via the
    allowlisted 'documents' table."""
    from app.services.ingestion import ingest_document

    ingest_document(
        db_session,
        filename="cd_policy.txt",
        raw_bytes=b"Some Consulting Delivery (CD) policy text about engagement standards.",
        document_type="policy",
        business_unit="CD",
        confidentiality_level="Internal",
        source="test",
    )

    gateway = ToolGateway()
    context = ToolContext(db=db_session, request_id="test-req", clearance="Internal")
    result = gateway.call(
        "structured_db_search",
        {"table": "documents", "filters": {"business_unit": "CD"}, "limit": 20},
        calls_so_far=0,
        context=context,
    )
    assert result.success is True
    assert any(row["filename"] == "cd_policy.txt" for row in result.output)


def test_query_parsing_heuristics_recognize_structured_db_shape():
    assert looks_like_structured_db_query("How many policies do we have for CD?")
    assert looks_like_structured_db_query("List all contracts for shared business unit")
    assert not looks_like_structured_db_query("What is our leave policy?")

    parsed = parse_structured_db_query("How many policies do we have for CD?")
    assert parsed.table == "documents"
    assert parsed.filters.get("business_unit") == "CD"
    assert parsed.filters.get("document_type") == "policy"
