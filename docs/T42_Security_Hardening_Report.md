# T42 — Security Hardening Report (OWASP LLM Top 10-oriented review)

Status: Phase 3 update, based on the Security Gateway and Authorization
module actually implemented and tested in this repository (78 passing
tests as of this phase, including new tool-gateway authorization tests
added in Phase 3). This is not a substitute for a real security team
review — see the disclaimer at the end.

## LLM01: Prompt Injection

**Addressed.** `app/security/injection.py` scans both user input and
every retrieved document chunk against known injection phrasings before
either reaches a prompt template (`app/security/gateway.py::inspect_input`,
`inspect_document_content`). Structurally, retrieved content is always
wrapped in `<untrusted_data source="...">` tags (`injection.wrap_as_untrusted_data`)
so the model is told, in the active `rag_answer_synthesis` prompt, to treat
that content as data, never as an instruction — this is the real defense;
the regex scan is a detection/logging layer on top of it. Tested:
`tests/test_security_gateway.py`, `tests/test_evaluation.py::test_safety_case_pass_rate_is_high`.

**Known gap:** regex-based detection will miss novel injection phrasings.
A classifier-based detector (e.g. a small Hugging Face model fine-tuned
for injection detection) is a reasonable Phase 3 addition if the
evaluation suite's safety-case pass rate drops on adversarial inputs
Satish supplies.

## LLM02: Sensitive Information Disclosure

**Addressed.** `app/security/pii.py` regex-scans and redacts email,
phone, SSN/national-ID-shaped, credit-card-shaped, Aadhaar-shaped, and IP
patterns before user input is used or logged. Logging
(`app/core/logging.py`) additionally scrubs known secret-shaped field
names. Output validation (`gateway.py::validate_output`) strips any
system-prompt leak markers before a response leaves the API.

**Known gap:** PII detection is pattern-based, not a full NER model — it
will not catch every real-world PII shape (e.g. free-text names). This
is Phase 3 scope if a real deployment needs stronger coverage.

## LLM03: Supply Chain

Dependencies are pinned in `backend/requirements.txt`. CI runs `pip-audit`
(advisory in Phase 2 — not yet a hard CI gate; flip to blocking once the
dependency set is finalized). Model weights are pulled from the official
Hugging Face Hub at run time; no third-party model mirrors are used.

## LLM04: Data and Model Poisoning

Out of scope for this build — no user-supplied data is used to fine-tune
or retrain any model. Documents are only used for retrieval (RAG), never
for training.

## LLM05: Improper Output Handling

**Addressed.** All chat/search responses are structured JSON via Pydantic
response models — no raw model output is executed, rendered as HTML, or
passed to a shell/SQL layer. `validate_output()` is the final gate.

## LLM06: Excessive Agency

**Addressed, deliberately conservative.** The orchestrator
(`app/agents/orchestrator.py`) is a bounded router with six fixed
outcomes (REFUSE, CLARIFY, TOOL/calculator, TOOL/structured_db_search,
MULTI_HOP, RAG), not an open-ended ReAct loop. Every tool call goes
through the Tool Gateway (`app/tools/gateway.py`), which enforces: an
explicit allowlist (no dynamic dispatch by string), Pydantic schema
validation of arguments, a timeout per call, and `max_agent_steps` per
request. The calculator tool uses Python's `ast` module with a strict
node-type allowlist — no `eval()`/`exec()` anywhere in the codebase. The
structured-DB-search tool only queries an explicit table allowlist
(`documents`), never arbitrary SQL, and rejects any filter field that
isn't a real column on that model. Tested (Phase 3 adds explicit
coverage for invalid arguments, non-allowlisted tables, unknown filter
fields, missing required context, timeouts, and the `max_agent_steps`
cap): `tests/test_calculator.py::test_disallows_arbitrary_code`,
`tests/test_orchestrator_router.py`, `tests/test_tool_gateway.py`,
`tests/test_structured_db_routing.py`.

## LLM07: System Prompt Leakage

Partially addressed via `validate_output()`'s leak-marker stripping.
Deeper mitigation (e.g. never including the literal system prompt text
in the same context as user-controllable output) is enforced by prompt
design in `app/prompts/registry.py`'s seed templates but not yet red-teamed.

## LLM08: Vector and Embedding Weaknesses

The flat-file vector store (`app/rag/vector_store.py`) has no
authentication of its own — it is only reachable through this backend
process, not exposed directly. Retrieval results are always passed
through the separate authorization layer (`app/security/authorization.py`)
before being shown to a user or an LLM, regardless of what the caller
requested via metadata filters — see that module's docstring for why
metadata filtering and authorization are kept as two distinct concerns.
Tested: `tests/test_authorization.py`,
`tests/test_search_and_chat_rag.py::test_chat_respects_authorization_over_metadata_filter`.

**Known gap (documented, not hidden):** requester clearance is currently
read from an `X-User-Clearance` header with no real identity provider
behind it. This is a deliberate, clearly-labeled staging/demo mechanism,
not a production authentication scheme — see the dedicated "Production
Migration Path" section below for exactly what changes before this can
ship.

## LLM09: Misinformation

Grounding is enforced by design: the RAG/multi-hop paths only answer from
retrieved, cited chunks (`app/rag/answer_synthesis.py`), and the fallback
path is explicitly extractive (verbatim sentences from source documents)
rather than a hallucination-prone paraphrase when Gemini is unavailable.
The `citation_presence_rate` evaluation metric (`app/evaluation/runner.py`)
gives this a real, re-measurable number rather than an assumption.

## LLM10: Unbounded Consumption

`max_agent_steps` and per-tool timeouts bound agent work
(`app/tools/gateway.py`). `MAX_HOPS = 4` bounds multi-hop retrieval
(`app/agents/multi_hop.py`). Upload size is capped at `MAX_UPLOAD_MB`
(`app/services/ingestion.py::validate_upload`). Gemini calls are retried
a bounded number of times (`llm_max_retries`) before falling back, never
retried indefinitely.

## Authorization vs. metadata filtering — explicit design note

This is called out separately because it was a specific requirement:
`app/rag/hybrid_retrieval.py::build_metadata_filter_set()` exists purely
to narrow search relevance (e.g. "only CD documents"). It is NOT a
security boundary and a caller omitting it does not grant broader access.
`app/security/authorization.py::filter_authorized_chunks()` is the actual
enforcement point, applied unconditionally after retrieval/reranking, on
every `/chat` and `/search` request, regardless of what filter (if any)
was requested.

## Production Migration Path: Enterprise SSO / Identity-Based Authorization

**This is a documentation-only section for Phase 3. No identity
provider — Azure AD or otherwise — has been implemented in this
codebase, and none should be added unless Satish explicitly asks for
it.** The `X-User-Clearance` header exists solely so the authorization
layer (`app/security/authorization.py`) has something real and testable
to enforce against in a local/staging environment without standing up
Fulcrum's actual identity infrastructure inside a capstone project.

What changes when this moves toward production, and roughly where:

1. **Authentication front door.** Requests would carry a validated
   bearer token (e.g. an Azure AD-issued JWT via OAuth2/OIDC) instead of
   a plain header. This is added as FastAPI middleware/dependency (a new
   `app/security/auth.py`, not a change to `authorization.py` itself) so
   the separation this project already has — authentication decides
   *who*, authorization decides *what they can see* — is preserved
   rather than collapsed back into one concern.
2. **Clearance source.** `clearance_for_confidentiality()` currently
   maps a trusted header string directly to a `ClearanceLevel`. In
   production this function's input would instead come from claims
   resolved from the validated token (an Azure AD group or app role
   claim mapped to Public/Internal/Confidential/Restricted), never from
   a client-supplied header — the header becomes untrusted input the
   moment a real identity provider exists, so it would be removed
   entirely rather than kept as a fallback.
3. **Token validation.** Standard OIDC validation against Azure AD's
   JWKS endpoint (signature, issuer, audience, expiry) — this is
   infrastructure, not business logic, and belongs in a thin
   middleware layer so `authorization.py`'s unit tests
   (`tests/test_authorization.py`) keep working unchanged against a
   `ClearanceLevel` input regardless of where that input came from.
4. **Group/role provisioning.** Mapping real Azure AD security groups or
   app roles to the four confidentiality levels is an IT/identity-team
   decision, not something this codebase can decide on its own — it
   needs Satish's (or Fulcrum IT's) actual Azure AD tenant configuration.
5. **What does NOT need to change:** the document confidentiality
   schema, `filter_authorized_chunks()`'s enforcement logic, or the
   metadata-filtering vs. authorization separation — those are already
   identity-provider-agnostic by design, which is the whole point of
   keeping this as a documented seam rather than baking a specific IdP
   into the enforcement code.

This section deliberately stops at "what would change and where" — it
is not an implementation, and implementing it is out of scope until
Satish explicitly requests it.

## What this report does NOT claim

No penetration test, red-team exercise, or external security audit has
been performed. No mentor or peer security review has occurred. The
gaps listed above (header-based clearance, regex-only PII/injection
detection) are real limitations of this phase, not resolved issues.

---
⚠️ AI-generated. Validate with a qualified security professional before
treating this as a compliance artifact. Questions on data handling or
security posture: CISO@fulcrumdigital.com.
