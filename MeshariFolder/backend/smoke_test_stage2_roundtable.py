"""
Smoke test for the Stage 2 agent roundtable (docs/STAGE2_ROUNDTABLE.md):
after the Mentor's review, the specialists on the team discuss the
submission *in sequence, each seeing the prior turns*, then the Manager
posts a synthesis. Proves the actual collaboration — that a later
specialist's prompt contains an earlier one's comment, and that the
Manager's synthesis prompt contains the whole discussion — not just that
messages get written. Mocked LLM, real HTTP API.

Security Reviewer / Data Reviewer now go through their own structured
review path (security_reviewer.py / data_reviewer.py — call_with_tool,
forced tool, real repo analysis when a GitHub link is present) instead of
the generic free-text call_agentic every specialist used before; DevOps
is unchanged. Both mocking targets are exercised below. The *observable*
behavior this test cares about — who posts, in what order, that a
failing specialist doesn't block the rest of the table, that later turns
see earlier ones — is unchanged; only how Security/Data Reviewer's own
LLM call is mocked reflects their new internals.

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
from app.agents.llm_client import AgentReply  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


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
    # A readable file, not just notes: Security/Data Reviewer skip the LLM
    # entirely ('not_reviewed') when there's no content to inspect, and
    # this test is about the discussion between specialists that do run.
    client.post(
        f"/tasks/{task_id}/submit",
        headers=headers,
        data={"submission_text": "my work"},
        files=[("files", ("app.py", b"print('hello')\n", "text/x-python"))],
    )
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

# Security/Data Reviewer now answer via call_with_tool (forced tool, their
# own structured schema) — a fixed tool-call result per agent, same shape
# security_reviewer.py / data_reviewer.py actually produce.
SECURITY_REVIEW_RESULT = {
    "tool_name": "submit_security_review",
    "input": {
        "verdict": "concerns_found",
        "risk_level": "high",
        "findings": [
            {
                "category": "injection_risk",
                "severity": "high",
                "description": "Unparameterized query built from user input.",
                "recommendation": "Use parameterized queries.",
            }
        ],
        "summary": "That unparameterized query is a real SQL injection risk — fix it.",
    },
}
DATA_REVIEW_RESULT = {
    "tool_name": "submit_data_review",
    "input": {
        "verdict": "concerns_found",
        "risk_level": "medium",
        "findings": [
            {
                "category": "data_quality",
                "severity": "medium",
                "description": "No validation step before the data is used.",
                "recommendation": "Validate on ingest.",
            }
        ],
        "summary": "The data isn't validated on ingest — worth adding before this grows.",
    },
}
# DevOps stays on the original free-text path.
DEVOPS_REPLY = "No CI config in the repo — worth adding before this grows."
MANAGER_SYNTHESIS = "Top priority: fix the SQL injection Security flagged. Then add input validation."

captured_calls = []  # app.agents.roundtable.call_agentic (DevOps + Manager synthesis)
captured_specialist_calls = []  # (agent_id, kwargs) for the two structured reviewers


def fake_call_agentic(**kwargs):
    system = kwargs["system"]
    captured_calls.append(kwargs)
    if "synthesis" in system.lower() or "synthesize" in system.lower() or "pull the discussion together" in system.lower():
        return AgentReply(text=MANAGER_SYNTHESIS)
    if system.startswith("You are the DevOps"):
        return AgentReply(text=DEVOPS_REPLY)
    return AgentReply(text="(generic)")


def fake_security_call_with_tool(**kwargs):
    captured_specialist_calls.append(("security_reviewer", kwargs))
    return SECURITY_REVIEW_RESULT


def fake_data_call_with_tool(**kwargs):
    captured_specialist_calls.append(("data_reviewer", kwargs))
    return DATA_REVIEW_RESULT


# --- full roundtable: all three specialists + manager synthesis ---
headers = register_and_login("roundtable-full@example.com")
for a in ("security_reviewer", "data_reviewer", "devops"):
    add_agent("roundtable-full@example.com", a)
task_id = new_submitted_task(headers, "full roundtable")

with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=fake_call_agentic
), patch(
    "app.agents.security_reviewer.call_with_tool", side_effect=fake_security_call_with_tool
), patch(
    "app.agents.data_reviewer.call_with_tool", side_effect=fake_data_call_with_tool
):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review -> 201", r.status_code == 201)

# Speaker order is deterministic (sorted by AgentType value):
# data_reviewer, devops, security_reviewer, then the manager synthesis.
check("two structured specialist calls (data + security reviewer)", len(captured_specialist_calls) == 2)
check("two free-text calls (devops + manager synthesis)", len(captured_calls) == 2)

data_call = captured_specialist_calls[0]
check("first specialist is the data reviewer (sorted order)", data_call[0] == "data_reviewer")
check(
    "first specialist sees the Mentor's review",
    "unparameterized" in data_call[1]["messages"][0]["content"],
)
check("data reviewer runs on the small tier", data_call[1]["tier"] == "small")

devops_call = captured_calls[0]
check(
    "second specialist (devops) sees the data reviewer's turn",
    "validated on ingest" in devops_call["messages"][0]["content"],
)

security_call = captured_specialist_calls[1]
check("second structured call is the security reviewer", security_call[0] == "security_reviewer")
check(
    "third specialist (security) sees BOTH prior turns",
    "validated on ingest" in security_call[1]["messages"][0]["content"]
    and "No CI config" in security_call[1]["messages"][0]["content"],
)

manager_call = captured_calls[1]
check(
    "manager synthesis sees the whole discussion",
    "SQL injection" in manager_call["messages"][0]["content"]
    and "No CI config" in manager_call["messages"][0]["content"],
)
check("manager synthesis uses the main tier", manager_call["tier"] == "main")

# The thread should now hold: mentor + 3 specialists + manager synthesis —
# same shape as before the upgrade, regardless of which internal path
# each specialist took to get there.
r = client.get(f"/tasks/{task_id}", headers=headers)
agent_msgs = [m for m in r.json()["messages"] if m["sender_type"] == "agent"]
check("thread has mentor + 3 specialists + manager = 5 agent messages", len(agent_msgs) == 5)
kinds = [m["agent_type"] for m in agent_msgs]
check("mentor spoke first", kinds[0] == "mentor")
check("manager synthesis is last", kinds[-1] == "manager")

# Security/Data Reviewer's structured findings are also stored as their
# own Review row (kind=specialist_review) — not just a chat message that
# would otherwise be the only record of what they found.
r = client.get(f"/users/me/reviews", headers=headers)
specialist_reviews = [rv for rv in r.json() if rv["kind"] == "specialist_review"]
check("security + data reviewer each left a specialist_review Review row", len(specialist_reviews) == 2)
check(
    "the security review's structured findings are queryable, not just prose",
    any(
        rv["agent_type"] == "security_reviewer"
        and rv["metrics_json"]["risk_level"] == "high"
        and rv["metrics_json"]["findings"][0]["category"] == "injection_risk"
        for rv in specialist_reviews
    ),
)


# --- no specialists on roster: no roundtable, no manager synthesis ---
captured_calls.clear()
captured_specialist_calls.clear()
headers2 = register_and_login("roundtable-none@example.com")
task_id2 = new_submitted_task(headers2, "no specialists")
with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=fake_call_agentic
), patch(
    "app.agents.security_reviewer.call_with_tool", side_effect=fake_security_call_with_tool
), patch(
    "app.agents.data_reviewer.call_with_tool", side_effect=fake_data_call_with_tool
):
    r = client.post(f"/agents/mentor/review/{task_id2}", headers=headers2)
check("mentor review -> 201 (no specialists)", r.status_code == 201)
check("no roundtable calls at all when nobody's on the roster", len(captured_calls) == 0)
check("no structured specialist calls either", len(captured_specialist_calls) == 0)
r = client.get(f"/tasks/{task_id2}", headers=headers2)
agent_msgs = [m for m in r.json()["messages"] if m["sender_type"] == "agent"]
check("only the mentor's message", len(agent_msgs) == 1 and agent_msgs[0]["agent_type"] == "mentor")


# --- one specialist errors: the rest of the table carries on ---
# Data Reviewer's structured call raises; Security Reviewer (also on the
# roster) still succeeds and the Manager still synthesizes from what's
# left — same "best-effort per turn" property as before the upgrade.
captured_calls.clear()
captured_specialist_calls.clear()
headers3 = register_and_login("roundtable-partial@example.com")
for a in ("security_reviewer", "data_reviewer"):
    add_agent("roundtable-partial@example.com", a)
task_id3 = new_submitted_task(headers3, "partial failure")


def flaky_data_call_with_tool(**kwargs):
    captured_specialist_calls.append(("data_reviewer", kwargs))
    raise RuntimeError("simulated failure")


with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.roundtable.call_agentic", side_effect=fake_call_agentic
), patch(
    "app.agents.security_reviewer.call_with_tool", side_effect=fake_security_call_with_tool
), patch(
    "app.agents.data_reviewer.call_with_tool", side_effect=flaky_data_call_with_tool
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
