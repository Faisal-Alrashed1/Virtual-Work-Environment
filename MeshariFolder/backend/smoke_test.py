"""
Quick end-to-end sanity check against an in-memory-style sqlite db.
Run: python smoke_test.py
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test.db"
)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()  # triggers startup event (create_all) — matches real server behavior


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# health check
r = client.get("/health")
check("health check", r.status_code == 200)

# register
r = client.post(
    "/auth/register",
    json={"email": "grad@example.com", "password": "hunter2pass", "full_name": "New Grad"},
)
check("register", r.status_code == 201)
user = r.json()
check("track defaults to junior_dev", user["track"] == "junior_dev")

# duplicate register should fail
r = client.post(
    "/auth/register",
    json={"email": "grad@example.com", "password": "hunter2pass", "full_name": "New Grad"},
)
check("duplicate email rejected", r.status_code == 400)

# login
r = client.post(
    "/auth/login",
    data={"username": "grad@example.com", "password": "hunter2pass"},
)
check("login", r.status_code == 200)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# wrong password
r = client.post("/auth/login", data={"username": "grad@example.com", "password": "wrong"})
check("wrong password rejected", r.status_code == 401)

# get me
r = client.get("/users/me", headers=headers)
check("get current user", r.status_code == 200 and r.json()["email"] == "grad@example.com")
check("has_cv starts false", r.json()["has_cv"] is False)

# no token -> 401
r = client.get("/users/me")
check("unauthenticated request rejected", r.status_code == 401)

# submit CV
r = client.post("/users/me/cv", json={"cv_raw_text": "Experienced in Python and React."}, headers=headers)
check("submit cv", r.status_code == 200)
check("submit cv response has_cv is true", r.json()["has_cv"] is True)

r = client.get("/users/me", headers=headers)
check("has_cv persists on refetch", r.json()["has_cv"] is True)

# create task (simulating what the Manager agent will do later)
r = client.post(
    "/tasks",
    json={"title": "Build a login form", "description": "Implement email/password login.", "user_id": user["id"]},
    headers=headers,
)
check("create task", r.status_code == 201)
task = r.json()
check("task starts as todo", task["status"] == "todo")

# list tasks
r = client.get("/tasks", headers=headers)
check("list tasks", r.status_code == 200 and len(r.json()) == 1)

# post a user message on the task thread
r = client.post(f"/tasks/{task['id']}/messages", json={"content": "Question about scope?"}, headers=headers)
check("post user message", r.status_code == 201 and r.json()["sender_type"] == "user")

# post an agent message on the task thread
r = client.post(
    f"/tasks/{task['id']}/messages",
    json={"content": "Use email + password, no OAuth needed for MVP.", "agent_type": "manager"},
    headers=headers,
)
check("post agent message", r.status_code == 201 and r.json()["sender_type"] == "agent")

# move task to submitted with a github link
r = client.patch(
    f"/tasks/{task['id']}/status",
    json={"status": "submitted", "github_link": "https://github.com/grad/login-form"},
    headers=headers,
)
check("update task status", r.status_code == 200 and r.json()["status"] == "submitted")

# task detail includes thread
r = client.get(f"/tasks/{task['id']}", headers=headers)
check("task detail includes thread", r.status_code == 200 and len(r.json()["messages"]) == 2)

# another user can't see this task
client.post("/auth/register", json={"email": "other@example.com", "password": "hunter2pass", "full_name": "Other"})
r2 = client.post("/auth/login", data={"username": "other@example.com", "password": "hunter2pass"})
other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
r = client.get(f"/tasks/{task['id']}", headers=other_headers)
check("task isolated between users", r.status_code == 404)

print("\nAll checks passed.")
