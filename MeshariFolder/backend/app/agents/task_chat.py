"""
Task-thread chat: who replies when the graduate posts a message on a
specific task (docs/TASK_CHAT.md). The Mentor is the default and does
the day-to-day lifting — working through the task itself, the way a
senior engineer would (mentor.respond_in_thread,
guardrails.MENTOR_TASK_SENIOR_FRAMING). The Manager only handles the big
picture (assigning tasks, project/week questions, end-of-week progress)
and redirects hands-on asks back to the Mentor
(guardrails.MANAGER_DELEGATES_TASK_WORK) rather than answering them.

A graduate can also address a task directly to any *technical* agent on
their own roster — Security Reviewer, Data Reviewer, DevOps, QA
Engineer, UX Reviewer — e.g. "is this deployment config safe?" straight
to DevOps, without waiting for a formal roundtable after submission. HR,
Career Coach, and Technical Writer are deliberately not available here:
HR's job is periodic/behavioral, Career Coach is about career topics,
and Technical Writer is a review-time concern, not a "help me while I'm
working" one — all three stay reachable in the Meeting Room and the
Team Room instead.
"""
from sqlalchemy.orm import Session

from app.agents import manager, meeting, mentor
from app.agents.guardrails import ROLE_BOUNDARY
from app.agents.llm_client import call_agentic
from app.agents.tools import POST_MESSAGE_TOOL
from app.models import AgentType, SenderType, Task, TaskMessage, User

# Agents a graduate can address directly in a task's thread. The default
# three (Manager, Mentor) are always available; the technical roster
# agents need to actually be on the graduate's team first — see
# is_available_for_task, which checks meeting.is_on_users_team.
TASK_CHAT_AGENTS = {
    AgentType.MENTOR,
    AgentType.MANAGER,
    AgentType.SECURITY_REVIEWER,
    AgentType.DATA_REVIEWER,
    AgentType.DEVOPS,
    AgentType.QA_ENGINEER,
    AgentType.UX_REVIEWER,
}

DEFAULT_TASK_CHAT_AGENT = AgentType.MENTOR


def is_available_for_task(db: Session, user: User, agent: AgentType) -> bool:
    """Whether `agent` can be addressed on a task thread at all, for this
    graduate specifically (a roster agent they never added is a 403, same
    as the Meeting Room's gate)."""
    return agent in TASK_CHAT_AGENTS and meeting.is_on_users_team(db, user, agent)


def _history(task: Task) -> list[dict]:
    return [
        {
            "role": "assistant" if m.sender_type == SenderType.AGENT else "user",
            "content": m.content,
        }
        for m in task.messages
    ]


def _roster_agent_reply(db: Session, task: Task, agent_type: AgentType) -> TaskMessage:
    """A technical roster agent (Security Reviewer/Data Reviewer/DevOps)
    addressed directly about this task. They have no task-flow module of
    their own, so this reuses their Meeting Room persona
    (meeting.PERSONA) plus the task's context — the same pattern
    manager.respond_in_thread and mentor.respond_in_thread follow."""
    system = (
        meeting.PERSONA[agent_type]
        + f"\n\nThe graduate is asking about a specific task they're working on.\n"
        + f"Task: {task.title} — {task.description}\nStatus: {task.status.value}."
        + ROLE_BOUNDARY
    )
    reply = call_agentic(
        system=system,
        messages=_history(task) or [{"role": "user", "content": "(no messages yet)"}],
        tools=[POST_MESSAGE_TOOL],
    )
    content = next(
        (c.input["content"] for c in reply.tool_calls if c.name == "post_message"), None
    )
    content = content or reply.text or "Got it — let me know if you need anything else."

    message = TaskMessage(
        task_id=task.id, sender_type=SenderType.AGENT, agent_type=agent_type, content=content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def reply_in_thread(db: Session, task: Task, user: User, agent_type: AgentType) -> TaskMessage:
    """Routes to whichever agent the graduate is addressing. Caller (the
    router) must already have checked is_available_for_task."""
    if agent_type == AgentType.MANAGER:
        return manager.respond_in_thread(db, task, user)
    if agent_type == AgentType.MENTOR:
        return mentor.respond_in_thread(db, task, user)
    return _roster_agent_reply(db, task, agent_type)
