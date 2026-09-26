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
from sqlalchemy.orm import Session

from app.agents import data_reviewer, manager, security_reviewer
from app.agents.github_client import fetch_repo_context
from app.agents.language import LANGUAGE_RULE
from app.agents.llm_client import call_agentic
from app.agents.meeting import PERSONA
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

ROUNDTABLE_AGENTS = {
    AgentType.SECURITY_REVIEWER,
    AgentType.DATA_REVIEWER,
    AgentType.DEVOPS,
}

# Security Reviewer / Data Reviewer graduated from a free-text persona
# comment to a real, structured review of their own (security_reviewer.py,
# data_reviewer.py) — grounded in actual repo content, not just a prompt.
# DevOps stays on the original free-text path below; it wasn't part of
# this round of work. Keyed by AgentType so the dispatch in run_roundtable
# is a single lookup rather than a chain of ifs.
_STRUCTURED_REVIEWERS = {
    AgentType.SECURITY_REVIEWER: security_reviewer,
    AgentType.DATA_REVIEWER: data_reviewer,
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


def run_roundtable(db: Session, user: User, task: Task) -> list[TaskMessage]:
    """Called right after the Mentor's review. Runs one pass: each
    specialist on the team responds in turn (seeing all prior turns), then
    the Manager synthesizes. Returns every message posted, in order —
    empty if no specialists are on the roster (then the Manager has
    nothing to synthesize and stays quiet too). Ordering is deterministic
    (by AgentType) so the conversation reads consistently."""
    active = sorted(
        _roster_agent_types(db, user) & ROUNDTABLE_AGENTS, key=lambda a: a.value
    )
    if not active:
        return []

    submission = _submission_context(task)
    mentor_text = _mentor_review_text(task)

    transcript: list[str] = [mentor_text]
    posted: list[TaskMessage] = []

    for agent_type in active:
        discussion_so_far = "\n\n".join(transcript)
        reviewer_module = _STRUCTURED_REVIEWERS.get(agent_type)
        try:
            if reviewer_module is not None:
                # Security Reviewer / Data Reviewer: real repo analysis +
                # a structured, storable finding (their own tool schema),
                # not a free-text comment — see security_reviewer.py /
                # data_reviewer.py. discussion_so_far keeps them part of
                # the actual roundtable conversation on top of that.
                review = reviewer_module.review_task(db, task, user, discussion_so_far)
                text = review.content
            else:
                reply = call_agentic(
                    system=PERSONA[agent_type] + _SPECIALIST_FRAMING + LANGUAGE_RULE,
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
                text = reply.text
        except Exception:
            continue
        if not text:
            continue
        posted.append(_post(db, task, agent_type, text))
        name = PERSONA[agent_type].split(" at Venv")[0].replace("You are the ", "")
        transcript.append(f"{name}:\n{text}")

    if posted:
        discussion = "\n\n".join(transcript)
        try:
            reply = call_agentic(
                system=manager.SYSTEM_PROMPT + _MANAGER_SYNTHESIS_FRAMING + LANGUAGE_RULE,
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
