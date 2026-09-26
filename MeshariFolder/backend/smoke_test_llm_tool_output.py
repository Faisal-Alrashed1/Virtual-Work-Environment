"""
Smoke test for hardening against unusable model output (docs/LLM_PROVIDER_FAILOVER.md,
"Malformed tool output").

Found by running the REAL models: Claude sometimes returns the Manager's `subtasks`
as a JSON *string* instead of a list, which crashed plan_week with
"TypeError: string indices must be integers" - a random 500 mid-demo that no mocked
test could ever see. llm_client.call_with_tool now REPAIRS what it can, CHECKS what
would crash, RETRIES the same provider, FAILS OVER to the next, and only then answers
with a clean 503.

This suite covers the repair/check functions directly, every retry/failover path
through call_with_tool (Anthropic and OpenAI-compatible providers), and - through the
real endpoint - the exact failure from the real-model run.

Run: python smoke_test_llm_tool_output.py
"""
import json
import logging
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_llm_tool_output.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.agents import llm_client  # noqa: E402
from app.agents.llm_client import ALL_PROVIDERS_FAILED, AConnErr, call_with_tool  # noqa: E402
from app.agents.manager import _check_plan  # noqa: E402
from app.agents.tool_output import MalformedToolOutput, check_tool_input, repair_tool_input  # noqa: E402
from app.main import app  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "score": {"type": "integer"},
        "ratio": {"type": "number"},
        "subtasks": {"type": "array", "minItems": 5, "items": {"type": "object", "properties": {"title": {"type": "string"}, "effort": {"type": "integer"}}}},
        "meta": {"type": "object", "properties": {"n": {"type": "integer"}}},
    },
    "required": ["title", "subtasks"],
}
FIVE = [{"title": f"Step {i}", "description": "d"} for i in range(1, 6)]

# ---- repair ----------------------------------------------------------------------
out, rep = repair_tool_input({"title": "t", "subtasks": json.dumps(FIVE)}, SCHEMA)
check("a JSON-string list becomes a real list", isinstance(out["subtasks"], list) and len(out["subtasks"]) == 5)
check("...and the repair is reported", len(rep) == 1 and "subtasks" in rep[0])
out, rep = repair_tool_input({"title": "t", "subtasks": FIVE, "meta": '{"n": 3}'}, SCHEMA)
check("a JSON-string object becomes a real object", out["meta"] == {"n": 3})
out, _ = repair_tool_input({"title": "t", "subtasks": FIVE, "score": "4", "ratio": " 3.5 "}, SCHEMA)
check("numbers sent as strings are read as numbers", out["score"] == 4 and out["ratio"] == 3.5)
out, _ = repair_tool_input({"title": "t", "subtasks": FIVE, "score": "4.5"}, SCHEMA)
check("...but 4.5 is not silently truncated to an integer", out["score"] == "4.5")
out, _ = repair_tool_input({"title": "t", "subtasks": [{"title": "x", "effort": "3"}] * 5}, SCHEMA)
check("nested values are repaired too", all(s["effort"] == 3 for s in out["subtasks"]))
good = {"title": "t", "subtasks": FIVE, "score": 4}
out, rep = repair_tool_input(good, SCHEMA)
check("correct input comes back unchanged with no repairs", out == good and rep == [])
out, _ = repair_tool_input({"title": "t", "subtasks": "not json at all"}, SCHEMA)
check("an unparseable string is left alone (the check will catch it)", out["subtasks"] == "not json at all")
out, _ = repair_tool_input({"title": "t", "subtasks": '{"a": 1}'}, SCHEMA)
check("a string that parses to the WRONG type is left alone", out["subtasks"] == '{"a": 1}')
out, _ = repair_tool_input(json.dumps({"title": "t", "subtasks": FIVE}), SCHEMA)
check("a whole tool input double-encoded as a string is parsed", isinstance(out, dict) and out["title"] == "t")

# ---- check -----------------------------------------------------------------------
check("valid input has no problems", check_tool_input(good, SCHEMA) == [])
check("a missing required field is a problem", any("subtasks" in p for p in check_tool_input({"title": "t"}, SCHEMA)))
check("a None required field is a problem", any("title" in p for p in check_tool_input({"title": None, "subtasks": FIVE}, SCHEMA)))
check("a list that isn't a list is a problem", any("should be a list" in p for p in check_tool_input({"title": "t", "subtasks": "abc"}, SCHEMA)))
check("a list shorter than minItems is a problem", any("at least 5" in p for p in check_tool_input({"title": "t", "subtasks": FIVE[:3]}, SCHEMA)))
check("an object that isn't an object is a problem", any("should be an object" in p for p in check_tool_input({"title": "t", "subtasks": FIVE, "meta": [1]}, SCHEMA)))
check("a non-object tool input is a problem", check_tool_input("oops", SCHEMA) != [])
check("item CONTENTS are deliberately not judged by the generic check", check_tool_input({"title": "t", "subtasks": ["a", "b", "c", "d", "e"]}, SCHEMA) == [])

# ---- the Manager's own check --------------------------------------------------------
_check_plan({"subtasks": FIVE})
for label, subtasks in (("a string", ["a"] * 5), ("empty titles", [{"title": " ", "description": "d"}] * 5), ("missing description", [{"title": "t"}] * 5), ("only 3", FIVE[:3])):
    try:
        _check_plan({"subtasks": subtasks})
        ok = False
    except MalformedToolOutput:
        ok = True
    check(f"the Manager's plan check rejects {label}", ok)

# ---- through call_with_tool ----------------------------------------------------------
TOOL = {"name": "plan", "description": "d", "input_schema": SCHEMA}
logs = []


class Capture(logging.Handler):
    def emit(self, record):
        logs.append(record.getMessage())


logging.getLogger("venv.llm").addHandler(Capture())


def anthropic_response(name=None, data=None):
    if name is None:
        return MagicMock(content=[MagicMock(type="text", text="I refuse to call a tool")])
    block = MagicMock(type="tool_use")
    block.name, block.input = name, data
    return MagicMock(content=[block])


def oa_response(arguments=None, tool_calls=True):
    msg = MagicMock()
    if tool_calls:
        call = MagicMock()
        call.function.name, call.function.arguments = "plan", arguments
        msg.tool_calls = [call]
    else:
        msg.tool_calls = None
    return MagicMock(choices=[MagicMock(message=msg)])


def run(chain, anthropic_seq=(), oa_seq=(), **kw):
    """Run call_with_tool with scripted provider responses. Returns (result_or_exc, anthropic_calls, oa_calls)."""
    a = MagicMock()
    a.messages.create.side_effect = list(anthropic_seq)
    o = MagicMock()
    o.chat.completions.create.side_effect = list(oa_seq)
    logs.clear()
    with patch("app.agents.llm_client.resolve_provider_chain", return_value=chain), patch(
        "app.agents.llm_client._anthropic", return_value=a
    ), patch("app.agents.llm_client._openai_compatible", return_value=o):
        try:
            result = call_with_tool(system="s", messages=[{"role": "user", "content": "hi"}], tools=[TOOL], force_tool="plan", **kw)
        except Exception as exc:  # noqa: BLE001
            result = exc
    return result, a.messages.create.call_count, o.chat.completions.create.call_count


GOOD = {"title": "ok", "subtasks": FIVE}
r, a_calls, _ = run(["anthropic"], [anthropic_response("plan", {"title": "ok", "subtasks": json.dumps(FIVE)})])
check("a stringified list is repaired: ONE call, a real list returned", a_calls == 1 and isinstance(r["input"]["subtasks"], list) and len(r["input"]["subtasks"]) == 5)
check("...and the repair is logged so you can see how often a model does it", any("repaired tool output for 'plan'" in m for m in logs))

r, a_calls, _ = run(["anthropic"], [anthropic_response("plan", {"title": "ok"}), anthropic_response("plan", GOOD)])
check("a missing required field is retried on the same provider and succeeds", a_calls == 2 and r["input"] == GOOD)
check("...the malformed attempt is logged", any("malformed output" in m for m in logs))

r, a_calls, _ = run(["anthropic"], [anthropic_response(None), anthropic_response("plan", GOOD)])
check("a reply with no tool call is retried and succeeds", a_calls == 2 and r["input"] == GOOD)

r, a_calls, o_calls = run(["anthropic", "deepseek"], [anthropic_response("plan", {"title": "x"})] * 2, [oa_response(json.dumps(GOOD))])
check("persistently malformed: 2 attempts on the first provider, then it fails over", a_calls == 2 and o_calls == 1)
check("...and the second provider's answer is returned", r["input"] == GOOD)

r, a_calls, o_calls = run(["deepseek"], oa_seq=[oa_response(tool_calls=False), oa_response(json.dumps(GOOD))])
check("OpenAI-compatible: a text answer instead of a tool call is retried", o_calls == 2 and r["input"] == GOOD)
r, a_calls, o_calls = run(["deepseek"], oa_seq=[oa_response("{not valid json"), oa_response(json.dumps(GOOD))])
check("OpenAI-compatible: unparseable arguments are retried (was an unhandled crash)", o_calls == 2 and r["input"] == GOOD)
r, _, o_calls = run(["deepseek"], oa_seq=[oa_response(json.dumps({"title": "ok", "subtasks": json.dumps(FIVE)}))])
check("OpenAI-compatible: a stringified list is repaired too", o_calls == 1 and len(r["input"]["subtasks"]) == 5)

r, a_calls, o_calls = run(["anthropic", "deepseek"], [AConnErr(request=MagicMock())], [oa_response(json.dumps(GOOD))])
check("a DOWN provider fails over at once - it is NOT retried", a_calls == 1 and o_calls == 1 and r["input"] == GOOD)

r, a_calls, o_calls = run(["anthropic", "deepseek"], [anthropic_response("plan", {"title": "x"})] * 2, [oa_response("{bad")] * 2)
check("everything malformed -> a clean 'all providers failed' error, not a crash",
      isinstance(r, RuntimeError) and str(r).startswith(ALL_PROVIDERS_FAILED))
check("...that says the answers were malformed, per provider", "anthropic: malformed output" in str(r) and "deepseek: malformed output" in str(r))
check("...after exactly 2 attempts per provider", a_calls == 2 and o_calls == 2)

def once_then_ok(exc):
    seen = []

    def validate(data):
        seen.append(1)
        if len(seen) == 1:
            raise exc

    return validate, seen


validate, seen = once_then_ok(MalformedToolOutput("first answer not good enough"))
r, a_calls, _ = run(["anthropic"], [anthropic_response("plan", GOOD)] * 2, validate=validate)
check("a caller's validate hook that rejects once is retried and then accepted", a_calls == 2 and len(seen) == 2 and r["input"] == GOOD)
validate, seen = once_then_ok(KeyError("title"))
r, a_calls, _ = run(["anthropic"], [anthropic_response("plan", GOOD)] * 2, validate=validate)
check("...a KeyError/TypeError raised by it is converted and retried, not propagated", a_calls == 2 and r["input"] == GOOD)

# ---- the exact failure from the real-model run, through the real endpoint --------------
seen_plan_calls = []
MODE = {"plan": "stringify"}  # stringify | short | good


def gen(schema, key=""):
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "string":
        gen.n += 1
        return f"Sample {key or 'text'} #{gen.n} that is long enough."
    if t in ("integer", "number"):
        return 4
    if t == "boolean":
        return True
    if t == "array":
        n = max(schema.get("minItems", 1), 1)
        return [gen(schema.get("items", {}), key) for _ in range(n)]
    if t == "object":
        return {k: gen(v, k) for k, v in schema.get("properties", {}).items()}
    return "x"


gen.n = 0


def fake_create(**kw):
    choice = kw["tool_choice"]
    tool = next(t for t in kw["tools"] if t["name"] == choice["name"])
    data = gen(tool["input_schema"])
    if tool["name"] == "plan_week":
        seen_plan_calls.append(MODE["plan"])
        if MODE["plan"] == "stringify":
            data["subtasks"] = json.dumps(data["subtasks"])  # <- exactly what Claude did
        elif MODE["plan"] == "short":
            data["subtasks"] = data["subtasks"][:3]
    return anthropic_response(tool["name"], data)


client = TestClient(app)
client.__enter__()
strict_client = TestClient(app, raise_server_exceptions=False)  # sees the real HTTP status a browser would


def signup(email):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Tool Tester"})
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# Pinned to a single provider throughout this section: without this, a real
# backend/.env with other providers' keys set (a normal developer machine) would
# let a failed/exhausted "anthropic" fall over to a REAL, unmocked second provider
# call, silently changing what this section is actually testing (retry/failover
# logic in isolation) — found running this suite on a machine with real keys.
with patch("app.agents.llm_client._anthropic") as mock_a, patch(
    "app.agents.llm_client.resolve_provider_chain", return_value=["anthropic"]
):
    mock_a.return_value.messages.create.side_effect = fake_create

    h = signup("tool-a@example.com")
    logs.clear()
    r = client.post("/agents/manager/assign-task", headers=h)
    check("Claude returns `subtasks` as a JSON string -> the task is still assigned (was: TypeError)", r.status_code == 201)
    plan = client.get("/projects/me", headers=h).json()["weeks"][0]["subtasks_plan_json"]
    check("...and the stored week plan has 5 real subtasks with titles", len(plan) == 5 and all(isinstance(s["title"], str) and s["title"] for s in plan))
    check("...the plan was made in ONE model call (repaired, not retried)", seen_plan_calls == ["stringify"])
    check("...and the repair shows up in the log", any("repaired tool output for 'plan_week'" in m for m in logs))

    h2 = signup("tool-b@example.com")
    seen_plan_calls.clear()
    MODE["plan"] = "short"
    orig = fake_create

    def short_then_good(**kw):
        if len(seen_plan_calls) >= 1:
            MODE["plan"] = "good"
        return orig(**kw)

    mock_a.return_value.messages.create.side_effect = short_then_good
    r = client.post("/agents/manager/assign-task", headers=h2)
    check("a plan with only 3 subtasks is retried and the second try is used", r.status_code == 201 and seen_plan_calls == ["short", "good"])
    check("...and the week has all 5", len(client.get("/projects/me", headers=h2).json()["weeks"][0]["subtasks_plan_json"]) == 5)

    h3 = signup("tool-c@example.com")
    seen_plan_calls.clear()
    MODE["plan"] = "short"
    mock_a.return_value.messages.create.side_effect = fake_create
    r = strict_client.post("/agents/manager/assign-task", headers=h3)
    check("a model that ALWAYS returns a bad plan gives a clean 503, not a 500", r.status_code == 503)
    check("...with a message saying why", "malformed output" in r.json()["detail"])
    check("...after exactly 2 attempts on the one provider", seen_plan_calls == ["short", "short"])
    MODE["plan"] = "good"
    r = strict_client.post("/agents/manager/assign-task", headers=h3)
    check("...and the graduate can simply try again - nothing was left half-broken", r.status_code == 201)

print("\nAll LLM tool-output smoke checks passed.")
