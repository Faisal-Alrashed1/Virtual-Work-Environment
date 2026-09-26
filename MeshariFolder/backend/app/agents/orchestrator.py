"""
Thin routing layer between the API (routers/agents.py) and the agent
modules. Nothing here talks to the LLM directly — it just calls into
weekly_cycle.py / manager.py / mentor.py / hr.py, so the router doesn't
need to import them directly or know their internals. This is the seam
agents/README.md describes: as Stage 2 adds more tracks and user-
selectable agents, new routing decisions (e.g. "which agent handles this
track") live here, not in the router or in an individual agent module.
"""
from sqlalchemy.orm import Session

from app.agents import career_coach, hr, manager, mentor, roundtable, task_chat, weekly_cycle
from app.models import AgentType, Review, Task, TaskMessage, User


def manager_assign_task(db: Session, user: User) -> Task:
    """The graduate's next task — bootstraps their Project/Week on the
    first call, hands out the next subtask, or (once a week's 5 are all
    approved) runs the end-of-week cascade and rolls into the next week.
    See weekly_cycle.get_next_task."""
    return weekly_cycle.get_next_task(db, user)


def manager_reply(db: Session, task: Task, user: User) -> TaskMessage:
    """Kept for the original, Manager-only reply path some callers may
    still use directly. The app itself now goes through task_chat_reply,
    which lets the graduate address the Mentor (the default) or a roster
    agent instead — see docs/TASK_CHAT.md."""
    return manager.respond_in_thread(db, task, user)


def task_chat_reply(db: Session, task: Task, user: User, agent_type: AgentType) -> TaskMessage:
    """Reply in a task's thread from whichever agent the graduate is
    addressing. Caller (the router) must already have checked
    task_chat.is_available_for_task."""
    return task_chat.reply_in_thread(db, task, user, agent_type)


def mentor_review(db: Session, task: Task, user: User) -> Review:
    return mentor.review_task(db, task, user)


def run_co_reviews(db: Session, task: Task, user: User) -> list[TaskMessage]:
    """Stage 2 — the agent roundtable: after the Mentor's review, the
    specialists on the graduate's team (Security Reviewer/Data Reviewer/
    DevOps) discuss the submission with each other, then the Manager
    synthesizes what matters most. See roundtable.run_roundtable.

    (Named run_co_reviews for continuity — the router and its docstring
    call it that; the roundtable is the richer evolution of the original
    parallel co-reviews, which still lives in co_reviewers.py as the
    simpler fallback and for its dedicated tests.)"""
    return roundtable.run_roundtable(db, user, task)


def start_roundtable(db: Session, task: Task, user: User, background) -> bool:
    """Stage 2 — start the agent roundtable IN THE BACKGROUND, after the Mentor's review.
    Returns whether one was started (False when the graduate has no specialists: there is
    nothing to discuss, and nothing should show as "running").

    The graduate gets the Mentor's review as soon as it is written; the specialists' turns
    and the Manager's synthesis then appear in the task thread one by one, and the task's
    `roundtable_running` flag tells the frontend to keep refreshing until they are done.
    See docs/BACKGROUND_ROUNDTABLE.md. (run_co_reviews above is the same discussion run
    inline; it remains for direct callers and the tests that exercise it.)"""
    if not roundtable.specialists_for(db, user):
        return False
    started_at = roundtable.begin_roundtable(db, task)
    background.add_task(roundtable.run_roundtable_job, task.id, user.id, started_at)
    return True


def hr_rollup(db: Session, user: User) -> Review:
    return hr.run_rollup(db, user)


def career_coach_checkin(db: Session, user: User) -> Review:
    return career_coach.run_checkin(db, user)
