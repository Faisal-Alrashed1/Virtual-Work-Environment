"""
Smoke test for the company's view into a hired student
(docs/STAGE3_COMPANY_RAG.md): a live roster (GET /company/students) and
per-student week-by-week detail with the same Manager/HR end-of-week
reviews the weekly cycle already produces (GET /company/students/{id}) —
this IS the "end-of-week report". Mocked LLM for the weekly-cycle bits
that need it; the roster/report endpoints themselves make no LLM calls.

Run: python smoke_test_company_students.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_company_students.db"
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


def register_student(email):
    r = client.post(
        "/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Student " + email}
    )
    assert r.status_code == 201, r.text
    return login(email)


def login(email):
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- set up a company, job title, and company project ---
r = client.post(
    "/company/register",
    json={"email": "hr@buildco.com", "password": "hunter2pass", "full_name": "HR", "company_name": "BuildCo"},
)
company_headers = login("hr@buildco.com")
r = client.post("/company/job-titles", json={"title": "Data Analyst"}, headers=company_headers)
job_title_id = r.json()["id"]
r = client.post(
    f"/company/job-titles/{job_title_id}/projects",
    data={"title": "Sales Dashboard", "description": "Real BuildCo dashboard work."},
    headers=company_headers,
)
company_project_id = r.json()["id"]

# --- empty roster before anyone accepts ---
r = client.get("/company/students", headers=company_headers)
check("empty roster before any acceptance", r.json() == [])

# --- invite + accept: candidate A gets the company project, B gets the platform track ---
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-a@example.com", "company_project_id": company_project_id},
    headers=company_headers,
)
invite_a_id = r.json()["id"]
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-b@example.com"},
    headers=company_headers,
)
invite_b_id = r.json()["id"]

a_headers = register_student("candidate-a@example.com")
client.post(f"/invitations/{invite_a_id}/accept", json={"consent": True}, headers=a_headers)
b_headers = register_student("candidate-b@example.com")
client.post(f"/invitations/{invite_b_id}/accept", json={"consent": True}, headers=b_headers)

# --- a pending invitation never shows up on the roster ---
client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-pending@example.com"},
    headers=company_headers,
)

r = client.get("/company/students", headers=company_headers)
roster = r.json()
check("roster now has exactly the 2 accepted students", len(roster) == 2)
check("no student entry for the still-pending invitation", all(s["student_email"] != "candidate-pending@example.com" for s in roster))

student_a = next(s for s in roster if s["student_email"] == "candidate-a@example.com")
check("student A shows the company project title", student_a["company_project_title"] == "Sales Dashboard")
check("student A has a real project already (from the company project)", student_a["project_title"] == "Sales Dashboard")
check("student A's task counts start at zero", student_a["task_counts"] == {"todo": 0, "in_progress": 0, "submitted": 0, "reviewed": 0})

student_b = next(s for s in roster if s["student_email"] == "candidate-b@example.com")
check("student B has no company project", student_b["company_project_title"] is None)
check("student B has no project yet (hasn't called assign-task)", student_b["project_title"] is None)
check("student B's current week is None before any project exists", student_b["current_week_number"] is None)

# --- another company sees none of this ---
client.post("/company/register", json={"email": "x@othercorp.com", "password": "hunter2pass", "full_name": "X", "company_name": "OtherCorp"})
other_headers = login("x@othercorp.com")
r = client.get("/company/students", headers=other_headers)
check("a different company's roster is empty (isolated)", r.json() == [])
r = client.get(f"/company/students/{invite_a_id}", headers=other_headers)
check("a different company can't read this student's detail -> 404", r.status_code == 404)

# --- student A actually does some work; company's roster reflects it ---
fake_project_input = {"title": "unused", "description": "unused"}
fake_week_input = {
    "big_task_title": "Ship the dashboard",
    "big_task_description": "Real work for BuildCo.",
    "subtasks": [{"title": f"Subtask {i}", "description": f"Do {i}."} for i in range(1, 6)],
}
with patch(
    "app.agents.manager.call_with_tool",
    side_effect=[{"tool_name": "plan_week", "input": fake_week_input}],
):
    r = client.post("/agents/manager/assign-task", headers=a_headers)
check("student A's first task assigned (project already existed, so only plan_week ran)", r.status_code == 201)

r = client.get("/company/students", headers=company_headers)
student_a = next(s for s in r.json() if s["student_email"] == "candidate-a@example.com")
check("roster reflects the new task (1 todo)", student_a["task_counts"]["todo"] == 1)
check("roster shows the current week number", student_a["current_week_number"] == 1)

# --- detail view: week 1 present, with the task, no review yet ---
r = client.get(f"/company/students/{invite_a_id}", headers=company_headers)
check("student detail -> 200", r.status_code == 200)
detail = r.json()
check("detail has exactly 1 week so far", len(detail["weeks"]) == 1)
check("week 1 has the 1 task", len(detail["weeks"][0]["tasks"]) == 1)
check("no end-of-week reviews yet (week still active)", detail["weeks"][0]["reviews"] == [])
check("task detail includes submission fields (matches the consent notice)", "submission_text" in detail["weeks"][0]["tasks"][0])

# --- once a WEEK_PROGRESS/BEHAVIORAL review exists for the week, it
#     surfaces here too (the "end-of-week report") — the cascade that
#     actually produces these is covered by smoke_test_weekly_cycle.py
#     and smoke_test_orchestration.py; this only checks that this
#     endpoint's own query picks the review up correctly once it exists.
from app.database import SessionLocal  # noqa: E402
from app.models import AgentType, Review, ReviewKind, Week  # noqa: E402

db = SessionLocal()
week_row = db.query(Week).filter(Week.week_number == 1).first()
db.add(
    Review(
        user_id=week_row.user_id,
        week_id=week_row.id,
        agent_type=AgentType.MANAGER,
        kind=ReviewKind.WEEK_PROGRESS,
        content="Solid first week, on pace.",
        metrics_json={"tasks_completed": 1},
    )
)
db.commit()
db.close()

r = client.get(f"/company/students/{invite_a_id}", headers=company_headers)
week_reviews = r.json()["weeks"][0]["reviews"]
check("the end-of-week review now surfaces in the report", len(week_reviews) == 1)
check("review content matches what the Manager wrote", week_reviews[0]["content"] == "Solid first week, on pace.")
check("review kind is week_progress", week_reviews[0]["kind"] == "week_progress")

print("\nAll company-students smoke checks passed.")
