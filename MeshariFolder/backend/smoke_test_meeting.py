"""
Smoke test for the Meeting Room (/meeting) — direct, task-free chat with
each agent. Mocked LLM (the reply text), same style as the other agent
smoke tests, no API key needed.

Run: python smoke_test_meeting.py
"""
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_meeting.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def mock_reply(text):
    resp = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp.content = [block]
    return resp


# --- setup ---
r = client.post(
    "/auth/register",
    json={"email": "meeting@x.com", "password": "hunter2pass", "full_name": "Sam Meeting"},
)
check("register", r.status_code == 201)
tok = client.post(
    "/auth/login", data={"username": "meeting@x.com", "password": "hunter2pass"}
).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

# --- empty history for each agent ---
for agent in ["manager", "mentor", "hr"]:
    r = client.get(f"/meeting/{agent}", headers=h)
    check(f"{agent}: empty history returns []", r.status_code == 200 and r.json() == [])

# --- unknown agent is rejected by enum validation ---
r = client.get("/meeting/ceo", headers=h)
check("unknown agent -> 422", r.status_code == 422)

# --- send a message to the mentor ---
with patch(
    "app.agents.meeting.get_client",
    return_value=MagicMock(
        messages=MagicMock(create=MagicMock(return_value=mock_reply("Try smaller commits.")))
    ),
):
    r = client.post("/meeting/mentor", json={"content": "How do I improve my PRs?"}, headers=h)
check("send to mentor -> 201", r.status_code == 201)
check("reply is from the agent", r.json()["sender_type"] == "agent")
check("reply agent_type is mentor", r.json()["agent_type"] == "mentor")
check("reply content is the mocked text", r.json()["content"] == "Try smaller commits.")

# --- history now has both the user message and the reply, in order ---
r = client.get("/meeting/mentor", headers=h)
hist = r.json()
check("mentor history has 2 messages", len(hist) == 2)
check(
    "order is user then agent",
    hist[0]["sender_type"] == "user" and hist[1]["sender_type"] == "agent",
)
check("user message content persisted", hist[0]["content"] == "How do I improve my PRs?")

# --- conversations are isolated per agent ---
r = client.get("/meeting/manager", headers=h)
check("manager history still empty (isolated per agent)", r.json() == [])

# --- a second mentor message appends, doesn't replace ---
with patch(
    "app.agents.meeting.get_client",
    return_value=MagicMock(
        messages=MagicMock(create=MagicMock(return_value=mock_reply("Good question.")))
    ),
):
    client.post("/meeting/mentor", json={"content": "And code review etiquette?"}, headers=h)
r = client.get("/meeting/mentor", headers=h)
check("mentor history now has 4 messages", len(r.json()) == 4)

# --- another user can't see this user's conversation ---
client.post(
    "/auth/register",
    json={"email": "other@x.com", "password": "hunter2pass", "full_name": "Other"},
)
tok2 = client.post(
    "/auth/login", data={"username": "other@x.com", "password": "hunter2pass"}
).json()["access_token"]
r = client.get("/meeting/mentor", headers={"Authorization": f"Bearer {tok2}"})
check("other user's mentor history is empty (isolated per user)", r.json() == [])

print("\nAll meeting checks passed.")
