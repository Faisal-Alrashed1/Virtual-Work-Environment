"""
Smoke test for the weekly-cycle schema (Project, Week, Task
deadline/submitted_at/completed_at/is_late, Review kind/week_id) and the
Mentor's iterative-review fix (needs_changes now bounces the task back to
in_progress instead of dead-ending in 'reviewed'). Same mocked-LLM style as
smoke_test_agents.py — no Anthropic API key needed.

Project/Week/Task are all written directly via the ORM here rather than
through the API, to isolate what this test actually cares about (the
fields, and Mentor's approve/needs_changes behavior) from the orchestration
that normally creates them. That orchestration — Manager actually bootstrapping
a Project/Week and releasing subtasks one at a time — is covered end to end,
through the real API, by smoke_test_orchestration.py.

Run: python smoke_test_weekly_cycle.py
"""
import os
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_weekly_cycle.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Project, ProjectStatus, Task, WeekStatus, Week  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# --- setup ---
r = client.post(
    "/auth/register",
    json={"email": "weekly-test@example.com", "password": "hunter2pass", "full_name": "Weekly Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "weekly-test@example.com", "password": "hunter2pass"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
user_id = client.get("/users/me", headers=headers).json()["id"]

# --- Project + Week, written directly (no endpoint yet) ---
db = SessionLocal()
project = Project(user_id=user_id, title="Landing page revamp", description="Rebuild the marketing site's landing page.")
db.add(project)
db.commit()
db.refresh(project)
check("project created", project.status == ProjectStatus.ACTIVE)

week = Week(
    project_id=project.id,
    user_id=user_id,
    week_number=1,
    big_task_title="Ship the new landing page",
    big_task_description="Hero, features grid, footer, mobile-responsive.",
    target_end_at=datetime.utcnow() + timedelta(days=5),
    subtasks_plan_json=[{"title": f"Subtask {i}", "description": "..."} for i in range(1, 6)],
)
db.add(week)
db.commit()
db.refresh(week)
check("week created", week.status == WeekStatus.ACTIVE and len(week.subtasks_plan_json) == 5)
check("project.weeks relationship", project.weeks[0].id == week.id)
week_id = week.id
db.close()

# --- Task, written directly too (orchestration itself — Manager actually
# creating this via the weekly-cycle state machine — is covered end to end
# by smoke_test_orchestration.py; this test only needs a Task with a
# week_id + deadline in place to exercise the fields/Mentor behavior below) ---
db = SessionLocal()
task = Task(
    title="Build the hero section",
    description="Hero section per the design spec.",
    user_id=user_id,
    week_id=week_id,
    deadline=datetime.utcnow() + timedelta(days=1),
)
db.add(task)
db.commit()
db.refresh(task)
task_id = task.id
db.close()

# --- submit, Mentor says needs_changes -> bounces back to in_progress ---
r = client.patch(
    f"/tasks/{task_id}/status",
    json={"status": "submitted", "github_link": "https://github.com/psf/requests"},
    headers=headers,
)
check("submit task", r.status_code == 200)
check("submitted_at stamped", r.json()["submitted_at"] is not None)
check("task carries week_id", r.json()["week_id"] == week_id)

fake_needs_changes = {
    "verdict": "needs_changes",
    "summary": "Close, but the hero section doesn't render on mobile widths.",
    "categories": [
        {"key": "correctness", "label": "Meets requirements", "score": 2},
        {"key": "code_quality", "label": "Code quality", "score": 3},
        {"key": "testing", "label": "Testing", "score": 2},
        {"key": "documentation", "label": "Documentation", "score": 3},
    ],
    "comments": [{"category": "correctness", "content": "Layout breaks under 400px."}],
}
with patch(
    "app.agents.mentor.call_with_tool",
    return_value={"tool_name": "submit_review", "input": fake_needs_changes},
):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review (needs_changes)", r.status_code == 201)
check("review kind is task_review", r.json()["kind"] == "task_review")
check("review carries week_id", r.json()["week_id"] == week_id)

r = client.get(f"/tasks/{task_id}", headers=headers)
check("needs_changes bounces task back to in_progress, not reviewed", r.json()["status"] == "in_progress")
check("completed_at NOT set on needs_changes", r.json()["completed_at"] is None)

# --- resubmit, Mentor approves this time -> reviewed + completed_at + is_late ---
r = client.patch(
    f"/tasks/{task_id}/status",
    json={"status": "submitted", "github_link": "https://github.com/psf/requests"},
    headers=headers,
)
check("resubmit", r.status_code == 200)

fake_approved = {
    "verdict": "approved",
    "summary": "Mobile layout fixed, looks good now.",
    "categories": [
        {"key": "correctness", "label": "Meets requirements", "score": 5},
        {"key": "code_quality", "label": "Code quality", "score": 4},
        {"key": "testing", "label": "Testing", "score": 3},
        {"key": "documentation", "label": "Documentation", "score": 3},
    ],
    "comments": [],
}
with patch(
    "app.agents.mentor.call_with_tool",
    return_value={"tool_name": "submit_review", "input": fake_approved},
):
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
check("mentor review (approved)", r.status_code == 201)

r = client.get(f"/tasks/{task_id}", headers=headers)
task_final = r.json()
check("approved moves task to reviewed", task_final["status"] == "reviewed")
check("completed_at set on approval", task_final["completed_at"] is not None)
check("is_late computed correctly (deadline was a day out)", task_final["is_late"] is False)

print("\nAll weekly-cycle schema checks passed.")
