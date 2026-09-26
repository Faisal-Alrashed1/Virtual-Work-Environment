"""
Smoke test for task-thread chat with an agent switcher (docs/TASK_CHAT.md):
the graduate can address a task message to the Mentor (the default), the
Manager, or a technical roster agent (Security Reviewer/Data Reviewer/
DevOps) — and can't address HR or an unadded roster agent. Mocked LLM, no
API key needed.

Run: python smoke_test_task_chat.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_task_chat.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402
from app.agents.llm_client import AgentReply, ToolCall  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def post_message_reply(text: str) -> AgentReply:
    return AgentReply(tool_calls=[ToolCall(name="post_message", input={"content": text})])


# --- setup: register, login, cv, first task ---
r = client.post(
    "/auth/register",
    json={"email": "task-chat@example.com", "password": "hunter2pass", "full_name": "Task Chat Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "task-chat@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

fake_project_input = {"title": "Venv Dashboard", "description": "A small internal dashboard."}
fake_week_input = {
    "big_task_title": "Ship the login flow",
    "big_task_description": "Get a working, tested login flow into the dashboard.",
    "subtasks": [
        {"title": f"Subtask {i}", "description": f"Do subtask {i}."} for i in range(1, 6)
    ],
}
with patch(
    "app.agents.manager.call_with_tool",
    side_effect=[
        {"tool_name": "create_project", "input": fake_project_input},
        {"tool_name": "plan_week", "input": fake_week_input},
    ],
):
    r = client.post("/agents/manager/assign-task", headers=headers)
check("first task assigned", r.status_code == 201)
task_id = r.json()["id"]

r = client.post(f"/tasks/{task_id}/messages", json={"content": "How should I start this?"}, headers=headers)
check("user posts message", r.status_code == 201)

# --- default (no body) routes to the Mentor, not the Manager ---
with patch("app.agents.mentor.call_agentic", return_value=post_message_reply("Start with the form component.")):
    r = client.post(f"/agents/task/{task_id}/reply", headers=headers)
check("default task-chat reply -> 201", r.status_code == 201)
check("default task-chat agent is mentor", r.json()["agent_type"] == "mentor")
check("mentor reply content used", "form component" in r.json()["content"])

# --- explicitly addressing the Manager still works, and stays in character ---
with patch("app.agents.manager.call_agentic", return_value=post_message_reply("Ask the Mentor for that one.")):
    r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "manager"})
check("manager task-chat reply -> 201", r.status_code == 201)
check("manager task-chat agent is manager", r.json()["agent_type"] == "manager")

# --- HR is never available for task-level chat, even though it's a default agent ---
r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "hr"})
check("hr not available for task chat -> 403", r.status_code == 403)

# --- an un-added roster agent (devops) is also refused ---
r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "devops"})
check("devops refused before being added to roster -> 403", r.status_code == 403)

# --- add devops to this graduate's roster directly (bypassing onboarding) ---
db = SessionLocal()
user = db.query(User).filter(User.email == "task-chat@example.com").first()
agent = db.query(AgentCatalog).filter(AgentCatalog.id == "devops").first()
db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
db.commit()
db.close()

with patch(
    "app.agents.task_chat.call_agentic", return_value=post_message_reply("That config looks fine to deploy.")
) as mock_call:
    r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "devops"})
check("devops task-chat reply -> 201 once on roster", r.status_code == 201)
check("devops task-chat agent is devops", r.json()["agent_type"] == "devops")
check("devops persona used, not a generic one", "DevOps" in mock_call.call_args.kwargs["system"])

# --- the task thread now has all of these messages, in order ---
r = client.get(f"/tasks/{task_id}", headers=headers)
messages = r.json()["messages"]
agent_speakers = [m["agent_type"] for m in messages if m["agent_type"]]
check(
    "thread shows mentor, manager, and devops all replying to the same task",
    {"mentor", "manager", "devops"} <= set(agent_speakers),
)

print("\nAll task-chat smoke checks passed.")
