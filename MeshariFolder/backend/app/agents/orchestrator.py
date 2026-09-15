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

from app.agents import hr, manager, mentor, roundtable, weekly_cycle
from app.models import Review, Task, TaskMessage, User


def manager_assign_task(db: Session, user: User) -> Task:
    """The graduate's next task — bootstraps their Project/Week on the
    first call, hands out the next subtask, or (once a week's 5 are all
    approved) runs the end-of-week cascade and rolls into the next week.
    See weekly_cycle.get_next_task."""
    return weekly_cycle.get_next_task(db, user)


def manager_reply(db: Session, task: Task, user: User) -> TaskMessage:
    return manager.respond_in_thread(db, task, user)


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


def hr_rollup(db: Session, user: User) -> Review:
    return hr.run_rollup(db, user)
