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

from app.agents import coach , hr, manager, mentor 
from app.agents.llm_client import call_agentic
from app.models import (
    AgentCatalog,
    AgentType,
    ChatMessage,
    Project,
    ProjectStatus,
    SenderType,
    User,
    UserAgent,
    Week,
    WeekStatus,
)

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
    AgentType.CAREER_COACH: coach.SYSTEM_PROMPT ,
    
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
    return "\n".join(parts) if parts else "No CV, project, or history yet."


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
shared_context = _shared_context(db, user)

if agent == AgentType.CAREER_COACH:
    shared_context += "\n\n" + coach.build_context(db, user)

system = PERSONA[agent] + _MEETING_FRAMING + "\n\n" + shared_context

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
