"""
Smoke test for the Mentor reading uploaded files (docs/TEAM_CHANGES.md,
fix #1). Before, mentor.review_task put only attachment *names* in the
prompt ("not previewable here, judge by name/context"), so it reviewed
code it never saw. Now text/code/notebook content goes into the prompt
via app/agents/submission_files.py; unreadable files (zip, binaries) are
named as unopened; images still go in as vision blocks, unchanged.

Captures the exact prompt the Mentor sends — mocked LLM, no API key.

Run: python smoke_test_mentor_file_reading.py
"""
import json
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_mentor_file_reading.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskAttachment, TaskStatus, User  # noqa: E402
from app.storage import save_attachment  # noqa: E402
from app.agents import mentor  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


MENTOR_RESULT = {
    "tool_name": "submit_review",
    "input": {
        "verdict": "needs_changes",
        "summary": "DB_PASSWORD is hardcoded in app.py.",
        "categories": [
            {"key": "correctness", "label": "Correctness", "score": 3},
            {"key": "code_quality", "label": "Code quality", "score": 2},
            {"key": "testing", "label": "Testing", "score": 1},
            {"key": "documentation", "label": "Documentation", "score": 2},
        ],
        "comments": [],
    },
}

email = "mentor-files@example.com"
r = client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Mentor Files"})
check("register", r.status_code == 201)

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
task = Task(user_id=user.id, title="Build an API", description="d", status=TaskStatus.SUBMITTED)
db.add(task)
db.commit()
db.refresh(task)

notebook = json.dumps(
    {
        "cells": [
            {"cell_type": "markdown", "source": ["# Notes"]},
            {"cell_type": "code", "source": ["model.fit(X_train, y_train)\n"]},
        ]
    }
).encode()
uploads = [
    ("app.py", "text/x-python", b'DB_PASSWORD = "SuperSecret123!"\n'),
    ("analysis.ipynb", "application/json", notebook),
    ("project.zip", "application/zip", b"PK\x03\x04\x00\x00binary-archive"),
    ("screen.png", "image/png", b"\x89PNG\r\n\x1a\n\x00\x00fake"),
]
for filename, content_type, content in uploads:
    db.add(
        TaskAttachment(
            task_id=task.id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=save_attachment(task.id, filename, content),
        )
    )
db.commit()
db.refresh(task)

with patch("app.agents.mentor.call_with_tool", return_value=MENTOR_RESULT) as mock_call:
    mentor.review_task(db, task, user)
content = mock_call.call_args.kwargs["messages"][0]["content"]
text = "\n".join(b["text"] for b in content if b["type"] == "text")
images = [b for b in content if b["type"] == "image"]

check("uploaded code's CONTENT reaches the Mentor, not just its name", "SuperSecret123!" in text)
check("notebook code cells reach the Mentor", "model.fit(X_train, y_train)" in text)
check("notebook markdown is left out", "# Notes" not in text)
check("zip is named as not openable", "can't be opened here" in text and "project.zip" in text)
check("zip bytes never reach the prompt", "binary-archive" not in text)
check("the old 'judge by name' instruction is gone", "judge by name" not in text)
check("images still go in as a vision block (unchanged)", len(images) == 1)
check("the image isn't listed as 'can't be opened'", "screen.png" not in text.split("can't be opened here")[-1])
db.close()

print("\nAll Mentor file-reading smoke checks passed.")
