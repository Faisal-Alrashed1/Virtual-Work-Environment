"""
Model routing for the Stage 2 LangGraph agents, mirroring the same
priority-chain failover as llm_client.py. Cheap, mechanical steps
(CV gap-detection, Q&A generation, track/agent suggestion) route to the
small tier; anything that's real judgment stays on the main tier.

small_model_chain / reasoning_model_chain return the full ordered list of
(provider, model) pairs for the current priority chain — the caller
(onboarding_graph.py) tries each in turn, the same way llm_client.py does
for the raw SDK path.
"""
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.agents.llm_client import (
    LLMConfigError,
    NO_PROVIDER_CONFIGURED,
    resolve_api_key,
    resolve_provider_chain,
)
from app.config import settings

_BASE_URLS = {
    "openai": None,
    "deepseek": settings.deepseek_base_url,
    "qwen": settings.qwen_base_url,
}


def _model_name_for(provider: str, tier: str) -> str:
    pairs = {
        "anthropic": (settings.anthropic_model, settings.anthropic_small_model),
        "openai": (settings.openai_model, settings.openai_small_model),
        "deepseek": (settings.deepseek_model, settings.deepseek_small_model),
        "qwen": (settings.qwen_model, settings.qwen_small_model),
    }
    main, small = pairs[provider]
    return small if tier == "small" else main


def _build_chat_model(provider: str, model_name: str, max_tokens: int, **kwargs) -> BaseChatModel:
    if provider == "anthropic":
        return ChatAnthropic(
            model=model_name,
            api_key=settings.anthropic_api_key,
            max_tokens=max_tokens,
            **kwargs,
        )
    return ChatOpenAI(
        model=model_name,
        api_key=resolve_api_key(provider),
        base_url=_BASE_URLS[provider],
        max_tokens=max_tokens,
        **kwargs,
    )


def _model_chain(tier: str, max_tokens: int, **kwargs) -> list[tuple[str, BaseChatModel]]:
    chain = resolve_provider_chain()
    if not chain:
        raise LLMConfigError(NO_PROVIDER_CONFIGURED)
    return [
        (provider, _build_chat_model(provider, _model_name_for(provider, tier), max_tokens, **kwargs))
        for provider in chain
    ]


def small_model_chain(max_tokens: int = 1024, **kwargs) -> list[tuple[str, BaseChatModel]]:
    """Cheap tier: classification, question generation, suggestions."""
    return _model_chain("small", max_tokens, **kwargs)


def reasoning_model_chain(max_tokens: int = 1500, **kwargs) -> list[tuple[str, BaseChatModel]]:
    """Main tier: the model the rest of the app already runs on."""
    return _model_chain("main", max_tokens, **kwargs)