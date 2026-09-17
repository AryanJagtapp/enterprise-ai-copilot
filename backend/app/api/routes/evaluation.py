import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.evaluation.regression import compare_runs, evaluate_prompt_change
from app.evaluation.runner import run_evaluation
from app.models.db import Evaluation, get_db

router = APIRouter(tags=["evaluation"])


class RunEvaluationRequest(BaseModel):
    run_label: str | None = None


class CompareRunsRequest(BaseModel):
    baseline_label: str
    candidate_label: str
    threshold: float = 0.10


class EvaluatePromptChangeRequest(BaseModel):
    prompt_id: str
    candidate_version: int
    decisive_metric: str = "citation_presence_rate"
    threshold: float = 0.10
    auto_rollback: bool = True


@router.post("/evaluate")
def evaluate(payload: RunEvaluationRequest, db: Session = Depends(get_db)):
    run_label = payload.run_label or f"run_{uuid.uuid4().hex[:8]}"
    results = run_evaluation(db, run_label)
    return {"run_label": run_label, "metrics": [{"name": r.name, "value": r.value} for r in results]}


@router.post("/evaluate/compare")
def compare(payload: CompareRunsRequest, db: Session = Depends(get_db)):
    comparisons = compare_runs(db, payload.baseline_label, payload.candidate_label, threshold=payload.threshold)
    return {"comparisons": [c.__dict__ for c in comparisons]}


@router.post("/evaluate/prompt-change")
def evaluate_prompt_change_endpoint(payload: EvaluatePromptChangeRequest, db: Session = Depends(get_db)):
    return evaluate_prompt_change(
        db,
        prompt_id=payload.prompt_id,
        candidate_version=payload.candidate_version,
        decisive_metric=payload.decisive_metric,
        threshold=payload.threshold,
        auto_rollback=payload.auto_rollback,
    )


@router.get("/metrics")
def metrics(run_label: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Evaluation)
    if run_label:
        query = query.filter(Evaluation.run_label == run_label)
    rows = query.order_by(Evaluation.created_at.desc()).limit(limit).all()
    return [
        {
            "run_label": r.run_label,
            "metric_name": r.metric_name,
            "metric_value": r.metric_value,
            "baseline_value": r.baseline_value,
            "regression_detected": r.regression_detected,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
