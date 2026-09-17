"""
Smoke test for Stage 2's meeting-room extension: a graduate can only chat
with an optional agent they've actually added, and once added, the agent
replies in its own persona (not a KeyError, not the Manager's voice).
Mocked LLM, real HTTP API. See docs/STAGE2_MEETING_AND_SUBMISSIONS.md.

Run: python smoke_test_stage2_meeting.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_meeting.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402
from app.agents.llm_client import AgentReply  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


r = client.post(
    "/auth/register",
    json={"email": "meeting-test@example.com", "password": "hunter2pass", "full_name": "Meeting Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "meeting-test@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- before adding it: can't chat with an optional agent ---
r = client.get("/meeting/security_reviewer", headers=headers)
check("no access to an unadded optional agent -> 403", r.status_code == 403)

r = client.post("/meeting/security_reviewer", headers=headers, json={"content": "hi"})
check("sending to an unadded optional agent also -> 403", r.status_code == 403)

# defaults always work, no roster entry needed
r = client.get("/meeting/manager", headers=headers)
check("default agent (manager) always accessible", r.status_code == 200)

# --- add security_reviewer to this graduate's roster directly (bypassing
# onboarding, which is covered elsewhere) ---
db = SessionLocal()
user = db.query(User).filter(User.email == "meeting-test@example.com").first()
agent = db.query(AgentCatalog).filter(AgentCatalog.id == "security_reviewer").first()
db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
db.commit()
db.close()

r = client.get("/meeting/security_reviewer", headers=headers)
check("now accessible after being added to the roster", r.status_code == 200)

with patch("app.agents.meeting.call_agentic") as mock_call:
    mock_call.return_value = AgentReply(
        text="Looks like that endpoint doesn't validate the redirect URL — open redirect risk."
    )
    r = client.post(
        "/meeting/security_reviewer",
        headers=headers,
        json={"content": "Anything concerning in my auth callback route?"},
    )
    check("chat with the added optional agent -> 201", r.status_code == 201)
    check("reply is from the right agent", r.json()["agent_type"] == "security_reviewer")
    check("reply uses the mocked persona text, not a crash", "open redirect" in r.json()["content"])

    # the system prompt actually sent should be the security-reviewer
    # persona, not manager/mentor/hr's
    sent_system = mock_call.call_args.kwargs["system"]
    check("security reviewer persona used, not a generic/wrong one", "Security Reviewer" in sent_system)

print("\nAll Stage 2 meeting-room smoke checks passed.")
