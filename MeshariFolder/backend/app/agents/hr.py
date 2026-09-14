"""
HR agent. Two jobs:
  1. `run_rollup` — periodically rolls up a graduate's Mentor review
     history into an updated Employee File (the shared record Manager and
     Mentor also read) plus a standalone SKILLS_ROLLUP Review. Run cadence
     (after every task? weekly?) is still an open decision per
     docs/PROJECT_STATUS.md; this just implements "run it once now."
  2. `run_behavioral_review` — the end-of-week behavioral evaluation
     (attendance, consistency, absence) from docs/STAGE1_PRODUCT_FLOW.md,
     called by weekly_cycle.py right after the Manager's week_progress
     review. Attendance/lateness figures are computed in code from
     existing Task/TaskMessage timestamps ("meaningful progress" days,
     confirmed with Meshari — a status change, submission, or resubmission
     counts, not just opening the app) — the LLM only writes the narrative
     and a rating on top of numbers it's handed, not the figures themselves.

Storage note: EmployeeFile.skills_json / strengths_json / growth_areas_json
are typed `dict` in models.py (so the SQLAlchemy default of `{}` before any
HR rollup stays valid). Each holds `{"items": [...]}` once HR has written to
it — the frontend will need a one-line `.items` unwrap when it's wired to
this instead of its current mock arrays.
"""
from sqlalchemy.orm import Session

from app.agents.llm_client import call_with_tool
from app.agents.tools import BEHAVIORAL_REVIEW_TOOL, UPDATE_EMPLOYEE_FILE_TOOL
from app.models import AgentType, Review, ReviewKind, User, Week
from app.scheduling import n_workdays_from

SYSTEM_PROMPT = (
    "You are HR at Venv. You maintain one graduate's Employee File based "
    "on their Mentor review history: what skills they've demonstrated, "
    "genuine strengths, and honest growth areas. Be specific and "
    "evidence-based — reference what actually happened in the reviews, "
    "not generic praise. Growth areas should be actionable, not vague "
    "('add tests alongside the feature' rather than 'improve quality')."
)

BEHAVIORAL_SYSTEM_PROMPT = (
    "You are HR at Venv, writing a graduate's end-of-week behavioral "
    "evaluation — attendance, consistency, and absence. You'll be given "
    "the actual attendance and lateness figures for the week; write a "
    "fair, specific summary grounded in those numbers, not a generic one."
)


def run_rollup(db: Session, user: User) -> Review:
    mentor_reviews = [r for r in user.reviews if r.agent_type == AgentType.MENTOR]
    if not mentor_reviews:
        raise ValueError("No Mentor reviews yet — nothing for HR to roll up.")

    ef = user.employee_file
    history_text = "\n\n".join(
        f"Review {i + 1} (verdict: {r.metrics_json.get('verdict', '?') if r.metrics_json else '?'}): {r.content}"
        for i, r in enumerate(mentor_reviews)
    )
    prompt = (
        "Current Employee File:\n"
        f"  Skills: {ef.skills_json}\n"
        f"  Strengths: {ef.strengths_json}\n"
        f"  Growth areas: {ef.growth_areas_json}\n"
        f"  Summary: {ef.summary_text}\n\n"
        f"Mentor review history ({len(mentor_reviews)} reviews):\n{history_text}\n\n"
        "Update the Employee File now via the update_employee_file tool."
    )
    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[UPDATE_EMPLOYEE_FILE_TOOL],
        force_tool="update_employee_file",
        max_tokens=1500,
    )
    data = result["input"]

    ef.skills_json = {"items": data["skills"]}
    ef.strengths_json = {"items": data["strengths"]}
    ef.growth_areas_json = {"items": data["growth_areas"]}
    ef.summary_text = data["summary"]
    db.add(ef)

    scored = [
        c["score"]
        for r in mentor_reviews
        for c in (r.metrics_json or {}).get("categories", [])
    ]
    average_score = round(sum(scored) / len(scored), 2) if scored else None

    review = Review(
        user_id=user.id,
        task_id=None,
        agent_type=AgentType.HR,
        kind=ReviewKind.SKILLS_ROLLUP,
        content=data["summary"],
        metrics_json={
            "reviewed_task_count": len(mentor_reviews),
            "average_score": average_score,
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def _active_days(week: Week) -> set:
    """Calendar dates with 'meaningful progress' on this week's subtasks —
    a status change, submission, or resubmission — per the definition
    Meshari confirmed. Derived entirely from timestamps that already exist
    (no new tracking): a task's creation/submission/completion, plus every
    message in its thread (which includes every Mentor review, including
    ones after a needs_changes resubmit)."""
    days = set()
    for task in week.tasks:
        days.add(task.created_at.date())
        if task.submitted_at:
            days.add(task.submitted_at.date())
        if task.completed_at:
            days.add(task.completed_at.date())
        for m in task.messages:
            days.add(m.created_at.date())
    return days


def run_behavioral_review(db: Session, user: User, week: Week, mentor_consult: str | None = None) -> Review:
    """The second step of the end-of-week cascade (after the Manager's
    week_progress review) — see weekly_cycle.py.

    mentor_consult (Stage 2, docs/STAGE2_WEEKLY_CYCLE_FLOW.md): the
    Mentor's direct answer when actually asked about consistency/
    engagement this week (app/agents/graph/collaboration.py's
    ask_mentor), on top of the raw attendance numbers below. Optional,
    defaults to None — Stage 1 behavior unchanged if omitted."""
    workdays = {d.date() for d in n_workdays_from(week.started_at, 5)}
    active = _active_days(week) & workdays
    attended_days = len(active)
    absent_days = max(0, 5 - attended_days)
    late_count = sum(1 for t in week.tasks if t.is_late)

    consult_text = (
        f"\n\nWhen asked directly about consistency/engagement this week, "
        f"the Mentor said:\n{mentor_consult}"
        if mentor_consult
        else ""
    )
    prompt = (
        f"Week {week.week_number} ({week.big_task_title}):\n"
        f"  {attended_days}/5 workdays had meaningful progress\n"
        f"  {absent_days}/5 workdays had none\n"
        f"  {late_count} of {len(week.tasks)} subtasks completed late"
        f"{consult_text}\n\n"
        "Write the behavioral evaluation now via the submit_behavioral_review tool."
    )
    result = call_with_tool(
        system=BEHAVIORAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[BEHAVIORAL_REVIEW_TOOL],
        force_tool="submit_behavioral_review",
    )
    data = result["input"]

    review = Review(
        user_id=user.id,
        task_id=None,
        week_id=week.id,
        agent_type=AgentType.HR,
        kind=ReviewKind.BEHAVIORAL,
        content=data["summary"],
        metrics_json={
            "attended_days": attended_days,
            "absent_days": absent_days,
            "late_task_count": late_count,
            "total_subtasks": len(week.tasks),
            "consistency_rating": data["consistency_rating"],
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
