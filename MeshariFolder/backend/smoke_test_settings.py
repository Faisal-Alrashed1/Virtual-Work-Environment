"""
Smoke test for the settings page's backend: PATCH /users/me (rename,
change password, or both). No API key needed — nothing here calls an LLM.

Run: python smoke_test_settings.py
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_settings.db"
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


r = client.post(
    "/auth/register",
    json={"email": "settings@example.com", "password": "hunter2pass", "full_name": "Original Name"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "settings@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- rename only ---
r = client.patch("/users/me", json={"full_name": "New Name"}, headers=headers)
check("rename -> 200", r.status_code == 200)
check("full_name updated", r.json()["full_name"] == "New Name")

# --- empty name rejected, doesn't touch the existing name ---
r = client.patch("/users/me", json={"full_name": "   "}, headers=headers)
check("blank name rejected -> 400", r.status_code == 400)
r = client.get("/users/me", headers=headers)
check("name unchanged after rejected blank update", r.json()["full_name"] == "New Name")

# --- password change without current_password is refused ---
r = client.patch("/users/me", json={"new_password": "newpassword123"}, headers=headers)
check("password change without current_password -> 400", r.status_code == 400)

# --- password change with wrong current_password is refused ---
r = client.patch(
    "/users/me",
    json={"current_password": "wrongpass", "new_password": "newpassword123"},
    headers=headers,
)
check("password change with wrong current password -> 400", r.status_code == 400)

# --- old password still works (rejected change didn't touch it) ---
r = client.post("/auth/login", data={"username": "settings@example.com", "password": "hunter2pass"})
check("old password still works after rejected attempts", r.status_code == 200)

# --- too-short new password rejected ---
r = client.patch(
    "/users/me",
    json={"current_password": "hunter2pass", "new_password": "short"},
    headers=headers,
)
check("too-short new password rejected -> 400", r.status_code == 400)

# --- correct current_password + valid new_password succeeds ---
r = client.patch(
    "/users/me",
    json={"current_password": "hunter2pass", "new_password": "newpassword123"},
    headers=headers,
)
check("password change -> 200", r.status_code == 200)

# --- new password now works, old one doesn't ---
r = client.post("/auth/login", data={"username": "settings@example.com", "password": "newpassword123"})
check("new password logs in", r.status_code == 200)
r = client.post("/auth/login", data={"username": "settings@example.com", "password": "hunter2pass"})
check("old password no longer works", r.status_code == 401)

# --- rename + password change together in one call ---
r = client.patch(
    "/users/me",
    json={"full_name": "Final Name", "current_password": "newpassword123", "new_password": "anotherpass123"},
    headers=headers,
)
check("combined rename + password change -> 200", r.status_code == 200)
check("name updated in combined call", r.json()["full_name"] == "Final Name")
r = client.post("/auth/login", data={"username": "settings@example.com", "password": "anotherpass123"})
check("combined call's new password works", r.status_code == 200)

print("\nAll settings smoke checks passed.")
