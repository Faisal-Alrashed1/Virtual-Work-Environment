"""
Mentor agent. Reads a submitted task's submission — a GitHub link, free
text, image/file attachments, or any mix (docs/
STAGE2_MEETING_AND_SUBMISSIONS.md) — writes a structured Review
(metrics_json holds verdict + rubric categories + inline comments — see
tools.SUBMIT_REVIEW_TOOL for the exact contract, matching
frontend/src/lib/reviews.ts's proposed shape), posts a summary message in
the task thread, and moves the task to 'reviewed' — per agents/README.md,
that transition is the Mentor's job, not the graduate's.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.github_client import fetch_repo_context
from app.agents.guardrails import MENTOR_TASK_SENIOR_FRAMING, ROLE_BOUNDARY
from app.agents.llm_client import call_agentic, call_with_tool
from app.agents.rubric import RUBRIC_VERSION, apply_rubric_rules, system_prompt
from app.agents.tools import POST_MESSAGE_TOOL, SUBMIT_REVIEW_TOOL
from app.models import AgentType, Review, ReviewKind, SenderType, Task, TaskMessage, TaskStatus, User
from app.storage import read_attachment_base64

# The rubric, anchors, verdict rule and review style live in agents/rubric.py
# (docs/MENTOR_RUBRIC.md) so the team can read and tune them in one place.
SYSTEM_PROMPT = system_prompt()


def _previous_feedback(task: Task) -> str | None:
    """What the Mentor asked for last time, if the task was bounced. Without
    this a resubmission is reviewed blind: the Mentor can't check its own
    requests were met, and tends to invent new ones (an endless bounce)."""
    reviews = sorted(
        (r for r in task.reviews if r.kind == ReviewKind.TASK_REVIEW),
        key=lambda r: r.created_at,
    )
    if not reviews or (reviews[-1].metrics_json or {}).get("verdict") != "needs_changes":
        return None
    last = reviews[-1]
    lines = [f"Your previous review asked for changes.\nSummary: {last.content}"]
    for c in (last.metrics_json or {}).get("comments", []):
        if isinstance(c, dict):
            lines.append(f"- [{c.get('category')}] {c.get('content')}")
        else:  # a model that returned plain strings
            lines.append(f"- {c}")
    return "\n".join(lines)


def _context_line(task: Task, user: User, previous: str | None) -> str:
    bits = [f"Graduate's track: {user.track.value}."]
    if task.week is not None:
        bits.append(f"Program week: {task.week.week_number}.")
    revisions = sum(
        1 for r in task.reviews
        if r.kind == ReviewKind.TASK_REVIEW and (r.metrics_json or {}).get("verdict") == "needs_changes"
    )
    bits.append(f"This is revision {revisions + 1} of this task." if previous else "This is the first submission of this task.")
    return " ".join(bits)


def review_task(db: Session, task: Task, user: User) -> Review:
    images = [a for a in task.attachments if a.content_type.startswith("image/")]
    other_files = [a for a in task.attachments if not a.content_type.startswith("image/")]

    if not task.github_link and not task.submission_text and not task.attachments:
        raise ValueError("Task has no submission to review yet.")

    previous = _previous_feedback(task)
    parts = [f"Task assigned: {task.title}\n{task.description}\n", _context_line(task, user, previous) + "\n"]
    if previous:
        parts.append(previous + "\n")
    if task.github_link:
        parts.append(f"Submitted repo:\n{fetch_repo_context(task.github_link)}\n")
    if task.submission_text:
        parts.append(f"Graduate's own notes on this submission:\n{task.submission_text}\n")
    if other_files:
        parts.append(
            "Other files submitted (not previewable here, judge by name/"
            "context): " + ", ".join(a.filename for a in other_files) + "\n"
        )
    if images:
        parts.append(f"{len(images)} image(s) submitted — shown below.\n")
    parts.append("Submit your review now via the submit_review tool.")
    text_prompt = "\n".join(parts)

    if images:
        # Vision: images go in as real content blocks alongside the text,
        # not just named in the prompt — the Mentor can actually look at a
        # submitted screenshot, not just know one exists.
        content: list[dict] = [{"type": "text", "text": text_prompt}]
        for image in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.content_type,
                        "data": read_attachment_base64(image.storage_path),
                    },
                }
            )
        message_content: str | list[dict] = content
    else:
        message_content = text_prompt

    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message_content}],
        tools=[SUBMIT_REVIEW_TOOL],
        force_tool="submit_review",
        max_tokens=2000,
    )
    data, verdict_adjusted = apply_rubric_rules(result["input"])

    review = Review(
        user_id=user.id,
        task_id=task.id,
        week_id=task.week_id,
        agent_type=AgentType.MENTOR,
        kind=ReviewKind.TASK_REVIEW,
        content=data["summary"],
        metrics_json={
            "verdict": data["verdict"],
            "categories": data["categories"],
            "comments": data["comments"],
            # Traceability ("how was this decided?"): which rubric produced it,
            # and whether the verdict had to be brought in line with the scores.
            "rubric_version": RUBRIC_VERSION,
            "verdict_adjusted": verdict_adjusted,
        },
    )
    db.add(review)

    # Iterative review (STAGE1_PRODUCT_FLOW.md): a task isn't done until the
    # Mentor is satisfied. 'approved' completes it; 'needs_changes' bounces
    # it back to in_progress so the graduate can revise and resubmit,
    # rather than dead-ending in 'reviewed' either way.
    if data["verdict"] == "approved":
        task.status = TaskStatus.REVIEWED
        task.completed_at = datetime.utcnow()
    else:
        task.status = TaskStatus.IN_PROGRESS
    db.add(task)

    db.add(
        TaskMessage(
            task_id=task.id,
            sender_type=SenderType.AGENT,
            agent_type=AgentType.MENTOR,
            content=data["summary"],
        )
    )
    db.commit()
    db.refresh(review)
    return review


def respond_in_thread(db: Session, task: Task, user: User) -> TaskMessage:
    """Replies in a task's comment thread — the Mentor's day-to-day presence
    on the task itself, working through it with the graduate the way a
    senior engineer would (guardrails.MENTOR_TASK_SENIOR_FRAMING). Separate
    from review_task's formal, structured review once they actually submit.
    Called after the graduate posts a message via POST /tasks/{id}/messages,
    when they're addressing the Mentor — the default in-task agent as of
    docs/TASK_CHAT.md, routed through agents/task_chat.py."""
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
        + f"Status: {task.status.value}."
        + MENTOR_TASK_SENIOR_FRAMING
        + ROLE_BOUNDARY
    )
    reply = call_agentic(
        system=system,
        messages=history or [{"role": "user", "content": "(no messages yet)"}],
        tools=[POST_MESSAGE_TOOL],
    )

    content = next(
        (c.input["content"] for c in reply.tool_calls if c.name == "post_message"), None
    )
    content = content or reply.text or "Tell me a bit more about where you're stuck — happy to work through it with you."

    message = TaskMessage(
        task_id=task.id,
        sender_type=SenderType.AGENT,
        agent_type=AgentType.MENTOR,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
