"""
Smoke test for the Manager seeing the submission when it replies in a task
thread (docs/TEAM_CHANGES.md, fix #3). Before, manager.respond_in_thread's
prompt had the task title/status and the thread, but nothing about what
was submitted — not even file names — so "is my app.py okay?" got a guess.

Captures the exact system prompt sent to the model — mocked LLM, no key.

Run: python smoke_test_manager_sees_submission.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_manager_sees_submission.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskAttachment, TaskStatus, User  # noqa: E402
from app.storage import save_attachment  # noqa: E402
from app.agents import manager  # noqa: E402
from app.agents.llm_client import AgentReply  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


email = "manager-sees@example.com"
r = client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "M"})
check("register", r.status_code == 201)

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
task = Task(user_id=user.id, title="Build an API", description="d", status=TaskStatus.IN_PROGRESS)
db.add(task)
db.commit()
db.refresh(task)


def manager_system_prompt():
    with patch("app.agents.manager.call_agentic", return_value=AgentReply(text="ok")) as mock_call:
        manager.respond_in_thread(db, task, user)
    return mock_call.call_args.kwargs["system"]


# --- before anything is submitted ---
system = manager_system_prompt()
check("before submitting: the Manager knows nothing was submitted", "Nothing has been submitted" in system)

# --- after submitting a link, notes, a code file, a long file, and a zip ---
long_file = ("# filler line\n" * 400).encode()  # ~5,600 chars
for filename, content_type, content in [
    ("app.py", "text/x-python", b'DB_PASSWORD = "SuperSecret123!"\n'),
    ("long.py", "text/x-python", long_file),
    ("project.zip", "application/zip", b"PK\x03\x04\x00\x00binary"),
]:
    db.add(
        TaskAttachment(
            task_id=task.id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=save_attachment(task.id, filename, content),
        )
    )
task.github_link = "https://github.com/example/api"
task.submission_text = "Added the lookup endpoint."
task.status = TaskStatus.SUBMITTED
db.commit()
db.refresh(task)

with patch("app.agents.github_client.httpx.Client") as mock_http:
    system = manager_system_prompt()
check("after submitting: uploaded file CONTENT reaches the Manager", "SuperSecret123!" in system)
check("after submitting: the GitHub link is there", "https://github.com/example/api" in system)
check("after submitting: the notes are there", "Added the lookup endpoint." in system)
check("after submitting: the zip is named as not readable", "project.zip" in system and "not readable here" in system)
check("long files are cut to the Manager's smaller slice", "(truncated)" in system and system.count("# filler line") < 150)
check("no GitHub request is made for a thread reply", mock_http.call_count == 0)
db.close()

print("\nAll Manager-sees-submission smoke checks passed.")
