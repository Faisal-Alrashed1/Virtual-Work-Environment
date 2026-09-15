"""
Smoke test for Stage 2's first slice: the onboarding LangGraph (CV ->
agent-generated Q&A -> track approval -> agent roster approval), the
AgentCatalog seed/read helpers, and the new User/AgentCatalog/UserAgent
schema. Mocks the LLM (no Anthropic API key needed to run this) — same
style as smoke_test_agents.py.

Run: python smoke_test_stage2_onboarding.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_onboarding.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from langgraph.types import Command  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AgentCatalog, OnboardingStage, TrackEnum, User, UserAgent  # noqa: E402
from app.agents.graph.catalog import catalog_as_dicts, seed_agent_catalog  # noqa: E402
from app.agents.graph.onboarding_graph import build_onboarding_graph  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# --- fake model: dispatches on which tool was bound, same shape LangChain
# gives a real ChatAnthropic response (.tool_calls = [{"name", "args"}]) ---

class FakeAIMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


class FakeBoundModel:
    def __init__(self, name, args):
        self._name, self._args = name, args

    def invoke(self, messages):
        return FakeAIMessage([{"name": self._name, "args": self._args}])


class FakeModel:
    def __init__(self, responses):
        self._responses = responses

    def bind_tools(self, tools, tool_choice):
        name = tools[0]["name"]
        return FakeBoundModel(name, self._responses[name])


FAKE_RESPONSES = {
    "generate_questions": {
        "questions": [
            "What was your role in your capstone project?",
            "Have you worked with Docker or Kubernetes?",
        ]
    },
    "suggest_track": {
        "track": "software_engineering",
        "reasoning": "CV shows solid full-stack web experience.",
    },
    "suggest_agents": {"agent_ids": ["career_coach"]},
}


# --- setup: real user via the real API + real DB session ---

r = client.post(
    "/auth/register",
    json={"email": "stage2-test@example.com", "password": "hunter2pass", "full_name": "Stage 2 Tester"},
)
check("register user", r.status_code == 201)

db = SessionLocal()
user = db.query(User).filter(User.email == "stage2-test@example.com").first()
check("user row exists", user is not None)
check("onboarding_stage defaults to CV", user.onboarding_stage == OnboardingStage.CV)
check("track defaults to junior_dev (unchanged from Stage 1)", user.track == TrackEnum.JUNIOR_DEV)
check("track_confirmed defaults False", user.track_confirmed is False)


# --- catalog seeding: idempotent, and readable as plain dicts ---

seed_agent_catalog(db)
count_after_first_seed = db.query(AgentCatalog).count()
check("catalog seeded with 4 entries", count_after_first_seed == 4)

seed_agent_catalog(db)  # calling again should not duplicate
check("re-seeding is idempotent", db.query(AgentCatalog).count() == count_after_first_seed)

catalog = catalog_as_dicts(db)
check("catalog_as_dicts returns plain dicts", all(set(c) == {"id", "name", "description"} for c in catalog))
check(
    "career_coach is in the catalog",
    any(c["id"] == "career_coach" for c in catalog),
)


# --- the onboarding graph itself, end to end through all three interrupts ---

with patch(
    "app.agents.graph.onboarding_graph.small_model",
    return_value=FakeModel(FAKE_RESPONSES),
):
    graph = build_onboarding_graph()
    config = {"configurable": {"thread_id": user.id}}

    initial = {
        "user_id": user.id,
        "cv_raw_text": "Built several Next.js apps and a FastAPI backend for a capstone project.",
        "catalog": catalog,
    }
    step1 = graph.invoke(initial, config=config)
    check("step 1 pauses for Q&A", "__interrupt__" in step1)
    check("two questions generated", len(step1["questions"]) == 2)

    # graduate answers the first question, skips the second, adds free text
    step2 = graph.invoke(
        Command(resume={"answers": {"0": "Led the backend for our capstone."}, "intro_text": "I love clean APIs."}),
        config=config,
    )
    check("step 2 pauses for track approval", "__interrupt__" in step2)
    check("first answer recorded", step2["questions"][0]["answer"] == "Led the backend for our capstone.")
    check("skipped question stays unanswered", step2["questions"][1]["answer"] is None)
    check("track suggested", step2["suggested_track"] == "software_engineering")

    # graduate approves the suggested track as-is — note: resume must not be
    # an empty dict, or LangGraph treats it as "nothing to resume" and
    # replays the same interrupt instead of advancing (see onboarding_graph
    # docstring / STAGE2_ONBOARDING_FLOW.md).
    step3 = graph.invoke(Command(resume={"track": None}), config=config)
    check("step 3 pauses for agent-roster approval", "__interrupt__" in step3)
    check("track approved", step3["approved_track"] == "software_engineering")
    check("agents suggested from catalog", step3["suggested_agent_ids"] == ["career_coach"])

    # graduate overrides the roster: rejects the suggestion, picks none
    step4 = graph.invoke(Command(resume={"agent_ids": []}), config=config)
    check("graph reaches complete", step4["stage"] == "complete")
    check("no interrupt left pending", "__interrupt__" not in step4)
    check("override respected over the suggestion", step4["approved_agent_ids"] == [])

    # a graduate who instead approves the suggestion as given
    config2 = {"configurable": {"thread_id": user.id + "-approve-path"}}
    graph.invoke(initial, config=config2)
    graph.invoke(Command(resume={"answers": {}, "intro_text": None}), config=config2)
    graph.invoke(Command(resume={"track": None}), config=config2)
    approve_step = graph.invoke(Command(resume={"agent_ids": ["career_coach"]}), config=config2)
    check("approve-as-suggested path also completes", approve_step["stage"] == "complete")
    check("approved roster matches suggestion", approve_step["approved_agent_ids"] == ["career_coach"])


# --- writing the graph's output back onto the User row (what the future
# router endpoint will do once it's built) ---

user.suggested_track = TrackEnum(step2["suggested_track"])
user.track = TrackEnum(step3["approved_track"])
user.track_confirmed = True
user.intro_text = step2["intro_text"]
user.onboarding_qa_json = step2["questions"]
user.onboarding_stage = OnboardingStage.COMPLETE
db.add(user)
db.commit()
db.refresh(user)

check("approved track persisted", user.track == TrackEnum.SOFTWARE_ENGINEERING)
check("onboarding_stage persisted as complete", user.onboarding_stage == OnboardingStage.COMPLETE)
check("Q&A log persisted", len(user.onboarding_qa_json) == 2)

career_coach = db.query(AgentCatalog).filter(AgentCatalog.id == "career_coach").first()
db.add(UserAgent(user_id=user.id, agent_catalog_id=career_coach.id))
db.commit()
check("selected agent persisted", len(user.selected_agents) == 1)
check("selected agent links to the right catalog row", user.selected_agents[0].agent.id == "career_coach")

db.close()

print("\nAll Stage 2 onboarding smoke checks passed.")
