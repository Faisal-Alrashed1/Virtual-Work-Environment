"""
Model routing for the Stage 2 LangGraph agents. Cheap, mechanical steps
(CV gap-detection, Q&A generation, track/agent suggestion) route to the
small model; anything that's real judgment — the Mentor's review, the
Manager/HR end-of-week synthesis, once weekly_cycle.py is ported to a
StateGraph in a later branch — stays on the same model the rest of the
app already uses (settings.llm_model).

Two thin factories rather than module-level singletons so a test can
construct a fake model and pass it into a node directly instead of
patching global state.
"""
from langchain_anthropic import ChatAnthropic

from app.agents.llm_client import LLMConfigError
from app.config import settings


def _require_api_key() -> None:
    if not settings.anthropic_api_key:
        raise LLMConfigError(
            "No ANTHROPIC_API_KEY is set. Add one to backend/.env (get a key "
            "at console.anthropic.com) and restart the server."
        )


def small_model(max_tokens: int = 1024, **kwargs) -> ChatAnthropic:
    """Cheap tier: classification, question generation, suggestions."""
    _require_api_key()
    return ChatAnthropic(
        model=settings.small_llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        **kwargs,
    )


def reasoning_model(max_tokens: int = 1500, **kwargs) -> ChatAnthropic:
    """Main tier: the model the rest of the app already runs on."""
    _require_api_key()
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=max_tokens,
        **kwargs,
    )
