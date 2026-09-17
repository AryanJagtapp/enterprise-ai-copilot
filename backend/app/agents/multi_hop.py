"""
Multi-hop retrieval loop (Feature 1, MULTI_HOP path).

Plans up to 4 sub-questions (via Gemini + the `multi_hop_planner` prompt;
falls back to a deterministic split on comparison keywords if Gemini is
unavailable — Feature 4 applies here too, not just to answer synthesis),
retrieves for each sub-question independently, merges the chunk pools
(de-duplicated), and hands the merged pool to the same answer-synthesis
path RAG uses. Capped at 4 hops regardless of what the planner returns,
per the orchestrator's explicit stopping-criteria requirement.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.core.errors import DependencyUnavailable
from app.prompts.registry import PromptRegistry
from app.rag.hybrid_retrieval import RetrievedChunk, retrieve
from app.services.gemini_client import generate

MAX_HOPS = 4


@dataclass
class MultiHopResult:
    sub_questions: List[str]
    chunks: List[RetrievedChunk]
    planning_fallback_used: bool
    planning_fallback_reason: Optional[str] = None
    retrieval_fallback_triggered: bool = False
    retrieval_fallback_reason: Optional[str] = None


def _heuristic_split(query: str) -> List[str]:
    """Deterministic fallback planner: split on comparison conjunctions."""
    parts = re.split(r"\b(?:versus|vs\.?|and how|and what)\b", query, flags=re.IGNORECASE)
    parts = [p.strip(" ?.") for p in parts if p.strip(" ?.")]
    return parts[:MAX_HOPS] if len(parts) > 1 else [query]


def plan_sub_questions(db: Session, query: str) -> tuple[List[str], bool, Optional[str]]:
    registry = PromptRegistry(db)
    active_prompt = registry.get_active("multi_hop_planner")
    prompt = active_prompt.template.format(query=query)
    try:
        raw = generate(prompt)
        sub_questions = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
        sub_questions = [q for q in sub_questions if len(q) > 5][:MAX_HOPS]
        if not sub_questions:
            raise ValueError("planner returned no usable sub-questions")
        return sub_questions, False, None
    except (DependencyUnavailable, ValueError) as exc:
        return _heuristic_split(query), True, f"planner unavailable/empty ({exc}); used heuristic keyword split"


def run_multi_hop(db: Session, query: str, *, allowed_chunk_ids: Optional[Set[str]] = None, top_k_per_hop: int = 5) -> MultiHopResult:
    sub_questions, planning_fallback_used, planning_fallback_reason = plan_sub_questions(db, query)

    seen_chunk_ids: Set[str] = set()
    merged_chunks: List[RetrievedChunk] = []
    retrieval_fallback_triggered = False
    retrieval_fallback_reason = None

    for sub_q in sub_questions[:MAX_HOPS]:
        result = retrieve(db, sub_q, top_k=top_k_per_hop, allowed_chunk_ids=allowed_chunk_ids)
        if result.fallback_triggered:
            retrieval_fallback_triggered = True
            retrieval_fallback_reason = result.fallback_reason
        for chunk in result.chunks:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                merged_chunks.append(chunk)

    merged_chunks.sort(key=lambda c: -c.fused_score)

    return MultiHopResult(
        sub_questions=sub_questions,
        chunks=merged_chunks,
        planning_fallback_used=planning_fallback_used,
        planning_fallback_reason=planning_fallback_reason,
        retrieval_fallback_triggered=retrieval_fallback_triggered,
        retrieval_fallback_reason=retrieval_fallback_reason,
    )
