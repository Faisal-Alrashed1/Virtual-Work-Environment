"""
The Meeting Room (/meeting) — a direct, task-free chat with any agent on
the graduate's team: the default three (Manager/Mentor/HR) plus whichever
optional agents they added during onboarding. Unlike
manager.respond_in_thread (which is scoped to a task's comment thread),
this is open-ended: the graduate asks the Manager about their week, the
Mentor for advice, HR about their growth, or an optional agent about
whatever it's meant for — with no task attached. Persisted as ChatMessage
rows, one running thread per (user, agent). The router (routers/
meeting.py) is what actually checks a graduate has an optional agent on
their team before letting them chat with it — see is_on_users_team below.

Each agent answers in its own voice: the default three reuse the same
persona the task-flow agents use, the four optional agents (roster-only
for now, no task-flow module of their own) have a persona defined here
directly, plus whatever shared context (CV, employee file, and — for
grounding — the current project/week) helps any of them give a useful
answer. The model just replies in plain text here; there are no tools to
call in a conversation, so this uses call_agentic with an empty tool list
rather than call_with_tool.
"""
from sqlalchemy.orm import Session

from app.agents import hr, manager, mentor
from app.agents.language import LANGUAGE_RULE
from app.agents.llm_client import call_agentic
from app.agents.submission_files import read_submitted_files
from app.models import (
    AgentCatalog,
    AgentType,
    ChatMessage,
    Project,
    ProjectStatus,
    Review,
    ReviewKind,
    SenderType,
    Task,
    User,
    UserAgent,
    Week,
    WeekStatus,
)

# Same per-file slice as the Mentor's review. A smaller one (1,500) left
# the model saying it had only seen part of a typical solution file.
_FILE_CHARS_FOR_MEETING = 4000

PERSONA: dict[AgentType, str] = {
    AgentType.MANAGER: manager.SYSTEM_PROMPT,
    AgentType.MENTOR: mentor.SYSTEM_PROMPT,
    AgentType.HR: hr.SYSTEM_PROMPT,
    AgentType.SECURITY_REVIEWER: (
        "You are the Security Reviewer at Venv, a recent graduate's go-to "
        "for secure-coding questions and vulnerability concerns outside a "
        "formal review. Be specific and practical — point at concrete "
        "risks and how to fix them, not generic security advice."
    ),
    AgentType.DATA_REVIEWER: (
        "You are the Data Reviewer at Venv, helping a recent graduate "
        "think through data quality, pipeline design, and evaluation "
        "methodology. Be specific and grounded in what they're actually "
        "working on, not textbook generalities."
    ),
    AgentType.CAREER_COACH: (
        "You are the Career Coach at Venv, helping a recent graduate with "
        "their resume, interview prep, and career questions — separate "
        "from their day-to-day task work. Be direct and practical, the "
        "way a good career mentor would be, not generic motivational "
        "advice."
    ),
    AgentType.DEVOPS: (
        "You are the DevOps agent at Venv, helping a recent graduate with "
        "CI/CD, deployment, and infrastructure-as-code questions. Be "
        "specific and hands-on — concrete commands or config where "
        "relevant, not abstract best-practice lists."
    ),
}

_DEFAULT_AGENTS = {AgentType.MANAGER, AgentType.MENTOR, AgentType.HR}


def is_on_users_team(db: Session, user: User, agent: AgentType) -> bool:
    if agent in _DEFAULT_AGENTS:
        return True
    return (
        db.query(UserAgent)
        .join(AgentCatalog, UserAgent.agent_catalog_id == AgentCatalog.id)
        .filter(UserAgent.user_id == user.id, AgentCatalog.agent_type == agent)
        .first()
        is not None
    )

_MEETING_FRAMING = (
    "\n\nYou're in a one-on-one meeting with this graduate — an open "
    "conversation, not tied to any specific task. Answer their questions "
    "directly and helpfully in your own voice, staying in character. Keep "
    "replies concise and conversational (a few sentences), not essays."
    # Without this, the model answered "I can't see files you sent" even
    # though the submission's content was in its context (live-tested).
    "\n\nYou work inside the Venv platform and have access to what the "
    "graduate submitted: below, under 'most recent submission', is the "
    "actual content of the last work they sent (their files, notes, and "
    "the Mentor's review of it). When they ask about their solution, their "
    "work, or what they sent, answer from that content — name the file and "
    "talk about what's in it. Never say you can't see their files or ask "
    "them to paste it again when it's there. If an earlier reply in this "
    "conversation said you couldn't see it, that was wrong: correct it "
    "plainly. If the section says nothing has been submitted, tell them "
    "that instead."
)


def _shared_context(db: Session, user: User) -> str:
    parts: list[str] = []
    if user.cv_raw_text:
        parts.append(f"Their CV (raw): {user.cv_raw_text[:1500]}")
    ef = user.employee_file
    if ef and ef.summary_text:
        parts.append(f"HR summary so far: {ef.summary_text}")
    project = (
        db.query(Project)
        .filter(Project.user_id == user.id, Project.status == ProjectStatus.ACTIVE)
        .order_by(Project.created_at.desc())
        .first()
    )
    if project:
        parts.append(f"Current project: {project.title} — {project.description}")
        week = (
            db.query(Week)
            .filter(Week.project_id == project.id, Week.status == WeekStatus.ACTIVE)
            .order_by(Week.week_number.desc())
            .first()
        )
        if week:
            parts.append(
                f"Current week {week.week_number}: {week.big_task_title} — "
                f"{week.big_task_description}"
            )
    parts.append(
        _latest_submission_context(db, user)
        or "Their most recent submission: nothing has been submitted yet."
    )
    return "\n".join(parts) if parts else "No CV, project, or history yet."


def _latest_submission_context(db: Session, user: User) -> str | None:
    """What the graduate most recently submitted, and the Mentor's latest
    review of it — so "what did you think of my solution?" in a meeting
    gets an answer about the actual work (docs/TEAM_CHANGES.md #10).
    Before, meeting agents only knew the CV and the project."""
    task = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.submitted_at.isnot(None))
        .order_by(Task.submitted_at.desc())
        .first()
    )
    if task is None:
        return None
    parts = [
        f"Their most recent submission — task \"{task.title}\" "
        f"(status: {task.status.value}):\n{task.description}"
    ]
    if task.github_link:
        parts.append(f"GitHub link: {task.github_link}")
    if task.submission_text:
        parts.append(f"Their notes: {task.submission_text}")
    readable, unreadable = read_submitted_files(task, max_chars_per_file=_FILE_CHARS_FOR_MEETING)
    for filename, text in readable:
        parts.append(f"--- {filename} ---\n{text}")
    if unreadable:
        parts.append("Also attached, but not readable here: " + ", ".join(unreadable))
    review = (
        db.query(Review)
        .filter(
            Review.task_id == task.id,
            Review.agent_type == AgentType.MENTOR,
            Review.kind == ReviewKind.TASK_REVIEW,
        )
        .order_by(Review.created_at.desc())
        .first()
    )
    if review:
        verdict = (review.metrics_json or {}).get("verdict", "?")
        parts.append(f"The Mentor's latest review of it ({verdict}): {review.content}")
    return "\n".join(parts)


def get_history(db: Session, user: User, agent: AgentType) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.agent_type == agent)
        .order_by(ChatMessage.created_at)
        .all()
    )


def send_message(
    db: Session, user: User, agent: AgentType, content: str
) -> ChatMessage:
    """Stores the user's message, generates the agent's reply, stores and
    returns that reply."""
    db.add(
        ChatMessage(
            user_id=user.id,
            agent_type=agent,
            sender_type=SenderType.USER,
            content=content,
        )
    )
    db.commit()

    history = get_history(db, user, agent)
    messages = [
        {
            "role": "assistant" if m.sender_type == SenderType.AGENT else "user",
            "content": m.content,
        }
        for m in history
    ]
    system = PERSONA[agent] + _MEETING_FRAMING + LANGUAGE_RULE + "\n\n" + _shared_context(db, user)

    reply_obj = call_agentic(
        system=system,
        messages=messages,
        tools=[],
        max_tokens=1000,
    )
    reply_text = reply_obj.text or "Sorry, I didn't catch that — could you rephrase?"

    reply = ChatMessage(
        user_id=user.id,
        agent_type=agent,
        sender_type=SenderType.AGENT,
        content=reply_text,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply
