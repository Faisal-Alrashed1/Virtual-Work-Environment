"""
Smoke test for the Stage 2 agent roundtable (docs/STAGE2_ROUNDTABLE.md):
after the Mentor's review, the specialists on the team discuss the
submission *in sequence, each seeing the prior turns*, then the Manager
posts a synthesis. Proves the actual collaboration — that a later
specialist's prompt contains an earlier one's comment, and that the
Manager's synthesis prompt contains the whole discussion — not just that
messages get written. Mocked LLM, real HTTP API.

Run: python smoke_test_stage2_roundtable.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_roundtable.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


class FakeContentBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContentBlock(text)]


def register_and_login(email):
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "hunter2pass", "full_name": "Roundtable Tester"},
    )
    check(f"register {email}", r.status_code == 201)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_agent(email, agent_id):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    agent = db.query(AgentCatalog).filter(AgentCatalog.id == agent_id).first()
    db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
    db.commit()
    db.close()


def new_submitted_task(headers, title):
    r = client.post("/tasks", json={"title": title, "description": "d", "user_id": "x"}, headers=headers)
    task_id = r.json()["id"]
    client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers)
    client.post(f"/tasks/{task_id}/submit", headers=headers, data={"submission_text": "my work"})
    return task_id


MENTOR_APPROVE = {
    "tool_name": "submit_review",
    "input": {
        "verdict": "approved",
        "summary": "Solid. One SQL query looks unparameterized though.",
        "categories": {"correctness": 4, "code_quality": 3, "testing": 3, "documentation": 3},
        "comments": [],
    },
}

# Distinctive per-agent replies so we can trace who saw what in the prompts.
SPECIALIST_REPLIES = {
    "You are the Security Reviewer": "That unparameterized query is a real SQL injection risk — fix it.",
    "You are the Data Reviewer": "Agreeing with Security on the query; also the data isn't validated on ingest.",
    "You are the DevOps": "No CI config in the repo — worth adding before this grows.",
}
MANAGER_SYNTHESIS = "Top priority: fix the SQL injection Security flagged. Then add input validation."

captured_calls = []


def fake_call_agentic(**kwargs):
    system = kwargs["system"]
    captured_calls.append(kwargs)
    if "synthesis" in system.lower() or "synthesize" in system.lower() or "pull the discussion together" in system.lower():
        return FakeResponse(MANAGER_SYNTHESIS)
    for prefix, reply in SPECIALIST_REPLIES.items():
        if system.startswith(prefix):
            return FakeResponse(reply)
    return FakeResponse("(generic)")


# --- full roundtable: all three specialists + manager synthesis ---
headers = register_and_login("roundtable-full@example.com")
for a in ("security_reviewer", "data_reviewer", "devops"):
    add_agent("roundtable-full@example.com", a)
task_id = new_submitted_task(headers, "full roundtable")

with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=fake_call_agentic
):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review -> 201", r.status_code == 201)

# 3 specialists + 1 manager synthesis = 4 roundtable calls
check("four roundtable LLM calls (3 specialists + manager synthesis)", len(captured_calls) == 4)

# The specialists run in deterministic order: data_reviewer, devops,
# security_reviewer (sorted by enum value). Verify each later turn's
# prompt contains the earlier turns' text — the core "they see each
# other" property.
data_call = captured_calls[0]
check("first specialist is the data reviewer (sorted order)", data_call["system"].startswith("You are the Data Reviewer"))
check("first specialist sees the Mentor's review", "unparameterized" in data_call["messages"][0]["content"])

devops_call = captured_calls[1]
check("second specialist (devops) sees the data reviewer's turn", "validated on ingest" in devops_call["messages"][0]["content"])

security_call = captured_calls[2]
check(
    "third specialist (security) sees BOTH prior turns",
    "validated on ingest" in security_call["messages"][0]["content"]
    and "No CI config" in security_call["messages"][0]["content"],
)

manager_call = captured_calls[3]
check(
    "manager synthesis sees the whole discussion",
    "SQL injection" in manager_call["messages"][0]["content"]
    and "No CI config" in manager_call["messages"][0]["content"],
)
check("manager synthesis uses the main model", manager_call["model"] == "claude-sonnet-5")
check("specialists use the small model", data_call["model"] == "claude-haiku-4-5-20251001")

# The thread should now hold: mentor + 3 specialists + manager synthesis.
r = client.get(f"/tasks/{task_id}", headers=headers)
agent_msgs = [m for m in r.json()["messages"] if m["sender_type"] == "agent"]
check("thread has mentor + 3 specialists + manager = 5 agent messages", len(agent_msgs) == 5)
kinds = [m["agent_type"] for m in agent_msgs]
check("mentor spoke first", kinds[0] == "mentor")
check("manager synthesis is last", kinds[-1] == "manager")


# --- no specialists on roster: no roundtable, no manager synthesis ---
captured_calls.clear()
headers2 = register_and_login("roundtable-none@example.com")
task_id2 = new_submitted_task(headers2, "no specialists")
with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=fake_call_agentic
):
    r = client.post(f"/agents/mentor/review/{task_id2}", headers=headers2)
check("mentor review -> 201 (no specialists)", r.status_code == 201)
check("no roundtable calls at all when nobody's on the roster", len(captured_calls) == 0)
r = client.get(f"/tasks/{task_id2}", headers=headers2)
agent_msgs = [m for m in r.json()["messages"] if m["sender_type"] == "agent"]
check("only the mentor's message", len(agent_msgs) == 1 and agent_msgs[0]["agent_type"] == "mentor")


# --- one specialist errors: the rest of the table carries on ---
captured_calls.clear()
headers3 = register_and_login("roundtable-partial@example.com")
for a in ("security_reviewer", "data_reviewer"):
    add_agent("roundtable-partial@example.com", a)
task_id3 = new_submitted_task(headers3, "partial failure")


def flaky(**kwargs):
    captured_calls.append(kwargs)
    if kwargs["system"].startswith("You are the Data Reviewer"):
        raise RuntimeError("simulated failure")
    if "pull the discussion together" in kwargs["system"].lower():
        return FakeResponse(MANAGER_SYNTHESIS)
    return FakeResponse("Security take: looks fine.")


with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=flaky
):
    r = client.post(f"/agents/mentor/review/{task_id3}", headers=headers3)
check("mentor review still -> 201 despite a specialist erroring", r.status_code == 201)
r = client.get(f"/tasks/{task_id3}", headers=headers3)
agent_types = [m["agent_type"] for m in r.json()["messages"] if m["sender_type"] == "agent"]
check(
    "thread has mentor + security + manager, not the errored data reviewer",
    agent_types == ["mentor", "security_reviewer", "manager"],
)

print("\nAll Stage 2 roundtable smoke checks passed.")
