"""
Smoke test for resumable onboarding (docs/ONBOARDING_RESUME.md): the real
FastAPI app + sqlite + real HTTP calls, mocked LLM (no API key needed).

The point of this suite is the thing the old in-memory checkpointer could not
survive: a SERVER RESTART. `restart_server()` below swaps in a brand-new graph
with an empty checkpointer — exactly what a redeploy, a crash, or a second API
worker looks like to a graduate who is halfway through the wizard — and every
scenario then proves the wizard carries on from what the database saved,
without asking the LLM to redo earlier steps.

Also covered: step-order guards (incl. the double-click that used to auto-approve
a track), graduates who were mid-wizard before resume state existed, reset, a
fresh CV upload replacing a half-finished run, and the new file-based CV
replacement path (POST /users/me/cv/file).

Run: python smoke_test_stage2_onboarding_resume.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_stage2_onboarding_resume.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

import app.routers.onboarding as onboarding_router  # noqa: E402
from app.agents.graph.onboarding_graph import build_onboarding_graph  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import OnboardingStage, User  # noqa: E402

client = TestClient(app)
client.__enter__()

CALLS: list[str] = []  # which LLM tools were invoked since the last restart


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
        CALLS.append(self._name)
        return FakeAIMessage([{"name": self._name, "args": self._args}])


class FakeModel:
    def __init__(self, responses):
        self._responses = responses

    def bind_tools(self, tools, tool_choice):
        name = tools[0]["function"]["name"]
        return FakeBoundModel(name, self._responses[name])


FAKE_RESPONSES = {
    "generate_questions": {"questions": ["What was your role in your capstone project?", "Used Docker before?"]},
    "suggest_track": {"track": "cybersecurity", "reasoning": "CV mentions pen-testing coursework."},
    "suggest_agents": {"agent_ids": ["security_reviewer"]},
}
CV = b"Built a Flask app with basic auth, some pen-testing coursework."


def restart_server():
    """A redeploy / crash / another worker: same database, brand-new process —
    so a brand-new graph with an EMPTY in-memory checkpointer."""
    onboarding_router._graph = build_onboarding_graph()
    CALLS.clear()


def register_and_login(email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Resume Tester"})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def upload_cv(headers, name="cv.txt", data=CV):
    return client.post("/onboarding/cv", headers=headers, files={"file": (name, data, "text/plain")})


def db_user(email):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).one()
    finally:
        db.close()


def db_update(email, **fields):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).one()
        for k, v in fields.items():
            setattr(u, k, v)
        db.commit()
    finally:
        db.close()


with patch(
    "app.agents.graph.onboarding_graph.small_model_chain",
    return_value=[("anthropic", FakeModel(FAKE_RESPONSES))],
), patch(
    "app.agents.graph.cv_parsing.call_with_tool",
    return_value={"tool_name": "classify_document", "input": {"is_cv": True, "reason": ""}},
):
    # =====================================================================
    # A. The whole wizard, restarting the server between EVERY step
    # =====================================================================
    a_email = "resume-a@example.com"
    a = register_and_login(a_email)

    r = client.get("/onboarding/resume", headers=a)
    check("fresh graduate: resume -> stage cv, nothing to restore", r.status_code == 200 and r.json()["onboarding_stage"] == "cv" and r.json()["resumable"] is False)

    r = upload_cv(a)
    check("upload cv -> 200 with the agent's questions", r.status_code == 200 and len(r.json()["questions"]) == 2)
    first_questions = r.json()["questions"]

    # -- close the tab at the Q&A step: the wizard asks the server what to show
    r = client.get("/onboarding/resume", headers=a)
    check("Q&A step: resume is resumable", r.json()["onboarding_stage"] == "qa" and r.json()["resumable"] is True)
    check("Q&A step: resume returns the SAME questions (not freshly generated)", r.json()["questions"] == first_questions)

    restart_server()
    r = client.post(
        "/onboarding/qa", headers=a,
        json={"answers": {"0": "Led the backend."}, "intro_text": "Interested in appsec."},
    )
    check("after a server restart, submitting Q&A still works", r.status_code == 200)
    check("...and returns the track suggestion", r.json()["suggested_track"] == "cybersecurity")
    check("...without re-asking the LLM for questions (only suggest_track ran)", CALLS == ["suggest_track"])

    # -- close the tab at the track step
    r = client.get("/onboarding/resume", headers=a)
    check("track step: resume is resumable", r.json()["onboarding_stage"] == "track" and r.json()["resumable"] is True)
    check("track step: resume returns the suggestion", r.json()["suggested_track"] == "cybersecurity")
    check("track step: resume returns the saved reasoning", r.json()["reasoning"] == "CV mentions pen-testing coursework.")

    restart_server()
    r = client.post("/onboarding/track", headers=a, json={})
    check("after a restart, approving the track still works", r.status_code == 200)
    check("...only suggest_agents ran", CALLS == ["suggest_agents"])
    check("...and the track was applied", client.get("/users/me", headers=a).json()["track"] == "cybersecurity")

    # -- close the tab at the roster step
    r = client.get("/onboarding/resume", headers=a)
    check("roster step: resume is resumable", r.json()["onboarding_stage"] == "agents" and r.json()["resumable"] is True)
    check("roster step: resume returns the suggested agents", [x["id"] for x in r.json()["suggested_agents"]] == ["security_reviewer"])

    restart_server()
    r = client.post("/onboarding/agents", headers=a, json={"agent_ids": ["security_reviewer"]})
    check("after a restart, approving the roster completes onboarding", r.status_code == 200)
    check("...with no LLM call at all", CALLS == [])
    check("...stage is complete", client.get("/onboarding/state", headers=a).json()["onboarding_stage"] == "complete")
    r = client.get("/onboarding/resume", headers=a)
    check("complete: nothing to resume", r.json()["onboarding_stage"] == "complete" and r.json()["resumable"] is False)

    # editing the roster after finishing, after another restart
    restart_server()
    r = client.post("/onboarding/agents", headers=a, json={"agent_ids": ["security_reviewer", "devops"]})
    check("roster can be edited after completion, even after a restart", r.status_code == 200)
    r = client.get("/users/me/agents", headers=a)
    check("...and the new roster replaced the old one (no duplicates)", sorted(x["id"] for x in r.json()) == ["devops", "security_reviewer"])

    # =====================================================================
    # B. Steps must happen in order
    # =====================================================================
    b = register_and_login("resume-b@example.com")
    for path, body in (("/onboarding/qa", {"answers": {}}), ("/onboarding/track", {}), ("/onboarding/agents", {"agent_ids": []})):
        check(f"{path} before uploading a CV -> 409", client.post(path, headers=b, json=body).status_code == 409)

    c_email = "resume-c@example.com"
    c = register_and_login(c_email)
    upload_cv(c)
    check("first Q&A submit -> 200", client.post("/onboarding/qa", headers=c, json={"answers": {}}).status_code == 200)
    r = client.post("/onboarding/qa", headers=c, json={"answers": {}})
    check("a DOUBLE-CLICKED Q&A submit is refused (409) instead of resuming the next step", r.status_code == 409)
    st = client.get("/onboarding/state", headers=c).json()
    check("...the track was NOT silently auto-approved", st["track_confirmed"] is False and st["onboarding_stage"] == "track")

    # =====================================================================
    # C. Graduates who were mid-wizard BEFORE resume state existed
    # =====================================================================
    d_email = "resume-d@example.com"
    d = register_and_login(d_email)
    upload_cv(d)
    db_update(d_email, onboarding_qa_json=[])  # the old code never saved the questions
    restart_server()
    r = client.get("/onboarding/resume", headers=d)
    check("legacy Q&A-stage graduate: resume says not resumable", r.json()["onboarding_stage"] == "qa" and r.json()["resumable"] is False)
    r = client.post("/onboarding/qa", headers=d, json={"answers": {}})
    check("...and submitting is refused with a 'restart' message (409)", r.status_code == 409 and "upload your CV again" in r.json()["detail"])
    r = upload_cv(d)
    check("...uploading the CV again recovers them", r.status_code == 200 and len(r.json()["questions"]) == 2)
    check("...and they can then carry on", client.post("/onboarding/qa", headers=d, json={"answers": {}}).status_code == 200)

    e_email = "resume-e@example.com"
    e = register_and_login(e_email)
    upload_cv(e)
    client.post("/onboarding/qa", headers=e, json={"answers": {}})
    client.post("/onboarding/track", headers=e, json={})
    db_update(e_email, suggested_agent_ids_json=None)  # roster step reached before suggestions were saved
    restart_server()
    r = client.get("/onboarding/resume", headers=e)
    check("legacy roster-stage graduate: still resumable (they pick from the catalog)", r.json()["resumable"] is True and r.json()["suggested_agents"] == [])
    check("...and can finish", client.post("/onboarding/agents", headers=e, json={"agent_ids": []}).status_code == 200)

    # =====================================================================
    # D. Reset and fresh uploads start clean
    # =====================================================================
    f_email = "resume-f@example.com"
    f = register_and_login(f_email)
    upload_cv(f)
    client.post("/onboarding/qa", headers=f, json={"answers": {}})
    check("reset -> 200", client.post("/onboarding/reset", headers=f).status_code == 200)
    u = db_user(f_email)
    check("reset clears the saved suggestion reasoning", u.suggested_track_reasoning is None)
    check("reset clears the saved roster suggestion", u.suggested_agent_ids_json is None)
    check("reset -> resume shows the CV step", client.get("/onboarding/resume", headers=f).json()["resumable"] is False)

    g_email = "resume-g@example.com"
    g = register_and_login(g_email)
    upload_cv(g)
    client.post("/onboarding/qa", headers=g, json={"answers": {}})  # now at the track step
    restart_server()
    r = upload_cv(g, data=b"A much newer CV: Kubernetes, Terraform.")
    check("uploading a fresh CV mid-flow restarts the wizard cleanly", r.status_code == 200)
    st = client.get("/onboarding/state", headers=g).json()
    check("...back at the Q&A step, with no stale track suggestion", st["onboarding_stage"] == "qa" and st["suggested_track"] is None)
    check("...using the new CV text", "Kubernetes" in db_user(g_email).cv_raw_text)

    # =====================================================================
    # E. Replacing the CV after onboarding (POST /users/me/cv/file)
    # =====================================================================
    r = client.post("/users/me/cv/file", headers=a, files={"file": ("new-cv.txt", b"Updated CV: 2 years of DevOps at Acme.", "text/plain")})
    check("complete graduate can replace their CV -> 200", r.status_code == 200 and r.json()["has_cv"] is True)
    check("...the stored CV text changed", "DevOps at Acme" in db_user(a_email).cv_raw_text)
    check("...their track is untouched", client.get("/users/me", headers=a).json()["track"] == "cybersecurity")
    check("...their team is untouched", sorted(x["id"] for x in client.get("/users/me/agents", headers=a).json()) == ["devops", "security_reviewer"])
    check("...onboarding is still complete", client.get("/onboarding/state", headers=a).json()["onboarding_stage"] == "complete")

    before = db_user(c_email).cv_raw_text
    r = client.post("/users/me/cv/file", headers=c, files={"file": ("x.txt", b"should not be stored", "text/plain")})
    check("mid-wizard graduate can't swap the CV under the wizard -> 409", r.status_code == 409)
    check("...and their CV is unchanged", db_user(c_email).cv_raw_text == before)

    r = client.post("/users/me/cv/file", headers=a, files={"file": ("broken.pdf", b"this is not a real pdf", "application/pdf")})
    check("a corrupt PDF is a clean 400, not a 500", r.status_code == 400 and "Couldn't read" in r.json()["detail"])
    r = client.post("/users/me/cv/file", headers=a, files={"file": ("empty.txt", b"   ", "text/plain")})
    check("an empty file -> 400", r.status_code == 400)
    r = client.post("/users/me/cv/file", headers=a, files={"file": ("huge.txt", b"x" * (6 * 1024 * 1024), "text/plain")})
    check("an oversized file -> 413", r.status_code == 413)
    check("...none of those changed the stored CV", "DevOps at Acme" in db_user(a_email).cv_raw_text)
    check("replacing a CV needs login -> 401", client.post("/users/me/cv/file", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 401)

    h = register_and_login("resume-h@example.com")
    r = upload_cv(h, name="broken.pdf", data=b"this is not a real pdf")
    check("POST /onboarding/cv with a corrupt PDF is now a clean 400 too (was a 500)", r.status_code == 400)
    check("...and doesn't move the graduate out of the CV step", client.get("/onboarding/state", headers=h).json()["onboarding_stage"] == "cv")

print("\nAll Stage 2 onboarding-resume smoke checks passed.")
