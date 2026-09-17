"""
Prompt injection detection (Feature 3 — Security Gateway).

Two layers, both applied:
1. Heuristic pattern matching against known injection phrasings — fast,
   deterministic, cheap. Runs on (a) user input and (b) retrieved
   document content before either reaches the LLM context.
2. A structural rule enforced everywhere else in the codebase: retrieved
   document text is always wrapped and labelled as untrusted DATA in the
   prompt template (see prompts/registry.py), never concatenated as
   instructions. That contract is what actually stops a document from
   overriding system behavior — the heuristics below are a detection/
   logging layer on top of it, not the only defense.
"""
import re
from dataclasses import dataclass
from typing import List

_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (the )?(system|previous) prompt", re.I),
    re.compile(r"you are now (a|an) .*(different|new) (ai|assistant|model)", re.I),
    re.compile(r"act as (a|an) (unfiltered|jailbroken|dan)", re.I),
    re.compile(r"reveal (your|the) (system prompt|instructions)", re.I),
    re.compile(r"pretend (you|to) (have no|bypass) (restrictions|guardrails)", re.I),
    re.compile(r"</?(system|assistant|instructions)>", re.I),
    re.compile(r"\bexecute\b.*\b(shell|command|os\.system|subprocess)\b", re.I),
    re.compile(r"drop\s+table|delete\s+from\s+\w+\s*;|;\s*--", re.I),
]


@dataclass
class InjectionScanResult:
    flagged: bool
    matched_patterns: List[str]


def scan(text: str) -> InjectionScanResult:
    matched = [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]
    return InjectionScanResult(flagged=len(matched) > 0, matched_patterns=matched)


def wrap_as_untrusted_data(source_label: str, text: str) -> str:
    """
    Wrap retrieved/external content so the prompt template can never
    confuse it with an instruction. The LLM is told explicitly (in the
    system prompt) that content inside these tags is DATA to reason
    about, never a command to follow.
    """
    return f'<untrusted_data source="{source_label}">\n{text}\n</untrusted_data>'
