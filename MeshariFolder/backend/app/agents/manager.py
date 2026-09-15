"""
Manager agent. Jobs, matching agents/README.md and docs/STAGE1_PRODUCT_FLOW.md:
  1. Introduce the graduate's main Project (once, at their very first task).
  2. Plan each Week: one big task broken into 5 subtasks.
  3. Hand out one subtask at a time as a real Task row (no LLM call — the
     plan was already decided in plan_week).
  4. Reply in a task's comment thread when the graduate posts something.
  5. At the end of each Week, write the progress review that HR's
     behavioral review reads alongside.

Nothing here decides *when* to do these — that state machine (bootstrap a
Project, advance to the next subtask, or run the end-of-week cascade) lives
in weekly_cycle.py, which calls into this module's functions in order.
Keeping the "what" (this file) separate from the "when" (weekly_cycle.py)
is deliberate: this file is one LLM call each, easy to reason about in
isolation.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.llm_client import call_agentic, call_with_tool
from app.agents.tools import (
    CREATE_PROJECT_TOOL,
    PLAN_WEEK_TOOL,
    POST_MESSAGE_TOOL,
    WEEK_PROGRESS_TOOL,
)
from app.models import (
    AgentType,
    Project,
    ProjectSource,
    Review,
    ReviewKind,
    SenderType,
    Task,
    TaskMessage,
    User,
    Week,
)
from app.scheduling import n_workdays_from

SYSTEM_PROMPT = (
    "You are the Manager at Venv, a simulated software team a recent "
    "graduate has just joined. Your job is to introduce their main "
    "project, plan each week's work as one big task broken into 5 "
    "scoped subtasks, and hand those out one at a time — calibrated to "
    "what you know about this graduate's skills so far. Keep your tone "
    "professional and encouraging, like a good real manager onboarding a "
    "junior engineer."
)


def _cv_context(user: User) -> str:
    parts = []
    if user.cv_raw_text:
        parts.append(f"CV (raw text at intake):\n{user.cv_raw_text}")
    ef = user.employee_file
    if ef and ef.skills_json:
        parts.append(f"Known skills so far: {ef.skills_json}")
    if ef and ef.summary_text:
        parts.append(f"HR summary so far: {ef.summary_text}")
    return "\n\n".join(parts) if parts else "No CV or history yet — this is their first task."


def create_project(db: Session, user: User) -> Project:
    """Called once per graduate, the first time weekly_cycle.get_next_task
    finds no active Project yet. Stage 2: a graduate can bring their own
    project instead — POST /projects/own, called before this ever runs —
    in which case this function never runs at all for them; see
    docs/STAGE2_OWN_PROJECT.md."""
    prompt = (
        f"{_cv_context(user)}\n\n"
        "Introduce this graduate to the main project they'll be working on "
        "throughout the program. Create it now via the create_project tool."
    )
    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[CREATE_PROJECT_TOOL],
        force_tool="create_project",
    )
    data = result["input"]

    project = Project(
        user_id=user.id,
        title=data["title"],
        description=data["description"],
        source=ProjectSource.MANAGER,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def plan_week(db: Session, user: User, project: Project) -> Week:
    """Defines the week's big task + exactly 5 subtasks, with each
    subtask's deadline decided up front (Sun-Thu workdays — see
    scheduling.py) rather than recomputed whenever it's actually released,
    so a late-running week doesn't silently push deadlines back."""
    week_number = max((w.week_number for w in project.weeks), default=0) + 1
    started_at = datetime.utcnow()
    workday_deadlines = n_workdays_from(started_at, 5)

    prior_weeks_text = "\n\n".join(
        f"Week {w.week_number}: {w.big_task_title}" for w in project.weeks
    ) or "None yet — this is the first week."
    prompt = (
        f"Project: {project.title}\n{project.description}\n\n"
        f"{_cv_context(user)}\n\n"
        f"Prior weeks:\n{prior_weeks_text}\n\n"
        f"Plan week {week_number} now via the plan_week tool."
    )
    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[PLAN_WEEK_TOOL],
        force_tool="plan_week",
        max_tokens=2000,
    )
    data = result["input"]
    subtasks = data["subtasks"]
    if len(subtasks) < 5:
        raise ValueError(f"plan_week expected 5 subtasks, got {len(subtasks)}")

    subtasks_plan = [
        {
            "title": s["title"],
            "description": s["description"],
            "deadline": workday_deadlines[i].isoformat(),
        }
        for i, s in enumerate(subtasks[:5])
    ]

    week = Week(
        project_id=project.id,
        user_id=user.id,
        week_number=week_number,
        big_task_title=data["big_task_title"],
        big_task_description=data["big_task_description"],
        subtasks_plan_json=subtasks_plan,
        next_subtask_index=0,
        started_at=started_at,
        target_end_at=workday_deadlines[-1],
    )
    db.add(week)
    db.commit()
    db.refresh(week)
    return week


def release_next_subtask(db: Session, week: Week) -> Task:
    """Turns the next planned subtask into a real Task row. No LLM call —
    the plan (and its deadline) was already decided in plan_week; this just
    hands it out."""
    idx = week.next_subtask_index
    plan = week.subtasks_plan_json[idx]

    task = Task(
        title=plan["title"],
        description=plan["description"],
        user_id=week.user_id,
        week_id=week.id,
        deadline=datetime.fromisoformat(plan["deadline"]),
        created_by_agent=AgentType.MANAGER,
    )
    db.add(task)
    week.next_subtask_index = idx + 1
    db.add(week)
    db.commit()
    db.refresh(task)

    db.add(
        TaskMessage(
            task_id=task.id,
            sender_type=SenderType.AGENT,
            agent_type=AgentType.MANAGER,
            content=f"New task: {task.title}\n\n{task.description}",
        )
    )
    db.commit()
    db.refresh(task)
    return task


def submit_week_progress(db: Session, user: User, week: Week, mentor_consult: str | None = None) -> Review:
    """The Manager's end-of-week review, based on the Mentor's per-subtask
    reviews — the first step of the end-of-week cascade, before HR's
    behavioral review reads it alongside.

    mentor_consult (Stage 2, docs/STAGE2_WEEKLY_CYCLE_FLOW.md): the
    Mentor's direct answer when actually asked how the week went
    (app/agents/graph/collaboration.py's ask_mentor), on top of the
    stored per-subtask review text below. Optional and defaults to None
    so this function's Stage 1 behavior is unchanged for any caller that
    doesn't pass it."""
    mentor_reviews = [r for r in week.reviews if r.kind == ReviewKind.TASK_REVIEW]
    history_text = "\n\n".join(
        f"Subtask {i + 1} (verdict: {(r.metrics_json or {}).get('verdict', '?')}): {r.content}"
        for i, r in enumerate(mentor_reviews)
    ) or "No Mentor reviews recorded this week."
    consult_text = (
        f"\n\nWhen asked directly how the week went, the Mentor said:\n{mentor_consult}"
        if mentor_consult
        else ""
    )
    prompt = (
        f"Week {week.week_number} big task: {week.big_task_title}\n"
        f"{week.big_task_description}\n\n"
        f"Mentor's reviews of this week's subtasks:\n{history_text}"
        f"{consult_text}\n\n"
        "Submit the week's progress review now via the submit_week_progress tool."
    )
    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[WEEK_PROGRESS_TOOL],
        force_tool="submit_week_progress",
    )
    data = result["input"]

    review = Review(
        user_id=user.id,
        task_id=None,
        week_id=week.id,
        agent_type=AgentType.MANAGER,
        kind=ReviewKind.WEEK_PROGRESS,
        content=data["summary"],
        metrics_json={
            "subtasks_completed": data["subtasks_completed"],
            "subtasks_needed_changes": data["subtasks_needed_changes"],
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def respond_in_thread(db: Session, task: Task, user: User) -> TaskMessage:
    """Reads the task's thread and posts a reply. Called after the graduate
    posts a message via POST /tasks/{id}/messages."""
    history = [
        {
            "role": "assistant" if m.sender_type == SenderType.AGENT else "user",
            "content": m.content,
        }
        for m in task.messages
    ]
    system = (
        SYSTEM_PROMPT
        + f"\n\nCurrent task: {task.title} — {task.description}\n"
        + f"Status: {task.status.value}.\n{_cv_context(user)}"
    )
    response = call_agentic(
        system=system,
        messages=history or [{"role": "user", "content": "(no messages yet)"}],
        tools=[POST_MESSAGE_TOOL],
    )

    content = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "post_message":
            content = block.input["content"]
        elif block.type == "text" and block.text:
            content = block.text
    content = content or "Got it — keep going, and let me know if you get stuck."

    message = TaskMessage(
        task_id=task.id,
        sender_type=SenderType.AGENT,
        agent_type=AgentType.MANAGER,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
