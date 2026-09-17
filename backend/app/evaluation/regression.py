"""
Regression detection + rollback (Feature 2).

    Version A -> Benchmark -> Metrics
    Version B -> Benchmark -> Metrics
                    |
                 Compare
                /        \\
        Improvement    Regression -> PromptRegistry.rollback()

`compare_runs` reads the two runs' metric rows already written by
evaluation/runner.py (never fabricates numbers) and flags a regression
per "higher is better" metric when it drops by more than `threshold`
(relative), or per "lower is better" latency metric when it rises by
more than `threshold`. `evaluate_prompt_change` is the end-to-end
workflow: benchmark the candidate prompt version, compare against the
currently active version's last benchmark, and — only if the caller asks
for auto-rollback and a regression is confirmed on the decisive metric —
actually call PromptRegistry.rollback().
"""
from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.orm import Session

from app.evaluation.runner import run_evaluation
from app.models.db import Evaluation
from app.prompts.registry import PromptRegistry

LOWER_IS_BETTER = {"avg_retrieval_latency_ms"}
DEFAULT_THRESHOLD = 0.10  # 10% relative degradation counts as a regression


@dataclass
class MetricComparison:
    metric_name: str
    baseline_value: float
    candidate_value: float
    regression: bool
    delta_pct: float


def _latest_run_metrics(db: Session, run_label: str) -> Dict[str, float]:
    rows = db.query(Evaluation).filter(Evaluation.run_label == run_label).all()
    return {r.metric_name: r.metric_value for r in rows}


def compare_runs(db: Session, baseline_label: str, candidate_label: str, *, threshold: float = DEFAULT_THRESHOLD) -> List[MetricComparison]:
    baseline_metrics = _latest_run_metrics(db, baseline_label)
    candidate_metrics = _latest_run_metrics(db, candidate_label)

    comparisons: List[MetricComparison] = []
    for name, candidate_value in candidate_metrics.items():
        baseline_value = baseline_metrics.get(name)
        if baseline_value is None or baseline_value == 0:
            continue
        delta_pct = (candidate_value - baseline_value) / abs(baseline_value)
        if name in LOWER_IS_BETTER:
            regression = delta_pct > threshold  # candidate got slower
        else:
            regression = delta_pct < -threshold  # candidate got worse
        comparisons.append(
            MetricComparison(metric_name=name, baseline_value=baseline_value, candidate_value=candidate_value, regression=regression, delta_pct=delta_pct)
        )

    # Persist the verdict back onto the candidate's rows so /metrics and the
    # frontend Evaluation view can show it without recomputing.
    regressed_names = {c.metric_name for c in comparisons if c.regression}
    if regressed_names:
        rows = db.query(Evaluation).filter(Evaluation.run_label == candidate_label, Evaluation.metric_name.in_(regressed_names)).all()
        for row in rows:
            row.regression_detected = True
        db.commit()

    return comparisons


def evaluate_prompt_change(
    db: Session,
    *,
    prompt_id: str,
    candidate_version: int,
    decisive_metric: str = "citation_presence_rate",
    threshold: float = DEFAULT_THRESHOLD,
    auto_rollback: bool = True,
) -> dict:
    """
    Runs the full Version A vs Version B workflow for a single prompt:
    benchmark the currently-active version (baseline), activate the
    candidate version, benchmark it, compare, and roll back automatically
    if the decisive metric regressed and auto_rollback=True.
    """
    registry = PromptRegistry(db)
    baseline_view = registry.get_active(prompt_id)
    baseline_label = f"{prompt_id}_v{baseline_view.version}_baseline"
    run_evaluation(db, baseline_label)

    registry.activate_version(prompt_id, candidate_version)
    candidate_label = f"{prompt_id}_v{candidate_version}_candidate"
    run_evaluation(db, candidate_label)

    comparisons = compare_runs(db, baseline_label, candidate_label, threshold=threshold)
    decisive = next((c for c in comparisons if c.metric_name == decisive_metric), None)

    rolled_back = False
    if decisive is not None and decisive.regression and auto_rollback:
        registry.rollback(prompt_id, baseline_view.version)
        rolled_back = True
    elif decisive is None or not decisive.regression:
        # No regression on the decisive metric — keep the candidate active (already is).
        pass

    return {
        "prompt_id": prompt_id,
        "baseline_version": baseline_view.version,
        "candidate_version": candidate_version,
        "comparisons": [c.__dict__ for c in comparisons],
        "decisive_metric": decisive_metric,
        "regression_detected": bool(decisive and decisive.regression),
        "rolled_back": rolled_back,
        "active_version_after": registry.get_active(prompt_id).version,
    }
