"""
Smoke test for Stage 2's optional agents actually doing task work (docs/
STAGE2_AGENT_TASK_WORK.md): Security Reviewer/Data Reviewer/DevOps post a
follow-up comment in the task thread after the Mentor's review, only if
they're on the graduate's roster; Career Coach never does (deliberately
excluded — coaching isn't a code review); one agent's failure doesn't
block the others or the Mentor's review itself. Mocked LLM, real HTTP API.

Run: python smoke_test_stage2_co_reviews.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_co_reviews.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


class FakeContentBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContentBlock(text)]


def register_and_login(email):
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "hunter2pass", "full_name": "Co-Review Tester"},
    )
    check(f"register {email}", r.status_code == 201)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_agent(email, agent_id):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    agent = db.query(AgentCatalog).filter(AgentCatalog.id == agent_id).first()
    db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
    db.commit()
    db.close()


# --- The co_reviewers module is the simpler, parallel fallback (the
# router now uses the richer roundtable — see roundtable.py and
# smoke_test_stage2_roundtable.py). This tests co_reviewers.run_co_reviews
# directly as a unit, since it's no longer on the router's path but still
# a maintained module. ---
from app.agents import co_reviewers  # noqa: E402
from app.models import Task, TaskStatus  # noqa: E402


def make_submitted_task(email):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    task = Task(
        user_id=user.id,
        title="unit task",
        description="d",
        status=TaskStatus.SUBMITTED,
        submission_text="my work",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    tid, uid = task.id, user.id
    db.close()
    return tid, uid


def run_co(email, task_id):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    task = db.get(Task, task_id)
    result = co_reviewers.run_co_reviews(db, user, task)
    types = sorted(m.agent_type.value for m in result)
    db.close()
    return types


# no extras on roster -> nothing posted
email = "co-review-none@example.com"
register_and_login(email)
tid, _ = make_submitted_task(email)
check("no extras -> run_co_reviews posts nothing", run_co(email, tid) == [])

# security + devops on roster (not data) -> exactly those two
email = "co-review-some@example.com"
register_and_login(email)
add_agent(email, "security_reviewer")
add_agent(email, "devops")
tid, _ = make_submitted_task(email)
with patch("app.agents.co_reviewers.call_agentic") as mock_co, patch(
    "app.agents.co_reviewers.fetch_repo_context", return_value=""
):
    mock_co.return_value = FakeResponse("looks fine")
    types = run_co(email, tid)
check("run_co_reviews called call_agentic twice", mock_co.call_count == 2)
check("co-reviews use the small model", {c.kwargs["model"] for c in mock_co.call_args_list} == {"claude-haiku-4-5-20251001"})
check("exactly security + devops posted, not data", types == ["devops", "security_reviewer"])

# career coach on roster -> never co-reviews
email = "co-review-coach@example.com"
register_and_login(email)
add_agent(email, "career_coach")
tid, _ = make_submitted_task(email)
with patch("app.agents.co_reviewers.call_agentic") as mock_co:
    types = run_co(email, tid)
check("career coach never triggers a co-review call", mock_co.call_count == 0)
check("career coach posts nothing", types == [])

# one errors -> the other still posts
email = "co-review-partial@example.com"
register_and_login(email)
add_agent(email, "security_reviewer")
add_agent(email, "data_reviewer")
tid, _ = make_submitted_task(email)


def flaky_call(**kwargs):
    if kwargs["system"].startswith("You are the Security Reviewer"):
        raise RuntimeError("simulated rate limit")
    return FakeResponse("data quality reasonable")


with patch("app.agents.co_reviewers.call_agentic", side_effect=flaky_call), patch(
    "app.agents.co_reviewers.fetch_repo_context", return_value=""
):
    types = run_co(email, tid)
check("a co-reviewer erroring doesn't block the other", types == ["data_reviewer"])

print("\nAll Stage 2 co-review (unit) smoke checks passed.")
