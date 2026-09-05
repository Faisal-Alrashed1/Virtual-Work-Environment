import os
os.environ["DATABASE_URL"] = "sqlite:///./test_venv.db"

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import Base, engine


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def register(role="learner", email="learner@example.com"):
    response = client.post("/api/auth/register", json={"name": "Test User", "email": email, "password": "strong-pass-123", "role": role})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_and_auth():
    assert client.get("/health").json() == {"status": "ok"}
    headers = register()
    assert client.get("/api/me", headers=headers).json()["role"] == "learner"


def test_recruiter_knowledge_is_attested_and_tenant_owned():
    headers = register("recruiter", "recruiter@example.com")
    org = client.post("/api/organizations", headers=headers, json={"name": "Example Co"})
    assert org.status_code == 200
    rejected = client.post(f"/api/organizations/{org.json()['id']}/knowledge", headers=headers, json={"name": "Production", "content": "x" * 60, "attested_synthetic": False})
    assert rejected.status_code == 422
    accepted = client.post(f"/api/organizations/{org.json()['id']}/knowledge", headers=headers, json={"name": "Synthetic handbook", "content": "سياسة تجريبية " * 10, "attested_synthetic": True})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "indexed"


def test_company_task_requires_approval_and_blocks_early_intervention():
    recruiter = register("recruiter", "owner@example.com")
    candidate = client.post("/api/auth/register", json={"name": "Candidate", "email": "candidate@example.com", "password": "strong-pass-123", "role": "candidate"}).json()["user"]
    org = client.post("/api/organizations", headers=recruiter, json={"name": "Hiring Co"}).json()
    campaign = client.post("/api/campaigns", headers=recruiter, json={"organization_id": org["id"], "title": "Backend Hiring", "job_role": "Backend Engineer"}).json()
    task = client.post(f"/api/campaigns/{campaign['id']}/tasks", headers=recruiter, json={"candidate_user_id": candidate["id"], "title": "Secure API", "brief": "Build a secure API", "acceptance_criteria": ["Tests", "Validation"], "difficulty": 2})
    assert task.status_code == 200
    assert task.json()["status"] == "PENDING_APPROVAL"
    blocked = client.post(f"/api/company/tasks/{task.json()['id']}/interventions", headers=recruiter, json={"body": "Explain your choice"})
    assert blocked.status_code == 409
    approved = client.post(f"/api/campaigns/{campaign['id']}/tasks/{task.json()['id']}/approve", headers=recruiter)
    assert approved.json()["status"] == "TO_DO"


def teardown_module():
    Base.metadata.drop_all(engine)
    if os.path.exists("test_venv.db"): os.remove("test_venv.db")
