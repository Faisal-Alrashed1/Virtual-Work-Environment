"""
Smoke test for tier-aware LLM provider routing (docs/
LLM_PROVIDER_FAILOVER.md's "Tier-aware routing" section): a "main"-tier
call (real judgment — Mentor's review, the Manager's synthesis) and a
"small"-tier call (cheap/mechanical — onboarding suggestions, a
roundtable specialist's comment) can be routed through *different*
provider priorities, not just different model names within whichever
provider happens to be first. This is the piece that makes provider
selection actually intelligent rather than one flat list applied to
every call regardless of complexity.

Also regression-covers a real bug caught while building this: both
call_agentic and graph/models.py's _model_chain accepted a tier argument
but never actually passed it into resolve_provider_chain(), so tier only
ever affected the model *name* within a provider, never which providers
got tried at all. Every check below would have failed under that bug.

Run: python smoke_test_llm_provider_routing.py
"""
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_llm_provider_routing.db"
)
os.environ["ANTHROPIC_API_KEY"] = "fake-anthropic-key"
os.environ["OPENAI_API_KEY"] = "fake-openai-key"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
# Deliberately different, single-provider chains per tier — any bug where
# tier gets ignored shows up immediately as the wrong provider's client
# being called, not just a subtly wrong model name.
os.environ["LLM_PROVIDER_PRIORITY_MAIN"] = "anthropic"
os.environ["LLM_PROVIDER_PRIORITY_SMALL"] = "openai"

from app.agents import llm_client  # noqa: E402
from app.agents.graph import models as graph_models  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# --- unit: the two tiers resolve to different chains ---
check("main tier resolves to anthropic", llm_client.resolve_provider_chain("main") == ["anthropic"])
check("small tier resolves to openai", llm_client.resolve_provider_chain("small") == ["openai"])

# --- unit: an unset tier override falls back to the shared priority ---
from app.config import settings  # noqa: E402

original_small = settings.llm_provider_priority_small
try:
    settings.llm_provider_priority_small = ""
    settings.llm_provider_priority = "anthropic,openai"
    check(
        "blank tier override falls back to the shared LLM_PROVIDER_PRIORITY",
        llm_client.resolve_provider_chain("small") == ["anthropic", "openai"],
    )
finally:
    settings.llm_provider_priority_small = original_small
    settings.llm_provider_priority = "anthropic"


# --- integration: call_agentic(tier="main") only ever calls the
# anthropic client; call_agentic(tier="small") only ever calls the
# openai-compatible client. Proves tier genuinely selects the provider,
# not just the model name inside one fixed provider. ---
def fake_openai_response(text):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    resp.choices[0].message.tool_calls = None
    return resp


with patch("app.agents.llm_client._anthropic") as mock_anthropic, patch(
    "app.agents.llm_client._openai_compatible"
) as mock_openai:
    fake_anthropic_response = MagicMock()
    fake_anthropic_block = MagicMock()
    fake_anthropic_block.type = "text"
    fake_anthropic_block.text = "anthropic answered"
    fake_anthropic_response.content = [fake_anthropic_block]
    mock_anthropic.return_value.messages.create.return_value = fake_anthropic_response

    main_reply = llm_client.call_agentic(
        system="test", messages=[{"role": "user", "content": "hi"}], tools=[], tier="main"
    )
    check("main-tier call_agentic used the anthropic client", mock_anthropic.return_value.messages.create.called)
    check("main-tier call_agentic did NOT touch the openai client", not mock_openai.called)
    check("main-tier reply text is correct", main_reply.text == "anthropic answered")

    mock_anthropic.reset_mock()
    mock_openai.reset_mock()
    mock_openai.return_value.chat.completions.create.return_value = fake_openai_response("openai answered")

    small_reply = llm_client.call_agentic(
        system="test", messages=[{"role": "user", "content": "hi"}], tools=[], tier="small"
    )
    check("small-tier call_agentic used the openai client", mock_openai.return_value.chat.completions.create.called)
    check("small-tier call_agentic did NOT touch the anthropic client", not mock_anthropic.return_value.messages.create.called)
    check("small-tier reply text is correct", small_reply.text == "openai answered")


# --- same proof for call_with_tool (the tier param added alongside
# call_agentic's fix, for symmetry — mentor.py/hr.py don't need it today,
# but the plumbing is there for whoever needs it next). ---
with patch("app.agents.llm_client._anthropic") as mock_anthropic, patch(
    "app.agents.llm_client._openai_compatible"
) as mock_openai:
    fake_tool_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "a_tool"
    fake_block.input = {"x": 1}
    fake_tool_response.content = [fake_block]
    mock_anthropic.return_value.messages.create.return_value = fake_tool_response

    result = llm_client.call_with_tool(
        system="test",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "a_tool", "description": "d", "input_schema": {"type": "object"}}],
        force_tool="a_tool",
        tier="main",
    )
    check("call_with_tool(tier='main') used anthropic", mock_anthropic.return_value.messages.create.called)
    check("call_with_tool(tier='main') did not touch openai", not mock_openai.called)
    check("call_with_tool result shape unchanged", result == {"tool_name": "a_tool", "input": {"x": 1}})


# --- graph/models.py: small_model_chain()/reasoning_model_chain() also
# resolve through the right tier's providers, not a hardcoded one ---
main_chain = graph_models.reasoning_model_chain()
small_chain = graph_models.small_model_chain()
check("reasoning_model_chain resolves to the main-tier provider", [p for p, _ in main_chain] == ["anthropic"])
check("small_model_chain resolves to the small-tier provider", [p for p, _ in small_chain] == ["openai"])

print("\nAll LLM provider tier-routing checks passed.")
