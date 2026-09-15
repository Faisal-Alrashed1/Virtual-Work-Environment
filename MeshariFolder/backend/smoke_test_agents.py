"""
Agent-logic smoke test. Mocks the LLM (no Anthropic API key needed to run
this) but hits the real, public GitHub API for the Mentor's repo fetch, and
runs everything else through the real FastAPI app + sqlite, same style as
smoke_test.py.
Run: python smoke_test_agents.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_agents.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


class FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class FakeResponse:
    def __init__(self, content):
        self.content = content


# --- setup: register, login, submit CV ---
r = client.post(
    "/auth/register",
    json={"email": "agent-test@example.com", "password": "hunter2pass", "full_name": "Agent Tester"},
)
check("register", r.status_code == 201)

r = client.post("/auth/login", data={"username": "agent-test@example.com", "password": "hunter2pass"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.post(
    "/users/me/cv",
    json={"cv_raw_text": "Built two React apps, comfortable with Python, new to testing."},
    headers=headers,
)
check("submit cv", r.status_code == 200)

# --- Manager assigns the first task: this now bootstraps a Project + Week
# 1 behind the scenes (2 LLM calls — create_project, then plan_week — see
# app/agents/weekly_cycle.py), not a single flat create_task call anymore. ---
fake_project_input = {
    "title": "Venv Internal Dashboard",
    "description": "A small internal dashboard the graduate will build out incrementally.",
}
fake_week_input = {
    "big_task_title": "Ship the login flow",
    "big_task_description": "Get a working, tested login flow into the dashboard.",
    "subtasks": [
        {"title": "Add a login form", "description": "Build an email/password login form against the existing auth endpoints."},
        {"title": "Add form validation", "description": "Client-side validation with clear error states."},
        {"title": "Wire up the auth API", "description": "Connect the form to POST /auth/login."},
        {"title": "Handle auth errors", "description": "Show a clear message on invalid credentials."},
        {"title": "Add a logout button", "description": "Simple logout that clears the session."},
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
check(
    "manager assigns first subtask",
    r.status_code == 201 and r.json()["title"] == fake_week_input["subtasks"][0]["title"],
)
task = r.json()
check("task created_by_agent is manager", task["created_by_agent"] == "manager")
check("task carries a week_id", task["week_id"] is not None)
check("task has a deadline", task["deadline"] is not None)

r = client.get(f"/tasks/{task['id']}", headers=headers)
check("manager posted intro message", r.status_code == 200 and len(r.json()["messages"]) == 1)

# --- graduate asks a question, Manager replies (mocked LLM, auto tool choice) ---
r = client.post(
    f"/tasks/{task['id']}/messages", json={"content": "Should I use a UI library?"}, headers=headers
)
check("user posts message", r.status_code == 201)

fake_reply = FakeResponse(
    [FakeBlock("tool_use", name="post_message", input={"content": "No need — plain HTML/CSS is fine for this one."})]
)
with patch("app.agents.manager.call_agentic", return_value=fake_reply):
    r = client.post(f"/agents/manager/reply/{task['id']}", headers=headers)
check("manager replies in thread", r.status_code == 201 and "HTML/CSS" in r.json()["content"])

# --- graduate submits a real public repo link, Mentor reviews it ---
r = client.patch(
    f"/tasks/{task['id']}/status",
    json={"status": "submitted", "github_link": "https://github.com/psf/requests"},
    headers=headers,
)
check("submit task with github link", r.status_code == 200)

fake_review_input = {
    "verdict": "approved",
    "summary": "Solid first task — clean structure, good use of existing endpoints. Add tests next time.",
    "categories": [
        {"key": "correctness", "label": "Meets requirements", "score": 5},
        {"key": "code_quality", "label": "Code quality", "score": 4},
        {"key": "testing", "label": "Testing", "score": 2},
        {"key": "documentation", "label": "Documentation", "score": 3},
    ],
    "comments": [
        {"category": "testing", "content": "No tests yet — add at least one for the login flow next task."}
    ],
}
with patch(
    "app.agents.mentor.call_with_tool",
    return_value={"tool_name": "submit_review", "input": fake_review_input},
):
    r = client.post(f"/agents/mentor/review/{task['id']}", headers=headers)
check(
    "mentor reviews task (real GitHub fetch + mocked LLM)",
    r.status_code == 201 and r.json()["metrics_json"]["verdict"] == "approved",
)

r = client.get(f"/tasks/{task['id']}", headers=headers)
check("task moved to reviewed", r.status_code == 200 and r.json()["status"] == "reviewed")

r = client.get(f"/tasks/{task['id']}/review", headers=headers)
check("get task review", r.status_code == 200 and len(r.json()["metrics_json"]["categories"]) == 4)

# reviewing again should now be blocked (task no longer 'submitted')
r = client.post(f"/agents/mentor/review/{task['id']}", headers=headers)
check("mentor review blocked when not submitted", r.status_code == 400)

# --- HR rolls up the review history (mocked LLM, forced tool) ---
fake_ef_input = {
    "skills": ["React", "Python", "REST APIs"],
    "strengths": ["Ships working code quickly", "Follows existing patterns well"],
    "growth_areas": ["Add tests alongside the feature, not after"],
    "summary": "One task in: solid execution, testing is the clear next growth area.",
}
with patch(
    "app.agents.hr.call_with_tool",
    return_value={"tool_name": "update_employee_file", "input": fake_ef_input},
):
    r = client.post("/agents/hr/rollup", headers=headers)
check("hr rollup", r.status_code == 201 and r.json()["agent_type"] == "hr")

r = client.get("/users/me/employee-file", headers=headers)
ef = r.json()
check("employee file skills updated", r.status_code == 200 and ef["skills_json"]["items"] == fake_ef_input["skills"])
check("employee file summary updated", ef["summary_text"] == fake_ef_input["summary"])

r = client.get("/users/me/reviews", headers=headers)
check("list reviews returns mentor + hr", r.status_code == 200 and len(r.json()) == 2)

# HR rollup with zero Mentor reviews should be rejected
client.post(
    "/auth/register",
    json={"email": "no-reviews@example.com", "password": "hunter2pass", "full_name": "No Reviews"},
)
r2 = client.post("/auth/login", data={"username": "no-reviews@example.com", "password": "hunter2pass"})
other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = client.post("/agents/hr/rollup", headers=other_headers)
check("hr rollup blocked with no reviews", r.status_code == 400)

print("\nAll agent checks passed.")
