"""
Smoke test for graceful LLM-failure handling under the multi-provider
failover model (docs/LLM_PROVIDER_FAILOVER.md, main.py's generic
RuntimeError handler). Confirms the agent endpoints return clean,
actionable errors instead of raw 500 stack traces when no provider is
configured, or every configured provider fails — and, just as
importantly, that a genuine bug (a RuntimeError unrelated to provider
failure) still surfaces as a real 500, not a swallowed 503.

Run: python smoke_test_llm_errors.py
"""
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_llm_errors.db"
)
# Deliberately no key for the config-error checks; overridden per-test
# where a provider is meant to be configured and then fail.
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""

from anthropic import AuthenticationError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

# raise_server_exceptions=False so a would-be 500 is returned as a response
# we can assert on, rather than re-raised into the test.
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def raise_auth_error(*a, **k):
    resp = MagicMock()
    resp.status_code = 401
    resp.headers = {}
    raise AuthenticationError("invalid x-api-key", response=resp, body=None)


# --- setup ---
client.post(
    "/auth/register",
    json={"email": "llmerr@x.com", "password": "hunter2pass", "full_name": "Err Case"},
)
tok = client.post(
    "/auth/login", data={"username": "llmerr@x.com", "password": "hunter2pass"}
).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

# --- no provider configured at all -> clean 503, not 500 ---
r = client.post("/agents/manager/assign-task", headers=h)
check("assign-task with no provider configured -> 503 (not 500)", r.status_code == 503)
check(
    "503 body has an actionable detail",
    "API key" in r.json()["detail"] or "LLM_PROVIDER_PRIORITY" in r.json()["detail"],
)

r = client.post("/meeting/manager", json={"content": "hi"}, headers=h)
check("meeting with no provider configured -> 503", r.status_code == 503)

# --- non-agent endpoints are unaffected by all this ---
check("users/me still 200", client.get("/users/me", headers=h).status_code == 200)
check("health still 200", client.get("/health").status_code == 200)


# --- a single configured provider that fails -> the chain is exhausted,
# clean 503 (not the old code's provider-specific status codes — with
# nothing left to fail over to, every failure kind now lands here) ---
settings.anthropic_api_key = "fake-key-for-this-test"
try:
    with patch("app.agents.meeting.call_agentic", side_effect=RuntimeError("All configured LLM providers failed:\nanthropic: simulated")):
        r = client.post("/meeting/mentor", json={"content": "hi"}, headers=h)
    check("single provider, chain exhausted -> 503", r.status_code == 503)
    check("503 explains every provider failed", "failed" in r.json()["detail"].lower())
finally:
    settings.anthropic_api_key = ""


# --- a genuine bug (a RuntimeError that ISN'T the failover-exhausted
# message) must NOT be swallowed into a fake 503 — main.py's handler only
# catches the specific ALL_PROVIDERS_FAILED-prefixed message and
# re-raises anything else, so this should come back as a real 500 ---
with patch("app.agents.meeting.call_agentic", side_effect=RuntimeError("some unrelated bug")):
    r = client.post("/meeting/hr", json={"content": "hi"}, headers=h)
check("an unrelated RuntimeError is NOT mistaken for a provider failure -> 500", r.status_code == 500)


# --- real cross-provider failover: the first provider in the chain
# raises an availability error, the second one succeeds — the request
# should succeed end to end, not error at all. This is the actual
# promise of the feature, proven through a real HTTP call. ---
settings.anthropic_api_key = "fake-anthropic-key"
settings.openai_api_key = "fake-openai-key"
settings.llm_provider_priority = "anthropic,openai"
try:
    with patch("app.agents.llm_client._anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.side_effect = raise_auth_error

        fake_openai_response = MagicMock()
        fake_openai_response.choices = [MagicMock()]
        fake_openai_response.choices[0].message.content = "Failover worked — this is OpenAI answering."
        fake_openai_response.choices[0].message.tool_calls = None

        with patch("app.agents.llm_client._openai_compatible") as mock_openai_compat:
            mock_openai_compat.return_value.chat.completions.create.return_value = fake_openai_response
            r = client.post("/meeting/manager", json={"content": "hi"}, headers=h)

    check("anthropic fails, openai succeeds -> the request still succeeds (201)", r.status_code == 201)
    check(
        "the reply actually came from the failover provider, not a generic error",
        "Failover worked" in r.json()["content"],
    )
finally:
    settings.anthropic_api_key = ""
    settings.openai_api_key = ""
    settings.llm_provider_priority = "anthropic"

print("\nAll LLM-error-handling checks passed.")
