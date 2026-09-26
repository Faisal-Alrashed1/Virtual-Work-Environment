"""
Smoke test for the visible "needs changes" state (docs/NEEDS_CHANGES_VISIBLE.md).

When the Mentor bounces a task back, it returns to `in_progress` — the same
status as "started, nothing submitted yet" — so the board and workspace had no
way to say "you were asked to fix something". Task.needs_changes /
revision_count are derived from the reviews (no column, nothing to drift) and
exposed on the task API. This suite proves the derivation across a task's whole
life, that other tasks are unaffected, and that listing many tasks doesn't
run one extra query per task.

Run: python smoke_test_needs_changes.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_needs_changes.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Task  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


r = client.post("/auth/register", json={"email": "needs-changes@example.com", "password": "hunter2pass", "full_name": "NC Tester"})
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "needs-changes@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
user_id = client.get("/users/me", headers=headers).json()["id"]

db = SessionLocal()
ids = []
for title in ("Task under review", "Started, never submitted", "Not started"):
    t = Task(title=title, description="d", user_id=user_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    ids.append(t.id)
db.close()
main_id, started_id, todo_id = ids

CATEGORIES = [{"key": "correctness", "label": "Meets requirements", "score": 3}]


def mentor(task_id, verdict, summary):
    fake = {"verdict": verdict, "summary": summary, "categories": CATEGORIES, "comments": []}
    with patch("app.agents.mentor.call_with_tool", return_value={"tool_name": "submit_review", "input": fake}):
        return client.post(f"/agents/mentor/review/{task_id}", headers=headers)


def submit(task_id):
    return client.patch(f"/tasks/{task_id}/status", json={"status": "submitted", "github_link": "https://github.com/psf/requests"}, headers=headers)


def get(task_id):
    return client.get(f"/tasks/{task_id}", headers=headers).json()


# ---- a fresh task ---------------------------------------------------------------
t = get(main_id)
check("fresh task: needs_changes is false", t["needs_changes"] is False)
check("fresh task: revision_count is 0", t["revision_count"] == 0)

# ---- started, no review yet: in_progress but NOT 'needs changes' -----------------
client.patch(f"/tasks/{started_id}/status", json={"status": "in_progress"}, headers=headers)
client.patch(f"/tasks/{main_id}/status", json={"status": "in_progress"}, headers=headers)
t = get(started_id)
check("started task is in_progress", t["status"] == "in_progress")
check("...but it is NOT flagged needs_changes (no review has bounced it)", t["needs_changes"] is False)

# ---- Mentor bounces the main task ------------------------------------------------
check("submit", submit(main_id).status_code == 200)
t = get(main_id)
check("submitted: not needs_changes (it is waiting for review)", t["status"] == "submitted" and t["needs_changes"] is False)

check("mentor: needs_changes", mentor(main_id, "needs_changes", "Layout breaks under 400px.").status_code == 201)
t = get(main_id)
check("after a bounce the task is back in_progress", t["status"] == "in_progress")
check("...and now flagged needs_changes", t["needs_changes"] is True)
check("...revision_count is 1", t["revision_count"] == 1)

# ---- other tasks are unaffected --------------------------------------------------
check("the never-submitted task is still not flagged", get(started_id)["needs_changes"] is False)
check("the untouched todo task is still not flagged", get(todo_id)["needs_changes"] is False)

# ---- resubmit clears the flag; a second bounce sets it again ----------------------
check("resubmit", submit(main_id).status_code == 200)
t = get(main_id)
check("resubmitted: flag cleared (status is submitted again)", t["status"] == "submitted" and t["needs_changes"] is False)
check("...the revision history is kept (still 1)", t["revision_count"] == 1)

check("mentor: needs_changes again", mentor(main_id, "needs_changes", "Better, but the footer overlaps.").status_code == 201)
t = get(main_id)
check("second bounce: flagged again", t["needs_changes"] is True)
check("...revision_count is 2", t["revision_count"] == 2)

# ---- approval ends it ---------------------------------------------------------------
check("resubmit again", submit(main_id).status_code == 200)
check("mentor: approved", mentor(main_id, "approved", "All fixed.").status_code == 201)
t = get(main_id)
check("approved: reviewed, not flagged", t["status"] == "reviewed" and t["needs_changes"] is False)
check("...revision_count keeps the history (took 3 attempts)", t["revision_count"] == 2)

# ---- the list endpoint carries the fields, with no per-task query ---------------------
check("mentor: bounce the second task too", (submit(started_id).status_code == 200) and mentor(started_id, "needs_changes", "Needs tests.").status_code == 201)
listing = client.get("/tasks", headers=headers).json()
by_id = {x["id"]: x for x in listing}
check("GET /tasks includes needs_changes / revision_count on every task", all("needs_changes" in x and "revision_count" in x for x in listing))
check("GET /tasks: the bounced task is flagged", by_id[started_id]["needs_changes"] is True and by_id[started_id]["revision_count"] == 1)
check("GET /tasks: the approved task is not", by_id[main_id]["needs_changes"] is False)
check("GET /tasks: the todo task is not", by_id[todo_id]["needs_changes"] is False)

statements = []


def count_reviews_queries(conn, cursor, statement, parameters, context, executemany):
    if "FROM reviews" in statement:
        statements.append(statement)


event.listen(engine, "before_cursor_execute", count_reviews_queries)
client.get("/tasks", headers=headers)
event.remove(engine, "before_cursor_execute", count_reviews_queries)
check(f"listing {len(listing)} tasks loads reviews in ONE query, not one per task (got {len(statements)})", len(statements) == 1)

print("\nAll needs-changes smoke checks passed.")
