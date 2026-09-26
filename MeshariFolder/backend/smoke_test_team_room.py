"""
Smoke test for the Team Room (/meeting/team, docs/TEAM_ROOM.md) — a
shared conversation with the whole team, distinct from the Meeting
Room's one-thread-per-agent chats. Each graduate message is routed to
one teammate; routing failures and out-of-roster picks fall back to the
Manager rather than ever 500ing. Mocked LLM, no API key needed.

Run: python smoke_test_team_room.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_team_room.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402
from app.agents.llm_client import AgentReply  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def routed_to(agent: str) -> dict:
    return {"tool_name": "route_to_agent", "input": {"agent": agent}}


# --- setup ---
r = client.post(
    "/auth/register",
    json={"email": "team-room@example.com", "password": "hunter2pass", "full_name": "Team Room Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "team-room@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- empty history to start ---
r = client.get("/meeting/team", headers=headers)
check("team room starts empty", r.status_code == 200 and r.json() == [])

# --- a message routed to the Manager ---
with (
    patch("app.agents.meeting.call_with_tool", return_value=routed_to("manager")),
    patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Week's looking solid so far.")),
):
    r = client.post("/meeting/team", json={"content": "How's my week going overall?"}, headers=headers)
check("team message -> 201", r.status_code == 201)
check("routed to manager", r.json()["agent_type"] == "manager")
check("reply content used", r.json()["content"] == "Week's looking solid so far.")
check("reply is from an agent", r.json()["sender_type"] == "agent")

# --- history now has both turns, in order, user message has no agent_type ---
r = client.get("/meeting/team", headers=headers)
hist = r.json()
check("team history has 2 messages", len(hist) == 2)
check("first is the user's own message", hist[0]["sender_type"] == "user" and hist[0]["agent_type"] is None)
check("second is the manager's reply", hist[1]["sender_type"] == "agent" and hist[1]["agent_type"] == "manager")

# --- a different message routed to the Mentor, persona actually used ---
with (
    patch("app.agents.meeting.call_with_tool", return_value=routed_to("mentor")),
    patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Break the function up a bit.")) as mock_reply,
):
    r = client.post("/meeting/team", json={"content": "Any code style tips?"}, headers=headers)
check("second team message routed to mentor", r.status_code == 201 and r.json()["agent_type"] == "mentor")
check("mentor persona used, not manager's", "Mentor" in mock_reply.call_args.kwargs["system"])

# --- routing failure falls back to the Manager instead of 500ing ---
with (
    patch("app.agents.meeting.call_with_tool", side_effect=RuntimeError("provider down")),
    patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Let's take it from here.")),
):
    r = client.post("/meeting/team", json={"content": "..."}, headers=headers)
check("routing failure never 500s", r.status_code == 201)
check("routing failure falls back to manager", r.json()["agent_type"] == "manager")

# --- an out-of-roster pick (devops, never added) also falls back to the Manager ---
with (
    patch("app.agents.meeting.call_with_tool", return_value=routed_to("devops")),
    patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Falling back here.")),
):
    r = client.post("/meeting/team", json={"content": "..."}, headers=headers)
check("out-of-roster pick falls back to manager", r.status_code == 201 and r.json()["agent_type"] == "manager")

# --- add devops to the roster: now a valid routing target ---
db = SessionLocal()
user = db.query(User).filter(User.email == "team-room@example.com").first()
agent = db.query(AgentCatalog).filter(AgentCatalog.id == "devops").first()
db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
db.commit()
db.close()

with (
    patch("app.agents.meeting.call_with_tool", return_value=routed_to("devops")),
    patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="That pipeline config looks fine.")),
):
    r = client.post("/meeting/team", json={"content": "Is my CI config ok?"}, headers=headers)
check("devops reachable once on roster", r.status_code == 201 and r.json()["agent_type"] == "devops")

# --- the Team Room is separate from the 1:1 Meeting Room threads ---
r = client.get("/meeting/manager", headers=headers)
check("1:1 manager thread untouched by team room activity", r.json() == [])

# --- isolated per user ---
client.post(
    "/auth/register",
    json={"email": "other-team@example.com", "password": "hunter2pass", "full_name": "Other"},
)
tok2 = client.post(
    "/auth/login", data={"username": "other-team@example.com", "password": "hunter2pass"}
).json()["access_token"]
r = client.get("/meeting/team", headers={"Authorization": f"Bearer {tok2}"})
check("other user's team room is empty (isolated per user)", r.json() == [])

print("\nAll Team Room smoke checks passed.")
