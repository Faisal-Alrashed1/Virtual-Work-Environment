"""
Smoke test for the Meeting Room seeing the graduate's latest submission
(docs/TEAM_CHANGES.md #10) and the shared language rule (#11). Before,
meeting agents only had the CV, HR summary, and project/week, so "what
did you think of my solution?" got a guess.

Captures the exact system prompt — mocked LLM, no API key.

Run: python smoke_test_meeting_sees_submission.py
"""
import os
from datetime import datetime
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_meeting_sees_submission.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentType, Review, ReviewKind, Task, TaskAttachment, TaskStatus, User  # noqa: E402
from app.storage import save_attachment  # noqa: E402
from app.agents.llm_client import AgentReply  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


email = "meeting-sees@example.com"
client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "M"})
tok = client.post("/auth/login", data={"username": email, "password": "hunter2pass"}).json()["access_token"]
headers = {"Authorization": f"Bearer {tok}"}


def meeting_system_prompt(agent="mentor", text="what did you think of my solution?"):
    with patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="ok")) as mock_call:
        r = client.post(f"/meeting/{agent}", json={"content": text}, headers=headers)
    assert r.status_code == 201, r.text
    return mock_call.call_args.kwargs["system"]


system = meeting_system_prompt()
check("nothing submitted yet: no submission section", "most recent submission" not in system)
check("the language rule is in every meeting prompt", "Saudi Najdi dialect" in system)

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
older = Task(user_id=user.id, title="Old task", description="d", status=TaskStatus.REVIEWED,
             submission_text="OLD-NOTES", submitted_at=datetime(2026, 1, 1))
latest = Task(user_id=user.id, title="Inspect the crack dataset", description="Catalog the images.",
              status=TaskStatus.IN_PROGRESS, submission_text="Here is my solution.", submitted_at=datetime(2026, 2, 1))
db.add_all([older, latest])
db.commit()
db.refresh(latest)
db.add(
    TaskAttachment(
        task_id=latest.id, filename="solution.py", content_type="text/x-python", size_bytes=20,
        storage_path=save_attachment(latest.id, "solution.py", b"def convert_pdf(): pass\n"),
    )
)
db.add(
    Review(user_id=user.id, task_id=latest.id, agent_type=AgentType.MENTOR, kind=ReviewKind.TASK_REVIEW,
           content="This file converts documents; it doesn't catalog the dataset.",
           metrics_json={"verdict": "needs_changes", "categories": [], "comments": []})
)
db.commit()
db.close()

for agent in ("mentor", "manager", "hr"):
    system = meeting_system_prompt(agent)
    check(f"{agent}: sees the latest submitted task", 'task "Inspect the crack dataset"' in system)
    check(f"{agent}: sees the uploaded file's content", "def convert_pdf" in system)
    check(f"{agent}: sees the Mentor's latest review of it", "needs_changes" in system and "converts documents" in system)
check("only the latest submission, not older ones", "OLD-NOTES" not in system)

print("\nAll meeting-sees-submission smoke checks passed.")
