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
import logging
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
from app.agents.tool_output import MalformedToolOutput, check_tool_input, repair_tool_input
from app.language import with_language

# One line per call showing which provider/model actually answered (and
# a line per provider that got skipped via failover) — visible in the
# terminal at INFO level. Configured with its own handler/level rather
# than relying on uvicorn's root logging setup, which by default filters
# out INFO on any logger it didn't configure itself — without this, these
# calls would silently produce no output at all. propagate=False avoids
# a duplicate line if the app's own logging setup ever also attaches a
# root handler.
logger = logging.getLogger("venv.llm")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


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


def openai_client_for_embeddings() -> OpenAI:
    """The one client app/rag.py uses — embeddings are OpenAI-specific
    (Anthropic doesn't offer an embeddings endpoint, and DeepSeek/Qwen
    aren't wired up for one here), so there's no failover chain the way
    call_agentic/call_with_tool have. Shares the same cached client/base
    URL construction as the chat-completion path above rather than
    reimplementing it. Raises LLMConfigError (already a clean 503 via
    main.py) if OPENAI_API_KEY isn't set."""
    if not settings.openai_api_key:
        raise LLMConfigError(
            "Set OPENAI_API_KEY to enable the RAG knowledge base — embeddings "
            "require OpenAI specifically (see app/rag.py)."
        )
    return _openai_compatible("openai")


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


# A model's tool call is nondeterministic: an unusable answer (a list sent as a
# string, a missing field, no tool call at all) often comes right on the next try.
# Ask again on the SAME provider before failing over. See agents/tool_output.py.
MAX_ATTEMPTS_PER_PROVIDER = 2


def _tool_schema(tools: list[dict], name: str) -> dict | None:
    return next((t.get("input_schema") for t in tools if t.get("name") == name), None)


def _raw_tool_call(provider, model_name, system, messages, tools, force_tool, max_tokens):
    """One request to one provider -> (tool_name, raw_input). Anything the model did
    wrong (no tool call, unparseable arguments) is MalformedToolOutput, not a crash."""
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
                return block.name, block.input
        raise MalformedToolOutput(f"the model did not call '{force_tool}'")

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
    calls = response.choices[0].message.tool_calls
    if not calls:
        raise MalformedToolOutput(f"the model did not call '{force_tool}'")
    try:
        return calls[0].function.name, json.loads(calls[0].function.arguments)
    except ValueError as exc:
        raise MalformedToolOutput(f"the tool arguments were not valid JSON ({exc})") from exc


def _usable_tool_input(raw, schema, validate, provider, force_tool):
    """Repair, then check. Raises MalformedToolOutput if the result can't be used."""
    data = raw
    if schema:
        data, repairs = repair_tool_input(raw, schema)
        for repair in repairs:
            logger.warning("[LLM] %s repaired tool output for '%s': %s", provider, force_tool, repair)
        problems = check_tool_input(data, schema)
        if problems:
            raise MalformedToolOutput("; ".join(problems))
    if validate is not None:
        try:
            validate(data)
        except MalformedToolOutput:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise MalformedToolOutput(f"{type(exc).__name__}: {exc}") from exc
    return data


def call_with_tool(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    force_tool: str,
    max_tokens: int = 1500,
    tier: str = "main",
    validate=None,
) -> dict:
    """Force one tool call and return {"tool_name", "input"}.

    Network/auth/rate-limit trouble fails over to the next provider at once. A
    tool call that comes back unusable is first repaired if possible, else asked
    again (MAX_ATTEMPTS_PER_PROVIDER) and then failed over. `validate` lets a caller
    add its own shape check (raise MalformedToolOutput) — it is retried the same way.
    Only when every provider has failed does this raise, as a clean 503."""
    system = with_language(system)  # answer in the graduate's language (app/language.py)
    chain = resolve_provider_chain(tier)
    if not chain:
        raise LLMConfigError(NO_PROVIDER_CONFIGURED)
    schema = _tool_schema(tools, force_tool)
    errors = []
    for provider in chain:
        for attempt in range(1, MAX_ATTEMPTS_PER_PROVIDER + 1):
            try:
                model_name = _model_name_for(provider, tier)
                name, raw = _raw_tool_call(provider, model_name, system, messages, tools, force_tool, max_tokens)
                data = _usable_tool_input(raw, schema, validate, provider, force_tool)
                logger.info("[LLM] %s (%s, %s-tier) -> %s", provider, model_name, tier, force_tool)
                return {"tool_name": name, "input": data}
            except MalformedToolOutput as e:
                logger.warning(
                    "[LLM] %s returned malformed output for '%s' (attempt %d/%d): %s",
                    provider, force_tool, attempt, MAX_ATTEMPTS_PER_PROVIDER, e,
                )
                errors.append(f"{provider}: malformed output ({e})")
            except FAILOVER_EXCEPTIONS as e:
                logger.warning("[LLM] %s unavailable (%s) — failing over", provider, e)
                errors.append(f"{provider}: {e}")
                break  # a down/unauthorised provider won't recover on a retry
    raise RuntimeError(f"{ALL_PROVIDERS_FAILED}:\n" + "\n".join(errors))


def call_agentic(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_tokens: int = 1500,
    tier: str = "main",
) -> AgentReply:
    system = with_language(system)  # answer in the graduate's language (app/language.py)
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
                logger.info("[LLM] %s (%s, %s-tier) -> reply", provider, model_name, tier)
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
            logger.info("[LLM] %s (%s, %s-tier) -> reply", provider, model_name, tier)
            return AgentReply(text=msg.content, tool_calls=calls)
        except FAILOVER_EXCEPTIONS as e:
            logger.warning("[LLM] %s unavailable (%s) — failing over", provider, e)
            errors.append(f"{provider}: {e}")
            continue
    raise RuntimeError(f"{ALL_PROVIDERS_FAILED}:\n" + "\n".join(errors))
