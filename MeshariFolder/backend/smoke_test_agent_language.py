"""
Smoke test for Arabic agent replies (docs/AGENT_LANGUAGE.md).

The frontend sends `X-Venv-Language: ar|en` on every request; llm_client appends
a language instruction to the system prompt of every model call it makes. This
suite proves that end to end against the REAL endpoints and REAL agents, with
only the model SDK faked (a schema-driven stand-in that records the system
prompt each call actually sends): Manager, Mentor, meeting room, HR, the
roundtable's specialists and synthesis, and the onboarding graph.

It also proves the things that would be embarrassing in a demo: English users
are untouched (no instruction at all), one request's language never leaks into
the next, an unsupported/garbled header falls back to English, and the
instruction is added exactly once per call.

Run: python smoke_test_agent_language.py
"""
import os
import time
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_agent_language.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.agents import llm_client  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.language import (  # noqa: E402
    LanguageMiddleware,
    current_language,
    language_directive,
    normalize_language,
    with_language,
)
from app.main import app  # noqa: E402
from app.models import UserAgent  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


MARK = "LANGUAGE INSTRUCTION"

# ---- unit level ---------------------------------------------------------------
check("normalize: 'ar' -> ar", normalize_language("ar") == "ar")
check("normalize: 'AR' (any case) -> ar", normalize_language("AR") == "ar")
check("normalize: 'ar-SA' (regional) -> ar", normalize_language("ar-SA") == "ar")
check("normalize: 'en' -> en", normalize_language("en") == "en")
check("normalize: unsupported 'fr' -> en", normalize_language("fr") == "en")
check("normalize: missing/empty/garbage -> en", normalize_language(None) == "en" and normalize_language("") == "en" and normalize_language("???") == "en")
check("default language adds nothing to a prompt", with_language("Be helpful.") == "Be helpful.")
token = current_language.set("ar")
try:
    check("Arabic adds the instruction after the original prompt", with_language("Be helpful.").startswith("Be helpful.") and MARK in with_language("Be helpful."))
    check("...which keeps JSON keys / enum values / code in English", "enum values" in language_directive() and "JSON keys" in language_directive())
finally:
    current_language.reset(token)
check("the context variable resets after use", language_directive() == "")


# ---- a schema-driven fake of the Anthropic SDK -----------------------------------
SYSTEMS: list[str] = []
N = [0]


def gen(schema, key=""):
    if not isinstance(schema, dict):
        return "x"
    if "enum" in schema:
        e = schema["enum"]
        return "approved" if "approved" in e else e[0]
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if t == "string":
        N[0] += 1
        return f"Sample {key or 'text'} #{N[0]}: long enough to pass any sanity check."
    if t in ("integer", "number"):
        return max(schema.get("minimum", 1), min(schema.get("maximum", 5), 4))
    if t == "boolean":
        return True
    if t == "array":
        n = min(max(schema.get("minItems", 1), 1), schema.get("maxItems", 99))
        return [gen(schema.get("items", {}), key) for _ in range(n)]
    if t == "object":
        return {k: gen(v, k) for k, v in schema.get("properties", {}).items()}
    return "x"


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def fake_create(**kw):
    SYSTEMS.append(kw["system"])
    tools = kw.get("tools") or []
    choice = kw.get("tool_choice") or {}
    if choice.get("type") == "tool":
        tool = next(t for t in tools if t["name"] == choice["name"])
        return Block(content=[Block(type="tool_use", name=tool["name"], input=gen(tool["input_schema"]))])
    return Block(content=[Block(type="text", text="A plain reply from the fake model.")])


class FakeOnboardingModel:  # LangChain-style, used by the onboarding graph
    def bind_tools(self, tools, tool_choice):
        name = tools[0]["function"]["name"]
        responses = {
            "generate_questions": {"questions": ["What did you build?", "Used Docker?"]},
            "suggest_track": {"track": "cybersecurity", "reasoning": "pen-testing coursework."},
            "suggest_agents": {"agent_ids": []},
        }

        class Bound:
            def invoke(self_inner, messages):
                SYSTEMS.append(messages[0].content)
                return Block(tool_calls=[{"name": name, "args": responses[name]}])

        return Bound()


def register(email, lang=None):
    h = {"X-Venv-Language": lang} if lang else {}
    r = client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Lang Tester"}, headers=h)
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"}, headers=h)
    return {"Authorization": f"Bearer {r.json()['access_token']}", **h}


def wait_for_roundtable(headers, task_id, timeout=10):
    """The specialists' discussion now runs in the BACKGROUND after the Mentor's
    review (docs/BACKGROUND_ROUNDTABLE.md) — its calls may not have happened yet the
    instant client.post(...) returns (TestClient is not guaranteed to block on
    FastAPI BackgroundTasks; confirmed to vary by platform/library version). Poll the
    task's roundtable_running flag, exactly like a real frontend does, instead of
    assuming synchronous completion."""
    deadline = time.time() + timeout
    detail = client.get(f"/tasks/{task_id}", headers=headers).json()
    while detail.get("roundtable_running") and time.time() < deadline:
        time.sleep(0.05)
        detail = client.get(f"/tasks/{task_id}", headers=headers).json()
    return detail


def run_demo_path(headers):
    """Manager plan -> submit -> Mentor review (+ roundtable if the roster has
    specialists) -> meeting-room chat -> HR rollup. Returns the system prompts sent."""
    SYSTEMS.clear()
    r = client.post("/agents/manager/assign-task", headers=headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    r = client.post(f"/tasks/{task_id}/submit", headers=headers, data={"submission_text": "Here is my implementation with tests."})
    assert r.status_code == 200, r.text
    r = client.post(f"/agents/mentor/review/{task_id}", headers=headers)
    assert r.status_code == 201, r.text
    detail = wait_for_roundtable(headers, task_id)
    assert not detail.get("roundtable_running"), f"roundtable for {task_id} did not finish in time"
    r = client.post("/meeting/mentor", headers=headers, json={"content": "What should I focus on next?"})
    assert r.status_code == 201, r.text
    r = client.post("/agents/hr/rollup", headers=headers)
    assert r.status_code == 201, r.text
    return list(SYSTEMS)


with patch("app.agents.llm_client._anthropic") as mock_anthropic, patch(
    "app.agents.graph.onboarding_graph.small_model_chain", return_value=[("anthropic", FakeOnboardingModel())]
):
    mock_anthropic.return_value.messages.create.side_effect = fake_create

    # ---- English: nothing changes --------------------------------------------------
    en = register("lang-en@example.com")
    en_systems = run_demo_path(en)
    check(f"English demo path made model calls ({len(en_systems)})", len(en_systems) >= 5)
    check("English: NO call carries a language instruction (behaviour unchanged)", not any(MARK in s for s in en_systems))

    # ---- Arabic: every call carries it, once ---------------------------------------
    ar = register("lang-ar@example.com", lang="ar")
    db = SessionLocal()
    ar_user_id = client.get("/users/me", headers=ar).json()["id"]
    db.add(UserAgent(user_id=ar_user_id, agent_catalog_id="security_reviewer"))
    db.commit()
    db.close()
    ar_systems = run_demo_path(ar)
    check(f"Arabic demo path made model calls ({len(ar_systems)})", len(ar_systems) >= 5)
    check("Arabic: EVERY model call carries the language instruction", all(MARK in s for s in ar_systems))
    check("Arabic: added exactly once per call (no double application)", all(s.count(MARK) == 1 for s in ar_systems))
    check("Arabic: the roundtable's specialist + synthesis calls ran too (more calls than English) and are covered",
          len(ar_systems) >= len(en_systems) + 2)
    check("Arabic: the agents' own prompts are still there (instruction is appended, not replacing)",
          all(len(s.split(MARK)[0].strip()) > 30 for s in ar_systems))

    # ---- no leakage between requests -----------------------------------------------
    SYSTEMS.clear()
    r = client.post("/meeting/mentor", headers=en, json={"content": "And after that?"})
    check("an English request right after Arabic ones is still English (no leak)", r.status_code == 201 and SYSTEMS and not any(MARK in s for s in SYSTEMS))
    SYSTEMS.clear()
    r = client.post("/meeting/mentor", headers=ar, json={"content": "And after that?"})
    check("...and Arabic still works afterwards", r.status_code == 201 and SYSTEMS and all(MARK in s for s in SYSTEMS))

    # ---- the browser's CORS preflight ------------------------------------------------------
    # Every request now carries X-Venv-Language, a non-standard header, so a BROWSER first asks
    # the server "may I send it?" (an OPTIONS preflight). The test client never does that, so
    # without this every test could pass while every browser request was blocked.
    ORIGIN = "http://localhost:3000"
    pre = client.options("/tasks", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET",
                                            "Access-Control-Request-Headers": "authorization,x-venv-language,content-type"})
    allowed = pre.headers.get("access-control-allow-headers", "").lower()
    check("a browser's preflight for the language header is approved (200)", pre.status_code == 200)
    check("...the server explicitly allows x-venv-language (else the browser blocks every request)", "x-venv-language" in allowed)
    check("...alongside authorization and content-type", "authorization" in allowed and "content-type" in allowed)
    check("...for the methods the app uses", all(m in pre.headers.get("access-control-allow-methods", "") for m in ("GET", "POST", "PATCH")))
    real = client.post("/auth/login", data={"username": "lang-en@example.com", "password": "hunter2pass"}, headers={"Origin": ORIGIN, "X-Venv-Language": "ar"})
    check("a real cross-origin request carrying the header succeeds and is answered with CORS headers",
          real.status_code == 200 and real.headers.get("access-control-allow-origin") in ("*", ORIGIN))

    # ---- the header alone decides (it is per request, not per user) -----------------
    SYSTEMS.clear()
    r = client.post("/meeting/mentor", headers={**en, "X-Venv-Language": "ar"}, json={"content": "Switching language mid-session."})
    check("the same user can switch to Arabic on the next request (header only, no saved setting)", r.status_code == 201 and all(MARK in s for s in SYSTEMS))
    for raw, expect_ar in (("ar-SA", True), ("AR", True), ("fr", False), ("xx", False), ("", False)):
        SYSTEMS.clear()
        client.post("/meeting/mentor", headers={**en, "X-Venv-Language": raw}, json={"content": "hi"})
        got_ar = bool(SYSTEMS) and all(MARK in s for s in SYSTEMS)
        check(f"header {raw!r} -> {'Arabic' if expect_ar else 'English'}", got_ar == expect_ar)

    # ---- the onboarding graph (LangChain path) --------------------------------------
    SYSTEMS.clear()
    o_en = register("lang-onb-en@example.com")
    client.post("/onboarding/cv", headers=o_en, files={"file": ("cv.txt", b"Built a Flask app.", "text/plain")})
    client.post("/onboarding/qa", headers=o_en, json={"answers": {}})
    check("English onboarding: no instruction in the graph's prompts", len(SYSTEMS) == 3 and not any(MARK in s for s in SYSTEMS))
    SYSTEMS.clear()
    o_ar = register("lang-onb-ar@example.com", lang="ar")
    client.post("/onboarding/cv", headers=o_ar, files={"file": ("cv.txt", b"Built a Flask app.", "text/plain")})
    client.post("/onboarding/qa", headers=o_ar, json={"answers": {}})
    check("Arabic onboarding: the questions AND the track-suggestion prompts carry the instruction",
          len(SYSTEMS) == 3 and all(MARK in s for s in SYSTEMS))

# ---- the OpenAI-compatible providers (DeepSeek / Qwen / OpenAI) get it too ---------
oa_client = MagicMock()
oa_message = MagicMock()
oa_message.content = "ok"
oa_message.tool_calls = []
oa_client.chat.completions.create.return_value.choices = [MagicMock(message=oa_message)]
with patch("app.agents.llm_client.resolve_provider_chain", return_value=["deepseek"]), patch(
    "app.agents.llm_client._openai_compatible", return_value=oa_client
):
    token = current_language.set("ar")
    try:
        llm_client.call_agentic(system="You are the Mentor.", messages=[{"role": "user", "content": "hi"}], tools=[])
    finally:
        current_language.reset(token)
    sent = oa_client.chat.completions.create.call_args.kwargs["messages"][0]
    check("OpenAI-compatible provider: the system message carries the instruction", sent["role"] == "system" and MARK in sent["content"])
    check("...and starts with the agent's own prompt", sent["content"].startswith("You are the Mentor."))

print("\nAll agent-language smoke checks passed.")
