"""
Smoke test for the ten-agent roster (docs/TEN_AGENTS.md): the three new
agents (QA Engineer, UX Reviewer, Technical Writer) are seeded, reachable
in the Meeting Room, and correctly scoped in task-thread chat and the
roundtable; and the Career Coach's new dedicated action (a career
check-in, its one output beyond ordinary chat). Mocked LLM, no API key
needed.

Run: python smoke_test_ten_agents.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_ten_agents.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, User, UserAgent  # noqa: E402
from app.agents.llm_client import AgentReply, ToolCall  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def post_message_reply(text: str) -> AgentReply:
    return AgentReply(tool_calls=[ToolCall(name="post_message", input={"content": text})])


def add_to_roster(email: str, agent_id: str):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    agent = db.query(AgentCatalog).filter(AgentCatalog.id == agent_id).first()
    db.add(UserAgent(user_id=user.id, agent_catalog_id=agent.id))
    db.commit()
    db.close()


# --- the catalog now has 10 agents worth of roster (7 optional + 3 default) ---
r = client.get("/onboarding/catalog")
check("catalog -> 200", r.status_code == 200)
catalog_ids = {a["id"] for a in r.json()}
check("catalog has exactly 7 optional agents", len(catalog_ids) == 7)
check(
    "the three new agents are all seeded",
    {"qa_engineer", "ux_reviewer", "technical_writer"} <= catalog_ids,
)

# --- register a student, add the three new agents ---
r = client.post(
    "/auth/register",
    json={"email": "tenagents@example.com", "password": "hunter2pass", "full_name": "Ten Agents Tester"},
)
check("register", r.status_code == 201)
r = client.post("/auth/login", data={"username": "tenagents@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

for agent_id in ("qa_engineer", "ux_reviewer", "technical_writer"):
    add_to_roster("tenagents@example.com", agent_id)

# --- all three are reachable in the Meeting Room now that they're added ---
with patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Let's talk testing.")):
    r = client.post("/meeting/qa_engineer", json={"content": "What should I test here?"}, headers=headers)
check("QA Engineer reachable in the Meeting Room -> 201", r.status_code == 201)

with patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Let's talk usability.")):
    r = client.post("/meeting/ux_reviewer", json={"content": "Is this flow confusing?"}, headers=headers)
check("UX Reviewer reachable in the Meeting Room -> 201", r.status_code == 201)

with patch("app.agents.meeting.call_agentic", return_value=AgentReply(text="Let's talk docs.")):
    r = client.post("/meeting/technical_writer", json={"content": "Can you review my README?"}, headers=headers)
check("Technical Writer reachable in the Meeting Room -> 201", r.status_code == 201)

# --- a student who HASN'T added them is refused (403), same as any optional agent ---
r = client.post(
    "/auth/register",
    json={"email": "noaddons@example.com", "password": "hunter2pass", "full_name": "No Addons"},
)
noaddons_headers = {
    "Authorization": f"Bearer {client.post('/auth/login', data={'username': 'noaddons@example.com', 'password': 'hunter2pass'}).json()['access_token']}"
}
r = client.post("/meeting/qa_engineer", json={"content": "hi"}, headers=noaddons_headers)
check("QA Engineer refused for a student who hasn't added it -> 403", r.status_code == 403)

# --- task chat: QA Engineer and UX Reviewer are addressable directly; Technical Writer is not ---
fake_project_input = {"title": "D", "description": "d"}
fake_week_input = {
    "big_task_title": "a", "big_task_description": "b",
    "subtasks": [{"title": f"t{i}", "description": f"d{i}"} for i in range(5)],
}
with patch(
    "app.agents.manager.call_with_tool",
    side_effect=[
        {"tool_name": "create_project", "input": fake_project_input},
        {"tool_name": "plan_week", "input": fake_week_input},
    ],
):
    r = client.post("/agents/manager/assign-task", headers=headers)
task_id = r.json()["id"]
client.post(f"/tasks/{task_id}/messages", json={"content": "hi"}, headers=headers)

with patch("app.agents.task_chat.call_agentic", return_value=post_message_reply("Test the edge cases.")):
    r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "qa_engineer"})
check("QA Engineer answers directly in task chat -> 201", r.status_code == 201)
check("reply is tagged as QA Engineer", r.json()["agent_type"] == "qa_engineer")

with patch("app.agents.task_chat.call_agentic", return_value=post_message_reply("Simplify this flow.")):
    r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "ux_reviewer"})
check("UX Reviewer answers directly in task chat -> 201", r.status_code == 201)

r = client.post(f"/agents/task/{task_id}/reply", headers=headers, json={"agent_type": "technical_writer"})
check("Technical Writer NOT available in task chat -> 403", r.status_code == 403)

# --- roundtable: QA Engineer and UX Reviewer are eligible specialists once added ---
from app.agents import roundtable  # noqa: E402

db = SessionLocal()
user = db.query(User).filter(User.email == "tenagents@example.com").first()
specialists = roundtable.specialists_for(db, user)
db.close()
check(
    "QA Engineer and UX Reviewer are eligible roundtable specialists",
    {"qa_engineer", "ux_reviewer"} <= {a.value for a in specialists},
)
check(
    "Technical Writer is NOT a roundtable specialist (review-time, not code-review)",
    "technical_writer" not in {a.value for a in specialists},
)

# --- Career Coach: the new dedicated career check-in action ---
add_to_roster("tenagents@example.com", "career_coach")

# no employee file yet -> a clean 400, not a crash
r = client.post("/agents/career-coach/checkin", headers=headers)
check("career check-in with no employee file yet -> 400", r.status_code == 400)

# give the graduate an employee file to work from (bypassing a full HR
# rollup — this test is about the checkin action itself)
db = SessionLocal()
user = db.query(User).filter(User.email == "tenagents@example.com").first()
ef = user.employee_file
ef.summary_text = "Shipped two solid backend features this month."
ef.skills_json = {"items": ["FastAPI", "SQLAlchemy"]}
ef.strengths_json = {"items": ["Clean, well-tested code"]}
ef.growth_areas_json = {"items": ["More upfront design before coding"]}
db.commit()
db.close()

with patch(
    "app.agents.career_coach.call_with_tool",
    return_value={
        "tool_name": "submit_career_checkin",
        "input": {
            "summary": "Strong, demonstrable backend work — ready to talk about it in interviews.",
            "resume_highlights": [
                "Built and tested a FastAPI backend feature end-to-end",
                "Wrote comprehensive automated tests for new functionality",
            ],
            "suggested_focus": "Practice explaining your design decisions out loud.",
        },
    },
):
    r = client.post("/agents/career-coach/checkin", headers=headers)
check("career check-in -> 201", r.status_code == 201)
body = r.json()
check("review is tagged career_coach / career_checkin", body["agent_type"] == "career_coach" and body["kind"] == "career_checkin")
check("resume highlights are real, structured output", len(body["metrics_json"]["resume_highlights"]) == 2)
check("suggested focus is present", "interviews" not in body["metrics_json"]["suggested_focus"])

# --- a student who hasn't added Career Coach is refused ---
r = client.post("/agents/career-coach/checkin", headers=noaddons_headers)
check("career check-in refused for a student without Career Coach on roster -> 403", r.status_code == 403)

print("\nAll ten-agents smoke checks passed.")
