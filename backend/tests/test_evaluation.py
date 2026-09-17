import uuid

from app.evaluation.regression import compare_runs
from app.evaluation.runner import run_evaluation
from app.models.db import Evaluation
from app.prompts.registry import seed_default_prompts


def test_run_evaluation_produces_real_metrics(rag_isolated):
    db = rag_isolated
    seed_default_prompts(db)
    run_label = f"test_run_{uuid.uuid4().hex[:6]}"
    results = run_evaluation(db, run_label)
    names = {r.name for r in results}
    assert "retrieval_hit_rate" in names
    assert "citation_presence_rate" in names
    assert "safety_case_pass_rate" in names
    assert "tool_reliability_rate" in names

    rows = db.query(Evaluation).filter(Evaluation.run_label == run_label).all()
    assert len(rows) == len(results)


def test_safety_case_pass_rate_is_high(rag_isolated):
    """The seeded SAFETY_CASES include real injection strings the gateway
    must block and one benign query it must allow — this is a real
    assertion about gateway behavior, not a fabricated number."""
    db = rag_isolated
    seed_default_prompts(db)
    results = run_evaluation(db, "safety_check_run")
    safety_metric = next(r for r in results if r.name == "safety_case_pass_rate")
    assert safety_metric.value == 1.0


def test_compare_runs_flags_regression_on_worse_candidate(rag_isolated):
    db = rag_isolated
    baseline_label, candidate_label = "baseline_run", "candidate_run"
    db.add(Evaluation(id=uuid.uuid4().hex, run_label=baseline_label, metric_name="citation_presence_rate", metric_value=0.9))
    db.add(Evaluation(id=uuid.uuid4().hex, run_label=candidate_label, metric_name="citation_presence_rate", metric_value=0.5))
    db.commit()

    comparisons = compare_runs(db, baseline_label, candidate_label, threshold=0.10)
    citation_comparison = next(c for c in comparisons if c.metric_name == "citation_presence_rate")
    assert citation_comparison.regression is True

    updated_row = db.query(Evaluation).filter(Evaluation.run_label == candidate_label).first()
    assert updated_row.regression_detected is True


def test_compare_runs_no_regression_on_improvement(rag_isolated):
    db = rag_isolated
    db.add(Evaluation(id=uuid.uuid4().hex, run_label="base2", metric_name="retrieval_hit_rate", metric_value=0.6))
    db.add(Evaluation(id=uuid.uuid4().hex, run_label="cand2", metric_name="retrieval_hit_rate", metric_value=0.9))
    db.commit()

    comparisons = compare_runs(db, "base2", "cand2")
    hit_rate_comparison = next(c for c in comparisons if c.metric_name == "retrieval_hit_rate")
    assert hit_rate_comparison.regression is False


def test_compare_runs_flags_latency_regression_when_slower():
    from tests.conftest import fresh_session

    db = fresh_session()
    db.add(Evaluation(id=uuid.uuid4().hex, run_label="b3", metric_name="avg_retrieval_latency_ms", metric_value=100.0))
    db.add(Evaluation(id=uuid.uuid4().hex, run_label="c3", metric_name="avg_retrieval_latency_ms", metric_value=200.0))
    db.commit()

    comparisons = compare_runs(db, "b3", "c3", threshold=0.10)
    latency_comparison = next(c for c in comparisons if c.metric_name == "avg_retrieval_latency_ms")
    assert latency_comparison.regression is True  # slower candidate = regression for a latency metric
