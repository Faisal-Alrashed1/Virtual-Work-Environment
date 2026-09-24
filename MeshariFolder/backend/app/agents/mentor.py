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
from app.agents.llm_client import call_with_tool
from app.agents.submission_files import read_submitted_files
from app.agents.tools import SUBMIT_REVIEW_TOOL
from app.models import AgentType, Review, ReviewKind, SenderType, Task, TaskMessage, TaskStatus, User
from app.storage import read_attachment_base64

SYSTEM_PROMPT = (
    "You are the Mentor at Venv, reviewing a recent graduate's submitted "
    "work. Be specific and constructive: point at what's actually in the "
    "repo, the notes they left, or the images/files they attached — not "
    "generic advice. Only judge files whose content you were actually "
    "shown — if a file couldn't be opened, say so instead of guessing "
    "what's in it. You can't approve work you haven't seen: if the "
    "deliverable itself isn't in what you were shown (only a file you "
    "couldn't open, or notes describing work without the work), use "
    "'needs_changes' and say what's missing. Score each rubric category 1-5. Use 'needs_changes' "
    "only when something genuinely blocks the task's goal — minor gaps "
    "(missing tests, thin docs) can still be 'approved' with a comment "
    "about what to improve next time, the way a real early-career review "
    "would handle it."
)


def review_task(db: Session, task: Task, user: User) -> Review:
    images = [a for a in task.attachments if a.content_type.startswith("image/")]
    image_names = {a.filename for a in images}
    # Uploaded code/text/notebooks go in as their actual content. Before
    # this, only their names did (with "judge by name/context"), so the
    # Mentor reviewed code it never saw — in a live test it missed a
    # hardcoded password in a file it had "reviewed".
    readable_files, unreadable = read_submitted_files(task)
    unreadable_files = [name for name in unreadable if name not in image_names]

    if not task.github_link and not task.submission_text and not task.attachments:
        raise ValueError("Task has no submission to review yet.")

    # Only files that can't be opened (a PDF, a zip...) and nothing else:
    # there's no work to look at. Asking the model anyway is what made it
    # invent a whole review — in a live test it "approved" a CV PDF as a
    # finished project setup with 5/5. Decide this in code instead.
    if not (task.github_link or task.submission_text or readable_files or images):
        return _save_review(db, task, user, _not_reviewable(unreadable_files))

    parts = [f"Task assigned: {task.title}\n{task.description}\n"]
    if task.github_link:
        parts.append(f"Submitted repo:\n{fetch_repo_context(task.github_link)}\n")
    if task.submission_text:
        parts.append(f"Graduate's own notes on this submission:\n{task.submission_text}\n")
    for filename, text in readable_files:
        parts.append(f"--- {filename} (submitted file) ---\n{text}\n")
    if unreadable_files:
        parts.append(
            "Also submitted, but can't be opened here (don't guess at their "
            "contents): " + ", ".join(unreadable_files) + "\n"
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
    return _save_review(db, task, user, result["input"])


def _not_reviewable(unreadable_files: list[str]) -> dict:
    """A needs_changes review with no rubric scores — nothing was scored,
    so there's nothing to average (dashboard.py and the growth view both
    skip reviews without categories)."""
    return {
        "verdict": "needs_changes",
        "summary": (
            "I couldn't review this submission: I can't open "
            + ", ".join(unreadable_files)
            + ". Only code/text files, notebooks, images, notes, or a GitHub "
            "link can be reviewed here, and nothing I can see shows the task "
            "was done, so I can't approve it yet. Please upload the actual "
            "work (e.g. your .py files and requirements.txt) or link a public "
            "GitHub repo, then resubmit."
        ),
        "categories": [],
        "comments": [],
        "not_reviewable": True,
    }


def _save_review(db: Session, task: Task, user: User, data: dict) -> Review:
    metrics = {
        "verdict": data["verdict"],
        "categories": data["categories"],
        "comments": data["comments"],
    }
    if data.get("not_reviewable"):
        metrics["not_reviewable"] = True

    review = Review(
        user_id=user.id,
        task_id=task.id,
        week_id=task.week_id,
        agent_type=AgentType.MENTOR,
        kind=ReviewKind.TASK_REVIEW,
        content=data["summary"],
        metrics_json=metrics,
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
