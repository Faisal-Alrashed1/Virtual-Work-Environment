"""
Smoke test for the Stage 2 onboarding router (app/routers/onboarding.py) —
the real FastAPI app + sqlite + real HTTP calls, mocked LLM (no Anthropic
API key needed). Complements smoke_test_stage2_onboarding.py, which tests
the graph in isolation; this one proves the endpoints actually wire it up
correctly, including the CV file upload and the DB writes each step makes.

Run: python smoke_test_stage2_onboarding_router.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_onboarding_router.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


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
        "questions": ["What was your role in your capstone project?", "Used Docker before?"]
    },
    "suggest_track": {"track": "cybersecurity", "reasoning": "CV mentions pen-testing coursework."},
    "suggest_agents": {"agent_ids": ["security_reviewer"]},
}


def register_and_login(email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Router Tester"})
    check(f"register {email}", r.status_code == 201)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    check(f"login {email}", r.status_code == 200)
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


with patch(
    "app.agents.graph.onboarding_graph.small_model",
    return_value=FakeModel(FAKE_RESPONSES),
):
    headers = register_and_login("stage2-router-test@example.com")

    r = client.get("/onboarding/catalog")
    check("catalog -> 200, no auth required", r.status_code == 200)
    check("catalog has all 4 seeded agents", len(r.json()) == 4)
    check("catalog entries have id/name/description", all(set(a) == {"id", "name", "description"} for a in r.json()))

    # --- step 1: upload a CV file (plain text — extract_cv_text falls
    # back to plain text for anything that isn't .pdf/.docx) ---
    cv_bytes = b"Built a Flask app with basic auth, some pen-testing coursework."
    r = client.post(
        "/onboarding/cv",
        headers=headers,
        files={"file": ("cv.txt", cv_bytes, "text/plain")},
    )
    check("upload cv -> 200", r.status_code == 200)
    questions = r.json()["questions"]
    check("two questions returned", len(questions) == 2)

    r = client.get("/users/me", headers=headers)
    check("cv text stored (has_cv true)", r.json()["has_cv"] is True)

    r = client.get("/onboarding/state", headers=headers)
    check("state -> qa after cv upload", r.json()["onboarding_stage"] == "qa")

    # --- step 2: submit Q&A — answer the first, skip the second ---
    r = client.post(
        "/onboarding/qa",
        headers=headers,
        json={"answers": {"0": "Led the backend, wired up JWT auth."}, "intro_text": "Interested in appsec."},
    )
    check("submit qa -> 200", r.status_code == 200)
    check("track suggested", r.json()["suggested_track"] == "cybersecurity")

    r = client.get("/onboarding/state", headers=headers)
    check("state -> track after qa", r.json()["onboarding_stage"] == "track")
    check("suggested_track persisted", r.json()["suggested_track"] == "cybersecurity")

    # --- step 3: approve the suggested track as-is (omit the override) ---
    r = client.post("/onboarding/track", headers=headers, json={})
    check("approve track -> 200", r.status_code == 200)
    suggested_agents = r.json()["suggested_agents"]
    check("security_reviewer suggested", any(a["id"] == "security_reviewer" for a in suggested_agents))

    r = client.get("/users/me", headers=headers)
    check("track approved and persisted on user", r.json()["track"] == "cybersecurity")

    # --- step 4: approve the roster as suggested ---
    r = client.post("/onboarding/agents", headers=headers, json={"agent_ids": ["security_reviewer"]})
    check("approve agents -> 200", r.status_code == 200)
    check("final track in response", r.json()["track"] == "cybersecurity")
    check("final roster in response", [a["id"] for a in r.json()["agents"]] == ["security_reviewer"])

    r = client.get("/onboarding/state", headers=headers)
    check("state -> complete", r.json()["onboarding_stage"] == "complete")

    r = client.get("/users/me/agents", headers=headers)
    check("my agents -> 200", r.status_code == 200)
    check("my agents reflects the approved roster", [a["id"] for a in r.json()] == ["security_reviewer"])

    # --- reset sends a completed graduate back to the start, without
    # wiping their CV or selected agents ---
    r = client.post("/onboarding/reset", headers=headers)
    check("reset -> 200", r.status_code == 200)
    check("reset moves stage back to cv", r.json()["onboarding_stage"] == "cv")
    check("reset clears track_confirmed", r.json()["track_confirmed"] is False)
    r = client.get("/users/me", headers=headers)
    check("reset leaves the CV intact", r.json()["has_cv"] is True)
    r = client.get("/users/me/agents", headers=headers)
    check("reset leaves selected agents intact", [a["id"] for a in r.json()] == ["security_reviewer"])

    # re-submitting the same roster should be idempotent, not duplicate
    r = client.post("/onboarding/agents", headers=headers, json={"agent_ids": ["security_reviewer"]})
    check("re-approving agents doesn't error", r.status_code == 200)

    # --- a second graduate overrides the track instead of approving it ---
    headers2 = register_and_login("stage2-router-test-2@example.com")
    client.post("/onboarding/cv", headers=headers2, files={"file": ("cv.txt", cv_bytes, "text/plain")})
    client.post("/onboarding/qa", headers=headers2, json={"answers": {}, "intro_text": None})
    r = client.post("/onboarding/track", headers=headers2, json={"track": "software_engineering"})
    check("track override accepted", r.status_code == 200)
    r = client.get("/users/me", headers=headers2)
    check("overridden track persisted, not the suggestion", r.json()["track"] == "software_engineering")

    # graduate rejects every suggested agent
    r = client.post("/onboarding/agents", headers=headers2, json={"agent_ids": []})
    check("empty roster accepted", r.status_code == 200)
    check("no agents in final roster", r.json()["agents"] == [])


print("\nAll Stage 2 onboarding router smoke checks passed.")
