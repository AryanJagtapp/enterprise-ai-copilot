"""
Grounded answer synthesis with citations.

Primary path: Gemini, using the active `rag_answer_synthesis` prompt
version from the Prompt Registry, with every retrieved chunk wrapped as
untrusted_data (never as an instruction) before it reaches the model.

Fallback path (Feature 4): if Gemini is unavailable, synthesize an
extractive answer — the most relevant sentences from the top chunks,
concatenated with their citations — and say plainly that a fallback was
used. This is never presented as equivalent quality to a real generative
answer; the response always carries `fallback_triggered` +
`fallback_reason` so the frontend/observability layer can show it
honestly.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.errors import DependencyUnavailable
from app.prompts.registry import PromptRegistry
from app.rag.hybrid_retrieval import RetrievedChunk
from app.security.gateway import inspect_document_content
from app.services.gemini_client import generate


@dataclass
class SynthesizedAnswer:
    answer: str
    citations: List[str] = field(default_factory=list)
    used_fallback: bool = False
    fallback_reason: Optional[str] = None
    prompt_version: Optional[str] = None


def _extractive_fallback(query: str, chunks: List[RetrievedChunk]) -> str:
    """No LLM available — return the most query-relevant sentences verbatim, cited."""
    query_terms = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    scored_sentences = []
    for chunk in chunks:
        for sentence in re.split(r"(?<=[.!?])\s+", chunk.text):
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            terms = set(re.findall(r"[a-zA-Z0-9]+", sentence.lower()))
            overlap = len(query_terms & terms)
            if overlap:
                scored_sentences.append((overlap, sentence, chunk.filename, chunk.document_id))
    scored_sentences.sort(key=lambda x: -x[0])
    top = scored_sentences[:4]
    if not top:
        return "The retrieved documents did not contain sentences clearly matching this question."
    lines = [f"- {sentence} [source: {filename}]" for _, sentence, filename, _ in top]
    return "Extractive summary from retrieved documents (generative model unavailable):\n" + "\n".join(lines)


def synthesize(db: Session, query: str, chunks: List[RetrievedChunk], *, request_id: Optional[str] = None) -> SynthesizedAnswer:
    if not chunks:
        return SynthesizedAnswer(answer="No relevant documents were found for this question.", citations=[])

    citations = [f"{c.filename} (doc:{c.document_id}, chunk:{c.chunk_id})" for c in chunks]

    registry = PromptRegistry(db)
    active_prompt = registry.get_active("rag_answer_synthesis")

    wrapped_context = "\n\n".join(
        inspect_document_content(c.text, source_label=f"{c.filename}#chunk{c.chunk_id}", db=db, request_id=request_id)
        for c in chunks
    )
    prompt = active_prompt.template.format(context=wrapped_context, query=query)

    try:
        answer_text = generate(prompt)
        return SynthesizedAnswer(answer=answer_text, citations=citations, used_fallback=False, prompt_version=f"{active_prompt.prompt_id}::v{active_prompt.version}")
    except DependencyUnavailable as exc:
        fallback_answer = _extractive_fallback(query, chunks)
        return SynthesizedAnswer(
            answer=fallback_answer,
            citations=citations,
            used_fallback=True,
            fallback_reason=f"Gemini unavailable ({exc.detail}) — used extractive fallback synthesis",
            prompt_version=f"{active_prompt.prompt_id}::v{active_prompt.version}",
        )
