"""
Smoke test for the Stage 2 own-project path (POST /projects/own) —
proves a graduate who brings their own project skips the Manager's
create_project call entirely and plan_week plans straight into it, using
the real HTTP API + mocked LLM (no API key needed). See
docs/STAGE2_OWN_PROJECT.md.

Run: python smoke_test_stage2_own_project.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_own_project.db"
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


def subtasks(prefix):
    return [
        {"title": f"{prefix} — part {i}", "description": f"Step {i} of {prefix}."}
        for i in range(1, 6)
    ]


r = client.post(
    "/auth/register",
    json={"email": "own-project-test@example.com", "password": "hunter2pass", "full_name": "Own Project Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "own-project-test@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- create the own project, before any assign-task call ---
r = client.post(
    "/projects/own",
    headers=headers,
    data={
        "title": "Personal expense tracker",
        "description": "A Next.js + Supabase app for tracking personal spending by category.",
    },
)
check("create own project -> 201", r.status_code == 201)
check("source is 'own'", r.json()["source"] == "own")
own_project_id = r.json()["id"]

r = client.post("/projects/own", headers=headers, data={"title": "Second one", "description": "d"})
check("second own project rejected while one is active", r.status_code == 400)

r = client.get("/projects/me", headers=headers)
check("GET /projects/me returns the own project, no weeks yet", r.status_code == 200 and r.json()["weeks"] == [])
check("GET /projects/me title matches what was submitted", r.json()["title"] == "Personal expense tracker")
check("no materials were given, so has_materials is false", r.json()["has_materials"] is False)

# --- mocked LLM: only plan_week + release should ever be called; NOT
# create_project, since a Project already exists ---
manager_side_effects = [
    {
        "tool_name": "plan_week",
        "input": {
            "big_task_title": "Set up the expense tracker skeleton",
            "big_task_description": "Scaffold the Next.js app and Supabase schema.",
            "subtasks": subtasks("Tracker setup"),
        },
    },
]
with patch("app.agents.manager.call_with_tool", side_effect=manager_side_effects) as mock_manager:
    r = client.post("/agents/manager/assign-task", headers=headers)
    check("assign-task -> 201", r.status_code == 201)
    task = r.json()
    check("only 1 manager LLM call (plan_week — create_project skipped)", mock_manager.call_count == 1)
    check("first subtask matches the plan for the graduate's own project", task["title"] == subtasks("Tracker setup")[0]["title"])

r = client.get("/projects/me", headers=headers)
check("still the same project id (no duplicate created)", r.json()["id"] == own_project_id)
check("now has 1 week, planned around the own project", len(r.json()["weeks"]) == 1)
check(
    "week's big task reflects the mocked plan, not a generic one",
    r.json()["weeks"][0]["big_task_title"] == "Set up the expense tracker skeleton",
)

print("\nAll Stage 2 own-project smoke checks passed.")
