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

The Team Room (bottom of this file, docs/TEAM_ROOM.md) is this same
Meeting Room's *shared* mode: one thread per user instead of one per
(user, agent), where the whole team and the graduate talk together.
Every message the graduate sends is routed to whichever single teammate
fits best (route_team_message) rather than every agent replying at once —
but the thread itself shows everyone who has spoken, so past replies from
other agents stay visible and later replies can refer to them.
"""
from sqlalchemy.orm import Session

from app.agents import hr, manager, mentor
from app.agents.guardrails import MANAGER_DELEGATES_TASK_WORK, ROLE_BOUNDARY
from app.agents.llm_client import call_agentic, call_with_tool
from app.models import (
    AgentCatalog,
    AgentType,
    ChatMessage,
    Project,
    ProjectStatus,
    SenderType,
    TeamMessage,
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
    AgentType.QA_ENGINEER: (
        "You are the QA Engineer at Venv, helping a recent graduate think "
        "through testing — what to actually test, edge cases they might "
        "have missed, how to structure a test suite. Be concrete: name "
        "the specific case or scenario, don't just say 'add more tests.'"
    ),
    AgentType.UX_REVIEWER: (
        "You are the UX Reviewer at Venv, helping a recent graduate think "
        "through interface and interaction quality — clarity, "
        "accessibility, what a real user would find confusing. Be "
        "specific about what you'd actually change and why, not generic "
        "design-principle lectures."
    ),
    AgentType.TECHNICAL_WRITER: (
        "You are the Technical Writer at Venv, helping a recent graduate "
        "with documentation and written communication — READMEs, PR "
        "descriptions, code comments, commit messages. Be concrete: "
        "point at the actual sentence or section that needs work and say "
        "what to write instead, not generic 'be clearer' advice."
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


def team_roster(db: Session, user: User) -> list[AgentType]:
    """Every agent on the graduate's team, defaults first — the Team
    Room's cast of characters (docs/TEAM_ROOM.md)."""
    rows = (
        db.query(AgentCatalog.agent_type)
        .join(UserAgent, UserAgent.agent_catalog_id == AgentCatalog.id)
        .filter(UserAgent.user_id == user.id)
        .all()
    )
    return [AgentType.MANAGER, AgentType.MENTOR, AgentType.HR] + [row[0] for row in rows]

_MEETING_FRAMING = (
    "\n\nYou're in a one-on-one meeting with this graduate — an open "
    "conversation, not tied to any specific task. Answer their questions "
    "directly and helpfully in your own voice, staying in character. Keep "
    "replies concise and conversational (a few sentences), not essays."
    + ROLE_BOUNDARY
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
    # The Manager redirects hands-on task asks to the Mentor here too, not
    # just in a task thread — "ask the manager for a small task" is the
    # same overreach whether it happens in the Meeting Room or on a task.
    delegate = MANAGER_DELEGATES_TASK_WORK if agent == AgentType.MANAGER else ""
    system = PERSONA[agent] + _MEETING_FRAMING + delegate + "\n\n" + _shared_context(db, user)

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


# ---------------------------------------------------------------------------
# Team Room — the Meeting Room's shared mode (docs/TEAM_ROOM.md): one
# thread per user (TeamMessage) instead of one per (user, agent), where the
# graduate talks to their whole team at once. Each graduate message is
# routed to whichever single teammate fits best (a cheap small-tier tool
# call), rather than every agent replying — a genuinely shared room reads
# as one conversation, not a wall of simultaneous answers. The chosen
# agent still sees everyone's past turns, so it can pick up on what a
# teammate said earlier.
# ---------------------------------------------------------------------------

ROUTE_TOOL_NAME = "route_to_agent"


def _route_tool(roster: list[AgentType]) -> dict:
    return {
        "name": ROUTE_TOOL_NAME,
        "description": (
            "Pick the single team member best placed to reply to the "
            "graduate's latest message in the Team Room."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": [a.value for a in roster],
                    "description": "Which team member should reply.",
                },
            },
            "required": ["agent"],
        },
    }


def _router_system(roster: list[AgentType]) -> str:
    names = ", ".join(a.value for a in roster)
    return (
        "You are routing messages in Venv's Team Room, a shared chat where a "
        f"graduate talks with their whole team at once: {names}. Given the "
        "conversation so far, decide which ONE team member is best placed to "
        "reply to the graduate's latest message — whichever one it's actually "
        "their job to answer. Default to the Manager only for something "
        "genuinely about the project or team as a whole; prefer a specific "
        "specialist whenever the message is about their particular area "
        "(code/review questions -> Mentor, growth/behavior -> HR, security -> "
        "Security Reviewer, and so on)."
    )


def get_team_history(db: Session, user: User) -> list[TeamMessage]:
    return (
        db.query(TeamMessage)
        .filter(TeamMessage.user_id == user.id)
        .order_by(TeamMessage.created_at)
        .all()
    )


def _team_thread_messages(history: list[TeamMessage]) -> list[dict]:
    """Every past turn as one role-tagged sequence, agent replies labeled
    by speaker inline (there's no per-agent 'role' in a chat completion,
    so the label is how a reply from one agent lets a later agent — or
    the router — know who already said what)."""
    return [
        {
            "role": "assistant" if m.sender_type == SenderType.AGENT else "user",
            "content": f"[{m.agent_type.value}] {m.content}" if m.agent_type else m.content,
        }
        for m in history
    ]


def _choose_responder(db: Session, user: User, roster: list[AgentType], thread: list[dict]) -> AgentType:
    """Best-effort: a routing failure never blocks the room, it just falls
    back to the Manager, same spirit as roundtable.py's per-agent
    best-effort turns."""
    try:
        result = call_with_tool(
            system=_router_system(roster),
            messages=thread,
            tools=[_route_tool(roster)],
            force_tool=ROUTE_TOOL_NAME,
            tier="small",
        )
        chosen = AgentType(result["input"]["agent"])
        return chosen if chosen in roster else AgentType.MANAGER
    except Exception:
        return AgentType.MANAGER


def send_team_message(db: Session, user: User, content: str) -> TeamMessage:
    """Stores the graduate's message, routes it to whichever teammate fits,
    generates and stores that agent's reply, returns it."""
    db.add(TeamMessage(user_id=user.id, sender_type=SenderType.USER, content=content))
    db.commit()

    roster = team_roster(db, user)
    thread = _team_thread_messages(get_team_history(db, user))
    chosen = _choose_responder(db, user, roster, thread)

    names = ", ".join(a.value for a in roster)
    delegate = MANAGER_DELEGATES_TASK_WORK if chosen == AgentType.MANAGER else ""
    system = (
        PERSONA[chosen]
        + "\n\nYou're in the Team Room — a shared conversation with the "
        f"graduate and the rest of the team ({names}), not a private chat. "
        "Other teammates may have spoken earlier in this thread (their turns "
        "are labeled by who said them); you can refer to what they said. "
        "Reply only as yourself, in your own voice — don't speak for anyone "
        "else. Keep it concise and conversational."
        + delegate
        + ROLE_BOUNDARY
        + "\n\n"
        + _shared_context(db, user)
    )
    reply_obj = call_agentic(system=system, messages=thread, tools=[], max_tokens=1000)
    reply_text = reply_obj.text or "Sorry, I didn't catch that — could you rephrase?"

    reply = TeamMessage(
        user_id=user.id, sender_type=SenderType.AGENT, agent_type=chosen, content=reply_text
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply
