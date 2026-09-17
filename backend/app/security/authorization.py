"""
Authorization — deliberately a SEPARATE concern from metadata filtering.

app/rag/hybrid_retrieval.py's `build_metadata_filter_set()` narrows
retrieval by business_unit/document_type/client_name/tags for RELEVANCE —
"only search CD documents", "only the ACS engagement". That is a search
convenience, and a caller could omit it entirely and still see everything
their retrieval query matches.

This module is the actual security boundary: given a requester's
clearance and a chunk's document confidentiality_level, it decides
whether that chunk may ever be shown to that requester, independent of
what they asked to filter by. It is applied AFTER retrieval and reranking,
right before chunks are handed to the LLM or returned to the API caller,
so a broad or absent metadata filter can never leak a Restricted document.

Current limitation (documented, not hidden): there is no real identity
provider integrated yet. Clearance is read from an `X-User-Clearance`
request header, defaulting to "Internal" if absent. This is a stand-in
until real authentication (e.g. Azure AD, consistent with the rest of
Fulcrum's Azure footprint) is wired up — flagged here and in
docs/T42_Security_Hardening_Report.md as a known gap for a real
deployment, not something this build claims to have solved.
"""
from enum import IntEnum
from typing import List

from app.models.db import SecurityEvent
from app.rag.hybrid_retrieval import RetrievedChunk


class ClearanceLevel(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3

    @classmethod
    def from_str(cls, value: str) -> "ClearanceLevel":
        return {
            "public": cls.PUBLIC,
            "internal": cls.INTERNAL,
            "confidential": cls.CONFIDENTIAL,
            "restricted": cls.RESTRICTED,
        }.get((value or "internal").strip().lower(), cls.INTERNAL)


def clearance_for_confidentiality(level: str) -> ClearanceLevel:
    return ClearanceLevel.from_str(level)


def filter_authorized_chunks(
    chunks: List[RetrievedChunk],
    *,
    requester_clearance: ClearanceLevel,
    db=None,
    request_id: str | None = None,
) -> List[RetrievedChunk]:
    """
    The real enforcement point. Drops any chunk whose document
    confidentiality exceeds the requester's clearance, and logs a
    security event for each block so denied access is auditable.
    """
    allowed: List[RetrievedChunk] = []
    for chunk in chunks:
        doc_level = clearance_for_confidentiality(chunk.metadata.get("confidentiality_level", "Internal"))
        if doc_level <= requester_clearance:
            allowed.append(chunk)
        elif db is not None:
            import uuid

            db.add(
                SecurityEvent(
                    id=uuid.uuid4().hex,
                    event_type="policy_violation",
                    severity="high",
                    request_id=request_id,
                    detail=(
                        f"blocked chunk from document '{chunk.metadata.get('filename')}' "
                        f"(confidentiality={doc_level.name}) — requester clearance={requester_clearance.name}"
                    ),
                    blocked=True,
                )
            )
            db.commit()
    return allowed
