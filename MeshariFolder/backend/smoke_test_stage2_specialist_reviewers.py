"""
Unit-level smoke test for the Security Reviewer / Data Reviewer
(security_reviewer.py, data_reviewer.py) and the shared
submission_files.py they read uploads through: real content (uploaded
files + GitHub repo files) goes into the prompt, the files actually read
are recorded on the stored Review, and when nothing readable was
submitted no LLM call is made — the Review is stored as 'not_reviewed'
instead of a guessed 'clear'.

Tests review_task directly as a unit (same pattern
smoke_test_stage2_co_reviews.py uses for co_reviewers.py), not through
the roundtable — smoke_test_stage2_roundtable.py covers how they plug
into the full mentor-review flow. github_client's network calls are
mocked (list_repo_paths/fetch_file_content) so the outcome depends only
on this code, not on a public repo's current content or GitHub's rate
limit.

Run: python smoke_test_stage2_specialist_reviewers.py
"""
import json
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_specialist_reviewers.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskAttachment, TaskStatus, User  # noqa: E402
from app.storage import save_attachment  # noqa: E402
from app.agents import data_reviewer, security_reviewer  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def register(email):
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "hunter2pass", "full_name": "Specialist Tester"},
    )
    check(f"register {email}", r.status_code == 201)


def make_task(email, *, github_link=None, submission_text=None, files=()):
    """files: [(filename, content_type, bytes)] — saved through the real
    storage path, same as POST /tasks/{id}/submit does."""
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    task = Task(
        user_id=user.id,
        title="review me",
        description="A task worth reviewing.",
        status=TaskStatus.SUBMITTED,
        github_link=github_link,
        submission_text=submission_text,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    for filename, content_type, content in files:
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
    tid = task.id
    db.close()
    return tid


def load(email, task_id):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    task = db.get(Task, task_id)
    return db, user, task


APP_PY = b'DB_PASSWORD = "SuperSecret123!"\nrows = conn.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
NOTEBOOK = json.dumps(
    {
        "cells": [
            {"cell_type": "markdown", "source": ["# Training notebook"]},
            {
                "cell_type": "code",
                "source": [
                    "X_scaled = StandardScaler().fit_transform(X)\n",
                    "X_train, X_test = train_test_split(X_scaled)\n",
                ],
            },
        ]
    }
).encode()
ZIP_BYTES = b"PK\x03\x04\x00\x00binary-archive"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00fake"

SECURITY_RESULT = {
    "tool_name": "submit_security_review",
    "input": {
        "verdict": "concerns_found",
        "risk_level": "high",
        "findings": [
            {
                "category": "hardcoded_secret",
                "severity": "high",
                "description": "DB_PASSWORD is hardcoded in app.py.",
                "recommendation": "Move it to an environment variable.",
            }
        ],
        "summary": "Reviewed app.py: DB_PASSWORD is hardcoded.",
    },
}
DATA_RESULT = {
    "tool_name": "submit_data_review",
    "input": {
        "verdict": "concerns_found",
        "risk_level": "high",
        "findings": [
            {
                "category": "data_leakage",
                "severity": "high",
                "description": "The scaler is fit on all of X before the split.",
                "recommendation": "Split first, then fit the scaler on the training set only.",
            }
        ],
        "summary": "Reviewed analysis.ipynb: the scaler leaks test data.",
    },
}


# --- 1. Uploaded code file is actually read (the original gap). ---
email = "sec-upload@example.com"
register(email)
tid = make_task(email, submission_text="See attached.", files=[("app.py", "text/x-python", APP_PY)])
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool", return_value=SECURITY_RESULT) as mock_call:
    review = security_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("security: uploaded file's CONTENT is in the prompt, not just its name", "SuperSecret123!" in prompt)
check("security: reviewed_files records app.py", review.metrics_json["reviewed_files"] == ["app.py"])
check("security: findings stored", review.metrics_json["findings"][0]["category"] == "hardcoded_secret")
db.close()


# --- 2. Notes only -> 'not_reviewed', and no LLM call at all. ---
email = "sec-notes-only@example.com"
register(email)
tid = make_task(email, submission_text="I fixed the login bug.")
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool") as mock_call:
    review = security_reviewer.review_task(db, task, user)
check("security: notes-only submission makes no LLM call", mock_call.call_count == 0)
check("security: notes-only submission is 'not_reviewed', not 'clear'", review.metrics_json["verdict"] == "not_reviewed")
check("security: not_reviewed has no risk level", review.metrics_json["risk_level"] is None)
check("security: not_reviewed message tells the graduate what to upload", "Upload" in review.content)
db.close()


# --- 3. Only unreadable files -> 'not_reviewed', naming them. ---
email = "sec-unreadable@example.com"
register(email)
tid = make_task(
    email,
    files=[("project.zip", "application/zip", ZIP_BYTES), ("screen.png", "image/png", PNG_BYTES)],
)
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool") as mock_call:
    review = security_reviewer.review_task(db, task, user)
check("security: zip + image only makes no LLM call", mock_call.call_count == 0)
check("security: zip + image only is 'not_reviewed'", review.metrics_json["verdict"] == "not_reviewed")
check(
    "security: unreadable_files names both files",
    set(review.metrics_json["unreadable_files"]) == {"project.zip", "screen.png"},
)
check("security: message names the file it couldn't open", "project.zip" in review.content)
db.close()


# --- 4. Mixed readable + unreadable -> reviewed, and told what it can't see. ---
email = "sec-mixed@example.com"
register(email)
tid = make_task(
    email,
    files=[("app.py", "text/x-python", APP_PY), ("project.zip", "application/zip", ZIP_BYTES)],
)
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool", return_value=SECURITY_RESULT) as mock_call:
    review = security_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("security: mixed upload is reviewed", mock_call.call_count == 1)
check("security: prompt says which file could NOT be read", "Could NOT be read" in prompt and "project.zip" in prompt)
check("security: zip's bytes never reach the prompt", "binary-archive" not in prompt)
db.close()


# --- 5. GitHub link -> dependency files + the exposed-.env check. ---
email = "sec-github@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/demo-repo")
db, user, task = load(email, tid)
with patch(
    "app.agents.security_reviewer.list_repo_paths",
    return_value=[".env", "requirements.txt", "app.py"],
), patch(
    "app.agents.security_reviewer.fetch_file_content",
    side_effect=lambda owner, repo, path: "flask==2.0.0" if path == "requirements.txt" else None,
), patch(
    "app.agents.security_reviewer.call_with_tool", return_value=SECURITY_RESULT
) as mock_call:
    review = security_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("security: GitHub requirements.txt content is in the prompt", "flask==2.0.0" in prompt)
check("security: committed .env flagged as a verified fact", "VERIFIED FACT" in prompt)
check(
    "security: reviewed_files records the GitHub files",
    review.metrics_json["reviewed_files"] == ["requirements.txt (GitHub)", ".env (GitHub, presence check)"],
)
db.close()


# --- 6. Data Reviewer: uploaded notebook -> code cells only. ---
email = "data-upload@example.com"
register(email)
tid = make_task(email, files=[("analysis.ipynb", "application/json", NOTEBOOK)])
db, user, task = load(email, tid)
with patch("app.agents.data_reviewer.call_with_tool", return_value=DATA_RESULT) as mock_call:
    review = data_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("data: uploaded notebook's code cells are in the prompt", "fit_transform(X)" in prompt)
check("data: markdown cell left out", "# Training notebook" not in prompt)
check("data: reviewed_files records the notebook", review.metrics_json["reviewed_files"] == ["analysis.ipynb"])
db.close()


# --- 7. Data Reviewer: notes only -> 'not_reviewed', no LLM call. ---
email = "data-notes-only@example.com"
register(email)
tid = make_task(email, submission_text="Trained a classifier on the CSV.")
db, user, task = load(email, tid)
with patch("app.agents.data_reviewer.call_with_tool") as mock_call:
    review = data_reviewer.review_task(db, task, user)
check("data: notes-only submission makes no LLM call", mock_call.call_count == 0)
check("data: notes-only submission is 'not_reviewed'", review.metrics_json["verdict"] == "not_reviewed")
db.close()


# --- 8. Data Reviewer: GitHub repo with a notebook + no eval file. ---
email = "data-github@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/ml-repo")
db, user, task = load(email, tid)
with patch(
    "app.agents.data_reviewer.list_repo_paths",
    return_value=["train.ipynb", "README.md"],
), patch(
    "app.agents.data_reviewer.fetch_file_content",
    return_value=NOTEBOOK.decode(),
), patch(
    "app.agents.data_reviewer.call_with_tool", return_value=DATA_RESULT
) as mock_call:
    review = data_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("data: GitHub notebook code is in the prompt", "fit_transform(X)" in prompt)
check("data: missing evaluation file flagged as a verified fact", "VERIFIED FACT" in prompt)
check("data: reviewed_files records the GitHub notebook", review.metrics_json["reviewed_files"] == ["train.ipynb (GitHub)"])
db.close()


# --- 9. Data Reviewer: GitHub repo with no notebooks -> 'not_reviewed'. ---
email = "data-github-empty@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/http-lib")
db, user, task = load(email, tid)
with patch(
    "app.agents.data_reviewer.list_repo_paths",
    return_value=["src/client.py", "README.md"],
), patch(
    "app.agents.data_reviewer.fetch_file_content", return_value=None
), patch(
    "app.agents.data_reviewer.call_with_tool"
) as mock_call:
    review = data_reviewer.review_task(db, task, user)
check("data: repo with no notebooks makes no LLM call", mock_call.call_count == 0)
check("data: repo with no notebooks is 'not_reviewed'", review.metrics_json["verdict"] == "not_reviewed")
db.close()


# --- 10. discussion_so_far reaches the prompt alongside the real content. ---
email = "sec-discussion@example.com"
register(email)
tid = make_task(email, files=[("app.py", "text/x-python", APP_PY)])
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool", return_value=SECURITY_RESULT) as mock_call:
    security_reviewer.review_task(db, task, user, discussion_so_far="Data Reviewer:\nNo validation on ingest.")
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("discussion_so_far is included", "No validation on ingest" in prompt)
check("the uploaded file content is still there too", "SuperSecret123!" in prompt)
db.close()

# --- 10b. GitHub didn't respond (rate limit / private repo) -> say so,
# don't tell the graduate to "link a public repo" they already linked. ---
email = "sec-github-down@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/demo-repo")
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.list_repo_paths", return_value=None), patch(
    "app.agents.security_reviewer.fetch_file_content"
) as mock_fetch, patch("app.agents.security_reviewer.call_with_tool") as mock_call:
    review = security_reviewer.review_task(db, task, user)
check("github down: no file requests after the tree failed", mock_fetch.call_count == 0)
check("github down: no LLM call", mock_call.call_count == 0)
check("github down: stored as not_reviewed", review.metrics_json["verdict"] == "not_reviewed")
check("github down: message says GitHub didn't respond", "GitHub didn't respond" in review.content)
check("github down: no misleading 'binary files' explanation", "binary files" not in review.content)
db.close()

email = "data-github-down@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/ml-repo")
db, user, task = load(email, tid)
with patch("app.agents.data_reviewer.list_repo_paths", return_value=None), patch(
    "app.agents.data_reviewer.call_with_tool"
) as mock_call:
    review = data_reviewer.review_task(db, task, user)
check("github down (data): stored as not_reviewed, no LLM call", review.metrics_json["verdict"] == "not_reviewed" and mock_call.call_count == 0)
check("github down (data): message says GitHub didn't respond", "GitHub didn't respond" in review.content)
db.close()

email = "sec-github-requests@example.com"
register(email)
tid = make_task(email, github_link="https://github.com/example/demo-repo")
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.list_repo_paths", return_value=["requirements.txt", "app.py"]), patch(
    "app.agents.security_reviewer.fetch_file_content", return_value="flask==2.0.0"
) as mock_fetch, patch("app.agents.security_reviewer.call_with_tool", return_value=SECURITY_RESULT):
    security_reviewer.review_task(db, task, user)
check(
    "github: only candidate files that exist in the tree are requested (1, not 7)",
    [c.args[2] for c in mock_fetch.call_args_list] == ["requirements.txt"],
)
db.close()


# --- 11. The model says "clear", but a static check finds a hardcoded
# secret -> the verified finding still wins (the live-test failure mode). ---
CLEAR_SECURITY = {
    "tool_name": "submit_security_review",
    "input": {"verdict": "clear", "risk_level": "low", "findings": [], "summary": "Reviewed app.py, looks fine."},
}
email = "sec-static-override@example.com"
register(email)
tid = make_task(email, files=[("app.py", "text/x-python", APP_PY)])
db, user, task = load(email, tid)
with patch("app.agents.security_reviewer.call_with_tool", return_value=CLEAR_SECURITY) as mock_call:
    review = security_reviewer.review_task(db, task, user)
prompt = mock_call.call_args.kwargs["messages"][0]["content"]
check("static: model is told the secret is already recorded", "ALREADY RECORDED" in prompt)
check("static: model said clear, stored verdict is concerns_found", review.metrics_json["verdict"] == "concerns_found")
check("static: risk raised to high", review.metrics_json["risk_level"] == "high")
check(
    "static: the hardcoded secret is in the stored findings",
    any(f["category"] == "hardcoded_secret" and f.get("source") == "static_check" for f in review.metrics_json["findings"]),
)
check("static: thread message leads with the verified issue", review.content.startswith("Verified in code: app.py line 1"))
check("static: the secret's value isn't stored in the findings", "SuperSecret123!" not in json.dumps(review.metrics_json))
db.close()


# --- 12. Same for the Data Reviewer: model says clear, the notebook
# scales before splitting -> data_leakage is still recorded. ---
CLEAR_DATA = {
    "tool_name": "submit_data_review",
    "input": {"verdict": "clear", "risk_level": "low", "findings": [], "summary": "Reviewed the notebook."},
}
LEAKY_NOTEBOOK = json.dumps(
    {
        "cells": [
            {
                "cell_type": "code",
                "source": [
                    "from sklearn.model_selection import train_test_split\n",
                    "X_scaled = StandardScaler().fit_transform(X)\n",
                    "X_train, X_test, y_train, y_test = train_test_split(X_scaled, y)\n",
                ],
            }
        ]
    }
).encode()
email = "data-static-override@example.com"
register(email)
tid = make_task(email, files=[("analysis.ipynb", "application/json", LEAKY_NOTEBOOK)])
db, user, task = load(email, tid)
with patch("app.agents.data_reviewer.call_with_tool", return_value=CLEAR_DATA):
    review = data_reviewer.review_task(db, task, user)
check("static: data model said clear, stored verdict is concerns_found", review.metrics_json["verdict"] == "concerns_found")
check(
    "static: data_leakage is in the stored findings",
    any(f["category"] == "data_leakage" for f in review.metrics_json["findings"]),
)
db.close()

# --- 13. The quick path checks match real names, not substrings. ---
has_eval = data_reviewer._has_evaluation_file
check("eval check: tests/ counts", has_eval(["src/model.py", "tests/test_model.py"]))
check("eval check: evaluate.py counts", has_eval(["evaluate.py"]))
check("eval check: metrics_report.ipynb counts", has_eval(["notebooks/metrics_report.ipynb"]))
check("eval check: latest.py does NOT count", not has_eval(["latest.py", "src/contest_data.csv"]))
check("eval check: attestation.md does NOT count", not has_eval(["docs/attestation.md"]))

has_env = security_reviewer._has_exposed_env_file
check("env check: .env counts", has_env(["app.py", ".env"]))
check("env check: .env.production counts", has_env(["config/.env.production"]))
check("env check: .env.local counts", has_env([".env.local"]))
check("env check: .env.example does NOT count", not has_env([".env.example", ".env.sample"]))
check("env check: environment.py does NOT count", not has_env(["src/environment.py", "docs/.envrc-notes.md"]))

# --- 14. GITHUB_TOKEN: sent as a Bearer header only when it's set. ---
from app.config import settings  # noqa: E402
from app.agents import github_client  # noqa: E402

original_token = settings.github_token
try:
    settings.github_token = ""
    with github_client._client() as c:
        check("github: no token -> no Authorization header", "authorization" not in c.headers)
    settings.github_token = "ghp_exampletoken123"
    with github_client._client() as c:
        check("github: token set -> Bearer header", c.headers.get("authorization") == "Bearer ghp_exampletoken123")
finally:
    settings.github_token = original_token

print("\nAll Stage 2 specialist reviewer (unit) smoke checks passed.")
