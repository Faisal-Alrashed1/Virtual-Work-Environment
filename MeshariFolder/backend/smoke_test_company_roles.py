"""
Smoke test for company role permissions (docs/STAGE3_COMPANY_RAG.md):
sending an invitation is limited to ADMIN/HR, creating a real company
project is limited to ADMIN/TECH_LEAD — everything else in the company
router stays open to any role. No LLM calls in this test.

Run: python smoke_test_company_roles.py
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_company_roles.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-no-llm-calls-in-this-test")

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


# --- found a company (ADMIN) and bring on one of each other role ---
r = client.post(
    "/company/register",
    json={"email": "admin@rolecorp.com", "password": "hunter2pass", "full_name": "Admin", "company_name": "RoleCorp"},
)
join_code = r.json()["organization"]["join_code"]
admin_headers = login("admin@rolecorp.com")

client.post(
    "/company/register",
    json={"email": "hr@rolecorp.com", "password": "hunter2pass", "full_name": "HR", "join_code": join_code, "role": "hr"},
)
hr_headers = login("hr@rolecorp.com")

client.post(
    "/company/register",
    json={"email": "tech@rolecorp.com", "password": "hunter2pass", "full_name": "Tech", "join_code": join_code, "role": "tech_lead"},
)
tech_headers = login("tech@rolecorp.com")

r = client.post("/company/job-titles", json={"title": "Backend Developer"}, headers=admin_headers)
job_title_id = r.json()["id"]

# --- job titles and material uploads stay open to any role (unrestricted) ---
r = client.post("/company/job-titles", json={"title": "Made by HR"}, headers=hr_headers)
check("any role can create a job title (unrestricted)", r.status_code == 201)
r = client.post("/company/job-titles", json={"title": "Made by tech lead"}, headers=tech_headers)
check("any role can create a job title (unrestricted), tech lead too", r.status_code == 201)

# --- creating a real company project: ADMIN/TECH_LEAD only ---
def create_project(headers):
    return client.post(
        f"/company/job-titles/{job_title_id}/projects",
        data={"title": "Real Project", "description": "Real work."},
        headers=headers,
    )

r = create_project(admin_headers)
check("admin can create a company project -> 201", r.status_code == 201)
r = create_project(tech_headers)
check("tech_lead can create a company project -> 201", r.status_code == 201)
r = create_project(hr_headers)
check("hr is refused creating a company project -> 403", r.status_code == 403)
check("refusal names the allowed roles", "admin" in r.json()["detail"] and "tech_lead" in r.json()["detail"])

# --- sending an invitation: ADMIN/HR only ---
def send_invite(headers, email):
    return client.post(
        f"/company/job-titles/{job_title_id}/invitations",
        json={"invited_email": email},
        headers=headers,
    )

r = send_invite(admin_headers, "candidate-1@example.com")
check("admin can send an invitation -> 201", r.status_code == 201)
r = send_invite(hr_headers, "candidate-2@example.com")
check("hr can send an invitation -> 201", r.status_code == 201)
r = send_invite(tech_headers, "candidate-3@example.com")
check("tech_lead is refused sending an invitation -> 403", r.status_code == 403)
check("refusal names the allowed roles", "admin" in r.json()["detail"] and "hr" in r.json()["detail"])

# --- everything else (materials, RAG query, roster, listing) stays open to any role ---
r = client.get("/company/job-titles", headers=tech_headers)
check("tech_lead can list job titles (unrestricted)", r.status_code == 200)
r = client.get("/company/students", headers=hr_headers)
check("hr can view the roster (unrestricted)", r.status_code == 200)
r = client.get("/company/invitations", headers=tech_headers)
check("tech_lead can view sent invitations (unrestricted)", r.status_code == 200)

print("\nAll company-role-permission smoke checks passed.")
