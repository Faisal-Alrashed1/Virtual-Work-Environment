from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import AgentType, Review, SenderType, Task, TaskAttachment, TaskMessage, TaskStatus, User
from app.storage import save_attachment
from app.schemas import (
    ReviewOut,
    TaskCreate,
    TaskDetailOut,
    TaskMessageCreate,
    TaskMessageOut,
    TaskOut,
    TaskStatusUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10MB — generous for a screenshot or a small zip


def _get_owned_task(task_id: str, current_user: User, db: Session) -> Task:
    task = db.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=list[TaskOut])
def list_my_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Powers the task board columns (To Do / In Progress / Submitted / Reviewed)."""
    # selectinload: needs_changes/revision_count read each task's reviews —
    # load them all in one extra query instead of one per task.
    return (
        db.query(Task)
        .options(selectinload(Task.reviews))
        .filter(Task.user_id == current_user.id)
        .all()
    )


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manual/admin creation for now, for testing the board end-to-end. Once the
    Manager agent's tool-calling is live, it will call this same path
    internally to assign real tasks.
    """
    task = Task(
        title=payload.title,
        description=payload.description,
        user_id=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Task detail view with its full comment thread."""
    return _get_owned_task(task_id, current_user, db)


@router.patch("/{task_id}/status", response_model=TaskOut)
def update_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, current_user, db)
    task.status = payload.status
    if payload.status == TaskStatus.SUBMITTED:
        # Stamped fresh on every submission (including resubmits after
        # needs_changes) — completed_at (set by the Mentor) is what lateness
        # is actually judged against, see Task.is_late.
        task.submitted_at = datetime.utcnow()
    if payload.github_link is not None:
        task.github_link = payload.github_link
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/submit", response_model=TaskOut)
def submit_task(
    task_id: str,
    github_link: str | None = Form(None),
    submission_text: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stage 2 (docs/STAGE2_MEETING_AND_SUBMISSIONS.md): a submission is a
    GitHub link, free text, file/image attachments, or any mix — at least
    one, not github_link specifically. The older PATCH .../status path
    (github_link-only) still works unchanged for anything still calling
    it; this is the richer alternative the frontend now uses.
    """
    task = _get_owned_task(task_id, current_user, db)

    link = (github_link or "").strip() or None
    text = (submission_text or "").strip() or None
    real_files = [f for f in files if f.filename]

    if not link and not text and not real_files:
        raise HTTPException(
            status_code=400,
            detail="Submit at least a GitHub link, some notes, or a file.",
        )
    if len(real_files) > MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=400, detail=f"Up to {MAX_ATTACHMENTS} files per submission."
        )

    if link:
        task.github_link = link
    if text:
        task.submission_text = text

    for f in real_files:
        content = f.file.read()
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}' is over the {MAX_ATTACHMENT_BYTES // (1024 * 1024)}MB limit.",
            )
        storage_path = save_attachment(task.id, f.filename, content)
        db.add(
            TaskAttachment(
                task_id=task.id,
                filename=f.filename,
                content_type=f.content_type or "application/octet-stream",
                size_bytes=len(content),
                storage_path=storage_path,
            )
        )

    task.status = TaskStatus.SUBMITTED
    task.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}/attachments/{attachment_id}")
def download_attachment(
    task_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streams an attachment back — task-owner only, same as every other
    task endpoint (_get_owned_task 404s a task that isn't the caller's)."""
    task = _get_owned_task(task_id, current_user, db)
    attachment = (
        db.query(TaskAttachment)
        .filter(TaskAttachment.id == attachment_id, TaskAttachment.task_id == task.id)
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(
        attachment.storage_path,
        filename=attachment.filename,
        media_type=attachment.content_type,
    )


@router.post("/{task_id}/messages", response_model=TaskMessageOut, status_code=201)
def post_message(
    task_id: str,
    payload: TaskMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(task_id, current_user, db)
    message = TaskMessage(
        task_id=task.id,
        sender_type=SenderType.AGENT if payload.agent_type else SenderType.USER,
        agent_type=payload.agent_type,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{task_id}/review", response_model=ReviewOut)
def get_task_review(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mentor's review for this task — powers the review view once it exists."""
    task = _get_owned_task(task_id, current_user, db)
    review = (
        db.query(Review)
        .filter(Review.task_id == task.id, Review.agent_type == AgentType.MENTOR)
        .order_by(Review.created_at.desc())
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="No review yet for this task")
    return review
