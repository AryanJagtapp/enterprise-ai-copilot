"""
Gemini LLM client wrapper — the ONLY place `google.generativeai` is
called from. Centralizing it here means retry/fallback/observability
logic lives in one spot, and swapping models or adding a second provider
later never touches orchestrator/RAG code.

If GEMINI_API_KEY is unset/invalid, or the API call fails after retries,
this raises DependencyUnavailable — callers (rag/answer_synthesis.py,
agents/multi_hop.py) are expected to catch that and fall back to an
extractive, non-generative answer rather than crash the request. This is
deliberate: this project is not fabricating a working Gemini integration
when no real key has been provided — it exercises the real failure path.
"""
import logging

from app.core.config import get_settings
from app.core.errors import DependencyUnavailable
from app.core.resilience import with_retry

logger = logging.getLogger("app.services.gemini_client")

_configured = False


def _ensure_configured() -> None:
    global _configured
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key in ("", "your_key_here", "test-key-not-real", "ci-placeholder-key"):
        raise DependencyUnavailable("Gemini", detail="GEMINI_API_KEY is not configured with a real key")
    if _configured:
        return
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        _configured = True
    except Exception as exc:  # noqa: BLE001
        raise DependencyUnavailable("Gemini", detail=f"failed to configure client: {exc}") from exc


def generate(prompt: str, *, max_output_tokens: int = 4096, temperature: float = 0.2) -> str:
    settings = get_settings()
    _ensure_configured()

    def _call() -> str:
        try:
            import google.generativeai as genai

            model = genai.GenerativeModel(settings.gemini_model)
            response = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_output_tokens, "temperature": temperature},
            )
            text = getattr(response, "text", None)
            if not text:
                raise DependencyUnavailable("Gemini", detail="empty response from model")
            return text
        except DependencyUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced as a retriable transient failure
            from app.core.errors import AppError, ErrorClass

            raise AppError(ErrorClass.TRANSIENT, "Gemini call failed.", detail=str(exc), retriable=True) from exc

    try:
        return with_retry(_call, max_retries=settings.llm_max_retries, backoff_seconds=settings.llm_retry_backoff_seconds)
    except DependencyUnavailable:
        raise
    except Exception as exc:  # AppError from _call after retries exhausted
        raise DependencyUnavailable("Gemini", detail=str(exc)) from exc
