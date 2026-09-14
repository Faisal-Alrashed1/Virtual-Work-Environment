"""
Smoke test for Stage 2's optional agents actually doing task work (docs/
STAGE2_AGENT_TASK_WORK.md): Security Reviewer/Data Reviewer/DevOps post a
follow-up comment in the task thread after the Mentor's review, only if
they're on the graduate's roster; Career Coach never does (deliberately
excluded — coaching isn't a code review); one agent's failure doesn't
block the others or the Mentor's review itself. Mocked LLM, real HTTP API.

Run: python smoke_test_stage2_co_reviews.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_co_reviews.db"
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
        json={"email": email, "password": "hunter2pass", "full_name": "Co-Review Tester"},
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
    r = client.post("/tasks", json={"title": title, "description": "d", "user_id": "ignored"}, headers=headers)
    task_id = r.json()["id"]
    client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers)
    client.post(f"/tasks/{task_id}/submit", headers=headers, data={"submission_text": "here's my work"})
    return task_id


MENTOR_APPROVE = {
    "tool_name": "submit_review",
    "input": {
        "verdict": "approved",
        "summary": "Looks good.",
        "categories": {"correctness": 4, "code_quality": 4, "testing": 3, "documentation": 3},
        "comments": [],
    },
}


# --- no extra agents on roster -> no co-review messages ---
headers = register_and_login("co-review-none@example.com")
task_id = new_submitted_task(headers, "no extras")
with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review -> 201 (no extras)", r.status_code == 201)
r = client.get(f"/tasks/{task_id}", headers=headers)
agent_messages = [m for m in r.json()["messages"] if m["sender_type"] == "agent"]
check("only the mentor's own message, no co-reviews", len(agent_messages) == 1 and agent_messages[0]["agent_type"] == "mentor")


# --- security_reviewer + devops on roster, not data_reviewer ---
headers = register_and_login("co-review-some@example.com")
add_agent("co-review-some@example.com", "security_reviewer")
add_agent("co-review-some@example.com", "devops")
task_id = new_submitted_task(headers, "two extras")
with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.co_reviewers.call_agentic"
) as mock_co:
    mock_co.return_value = FakeResponse("Nothing security-relevant here, looks fine.")
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review -> 201 (two extras)", r.status_code == 201)
check("co_reviewers.call_agentic called exactly twice", mock_co.call_count == 2)
called_models = {c.kwargs["model"] for c in mock_co.call_args_list}
check("co-reviews use the small model", called_models == {"claude-haiku-4-5-20251001"})

r = client.get(f"/tasks/{task_id}", headers=headers)
agent_types = {m["agent_type"] for m in r.json()["messages"] if m["sender_type"] == "agent"}
check("thread has mentor + both added extras, not data_reviewer", agent_types == {"mentor", "security_reviewer", "devops"})


# --- career_coach on roster -> never co-reviews, even though it's added ---
headers = register_and_login("co-review-coach@example.com")
add_agent("co-review-coach@example.com", "career_coach")
task_id = new_submitted_task(headers, "career coach only")
with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.co_reviewers.call_agentic"
) as mock_co:
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review -> 201 (career coach on roster)", r.status_code == 201)
check("career coach never gets a co-review call", mock_co.call_count == 0)
r = client.get(f"/tasks/{task_id}", headers=headers)
agent_types = {m["agent_type"] for m in r.json()["messages"] if m["sender_type"] == "agent"}
check("only the mentor posted", agent_types == {"mentor"})


# --- one co-reviewer errors -> doesn't block the other or the mentor review ---
headers = register_and_login("co-review-partial-fail@example.com")
add_agent("co-review-partial-fail@example.com", "security_reviewer")
add_agent("co-review-partial-fail@example.com", "data_reviewer")
task_id = new_submitted_task(headers, "partial failure")


def flaky_call(**kwargs):
    if kwargs["system"].startswith("You are the Security Reviewer"):
        raise RuntimeError("simulated rate limit")
    return FakeResponse("Data quality looks reasonable from the notes.")


with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_APPROVE), patch(
    "app.agents.co_reviewers.call_agentic", side_effect=flaky_call
):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review still -> 201 despite a co-reviewer erroring", r.status_code == 201)
r = client.get(f"/tasks/{task_id}", headers=headers)
agent_types = {m["agent_type"] for m in r.json()["messages"] if m["sender_type"] == "agent"}
check("mentor + the co-reviewer that succeeded, not the one that errored", agent_types == {"mentor", "data_reviewer"})

print("\nAll Stage 2 co-review smoke checks passed.")
