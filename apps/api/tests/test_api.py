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


def test_agents_use_new_company_roles():
    headers = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'learner@example.com', 'password': 'strong-pass-123'}).json()['access_token']}"}
    assert client.get("/api/agents/senior/messages", headers=headers).status_code == 200
    assert client.get("/api/agents/mentor/messages", headers=headers).status_code == 404


def test_learner_must_join_kickoff_before_first_senior_task(monkeypatch):
    from app.services.ai import ai
    monkeypatch.setattr(ai, "providers", [])
    headers = register(email="flow@example.com")
    created = client.post("/api/intake/manual-cv", headers=headers, json={"education": "Computer Science", "skills": ["HTML"], "target_role": "Web Developer"})
    assert created.status_code == 200
    for _ in range(10):
        assert client.post("/api/intake/chat", headers=headers, json={"body": "لا أعرف بعد"}).status_code == 200
    assert client.post("/api/intake/goal", headers=headers, json={"goal": "أريد تعلم تطوير الويب والعمل على مشروع كامل"}).status_code == 200
    confirmed = client.post("/api/intake/confirm", headers=headers, json={"corrections": ""})
    assert confirmed.json()["next"] == "project_kickoff"
    assert client.get("/api/workspace", headers=headers).json()["tasks"] == []
    assert client.post("/api/project/start", headers=headers).status_code == 409
    assert client.post("/api/project/join", headers=headers).json()["status"] == "kickoff"
    started = client.post("/api/project/start", headers=headers)
    assert started.status_code == 200
    workspace = client.get("/api/workspace", headers=headers).json()
    assert workspace["project_status"] == "active"
    assert len(workspace["tasks"]) == 1
    for expected_completed in range(1, 6):
        workspace = client.get("/api/workspace", headers=headers).json()
        task = next(item for item in workspace["tasks"] if item["status"] != "REVIEWED")
        assert client.patch(f"/api/tasks/{task['id']}/status", headers=headers, json={"status": "IN_PROGRESS"}).status_code == 200
        submitted = client.post(f"/api/tasks/{task['id']}/submit", headers=headers, json={"code": "def hello(name):\n    return f'Hello {name}'", "language": "python", "summary": "Implemented the requested small function"})
        assert submitted.status_code == 200
        assert submitted.json()["outcome"] == "improve"
        discussed = client.post("/api/agents/senior/messages", headers=headers, json={"body": "راجعت التحليل وسأتحقق من المعايير", "task_id": task["id"]})
        assert discussed.status_code == 200
        completed = client.post(f"/api/tasks/{task['id']}/complete-discussion", headers=headers)
        assert completed.status_code == 200
        if expected_completed < 5:
            assert completed.json()["next_task_id"]
        else:
            assert completed.json()["weekly_report"]["completed_tasks"] == 5
    finished = client.get("/api/workspace", headers=headers).json()
    assert finished["project_status"] == "week_complete"
    assert 0 <= finished["performance_score"] <= 100


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
