"""
Smoke test for Stage 2's richer task submission (docs/
STAGE2_MEETING_AND_SUBMISSIONS.md): POST /tasks/{id}/submit accepting a
GitHub link, free text, and file/image attachments in any combination;
attachment download with ownership checks; and the Mentor reviewing from
whatever combination was actually submitted — including an image
attachment sent to the model as a real vision content block. Mocked LLM,
real HTTP API, real (temp) disk writes for attachments.

Run: python smoke_test_stage2_submissions.py
"""
import base64
import os
import shutil
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_submissions.db"
)
os.environ["UPLOAD_DIR"] = os.environ.get(
    "UPLOAD_DIR", "./_smoke_test_uploads"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

shutil.rmtree(os.environ["UPLOAD_DIR"], ignore_errors=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def register_and_login(email):
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "hunter2pass", "full_name": "Submission Tester"},
    )
    check(f"register {email}", r.status_code == 201)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def new_in_progress_task(headers, title="Test task"):
    r = client.post("/tasks", json={"title": title, "description": "d", "user_id": "ignored"}, headers=headers)
    check(f"create task '{title}'", r.status_code == 201)
    task_id = r.json()["id"]
    r = client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers)
    check(f"start task '{title}'", r.status_code == 200)
    return task_id


headers = register_and_login("submission-test@example.com")

# --- rejects an empty submission ---
task_id = new_in_progress_task(headers, "empty submission")
r = client.post(f"/tasks/{task_id}/submit", headers=headers, data={})
check("empty submission -> 400", r.status_code == 400)

# --- text-only submission works (no github_link required anymore) ---
task_id = new_in_progress_task(headers, "text only")
r = client.post(
    f"/tasks/{task_id}/submit",
    headers=headers,
    data={"submission_text": "Couldn't get a public repo up in time, but here's what I built: ..."},
)
check("text-only submission -> 200", r.status_code == 200)
check("status moved to submitted", r.json()["status"] == "submitted")
check("submission_text persisted", "Couldn't get a public repo" in r.json()["submission_text"])
check("github_link stayed empty", r.json()["github_link"] is None)

with patch("app.agents.mentor.call_with_tool") as mock_call:
    mock_call.return_value = {
        "tool_name": "submit_review",
        "input": {
            "verdict": "approved",
            "summary": "Reasonable given no repo link.",
            "categories": {"correctness": 3, "code_quality": 3, "testing": 2, "documentation": 3},
            "comments": [],
        },
    }
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
    check("mentor can review a text-only (no github_link) submission", r.status_code == 201)
    sent_prompt = mock_call.call_args.kwargs["messages"][0]["content"]
    check("text-only prompt has no 'Submitted repo' section", "Submitted repo" not in sent_prompt)
    check("text-only prompt includes the graduate's notes", "Couldn't get a public repo" in sent_prompt)

# --- github-link-only submission still works exactly as in Stage 1 ---
task_id = new_in_progress_task(headers, "link only")
r = client.post(
    f"/tasks/{task_id}/submit", headers=headers, data={"github_link": "https://github.com/x/y"}
)
check("github-link-only submission -> 200", r.status_code == 200)
check("github_link persisted", r.json()["github_link"] == "https://github.com/x/y")

# --- file attachment: stored, listed, downloadable, owner-only ---
task_id = new_in_progress_task(headers, "with a file")
r = client.post(
    f"/tasks/{task_id}/submit",
    headers=headers,
    data={"submission_text": "See attached notes"},
    files={"files": ("notes.txt", b"some plain text notes", "text/plain")},
)
check("submission with a file attachment -> 200", r.status_code == 200)
check("one attachment listed", len(r.json()["attachments"]) == 1)
attachment_id = r.json()["attachments"][0]["id"]
check("attachment filename correct", r.json()["attachments"][0]["filename"] == "notes.txt")
check("attachment size correct", r.json()["attachments"][0]["size_bytes"] == len(b"some plain text notes"))

r = client.get(f"/tasks/{task_id}/attachments/{attachment_id}", headers=headers)
check("download attachment -> 200", r.status_code == 200)
check("downloaded content matches upload", r.content == b"some plain text notes")

other_headers = register_and_login("submission-test-2@example.com")
r = client.get(f"/tasks/{task_id}/attachments/{attachment_id}", headers=other_headers)
check("another user can't download this attachment -> 404", r.status_code == 404)

# --- too many files rejected ---
task_id = new_in_progress_task(headers, "too many files")
many_files = [("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(6)]
r = client.post(f"/tasks/{task_id}/submit", headers=headers, data={}, files=many_files)
check("more than 5 files -> 400", r.status_code == 400)

# --- oversized file rejected ---
task_id = new_in_progress_task(headers, "oversized file")
big_content = b"x" * (11 * 1024 * 1024)
r = client.post(
    f"/tasks/{task_id}/submit",
    headers=headers,
    files={"files": ("big.bin", big_content, "application/octet-stream")},
)
check("file over 10MB -> 400", r.status_code == 400)

# --- image attachment goes to the Mentor as a real vision content block ---
task_id = new_in_progress_task(headers, "with an image")
tiny_png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
r = client.post(
    f"/tasks/{task_id}/submit",
    headers=headers,
    files={"files": ("screenshot.png", tiny_png, "image/png")},
)
check("image submission -> 200", r.status_code == 200)

with patch("app.agents.mentor.call_with_tool") as mock_call:
    mock_call.return_value = {
        "tool_name": "submit_review",
        "input": {
            "verdict": "approved",
            "summary": "Screenshot looks right.",
            "categories": {"correctness": 4, "code_quality": 3, "testing": 2, "documentation": 3},
            "comments": [],
        },
    }
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
    check("mentor can review an image-only submission", r.status_code == 201)
    sent_content = mock_call.call_args.kwargs["messages"][0]["content"]
    check("message content is a list (text + image blocks)", isinstance(sent_content, list))
    image_blocks = [b for b in sent_content if b.get("type") == "image"]
    check("exactly one image block sent", len(image_blocks) == 1)
    check(
        "image block carries the actual uploaded bytes, base64-encoded",
        image_blocks[0]["source"]["data"] == base64.b64encode(tiny_png).decode("ascii"),
    )
    check("image media_type preserved", image_blocks[0]["source"]["media_type"] == "image/png")

shutil.rmtree(os.environ["UPLOAD_DIR"], ignore_errors=True)

print("\nAll Stage 2 submission smoke checks passed.")
