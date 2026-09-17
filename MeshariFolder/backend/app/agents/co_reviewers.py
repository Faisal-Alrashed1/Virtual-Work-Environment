"""
Stage 2 — optional agents doing real task work (docs/
STAGE2_AGENT_TASK_WORK.md), not just roster entries and meeting-room
chat. When a graduate has the Security Reviewer, Data Reviewer, or
DevOps agent on their team, each one posts a follow-up comment in the
task thread right after the Mentor's own review — their specialty lens
on the same submission, not a competing structured Review (that stays
the Mentor's alone; see run_co_reviews's docstring for why).

Career Coach is deliberately not part of this: resume/interview
coaching doesn't fit a per-task code review the way security, data, and
infra concerns do. It stays meeting-room-only (meeting.py).

Uses call_agentic (plain text, no tools) on the small tier — these are
quick specialty comments, not the primary judgment call the Mentor
already made, same reasoning as the onboarding graph's model routing
(docs/STAGE2_ONBOARDING_FLOW.md).
"""
from sqlalchemy.orm import Session

from app.agents.github_client import fetch_repo_context
from app.agents.llm_client import call_agentic
from app.agents.meeting import PERSONA
from app.models import AgentCatalog, AgentType, SenderType, Task, TaskMessage, User, UserAgent

CO_REVIEW_AGENTS = {AgentType.SECURITY_REVIEWER, AgentType.DATA_REVIEWER, AgentType.DEVOPS}

_FRAMING = (
    "\n\nA graduate just submitted work for a task and the Mentor already "
    "wrote the official review. Give your own specialty take as a quick "
    "follow-up comment in the task thread — a few sentences, not a full "
    "review. Only flag something if it's actually relevant to your "
    "specialty; if this submission doesn't touch your area at all, say "
    "so briefly rather than padding with generic comments."
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


def run_co_reviews(db: Session, user: User, task: Task) -> list[TaskMessage]:
    """Called right after the Mentor's review. Returns whatever messages
    got posted — empty if the graduate has none of CO_REVIEW_AGENTS on
    their roster. Each agent's call is independent and best-effort: one
    agent erroring (a rate limit, a flaky response) doesn't block the
    others or the Mentor's review that already succeeded."""
    active = _roster_agent_types(db, user) & CO_REVIEW_AGENTS
    if not active:
        return []

    context = _submission_context(task)
    posted: list[TaskMessage] = []
    for agent_type in active:
        try:
            reply = call_agentic(
                system=PERSONA[agent_type] + _FRAMING,
                messages=[{"role": "user", "content": context}],
                tools=[],
                tier="small",
                max_tokens=400,
            )
        except Exception:
            continue
        text = reply.text
        if not text:
            continue
        message = TaskMessage(
            task_id=task.id,
            sender_type=SenderType.AGENT,
            agent_type=agent_type,
            content=text,
        )
        db.add(message)
        posted.append(message)

    if posted:
        db.commit()
        for m in posted:
            db.refresh(m)
    return posted
