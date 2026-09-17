"""
Wrapper around any number of LLM providers, with automatic failover
between them based on a priority order each developer sets in their own
backend/.env (settings.llm_provider_priority). Every agent (manager.py,
mentor.py, hr.py, co_reviewers.py, roundtable.py, collaboration.py,
meeting.py) calls through here instead of importing a provider SDK
directly.

OpenAI, DeepSeek and Qwen all speak the OpenAI Chat Completions dialect
(tool calling included), so one openai.OpenAI client — pointed at each
provider's own base_url — covers all three. Anthropic keeps its own SDK
because its tool-use and vision content-block shapes differ from OpenAI's.

For every request, we build the chain of configured providers (those with
a non-empty API key) in priority order, and try each in turn. An error
that means "this provider is unavailable right now" (bad key, no credit,
rate limited, connection dropped) moves on to the next provider. Any other
error is raised immediately, since it isn't an availability problem.
"""
import json
from dataclasses import dataclass, field

from anthropic import Anthropic
from anthropic import APIConnectionError as AConnErr
from anthropic import APIStatusError as AStatusErr
from anthropic import AuthenticationError as AAuthErr
from anthropic import PermissionDeniedError as APermErr
from anthropic import RateLimitError as ARateErr
from openai import OpenAI
from openai import APIConnectionError as OConnErr
from openai import APIStatusError as OStatusErr
from openai import AuthenticationError as OAuthErr
from openai import PermissionDeniedError as OPermErr
from openai import RateLimitError as ORateErr

from app.config import settings


class LLMConfigError(RuntimeError):
    """Raised when no provider in the priority chain has a valid API key."""


# Errors that mean "this provider is unavailable right now" — worth
# failing over to the next provider in the chain rather than raising.
FAILOVER_EXCEPTIONS = (
    AAuthErr, APermErr, ARateErr, AConnErr, AStatusErr,
    OAuthErr, OPermErr, ORateErr, OConnErr, OStatusErr,
)

# Prefix used on the final error when every provider in the chain has
# been tried and failed. main.py checks for this prefix to return a
# clean 503 instead of a raw 500.
ALL_PROVIDERS_FAILED = "All configured LLM providers failed"

NO_PROVIDER_CONFIGURED = (
    "No provider in LLM_PROVIDER_PRIORITY has a valid API key configured. "
    "Set at least one *_API_KEY in backend/.env."
)

_KNOWN_PROVIDERS = ["anthropic", "openai", "deepseek", "qwen"]


@dataclass
class ToolCall:
    name: str
    input: dict


@dataclass
class AgentReply:
    """Normalized call_agentic result, regardless of which provider in the
    chain actually answered."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


def resolve_api_key(provider: str) -> str:
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "deepseek": settings.deepseek_api_key,
        "qwen": settings.qwen_api_key,
    }.get(provider, "")


def resolve_provider_chain(tier: str = "main") -> list[str]:
    """Reads the tier-specific provider priority (LLM_PROVIDER_PRIORITY_MAIN
    / _SMALL), falling back to the shared LLM_PROVIDER_PRIORITY if that
    tier has no override set, and returns only the known providers that
    have a non-empty API key, in the order given. This is what actually
    makes provider selection tier-aware — a cheap/mechanical call and a
    real judgment call can prefer different providers, not just different
    model names within whichever provider happens to be first."""
    tier_setting = (
        settings.llm_provider_priority_small
        if tier == "small"
        else settings.llm_provider_priority_main
    )
    raw = tier_setting or settings.llm_provider_priority or "anthropic"
    ordered = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return [p for p in ordered if p in _KNOWN_PROVIDERS and resolve_api_key(p)]


def _model_name_for(provider: str, tier: str) -> str:
    pairs = {
        "anthropic": (settings.anthropic_model, settings.anthropic_small_model),
        "openai": (settings.openai_model, settings.openai_small_model),
        "deepseek": (settings.deepseek_model, settings.deepseek_small_model),
        "qwen": (settings.qwen_model, settings.qwen_small_model),
    }
    main, small = pairs[provider]
    return small if tier == "small" else main


_anthropic_client: Anthropic | None = None
_openai_clients: dict[str, OpenAI] = {}


def _anthropic() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def _openai_compatible(provider: str) -> OpenAI:
    if provider not in _openai_clients:
        base_url = {
            "openai": None,
            "deepseek": settings.deepseek_base_url,
            "qwen": settings.qwen_base_url,
        }[provider]
        _openai_clients[provider] = OpenAI(api_key=resolve_api_key(provider), base_url=base_url)
    return _openai_clients[provider]


def _to_openai_tool(tool: dict) -> dict:
    """tools.py defines tools in Anthropic's native shape (name/description/
    input_schema). This is a pure key rename to OpenAI's function-calling
    shape — the JSON schema itself doesn't change."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _to_openai_content(content):
    """mentor.py builds vision messages with Anthropic's image block shape
    (type: image / source: base64). OpenAI-compatible providers expect
    image_url with a data: URI instead."""
    if isinstance(content, str):
        return content
    out = []
    for block in content:
        if block.get("type") == "image":
            src = block["source"]
            out.append({
                "type": "image_url",
                "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"},
            })
        else:
            out.append(block)
    return out


def call_with_tool(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    force_tool: str,
    max_tokens: int = 1500,
    tier: str = "main",
) -> dict:
    chain = resolve_provider_chain(tier)
    if not chain:
        raise LLMConfigError(NO_PROVIDER_CONFIGURED)
    errors = []
    for provider in chain:
        try:
            model_name = _model_name_for(provider, tier)
            if provider == "anthropic":
                response = _anthropic().messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "tool", "name": force_tool},
                )
                for block in response.content:
                    if block.type == "tool_use":
                        return {"tool_name": block.name, "input": block.input}
                raise RuntimeError(f"Model did not call '{force_tool}' as expected.")

            client = _openai_compatible(provider)
            oa_messages = [{"role": "system", "content": system}] + [
                {**m, "content": _to_openai_content(m["content"])} for m in messages
            ]
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=oa_messages,
                tools=[_to_openai_tool(t) for t in tools],
                tool_choice={"type": "function", "function": {"name": force_tool}},
            )
            call = response.choices[0].message.tool_calls[0]
            return {"tool_name": call.function.name, "input": json.loads(call.function.arguments)}
        except FAILOVER_EXCEPTIONS as e:
            errors.append(f"{provider}: {e}")
            continue
    raise RuntimeError(f"{ALL_PROVIDERS_FAILED}:\n" + "\n".join(errors))


def call_agentic(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_tokens: int = 1500,
    tier: str = "main",
) -> AgentReply:
    chain = resolve_provider_chain(tier)
    if not chain:
        raise LLMConfigError(NO_PROVIDER_CONFIGURED)
    errors = []
    for provider in chain:
        try:
            model_name = _model_name_for(provider, tier)
            if provider == "anthropic":
                response = _anthropic().messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    tools=tools,
                )
                text = next((b.text for b in response.content if b.type == "text" and b.text), None)
                calls = [ToolCall(b.name, b.input) for b in response.content if b.type == "tool_use"]
                return AgentReply(text=text, tool_calls=calls)

            client = _openai_compatible(provider)
            oa_messages = [{"role": "system", "content": system}] + [
                {**m, "content": _to_openai_content(m["content"])} for m in messages
            ]
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=oa_messages,
                tools=[_to_openai_tool(t) for t in tools] if tools else None,
            )
            msg = response.choices[0].message
            calls = [
                ToolCall(c.function.name, json.loads(c.function.arguments))
                for c in (msg.tool_calls or [])
            ]
            return AgentReply(text=msg.content, tool_calls=calls)
        except FAILOVER_EXCEPTIONS as e:
            errors.append(f"{provider}: {e}")
            continue
    raise RuntimeError(f"{ALL_PROVIDERS_FAILED}:\n" + "\n".join(errors))
