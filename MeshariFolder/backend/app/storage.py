"""
Local disk storage for task submission attachments
(docs/STAGE2_MEETING_AND_SUBMISSIONS.md). Dev-scope on purpose: files
live under settings.upload_dir on local disk, not cloud storage — fine
for a bootcamp project on one box, would need swapping out (S3 or
similar) before any multi-instance deployment. Everything that touches a
real file goes through here so that swap is one file, not scattered
open()/os.path calls across routers and agents — same reasoning as
llm_client.py being the one place that knows about the Anthropic SDK.
"""
import base64
import os
import uuid

from app.config import settings


def save_attachment(task_id: str, filename: str, content: bytes) -> str:
    """Writes content to disk under a per-task directory and returns the
    storage path (relative to the working directory) to record on the
    TaskAttachment row. Filenames are prefixed with a random hex id so two
    uploads of the same filename never collide."""
    task_dir = os.path.join(settings.upload_dir, "tasks", task_id)
    os.makedirs(task_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(task_dir, safe_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def read_attachment(storage_path: str) -> bytes:
    with open(storage_path, "rb") as f:
        return f.read()


def read_attachment_base64(storage_path: str) -> str:
    """For image attachments going into a vision-capable review prompt —
    see mentor.py's review_task."""
    return base64.b64encode(read_attachment(storage_path)).decode("ascii")
