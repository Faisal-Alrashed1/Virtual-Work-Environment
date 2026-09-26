"""
Smoke test for hardening the onboarding graph's tool calls (docs/ONBOARDING_GRAPH_HARDENING.md).

Found by running real models (e2e_real_llm.py): DeepSeek returned 5 follow-up questions
where the schema caps it at 4 (QUESTIONS_TOOL's maxItems) — nothing was checking it,
because the onboarding graph uses a *separate* tool-calling path (LangChain's
bind_tools/invoke) from the one hardened earlier (llm_client.call_with_tool, see
docs/LLM_PROVIDER_FAILOVER.md). It had no repair, no structural checks, and no retry
on unusable output at all — only on outright connectivity errors.

Reading the code around that path surfaced a second, more serious gap: an out-of-enum
track from the model was never validated, and both `submit_qa` and `approve_track` do
`TrackEnum(result["...track"])` with no try/except — an UNCAUGHT ValueError (-> 500) on
a graduate's very first onboarding screen for any model that drifts from the exact enum
spelling.

Both are now fixed by bringing agents/tool_output.py's repair/check machinery (already
used by the Manager/Mentor/HR path) to `_forced_tool_call` too, plus a `validate` hook
per tool — mirroring llm_client.call_with_tool exactly. Too many questions is truncated
(free, graceful, same precedent as the Manager's subtasks[:5]); an invalid track is
retried (no safe way to auto-correct it), then a clean 503 if every attempt and every
provider fails — never a 500.

This suite: unit-level checks on the repair/truncate/validate behaviour, mutation-tested;
and, through the real onboarding endpoints with a scripted fake model, the exact bug
(5 questions -> 4 delivered) and the exact crash (a bad track -> retried and recovered,
or cleanly refused) end to end.

Run: python smoke_test_onboarding_graph_hardening.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_onboarding_graph_hardening.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.graph.onboarding_graph import (  # noqa: E402
    AGENTS_TOOL,
    QUESTIONS_TOOL,
    TRACK_TOOL,
    _forced_tool_call,
    build_onboarding_graph,
)
from app.agents.llm_client import ALL_PROVIDERS_FAILED, MAX_ATTEMPTS_PER_PROVIDER  # noqa: E402
from app.agents.tool_output import MalformedToolOutput  # noqa: E402
from app.main import app  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


MARK = "LANGUAGE INSTRUCTION"


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class ScriptedModel:
    """A LangChain-shaped fake: one queue of scripted responses per tool name, popped
    in order on each .bind_tools(...).invoke(...) call. A response is either a dict of
    tool args (a successful call), the string "no-call" (the model didn't call the
    tool — one real failure mode), or an Exception instance to raise (a connectivity
    error the FAILOVER_EXCEPTIONS path is meant to catch)."""

    def __init__(self, **queues):
        self.queues = {k: list(v) for k, v in queues.items()}
        self.calls = {k: 0 for k in queues}

    def bind_tools(self, tools, tool_choice):
        name = tools[0]["function"]["name"]

        class Bound:
            def invoke(self_inner, messages):
                self.calls[name] = self.calls.get(name, 0) + 1
                SYSTEMS.append(messages[0].content)
                item = self.queues[name].pop(0)
                if isinstance(item, Exception):
                    raise item
                if item == "no-call":
                    return Block(tool_calls=[])
                return Block(tool_calls=[{"name": name, "args": item}])

        return Bound()


SYSTEMS: list[str] = []

# ============================ unit level: _forced_tool_call directly =================
GOOD_Q = {"questions": ["What did you build?", "Used Docker?"]}
GOOD_TRACK = {"track": "cybersecurity", "reasoning": "Mentions pen-testing coursework."}

model = ScriptedModel(generate_questions=[GOOD_Q])
SYSTEMS.clear()
r = _forced_tool_call([("fake", model)], QUESTIONS_TOOL, [type("M", (), {"content": "sys"})(), type("M", (), {"content": "hi"})()])
check("a normal, well-formed response succeeds on the first call", r == GOOD_Q and model.calls["generate_questions"] == 1)

# repair: a JSON-string list
model = ScriptedModel(generate_questions=[{"questions": '["A?", "B?"]'}])
r = _forced_tool_call([("fake", model)], QUESTIONS_TOOL, [type("M", (), {"content": "s"})()])
check("a JSON-string 'questions' list is repaired into a real list (1 call, no retry needed)", r["questions"] == ["A?", "B?"] and model.calls["generate_questions"] == 1)

# structural check (minItems=1): empty list is retried, then succeeds
model = ScriptedModel(generate_questions=[{"questions": []}, GOOD_Q])
r = _forced_tool_call([("fake", model)], QUESTIONS_TOOL, [type("M", (), {"content": "s"})()])
check("an empty questions list (violates minItems) is retried and recovers", r == GOOD_Q and model.calls["generate_questions"] == 2)

# "didn't call the tool" is retried too
model = ScriptedModel(generate_questions=["no-call", GOOD_Q])
r = _forced_tool_call([("fake", model)], QUESTIONS_TOOL, [type("M", (), {"content": "s"})()])
check("a response that never calls the tool at all is retried and recovers", r == GOOD_Q and model.calls["generate_questions"] == 2)

# a bad track is retried via the custom validate hook, then recovers
calls = {"n": 0}


def flaky_track_validate(data):
    calls["n"] += 1
    if calls["n"] == 1:
        raise MalformedToolOutput("bad")


model = ScriptedModel(suggest_track=[{"track": "not_a_real_track", "reasoning": "x"}, GOOD_TRACK])
r = _forced_tool_call([("fake", model)], TRACK_TOOL, [type("M", (), {"content": "s"})()], validate=lambda d: (_ for _ in ()).throw(MalformedToolOutput("bad")) if d["track"] == "not_a_real_track" else None)
check("a custom validate hook (track enum) rejects a bad value and the retry recovers", r == GOOD_TRACK and model.calls["suggest_track"] == 2)

# exhausting the whole chain on persistently malformed output -> a clean, labeled error
model = ScriptedModel(suggest_track=[{"track": "nope", "reasoning": "x"}] * MAX_ATTEMPTS_PER_PROVIDER)
try:
    _forced_tool_call([("fake", model)], TRACK_TOOL, [type("M", (), {"content": "s"})()], validate=lambda d: (_ for _ in ()).throw(MalformedToolOutput("always bad")))
    raised = None
except RuntimeError as exc:
    raised = str(exc)
check(f"persistently invalid output -> RuntimeError starting with {ALL_PROVIDERS_FAILED!r} (-> clean 503, never a 500)",
      raised is not None and raised.startswith(ALL_PROVIDERS_FAILED))
check(f"...after exactly {MAX_ATTEMPTS_PER_PROVIDER} attempts on the one provider, not more", model.calls["suggest_track"] == MAX_ATTEMPTS_PER_PROVIDER)

# a connectivity-type error still fails over immediately, unretried
model = ScriptedModel(suggest_track=[ConnectionError("down")])
model2 = ScriptedModel(suggest_track=[GOOD_TRACK])
with patch("app.agents.graph.onboarding_graph.FAILOVER_EXCEPTIONS", (ConnectionError,)):
    r = _forced_tool_call([("fake", model), ("fake2", model2)], TRACK_TOOL, [type("M", (), {"content": "s"})()])
check("a connectivity error fails over to the next provider at once (not retried on the dead one)",
      r == GOOD_TRACK and model.calls["suggest_track"] == 1 and model2.calls["suggest_track"] == 1)

print()

# ============================ through the real endpoints =============================
client = TestClient(app)
client.__enter__()


def signup(email, lang=None):
    h = {"X-Venv-Language": lang} if lang else {}
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Hardening Tester"}, headers=h)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"}, headers=h)
    return {"Authorization": f"Bearer {r.json()['access_token']}", **h}


CV = b"Built a Flask app with basic auth and Docker."

# Every /onboarding/cv call below also triggers cv_parsing.validate_is_cv
# (a separate, unrelated call_with_tool call — not the LangChain graph
# model these tests otherwise script). Patched once, for the rest of this
# file: none of what follows is testing CV-content validation itself
# (that's smoke_test_cv_validation.py), so it should always just pass.
patch(
    "app.agents.graph.cv_parsing.call_with_tool",
    return_value={"tool_name": "classify_document", "input": {"is_cv": True, "reason": ""}},
).start()


def with_model(models):
    return patch("app.agents.graph.onboarding_graph.small_model_chain", return_value=models)


# --- the exact reported bug: 5 questions from a misbehaving model, truncated to 4 ---
five_questions = {"questions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"]}
h = signup("hard-5q@example.com")
with with_model([("deepseek", ScriptedModel(generate_questions=[five_questions]))]):
    r = client.post("/onboarding/cv", headers=h, files={"file": ("cv.txt", CV, "text/plain")})
check("a model returning 5 questions (schema caps at 4) -> 200, not a crash", r.status_code == 200)
check("...exactly 4 questions reach the graduate, not 5", len(r.json()["questions"]) == 4)
check("...they are the FIRST 4 the model gave", r.json()["questions"] == ["Q1?", "Q2?", "Q3?", "Q4?"])

# strict_client never re-raises a server-side exception into the test process (a
# regression here would otherwise abort the whole script instead of a clean [FAIL]) —
# used for every real-endpoint call from here on that a broken track/question
# validation could otherwise crash.
strict_client = TestClient(app, raise_server_exceptions=False)

# --- track validation end to end: bad once, then a good retry recovers the flow ---
h = signup("hard-track-retry@example.com")
strict_client.cookies = client.cookies = strict_client.cookies
with with_model([("deepseek", ScriptedModel(generate_questions=[GOOD_Q]))]):
    strict_client.post("/onboarding/cv", headers=h, files={"file": ("cv.txt", CV, "text/plain")})
with with_model([("deepseek", ScriptedModel(suggest_track=[{"track": "not_real", "reasoning": "x"}, GOOD_TRACK]))]):
    r = strict_client.post("/onboarding/qa", headers=h, json={"answers": {}})
check("an invalid track that recovers on retry -> 200, valid track reaches the graduate (not a crash)", r.status_code == 200 and r.json().get("suggested_track") == "cybersecurity")

# --- track validation end to end: ALWAYS bad -> clean 503, never a 500 ---
h = signup("hard-track-dead@example.com")
with with_model([("deepseek", ScriptedModel(generate_questions=[GOOD_Q]))]):
    strict_client.post("/onboarding/cv", headers=h, files={"file": ("cv.txt", CV, "text/plain")})
always_bad_track = {"track": "definitely_not_a_track", "reasoning": "x"}
with with_model([("deepseek", ScriptedModel(suggest_track=[always_bad_track] * MAX_ATTEMPTS_PER_PROVIDER))]):
    r = strict_client.post("/onboarding/qa", headers=h, json={"answers": {}})
check("a model that NEVER returns a valid track -> a clean 503 (this used to be an uncaught ValueError -> 500)", r.status_code == 503)
check("...the graduate is left able to try again (still at the qa stage, not corrupted)", client.get("/onboarding/state", headers=h).json()["onboarding_stage"] == "qa")

# --- every onboarding tool call carries the language instruction, including suggest_agents ---
h = signup("hard-ar@example.com", lang="ar")
SYSTEMS.clear()
with with_model([("deepseek", ScriptedModel(generate_questions=[GOOD_Q]))]):
    client.post("/onboarding/cv", headers=h, files={"file": ("cv.txt", CV, "text/plain")})
with with_model([("deepseek", ScriptedModel(suggest_track=[GOOD_TRACK]))]):
    client.post("/onboarding/qa", headers=h, json={"answers": {}})
with with_model([("deepseek", ScriptedModel(suggest_agents=[{"agent_ids": []}]))]):
    client.post("/onboarding/track", headers=h, json={})
check(f"Arabic onboarding: all 3 tool calls carry the language instruction ({len(SYSTEMS)} calls)", len(SYSTEMS) == 3 and all(MARK in s for s in SYSTEMS))

# --- a healthy model is never retried needlessly (no hidden cost regression) ---
h = signup("hard-clean@example.com")
model = ScriptedModel(generate_questions=[GOOD_Q])
with with_model([("deepseek", model)]):
    r = client.post("/onboarding/cv", headers=h, files={"file": ("cv.txt", CV, "text/plain")})
check("a healthy response is used as-is: exactly one model call, no retry overhead", r.status_code == 200 and model.calls["generate_questions"] == 1)

print("\nAll onboarding-graph-hardening smoke checks passed.")
