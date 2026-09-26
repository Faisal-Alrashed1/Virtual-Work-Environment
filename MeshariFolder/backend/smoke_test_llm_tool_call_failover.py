"""
Smoke test for invalid tool calls (docs/TEAM_CHANGES.md, fix #2). When a
model answers without the forced tool call — plain text, no call, or
broken JSON arguments — llm_client retries once on the same provider,
then fails over; if every provider fails, the request gets a clean 503
(with CORS headers, so the browser can read it) instead of a raw 500
(which had no CORS headers, so the frontend showed "Can't reach the
server" while the backend was up). Same for onboarding's LangGraph path.

Provider SDK calls are mocked — no API key needed.

Run: python smoke_test_llm_tool_call_failover.py
"""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_llm_tool_call_failover.db"
)
for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY"):
    os.environ[key] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402
from app.agents.llm_client import ALL_PROVIDERS_FAILED, call_with_tool  # noqa: E402
from app.agents.graph.onboarding_graph import QUESTIONS_TOOL, _forced_tool_call  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def openai_response(tool_name=None, arguments='{"x": 1}', text="Sure! Here you go."):
    """A fake OpenAI-compatible chat completion: with a tool call if
    tool_name is given, otherwise a plain-text answer (the bad case)."""
    message = SimpleNamespace(content=None if tool_name else text, tool_calls=None)
    if tool_name:
        message.tool_calls = [SimpleNamespace(function=SimpleNamespace(name=tool_name, arguments=arguments))]
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


TOOL = {"name": "do_it", "description": "d", "input_schema": {"type": "object", "properties": {}}}


def fake_clients(responses_by_provider):
    """_openai_compatible(provider) -> a client whose create() returns that
    provider's responses in order."""
    clients = {}
    for provider, responses in responses_by_provider.items():
        c = MagicMock()
        c.chat.completions.create.side_effect = list(responses)
        clients[provider] = c
    return clients


def configure(priority, **keys):
    settings.llm_provider_priority = priority
    settings.llm_provider_priority_main = ""
    settings.llm_provider_priority_small = ""
    for name in ("anthropic", "openai", "deepseek", "qwen"):
        setattr(settings, f"{name}_api_key", keys.get(name, ""))


def run(responses_by_provider, **kw):
    clients = fake_clients(responses_by_provider)
    with patch("app.agents.llm_client._openai_compatible", side_effect=lambda p: clients[p]):
        try:
            result = call_with_tool(system="s", messages=[{"role": "user", "content": "u"}], tools=[TOOL], force_tool="do_it", **kw)
            error = None
        except RuntimeError as e:
            result, error = None, e
    return result, error, clients


try:
    configure("qwen", qwen="fake-key")

    # --- answers in text once, then correctly -> retried, succeeds ---
    result, error, clients = run({"qwen": [openai_response(), openai_response("do_it")]})
    check("text answer then a real call -> succeeds on retry", error is None and result["input"] == {"x": 1})
    check("same provider was asked twice", clients["qwen"].chat.completions.create.call_count == 2)

    # --- always answers in text -> clean ALL_PROVIDERS_FAILED, not a crash ---
    result, error, clients = run({"qwen": [openai_response(), openai_response()]})
    check("always text -> ALL_PROVIDERS_FAILED (becomes a 503)", error is not None and str(error).startswith(ALL_PROVIDERS_FAILED))
    check("gave up after 2 attempts, not 1 and not forever", clients["qwen"].chat.completions.create.call_count == 2)
    check("the error says what went wrong", "without calling 'do_it'" in str(error))

    # --- broken JSON arguments (what qwen3.7-flash returned live) ---
    bad = openai_response("do_it", arguments='{"questions": [unfinished')
    result, error, _ = run({"qwen": [bad, bad]})
    check("broken JSON arguments -> ALL_PROVIDERS_FAILED, not JSONDecodeError", error is not None and str(error).startswith(ALL_PROVIDERS_FAILED))

    # --- first provider keeps misbehaving -> fails over to the next ---
    configure("qwen,openai", qwen="fake-key", openai="fake-key")
    result, error, clients = run({
        "qwen": [openai_response(), openai_response()],
        "openai": [openai_response("do_it", arguments='{"from": "openai"}')],
    })
    check("misbehaving provider -> fails over to the next one", error is None and result["input"] == {"from": "openai"})
    check("qwen got its 2 attempts before failing over", clients["qwen"].chat.completions.create.call_count == 2)

    # --- through a real endpoint: 503 the browser can read, not a CORS-less 500 ---
    configure("qwen", qwen="fake-key")
    client.post("/auth/register", json={"email": "toolcall@x.com", "password": "hunter2pass", "full_name": "T"})
    tok = client.post("/auth/login", data={"username": "toolcall@x.com", "password": "hunter2pass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}", "Origin": "http://localhost:3000"}
    clients = fake_clients({"qwen": [openai_response(), openai_response()]})
    with patch("app.agents.llm_client._openai_compatible", side_effect=lambda p: clients[p]):
        r = client.post("/agents/manager/assign-task", headers=headers)
    check("endpoint returns 503, not 500", r.status_code == 503)
    check("503 carries the CORS header (frontend can show the message)", r.headers.get("access-control-allow-origin") is not None)
    check("503 detail explains the providers failed", "failed" in r.json()["detail"].lower())
finally:
    configure("anthropic")


# --- onboarding's LangGraph path (_forced_tool_call) ---
def fake_model(*tool_call_lists):
    model = MagicMock()
    model.model = "fake-model"
    model.bind_tools.return_value.invoke.side_effect = [SimpleNamespace(tool_calls=calls) for calls in tool_call_lists]
    return model


good_call = [{"name": "generate_questions", "args": {"questions": ["Q?"]}}]
m = fake_model([], good_call)
args = _forced_tool_call([("qwen", m)], QUESTIONS_TOOL, [])
check("onboarding: no tool call then a real one -> succeeds on retry", args == {"questions": ["Q?"]})

m1, m2 = fake_model([], []), fake_model(good_call)
args = _forced_tool_call([("qwen", m1), ("openai", m2)], QUESTIONS_TOOL, [])
check("onboarding: misbehaving provider fails over to the next", args == {"questions": ["Q?"]})

try:
    _forced_tool_call([("qwen", fake_model([], []))], QUESTIONS_TOOL, [])
    check("onboarding: always no tool call -> ALL_PROVIDERS_FAILED", False)
except RuntimeError as e:
    check("onboarding: always no tool call -> ALL_PROVIDERS_FAILED (a 503, not a 500)", str(e).startswith(ALL_PROVIDERS_FAILED))

print("\nAll tool-call failover smoke checks passed.")
