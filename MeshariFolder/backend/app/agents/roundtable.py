"""
Stage 2 — the agent roundtable (docs/STAGE2_ROUNDTABLE.md). The deeper
version of "more collaborative, not just assigning tasks": instead of
each optional agent posting an isolated comment in parallel
(co_reviewers.py's original behavior), they now discuss the submission
*with each other*, in sequence, each one seeing the Mentor's review and
everything said before it — so a Security Reviewer can pick up on a point
the Data Reviewer raised, agree, disagree, or add to it. The result is an
actual conversation in the task thread, not a stack of monologues.

Then the Manager reads the whole discussion and posts a short synthesis
— what to prioritize, given everything the team surfaced — so the
graduate gets one clear "here's what matters most" rather than being left
to reconcile four voices themselves.

Kept deliberately bounded: one pass around the table (not a free-running
loop), specialists on the small tier (quick, cheap takes), the Manager's
synthesis on the main tier (it's the judgment call that ties it
together). Each agent's turn is best-effort — one failing is skipped, the
rest of the table carries on.
"""
import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents import manager
from app.agents.github_client import fetch_repo_context
from app.agents.llm_client import call_agentic
from app.agents.meeting import PERSONA
from app.database import SessionLocal
from app.models import (
    AgentCatalog,
    AgentType,
    ReviewKind,
    SenderType,
    Task,
    TaskMessage,
    User,
    UserAgent,
)

logger = logging.getLogger("venv.roundtable")

ROUNDTABLE_AGENTS = {
    AgentType.SECURITY_REVIEWER,
    AgentType.DATA_REVIEWER,
    AgentType.DEVOPS,
    AgentType.QA_ENGINEER,
    AgentType.UX_REVIEWER,
}

_SPECIALIST_FRAMING = (
    "\n\nYou're in a team discussion about a graduate's submission. The "
    "Mentor has given the official review, and your colleagues may have "
    "already weighed in — their comments are below. Add your specialty "
    "perspective: build on, agree with, or respectfully push back on what "
    "others said where it overlaps your area, and raise anything they "
    "missed. A few sentences. Don't repeat points already well covered — "
    "if your area's already been addressed or isn't relevant here, say so "
    "briefly. Speak to the team, not just the graduate."
)

_MANAGER_SYNTHESIS_FRAMING = (
    "\n\nYour team just discussed a graduate's submission — the Mentor's "
    "review and each specialist's take are below. Write a short synthesis "
    "for the graduate: pull the discussion together into the two or three "
    "things that actually matter most to act on next, resolving any "
    "tension between what different agents emphasized. Be concrete and "
    "encouraging. A short paragraph, not a list of everything said."
)


def _roster_agent_types(db: Session, user: User) -> set[AgentType]:
    rows = (
        db.query(AgentCatalog.agent_type)
        .join(UserAgent, UserAgent.agent_catalog_id == AgentCatalog.id)
        .filter(UserAgent.user_id == user.id)
        .all()
    )
    return {row[0] for row in rows}


def _submission_context(task: Task) -> str:
    parts = [f"Task: {task.title}\n{task.description}\n"]
    if task.github_link:
        parts.append(f"Submitted repo:\n{fetch_repo_context(task.github_link)}\n")
    if task.submission_text:
        parts.append(f"Graduate's own notes:\n{task.submission_text}\n")
    if task.attachments:
        parts.append(
            "Files attached: " + ", ".join(a.filename for a in task.attachments) + "\n"
        )
    return "\n".join(parts)


def _mentor_review_text(task: Task) -> str:
    review = next(
        (r for r in task.reviews if r.kind == ReviewKind.TASK_REVIEW), None
    )
    if not review:
        return "The Mentor hasn't recorded a structured review."
    verdict = (review.metrics_json or {}).get("verdict", "?")
    return f"Mentor's review (verdict: {verdict}):\n{review.content}"


def _post(db: Session, task: Task, agent_type: AgentType, content: str) -> TaskMessage:
    message = TaskMessage(
        task_id=task.id,
        sender_type=SenderType.AGENT,
        agent_type=agent_type,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def specialists_for(db: Session, user: User) -> list[AgentType]:
    """The specialists on this graduate's team who join the roundtable, in the fixed
    speaking order (by AgentType value). Empty means: no roundtable at all."""
    return sorted(_roster_agent_types(db, user) & ROUNDTABLE_AGENTS, key=lambda a: a.value)


# ---- running it in the background (docs/BACKGROUND_ROUNDTABLE.md) -------------------------
#
# The Mentor's review is what the graduate is waiting for; the specialists' discussion
# (three small-model turns, then the Manager's main-model synthesis) roughly DOUBLES that
# wait. So the review endpoint returns as soon as the Mentor is done and this runs after it,
# each message appearing in the thread as it is written (_post commits each one).

_task_locks: dict[str, threading.Lock] = {}
_task_locks_guard = threading.Lock()


def _lock_for(task_id: str) -> threading.Lock:
    """One lock per task, so two reviews of the same task in quick succession (a fast
    resubmission) have their discussions one after the other, not interleaved in the
    thread. Process-local, which is enough: it only orders discussions run by THIS process."""
    with _task_locks_guard:
        return _task_locks.setdefault(task_id, threading.Lock())


def begin_roundtable(db: Session, task: Task) -> datetime:
    """Mark a roundtable as running, BEFORE the review response is sent, so that the very
    first thing the frontend fetches afterwards already says so. Returns a token that
    identifies this run (see run_roundtable_job)."""
    started_at = datetime.utcnow()
    task.roundtable_started_at = started_at
    task.roundtable_finished_at = None
    db.commit()
    return started_at


def _mark_finished(task_id: str, started_at: datetime) -> None:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        # Only the LATEST run may declare the task finished: if a newer review has begun a
        # discussion since (a resubmission), it is still queued or running - leave it "running".
        if task is not None and task.roundtable_started_at == started_at:
            task.roundtable_finished_at = datetime.utcnow()
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Could not record the end of the roundtable for task %s", task_id)
        db.rollback()
    finally:
        db.close()


def run_roundtable_job(task_id: str, user_id: str, started_at: datetime) -> None:
    """The background job. Takes ids, not ORM objects: the request's database session is
    gone by the time this runs, so it opens its own. Never raises - an error must not take
    the worker down, and the Mentor's review has already been delivered either way."""
    with _lock_for(task_id):
        db = SessionLocal()
        try:
            task = db.get(Task, task_id)
            user = db.get(User, user_id)
            if task is not None and user is not None:
                run_roundtable(db, user, task)
        except Exception:  # noqa: BLE001 - best-effort, like every turn inside run_roundtable
            logger.exception("Roundtable for task %s failed; the Mentor's review stands", task_id)
            db.rollback()
        finally:
            db.close()
            _mark_finished(task_id, started_at)


def run_roundtable(db: Session, user: User, task: Task) -> list[TaskMessage]:
    """Called right after the Mentor's review. Runs one pass: each
    specialist on the team responds in turn (seeing all prior turns), then
    the Manager synthesizes. Returns every message posted, in order —
    empty if no specialists are on the roster (then the Manager has
    nothing to synthesize and stays quiet too). Ordering is deterministic
    (by AgentType) so the conversation reads consistently."""
    active = specialists_for(db, user)
    if not active:
        return []

    submission = _submission_context(task)
    mentor_text = _mentor_review_text(task)

    transcript: list[str] = [mentor_text]
    posted: list[TaskMessage] = []

    for agent_type in active:
        discussion_so_far = "\n\n".join(transcript)
        try:
            reply = call_agentic(
                system=PERSONA[agent_type] + _SPECIALIST_FRAMING,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"{submission}\n\n--- Team discussion so far ---\n"
                            f"{discussion_so_far}\n\n--- Your turn ---"
                        ),
                    }
                ],
                tools=[],
                tier="small",
                max_tokens=400,
            )
        except Exception:
            continue
        text = reply.text
        if not text:
            continue
        posted.append(_post(db, task, agent_type, text))
        name = PERSONA[agent_type].split(" at Venv")[0].replace("You are the ", "")
        transcript.append(f"{name}:\n{text}")

    if posted:
        discussion = "\n\n".join(transcript)
        try:
            reply = call_agentic(
                system=manager.SYSTEM_PROMPT + _MANAGER_SYNTHESIS_FRAMING,
                messages=[
                    {
                        "role": "user",
                        "content": f"{submission}\n\n--- Full team discussion ---\n{discussion}",
                    }
                ],
                tools=[],
                tier="main",
                max_tokens=500,
            )
            text = reply.text
            if text:
                posted.append(_post(db, task, AgentType.MANAGER, text))
        except Exception:
            pass

    return posted
