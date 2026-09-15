"""
Smoke test for graceful LLM-failure handling (main.py's exception
handlers). Confirms the agent endpoints return clean, actionable errors
instead of raw 500 stack traces when the LLM can't be used — the exact
class of failure a reviewer or teammate hits with a missing/spent API key.

Run: python smoke_test_llm_errors.py
"""
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_llm_errors.db"
)
# Deliberately no key for the config-error checks; overridden where a call
# is mocked to raise a specific API error.
os.environ["ANTHROPIC_API_KEY"] = ""

from anthropic import AuthenticationError, RateLimitError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

# raise_server_exceptions=False so a would-be 500 is returned as a response
# we can assert on, rather than re-raised into the test.
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# --- setup ---
client.post(
    "/auth/register",
    json={"email": "llmerr@x.com", "password": "hunter2pass", "full_name": "Err Case"},
)
tok = client.post(
    "/auth/login", data={"username": "llmerr@x.com", "password": "hunter2pass"}
).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

# --- no API key configured -> clean 503 with an actionable message, not 500 ---
r = client.post("/agents/manager/assign-task", headers=h)
check("assign-task with no key -> 503 (not 500)", r.status_code == 503)
check("503 body has an actionable detail", "ANTHROPIC_API_KEY" in r.json()["detail"])

r = client.post("/meeting/manager", json={"content": "hi"}, headers=h)
check("meeting with no key -> 503", r.status_code == 503)

# --- non-agent endpoints are unaffected by all this ---
check("users/me still 200", client.get("/users/me", headers=h).status_code == 200)
check("health still 200", client.get("/health").status_code == 200)


# --- a genuine AuthenticationError from the API -> 503, mapped message ---
def raise_auth(*a, **k):
    resp = MagicMock()
    resp.status_code = 401
    resp.headers = {}
    raise AuthenticationError("invalid x-api-key", response=resp, body=None)


with patch("app.agents.meeting.get_client") as gc:
    gc.return_value.messages.create.side_effect = raise_auth
    r = client.post("/meeting/mentor", json={"content": "hi"}, headers=h)
check("auth error from API -> 503", r.status_code == 503)
check("auth 503 mentions the key", "key" in r.json()["detail"].lower())


# --- a RateLimitError -> 429 ---
def raise_rate(*a, **k):
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    raise RateLimitError("slow down", response=resp, body=None)


with patch("app.agents.meeting.get_client") as gc:
    gc.return_value.messages.create.side_effect = raise_rate
    r = client.post("/meeting/hr", json={"content": "hi"}, headers=h)
check("rate limit from API -> 429", r.status_code == 429)

print("\nAll LLM-error-handling checks passed.")
