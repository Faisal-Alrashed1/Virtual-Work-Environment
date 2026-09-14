"""
Thin wrapper around the Anthropic API. Every agent (manager.py, mentor.py,
hr.py) calls through here instead of importing `anthropic` directly — if
the team ever swaps providers (see agents/README.md), only this file and
`config.py` change; manager.py/mentor.py/hr.py stay untouched.

Two call patterns are used across the three agents:
  - `call_with_tool`: forces a specific tool, so the response is always a
    structured, parseable input dict. Used anywhere we need a guaranteed
    shape back (Manager assigning a task, Mentor submitting a review, HR
    updating the Employee File).
  - `call_agentic`: lets the model choose (reply in plain text, or call a
    tool). Used for the Manager's back-and-forth thread conversation, where
    "just reply" is a valid outcome.
"""
from anthropic import Anthropic

from app.config import settings


class LLMConfigError(RuntimeError):
    """Raised when the LLM client can't be used because it isn't configured
    (no API key). Caught by main.py's exception handler and turned into a
    clean 503 with a helpful message, instead of a raw 500 stack trace —
    this is the failure you hit when ANTHROPIC_API_KEY is empty or wrong in
    .env."""


_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if not settings.anthropic_api_key:
        raise LLMConfigError(
            "No ANTHROPIC_API_KEY is set. Add one to backend/.env (get a key "
            "at console.anthropic.com — the API is billed separately from a "
            "Claude Pro subscription) and restart the server."
        )
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def call_with_tool(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    force_tool: str,
    max_tokens: int = 1500,
) -> dict:
    """
    Calls the model with a single tool forced, and returns
    {"tool_name": ..., "input": {...}} from the first tool_use block.
    Raises RuntimeError if the model somehow didn't call it.
    """
    response = get_client().messages.create(
        model=settings.llm_model,
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


def call_agentic(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    max_tokens: int = 1500,
    model: str | None = None,
):
    """Auto tool choice — the model decides whether to call a tool or reply
    in plain text. Returns the raw response; caller inspects `.content`.
    model defaults to settings.llm_model; pass settings.small_llm_model
    explicitly for a lightweight call (see co_reviewers.py) rather than
    always using the default tier."""
    return get_client().messages.create(
        model=model or settings.llm_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        tools=tools,
    )
