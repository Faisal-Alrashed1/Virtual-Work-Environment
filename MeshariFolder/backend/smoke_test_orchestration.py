"""
End-to-end smoke test for the weekly-cycle orchestration
(app/agents/weekly_cycle.py) — the actual "what happens next" state
machine, driven through the real API exactly like the frontend would, not
direct ORM writes (that's what smoke_test_weekly_cycle.py covers, at the
schema level). Mocked LLM calls, same style as smoke_test_agents.py.

Covers: bootstrapping a Project + Week 1 on the first assign-task call,
releasing subtasks one at a time, idempotency (asking again mid-subtask
doesn't create a duplicate or call the LLM again), and the full
end-of-week cascade (Manager's week_progress review -> HR's behavioral
review -> Week 1 closes -> Week 2 starts) after all 5 subtasks are
approved.

Run: python smoke_test_orchestration.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_orchestration.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.scheduling import is_workday  # noqa: E402

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


def fake_review_result(i):
    return {
        "tool_name": "submit_review",
        "input": {
            "verdict": "approved",
            "summary": f"Subtask {i} looks solid — clean and working.",
            "categories": [
                {"key": "correctness", "label": "Meets requirements", "score": 5},
                {"key": "code_quality", "label": "Code quality", "score": 4},
                {"key": "testing", "label": "Testing", "score": 3},
                {"key": "documentation", "label": "Documentation", "score": 3},
            ],
            "comments": [],
        },
    }


# --- setup ---
r = client.post(
    "/auth/register",
    json={"email": "orchestration-test@example.com", "password": "hunter2pass", "full_name": "Orchestration Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "orchestration-test@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- mocks active for the whole run: 4 manager LLM calls expected total
# (create_project, plan_week x2, submit_week_progress), 5 mentor calls (one
# per subtask), 1 hr call (the behavioral review — no skills rollup here),
# and 2 collaboration calls (Stage 2 — the Manager and HR each consult the
# Mentor once during the cascade; see mock_collab below) ---
manager_side_effects = [
    {
        "tool_name": "create_project",
        "input": {"title": "Venv Internal Dashboard", "description": "A small internal dashboard, built out incrementally."},
    },
    {
        "tool_name": "plan_week",
        "input": {
            "big_task_title": "Ship the login flow",
            "big_task_description": "Get a working, tested login flow into the dashboard.",
            "subtasks": subtasks("Login flow"),
        },
    },
    {
        "tool_name": "submit_week_progress",
        "input": {
            "summary": "Strong first week — all 5 subtasks approved, no blockers.",
            "subtasks_completed": 5,
            "subtasks_needed_changes": 0,
        },
    },
    {
        "tool_name": "plan_week",
        "input": {
            "big_task_title": "Add user profile settings",
            "big_task_description": "Let the graduate view and edit their profile.",
            "subtasks": subtasks("Profile settings"),
        },
    },
]
mock_manager = patch("app.agents.manager.call_with_tool", side_effect=manager_side_effects)
mock_manager_obj = mock_manager.start()

mock_mentor = patch(
    "app.agents.mentor.call_with_tool", side_effect=[fake_review_result(i) for i in range(1, 6)]
)
mock_mentor_obj = mock_mentor.start()

mock_hr = patch(
    "app.agents.hr.call_with_tool",
    side_effect=[
        {
            "tool_name": "submit_behavioral_review",
            "input": {"summary": "Engaged throughout the week, no late work.", "consistency_rating": "strong"},
        }
    ],
)
mock_hr_obj = mock_hr.start()

# Stage 2 (docs/STAGE2_WEEKLY_CYCLE_FLOW.md): the cascade now has the
# Manager and HR each consult the Mentor directly before writing their
# own review — 2 calls total, routed through a separate patch target
# (app/agents/graph/collaboration.py) so they don't interfere with
# mentor_side_effect's 5-item list above (that's still just the 5
# per-subtask reviews).
mock_collab = patch(
    "app.agents.graph.collaboration.call_with_tool",
    side_effect=[
        {"tool_name": "reply_to_colleague", "input": {"reply": "Strong week — clean commits, picked things up fast."}},
        {"tool_name": "reply_to_colleague", "input": {"reply": "No concerns — submitted every subtask well ahead of deadline."}},
    ],
)
mock_collab_obj = mock_collab.start()

try:
    # --- first call bootstraps Project + Week 1 + subtask 1 (2 manager LLM calls) ---
    r = client.post("/agents/manager/assign-task", headers=headers)
    check("bootstrap: status 201", r.status_code == 201)
    task = r.json()
    check("bootstrap: subtask 1 title matches the plan", task["title"] == subtasks("Login flow")[0]["title"])
    check("bootstrap: task carries a week_id", task["week_id"] is not None)
    check("bootstrap: task has a deadline", task["deadline"] is not None)
    check("bootstrap: 2 manager LLM calls so far", mock_manager_obj.call_count == 2)

    # --- idempotency: asking again with the subtask still open returns the
    # same task, no new LLM call ---
    r = client.post("/agents/manager/assign-task", headers=headers)
    check("idempotent: same task_id, no duplicate", r.json()["id"] == task["id"])
    check("idempotent: manager LLM not called again", mock_manager_obj.call_count == 2)

    r = client.get("/projects/me", headers=headers)
    check("project has exactly 1 week so far", r.status_code == 200 and len(r.json()["weeks"]) == 1)
    week1_id = r.json()["weeks"][0]["id"]

    # --- work through all 5 subtasks: submit -> mentor approves -> next one releases ---
    deadlines = []
    current = task
    for i in range(1, 6):
        check(f"subtask {i} is in week 1", current["week_id"] == week1_id)
        deadlines.append(current["deadline"])
        r = client.patch(
            f"/tasks/{current['id']}/status",
            json={"status": "submitted", "github_link": "https://github.com/psf/requests"},
            headers=headers,
        )
        check(f"subtask {i}: submitted", r.status_code == 200)

        r = client.post(f"/agents/mentor/review/{current['id']}", headers=headers)
        check(f"subtask {i}: mentor approved", r.status_code == 201 and r.json()["metrics_json"]["verdict"] == "approved")
        check(f"subtask {i}: review carries week_id", r.json()["week_id"] == week1_id)

        r = client.post("/agents/manager/assign-task", headers=headers)
        check(f"assign-task after subtask {i}: 201", r.status_code == 201)
        current = r.json()

    check("all 5 deadlines are distinct and increasing", deadlines == sorted(set(deadlines)) and len(set(deadlines)) == 5)
    check(
        "all 5 deadlines fall on Saudi workdays (Sun-Thu)",
        all(is_workday(__import__("datetime").datetime.fromisoformat(d)) for d in deadlines),
    )

    # --- that last assign-task call should have run the full cascade and
    # landed on week 2's first subtask ---
    check("after cascade: now on week 2's first subtask", current["title"] == subtasks("Profile settings")[0]["title"])
    check("all 4 manager LLM calls used (project, plan_week x2, week_progress)", mock_manager_obj.call_count == 4)
    check("hr behavioral review was called once", mock_hr_obj.call_count == 1)
    check("mentor consulted twice during the cascade (manager + hr)", mock_collab_obj.call_count == 2)

    r = client.get("/projects/me", headers=headers)
    weeks = r.json()["weeks"]
    check("project now has 2 weeks", len(weeks) == 2)
    check("week 1's subtasks_plan_json has 5 full entries", len(weeks[0]["subtasks_plan_json"]) == 5)
    check(
        "each subtask plan entry has title/description/deadline",
        all(
            set(s.keys()) == {"title", "description", "deadline"}
            for s in weeks[0]["subtasks_plan_json"]
        ),
    )
    check(
        "week 1's plan titles match what the mocked Manager planned",
        [s["title"] for s in weeks[0]["subtasks_plan_json"]] == [s["title"] for s in subtasks("Login flow")],
    )
    check("week 1 is completed", weeks[0]["status"] == "completed" and weeks[0]["ended_at"] is not None)
    check("week 2 is active", weeks[1]["status"] == "active" and weeks[1]["next_subtask_index"] == 1)

    r = client.get("/users/me/reviews", headers=headers)
    reviews = r.json()
    kinds = [rv["kind"] for rv in reviews]
    check("7 reviews total (5 task_review + 1 week_progress + 1 behavioral)", len(reviews) == 7)
    check("kinds match the confirmed cascade order", kinds.count("task_review") == 5 and kinds.count("week_progress") == 1 and kinds.count("behavioral") == 1)

    behavioral = next(rv for rv in reviews if rv["kind"] == "behavioral")
    m = behavioral["metrics_json"]
    check(
        "behavioral metrics: attended + absent = 5, no late tasks (all deadlines are in the future)",
        m["attended_days"] + m["absent_days"] == 5 and m["late_task_count"] == 0 and m["total_subtasks"] == 5,
    )

    # --- dashboard aggregation (GET /users/me/dashboard) ---
    r = client.get("/users/me/dashboard", headers=headers)
    check("dashboard: 200", r.status_code == 200)
    d = r.json()
    # Week 1's 5 subtasks were all submitted+approved; week 2's first is
    # released but not reviewed, so 5 completed of 6 total.
    check("dashboard: 5 tasks completed", d["tasks_completed"] == 5)
    check("dashboard: 6 tasks total (5 done + week 2's first)", d["tasks_total"] == 6)
    check("dashboard: average_score is the mocked 3.75", abs(d["average_score"] - 3.75) < 0.01)
    check("dashboard: 5 task reviews counted", d["reviews_count"] == 5)
    check("dashboard: on_time_rate is 1.0 (nothing late)", d["on_time_rate"] == 1.0)
    check("dashboard: 1 week completed of 2", d["weeks_completed"] == 1 and d["weeks_total"] == 2)
    check("dashboard: has_active_project true", d["has_active_project"] is True)

    print("\nAll orchestration checks passed.")
finally:
    mock_manager.stop()
    mock_mentor.stop()
    mock_hr.stop()
    mock_collab.stop()
