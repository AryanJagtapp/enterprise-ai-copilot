"""
Executable evaluation harness (Feature 2).

`run_evaluation()` actually calls the real pipeline (ingestion, retrieval,
reranking, synthesis, security gateway, tool gateway) against the
benchmark cases in datasets.py and writes real metric values to the
`evaluations` table under the given run_label. Nothing here is a static
number — running it twice against different code produces different,
genuine measurements.
"""
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.evaluation.datasets import QA_CASES, SAFETY_CASES, SAMPLE_DOCUMENTS, TOOL_CASES
from app.models.db import Evaluation
from app.prompts.registry import PromptRegistry
from app.rag.answer_synthesis import synthesize
from app.rag.hybrid_retrieval import retrieve
from app.rag.reranker import rerank
from app.security.gateway import inspect_input
from app.services.ingestion import ingest_document
from app.tools.calculator import calculate


@dataclass
class MetricResult:
    name: str
    value: float


def ensure_sample_documents_ingested(db: Session) -> None:
    """Idempotent — skips a sample document if its content hash is already indexed."""
    from app.services.ingestion import compute_content_hash, find_duplicate

    for doc in SAMPLE_DOCUMENTS:
        raw_bytes = doc["text"].encode("utf-8")
        if find_duplicate(db, compute_content_hash(raw_bytes)) is not None:
            continue
        ingest_document(
            db,
            filename=doc["filename"],
            raw_bytes=raw_bytes,
            document_type=doc["document_type"],
            business_unit=doc["business_unit"],
            confidentiality_level=doc["confidentiality_level"],
            source="evaluation_seed",
        )


def _retrieval_and_citation_metrics(db: Session) -> Dict[str, float]:
    hits = 0
    citations_present = 0
    latencies: List[float] = []

    for case in QA_CASES:
        t0 = time.perf_counter()
        result = retrieve(db, case["query"], top_k=5)
        latencies.append((time.perf_counter() - t0) * 1000)

        reranked, _, _ = rerank(case["query"], result.chunks, top_k=3)
        combined_text = " ".join(c.text.lower() for c in reranked)
        if any(kw.lower() in combined_text for kw in case["expected_keywords"]):
            hits += 1

        synthesis = synthesize(db, case["query"], reranked)
        if synthesis.citations:
            citations_present += 1

    n = len(QA_CASES) or 1
    return {
        "retrieval_hit_rate": hits / n,
        "citation_presence_rate": citations_present / n,
        "avg_retrieval_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
    }


def _safety_metrics(db: Session) -> Dict[str, float]:
    correct = 0
    for case in SAFETY_CASES:
        blocked = False
        try:
            inspect_input(case["query"], db=db)
        except AppError:
            blocked = True
        if blocked == case["expect_blocked"]:
            correct += 1
    n = len(SAFETY_CASES) or 1
    return {"safety_case_pass_rate": correct / n}


def _tool_reliability_metrics() -> Dict[str, float]:
    correct = 0
    for case in TOOL_CASES:
        try:
            result = calculate(case["expression"])
            if result == case["expected"]:
                correct += 1
        except AppError:
            pass
    n = len(TOOL_CASES) or 1
    return {"tool_reliability_rate": correct / n}


def _prompt_template_validity_metrics(db: Session) -> Dict[str, float]:
    """
    Measures whether the CURRENTLY ACTIVE prompt templates render without
    error against a representative call. This is what actually changes
    when a prompt version is edited badly (e.g. a typo'd placeholder) —
    unlike the citation/hit-rate metrics above, which are computed by the
    extractive fallback path in this environment (no real Gemini key) and
    are therefore insensitive to prompt *wording*, this metric IS sensitive
    to whether the template is well-formed, which is exactly the kind of
    regression a bad prompt edit introduces. See evaluate_prompt_change()
    in regression.py for a worked example that trips this metric.
    """
    registry = PromptRegistry(db)
    results = {}

    rag_prompt = registry.get_active("rag_answer_synthesis")
    try:
        rag_prompt.template.format(context="sample context", query="sample query")
        results["rag_prompt_template_valid_rate"] = 1.0
    except (KeyError, IndexError):
        results["rag_prompt_template_valid_rate"] = 0.0

    multi_hop_prompt = registry.get_active("multi_hop_planner")
    try:
        multi_hop_prompt.template.format(query="sample query")
        results["multi_hop_prompt_template_valid_rate"] = 1.0
    except (KeyError, IndexError):
        results["multi_hop_prompt_template_valid_rate"] = 0.0

    return results


def run_evaluation(db: Session, run_label: str, *, seed_sample_documents: bool = True) -> List[MetricResult]:
    if seed_sample_documents:
        ensure_sample_documents_ingested(db)

    metrics: Dict[str, float] = {}
    metrics.update(_retrieval_and_citation_metrics(db))
    metrics.update(_safety_metrics(db))
    metrics.update(_tool_reliability_metrics())
    metrics.update(_prompt_template_validity_metrics(db))

    results = []
    for name, value in metrics.items():
        baseline = _get_latest_metric_value(db, metric_name=name, exclude_run_label=run_label)
        row = Evaluation(
            id=uuid.uuid4().hex,
            run_label=run_label,
            metric_name=name,
            metric_value=value,
            baseline_value=baseline,
            regression_detected=False,  # regression.py decides this explicitly, not this runner
        )
        db.add(row)
        results.append(MetricResult(name=name, value=value))
    db.commit()
    return results


def _get_latest_metric_value(db: Session, *, metric_name: str, exclude_run_label: str) -> Optional[float]:
    row = (
        db.query(Evaluation)
        .filter(Evaluation.metric_name == metric_name, Evaluation.run_label != exclude_run_label)
        .order_by(Evaluation.created_at.desc())
        .first()
    )
    return row.metric_value if row else None
