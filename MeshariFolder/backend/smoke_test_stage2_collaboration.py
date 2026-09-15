"""
Smoke test for the Stage 2 weekly-cycle collaboration piece
(app/agents/graph/collaboration.py + weekly_cycle_graph.py): proves the
Mentor is actually consulted — not just that the cascade still produces
two Review rows (smoke_test_orchestration.py already covers that end to
end) — by inspecting the real prompt text sent to Manager/HR's calls and
confirming the Mentor's consult reply shows up in it.

ORM-level, same style as smoke_test_weekly_cycle.py: builds a User/
Project/Week/Task/Review tree directly rather than through the API, to
isolate the collaboration piece from the rest of the orchestration.

Run: python smoke_test_stage2_collaboration.py
"""
import os
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_collaboration.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AgentType,
    Base,
    EmployeeFile,
    Project,
    ProjectStatus,
    Review,
    ReviewKind,
    Task,
    TaskStatus,
    User,
    Week,
    WeekStatus,
)
from app.database import engine  # noqa: E402
from app.agents.graph.weekly_cycle_graph import run_end_of_week_cascade  # noqa: E402

Base.metadata.create_all(bind=engine)


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


db = SessionLocal()

user = User(email="collab-test@example.com", hashed_password="x", full_name="Collab Tester")
db.add(user)
db.flush()
db.add(EmployeeFile(user_id=user.id))

project = Project(user_id=user.id, title="Test project", description="d", status=ProjectStatus.ACTIVE)
db.add(project)
db.flush()

week = Week(
    project_id=project.id,
    user_id=user.id,
    week_number=1,
    status=WeekStatus.ACTIVE,
    big_task_title="Ship login",
    big_task_description="Get login working end to end.",
    subtasks_plan_json=[],
    next_subtask_index=5,
    started_at=datetime.utcnow(),
    target_end_at=datetime.utcnow() + timedelta(days=5),
)
db.add(week)
db.flush()

task = Task(
    user_id=user.id,
    week_id=week.id,
    title="Subtask 1",
    description="d",
    status=TaskStatus.REVIEWED,
    created_by_agent=AgentType.MANAGER,
    deadline=datetime.utcnow(),
    completed_at=datetime.utcnow(),
)
db.add(task)
db.flush()

db.add(
    Review(
        user_id=user.id,
        task_id=task.id,
        week_id=week.id,
        agent_type=AgentType.MENTOR,
        kind=ReviewKind.TASK_REVIEW,
        content="Clean, working login flow.",
        metrics_json={"verdict": "approved"},
    )
)
db.commit()
db.refresh(week)

CONSULT_REPLIES = [
    {"tool_name": "reply_to_colleague", "input": {"reply": "Picked up JWT auth fast — strong week overall."}},
    {"tool_name": "reply_to_colleague", "input": {"reply": "No consistency concerns, submitted early every day."}},
]

manager_captured = {}
hr_captured = {}


def fake_manager_call(**kwargs):
    manager_captured.update(kwargs)
    return {
        "tool_name": "submit_week_progress",
        "input": {"summary": "Great first week.", "subtasks_completed": 1, "subtasks_needed_changes": 0},
    }


def fake_hr_call(**kwargs):
    hr_captured.update(kwargs)
    return {
        "tool_name": "submit_behavioral_review",
        "input": {"summary": "Consistent all week.", "consistency_rating": "strong"},
    }


with patch("app.agents.graph.collaboration.call_with_tool", side_effect=CONSULT_REPLIES) as mock_collab, patch(
    "app.agents.manager.call_with_tool", side_effect=fake_manager_call
), patch("app.agents.hr.call_with_tool", side_effect=fake_hr_call):
    manager_review, hr_review = run_end_of_week_cascade(db, user, week)

    check("mentor consulted exactly twice", mock_collab.call_count == 2)

    manager_question = mock_collab.call_args_list[0].kwargs["messages"][0]["content"]
    check("manager's consult asks about the week overall", "overall" in manager_question)

    hr_question = mock_collab.call_args_list[1].kwargs["messages"][0]["content"]
    check("hr's consult asks about consistency", "consistency" in hr_question or "engagement" in hr_question)

    manager_prompt = manager_captured["messages"][0]["content"]
    check(
        "the mentor's actual consult reply reached the manager's prompt",
        "Picked up JWT auth fast" in manager_prompt,
    )

    hr_prompt = hr_captured["messages"][0]["content"]
    check(
        "the mentor's actual consult reply reached hr's prompt",
        "No consistency concerns" in hr_prompt,
    )

    check("manager review persisted", manager_review.kind == ReviewKind.WEEK_PROGRESS)
    check("hr review persisted", hr_review.kind == ReviewKind.BEHAVIORAL)
    check("both reviews are attached to this week", manager_review.week_id == week.id and hr_review.week_id == week.id)

# --- backward compatibility: calling submit_week_progress/
# run_behavioral_review directly, without mentor_consult, still works
# exactly as it did in Stage 1 (no caller outside the new cascade graph
# passes it) ---
from app.agents import hr as hr_module  # noqa: E402
from app.agents import manager as manager_module  # noqa: E402

with patch("app.agents.manager.call_with_tool", side_effect=fake_manager_call), patch(
    "app.agents.hr.call_with_tool", side_effect=fake_hr_call
):
    manager_captured.clear()
    hr_captured.clear()
    manager_module.submit_week_progress(db, user, week)
    hr_module.run_behavioral_review(db, user, week)
    check(
        "no mentor_consult -> prompt unchanged from Stage 1 (no 'Mentor said' text)",
        "Mentor said" not in manager_captured["messages"][0]["content"]
        and "Mentor said" not in hr_captured["messages"][0]["content"],
    )

db.close()

print("\nAll Stage 2 collaboration smoke checks passed.")
