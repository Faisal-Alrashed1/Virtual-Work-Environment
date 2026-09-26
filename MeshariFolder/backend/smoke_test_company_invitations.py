"""
Smoke test for Stage 3's company projects + invitation/consent flow
(docs/STAGE3_COMPANY_RAG.md): a company's own real project (distinct from
a graduate's own project), inviting a specific email with or without one,
and a student's explicit-consent accept/decline. No LLM calls at all.

Run: python smoke_test_company_invitations.py
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_company_invitations.db"
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


def register_student(email):
    r = client.post(
        "/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Student " + email}
    )
    assert r.status_code == 201, r.text
    return login(email)


def login(email):
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- set up a company with a job title ---
r = client.post(
    "/company/register",
    json={
        "email": "hr@finco.com",
        "password": "hunter2pass",
        "full_name": "HR Rep",
        "company_name": "FinCo",
        "field": "Finance",
    },
)
check("company registered", r.status_code == 201)
org_id = r.json()["organization"]["id"]
company_headers = login("hr@finco.com")

r = client.post(
    "/company/job-titles",
    json={"title": "Data Analyst", "description": "Reporting and dashboards."},
    headers=company_headers,
)
job_title_id = r.json()["id"]

# --- a company's OWN project — distinct from a student's own-project feature ---
r = client.post(
    f"/company/job-titles/{job_title_id}/projects",
    data={
        "title": "Q3 Revenue Dashboard",
        "description": "Build a real internal dashboard FinCo actually uses.",
        "materials_text": "Pull from the sales_2026 table, group by region.",
    },
    headers=company_headers,
)
check("create company project -> 201", r.status_code == 201)
check("company project has the right title", r.json()["title"] == "Q3 Revenue Dashboard")
check("company project reports materials present", r.json()["has_materials"] is True)
company_project_id = r.json()["id"]

r = client.get(f"/company/job-titles/{job_title_id}/projects", headers=company_headers)
check("list company projects includes it", any(p["id"] == company_project_id for p in r.json()))

# --- other company can't see it ---
client.post(
    "/company/register",
    json={"email": "admin@othercorp.com", "password": "hunter2pass", "full_name": "Other", "company_name": "OtherCorp"},
)
other_headers = login("admin@othercorp.com")
r = client.get(f"/company/job-titles/{job_title_id}/projects/{company_project_id}", headers=other_headers)
check("other company can't read this company's project -> 404", r.status_code == 404)

# --- invite a student WITHOUT a company project (ordinary platform track) ---
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-a@example.com"},
    headers=company_headers,
)
check("invitation without a project -> 201", r.status_code == 201)
check("invitation status starts pending", r.json()["status"] == "pending")
check("invitation has no company project attached", r.json()["company_project_id"] is None)
invite_a_id = r.json()["id"]

# --- invite a second student WITH the real company project ---
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-b@example.com", "company_project_id": company_project_id},
    headers=company_headers,
)
check("invitation with a project -> 201", r.status_code == 201)
check("invitation carries the project title", r.json()["company_project_title"] == "Q3 Revenue Dashboard")
invite_b_id = r.json()["id"]

# --- a project belonging to a different job title is refused ---
r = client.post(
    "/company/job-titles",
    json={"title": "Backend Developer"},
    headers=company_headers,
)
other_job_title_id = r.json()["id"]
r = client.post(
    f"/company/job-titles/{other_job_title_id}/invitations",
    json={"invited_email": "candidate-c@example.com", "company_project_id": company_project_id},
    headers=company_headers,
)
check("project from a different job title is refused -> 400", r.status_code == 400)

# --- company sees both invitations it sent ---
r = client.get("/company/invitations", headers=company_headers)
check("company invitations list has both", len(r.json()) == 2)

# --- BEFORE registering, a matching student can't see it (no account yet) ---
# (nothing to check here directly — /invitations/mine requires auth)

# --- candidate-a registers and sees their pending invitation ---
a_headers = register_student("candidate-a@example.com")
r = client.get("/invitations/mine", headers=a_headers)
check("candidate A sees exactly 1 invitation", len(r.json()) == 1)
check("invitation shows the org name", r.json()[0]["organization_name"] == "FinCo")
check("invitation shows the job title", r.json()[0]["job_title"] == "Data Analyst")
check("data-sharing notice is present and names the company", "FinCo" in r.json()[0]["data_shared_notice"])
check("notice says what will NOT be shared too", "not see your CV" in r.json()[0]["data_shared_notice"])

# --- a different student's inbox is empty (isolated by email) ---
c_headers = register_student("someone-else@example.com")
r = client.get("/invitations/mine", headers=c_headers)
check("unrelated student sees no invitations", r.json() == [])

# --- accepting WITHOUT consent is refused ---
r = client.post(f"/invitations/{invite_a_id}/accept", json={"consent": False}, headers=a_headers)
check("accept without consent -> 400", r.status_code == 400)
r = client.post(f"/invitations/{invite_a_id}/accept", json={}, headers=a_headers)
check("accept with consent omitted -> 400 (defaults false)", r.status_code == 400)

# --- accepting WITH consent works (no company project this time) ---
r = client.post(f"/invitations/{invite_a_id}/accept", json={"consent": True}, headers=a_headers)
check("accept with consent -> 200", r.status_code == 200)
check("status flips to accepted", r.json()["status"] == "accepted")

r = client.get("/users/me", headers=a_headers)
check("student is now affiliated with the company", r.json()["organization_id"] == org_id)
check("student account_type is still student, not company", r.json()["account_type"] == "student")

r = client.get("/projects/me", headers=a_headers)
check("no company project was named, so no project was auto-created", r.status_code == 404)

# --- can't respond to the same invitation twice ---
r = client.post(f"/invitations/{invite_a_id}/accept", json={"consent": True}, headers=a_headers)
check("accepting an already-responded invitation -> 400", r.status_code == 400)

# --- candidate B accepts an invitation WITH a real company project ---
b_headers = register_student("candidate-b@example.com")
r = client.post(f"/invitations/{invite_b_id}/accept", json={"consent": True}, headers=b_headers)
check("candidate B accepts -> 200", r.status_code == 200)

r = client.get("/projects/me", headers=b_headers)
check("company project was copied into a real Project -> 200", r.status_code == 200)
check("project title matches the company project", r.json()["title"] == "Q3 Revenue Dashboard")
check("project has materials (copied from the company project)", r.json()["has_materials"] is True)

# --- declining works, and can't be responded to twice either ---
d_headers = register_student("candidate-d@example.com")
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "candidate-d@example.com"},
    headers=company_headers,
)
invite_d_id = r.json()["id"]
r = client.post(f"/invitations/{invite_d_id}/decline", headers=d_headers)
check("decline -> 200", r.status_code == 200)
check("status flips to declined", r.json()["status"] == "declined")
r = client.get("/users/me", headers=d_headers)
check("declining does NOT affiliate the student with the company", r.json()["organization_id"] is None)
r = client.post(f"/invitations/{invite_d_id}/decline", headers=d_headers)
check("declining twice -> 400", r.status_code == 400)

# --- a company account itself can't accept an invitation ---
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "hr@finco.com"},
    headers=company_headers,
)
self_invite_id = r.json()["id"]
r = client.post(f"/invitations/{self_invite_id}/accept", json={"consent": True}, headers=company_headers)
check("a company account can't accept an invitation -> 403", r.status_code == 403)

print("\nAll company-projects/invitations smoke checks passed.")
