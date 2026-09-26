"""
Smoke test for a student's own transparency view (docs/
STAGE3_COMPANY_RAG.md): GET /invitations/{id}/visibility shows a student
exactly what the company that invited them can currently see — and this
test proves that literally, by comparing the student's response against
the company's own GET /company/students/{id} response field for field,
not just checking each looks plausible on its own.

Run: python smoke_test_student_visibility.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_student_visibility.db"
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


def login(email):
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register_student(email):
    r = client.post(
        "/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Student " + email}
    )
    assert r.status_code == 201, r.text
    return login(email)


# --- set up a company, job title, and company project ---
client.post(
    "/company/register",
    json={
        "email": "admin@visibleco.com",
        "password": "hunter2pass",
        "full_name": "Admin",
        "company_name": "VisibleCo",
    },
)
admin_headers = login("admin@visibleco.com")
r = client.post("/company/job-titles", json={"title": "Data Analyst"}, headers=admin_headers)
job_title_id = r.json()["id"]
r = client.post(
    f"/company/job-titles/{job_title_id}/projects",
    data={"title": "Sales Dashboard", "description": "Real work."},
    headers=admin_headers,
)
company_project_id = r.json()["id"]

r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate@example.com", "company_project_id": company_project_id},
    headers=admin_headers,
)
invite_id = r.json()["id"]

# --- before accepting: visibility 404s (nothing has been shared yet) ---
student_headers = register_student("candidate@example.com")
r = client.get(f"/invitations/{invite_id}/visibility", headers=student_headers)
check("visibility before accepting -> 404 (nothing shared yet)", r.status_code == 404)

# --- accept, then visibility works ---
client.post(f"/invitations/{invite_id}/accept", json={"consent": True}, headers=student_headers)
r = client.get(f"/invitations/{invite_id}/visibility", headers=student_headers)
check("visibility after accepting -> 200", r.status_code == 200)
student_view = r.json()
check("shows the right project", student_view["project_title"] == "Sales Dashboard")
check("shows the right job title", student_view["job_title"] == "Data Analyst")

# --- a student can't see another student's visibility via a wrong invitation id ---
other_student_headers = register_student("someone-else@example.com")
r = client.get(f"/invitations/{invite_id}/visibility", headers=other_student_headers)
check("a different student can't read this invitation's visibility -> 404", r.status_code == 404)

# --- do some real work: assign a task, submit it, get reviewed ---
fake_week_input = {
    "big_task_title": "Ship the dashboard",
    "big_task_description": "Real work for VisibleCo.",
    "subtasks": [{"title": f"Subtask {i}", "description": f"Do {i}."} for i in range(1, 6)],
}
with patch("app.agents.manager.call_with_tool", side_effect=[{"tool_name": "plan_week", "input": fake_week_input}]):
    r = client.post("/agents/manager/assign-task", headers=student_headers)
task_id = r.json()["id"]

with patch(
    "app.agents.mentor.call_with_tool",
    return_value={
        "tool_name": "submit_review",
        "input": {
            "verdict": "meets_requirements",
            "categories": {"correctness": 4, "code_quality": 4, "completeness": 4},
            "comments": "Solid work.",
            "summary": "Nice job on subtask 1.",
        },
    },
):
    client.post(
        f"/tasks/{task_id}/submit",
        data={"github_link": "https://github.com/example/repo"},
        headers=student_headers,
    )
    client.post(f"/agents/mentor/review/{task_id}", headers=student_headers)

# --- the student's visibility view now reflects the real task + review,
#     and matches the company's own view of the same student EXACTLY ---
r_student = client.get(f"/invitations/{invite_id}/visibility", headers=student_headers)
r_company = client.get(f"/company/students/{invite_id}", headers=admin_headers)

check("student visibility -> 200", r_student.status_code == 200)
check("company detail -> 200", r_company.status_code == 200)
check(
    "student's own view is byte-for-byte identical to what the company sees",
    r_student.json() == r_company.json(),
)
check("both show the real task title", r_student.json()["weeks"][0]["tasks"][0]["title"] == "Subtask 1")
check(
    "both show real submission content (github_link)",
    r_student.json()["weeks"][0]["tasks"][0]["github_link"] == "https://github.com/example/repo",
)

# --- a declined invitation never grants visibility either ---
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "decliner@example.com"},
    headers=admin_headers,
)
decline_invite_id = r.json()["id"]
decline_headers = register_student("decliner@example.com")
client.post(f"/invitations/{decline_invite_id}/decline", headers=decline_headers)
r = client.get(f"/invitations/{decline_invite_id}/visibility", headers=decline_headers)
check("visibility on a declined invitation -> 404", r.status_code == 404)

print("\nAll student-visibility smoke checks passed.")
