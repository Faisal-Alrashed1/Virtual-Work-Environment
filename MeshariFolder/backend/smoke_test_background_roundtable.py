"""
Smoke test for the background roundtable (docs/BACKGROUND_ROUNDTABLE.md).

The problem: after the Mentor wrote its review, the endpoint ALSO waited for the whole
specialist discussion (three small-model turns + the Manager's synthesis) before answering,
so a submission took ~25 seconds to come back. Now the endpoint returns when the Mentor is
done, and the discussion appears in the task thread as it is written.

Two halves:

  (1) deterministic checks through the test client - what is stored, the running flag, no
      specialists = nothing scheduled, a failing roundtable never breaks the review, two
      reviews of one task are ordered not interleaved, Arabic still reaches the background;

  (2) the one that proves the point: a REAL HTTP server (uvicorn, in this process) with slow
      fake models, checking over the wire that the review response arrives BEFORE the
      discussion finishes, that the thread then grows message by message, and that the flag
      is true right after the response and false at the end. A test client can't show that -
      it always waits for background work - which is why this half exists.

Run: python smoke_test_background_roundtable.py
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_background_roundtable.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.agents import roundtable  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ROUNDTABLE_STALE_AFTER, Task, User, UserAgent  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


SPECIALISTS = ["security_reviewer", "data_reviewer", "devops"]
MARK = "LANGUAGE INSTRUCTION"
SYSTEMS: list[str] = []
DELAY = {"agentic": 0.0}


def gen(schema, key=""):
    if "enum" in schema:
        return "approved" if "approved" in schema["enum"] else schema["enum"][0]
    t = schema.get("type")
    if t == "string":
        gen.n += 1
        return f"Sample {key or 'text'} #{gen.n} that is long enough to pass."
    if t in ("integer", "number"):
        return 4
    if t == "boolean":
        return True
    if t == "array":
        return [gen(schema.get("items", {}), key) for _ in range(max(schema.get("minItems", 1), 1))]
    if t == "object":
        return {k: gen(v, k) for k, v in schema.get("properties", {}).items()}
    return "x"


gen.n = 0


def fake_create(**kw):
    SYSTEMS.append(kw["system"])
    choice = kw.get("tool_choice") or {}
    if choice.get("type") == "tool":  # the Mentor's review, the Manager's plan...
        tool = next(t for t in kw["tools"] if t["name"] == choice["name"])
        block = MagicMock(type="tool_use")
        block.name, block.input = tool["name"], gen(tool["input_schema"])
        return MagicMock(content=[block])
    time.sleep(DELAY["agentic"])  # a specialist's turn or the Manager's synthesis
    return MagicMock(content=[MagicMock(type="text", text="A thoughtful comment from the team.")])


client = TestClient(app)
client.__enter__()


def signup(email, lang=None, roster=SPECIALISTS):
    h = {"X-Venv-Language": lang} if lang else {}
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Roundtable Tester"}, headers=h)
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"}, headers=h)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}", **h}
    user_id = client.get("/users/me", headers=headers).json()["id"]
    db = SessionLocal()
    for agent_id in roster:
        db.add(UserAgent(user_id=user_id, agent_catalog_id=agent_id))
    task = Task(title="Build the thing", description="Per the spec.", user_id=user_id)
    db.add(task)
    db.commit()
    task_id = task.id
    db.close()
    return headers, user_id, task_id


def db_task(task_id):
    db = SessionLocal()
    try:
        t = db.get(Task, task_id)
        db.expunge(t)
        return t
    finally:
        db.close()


def submit_and_review(headers, task_id):
    client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"}, headers=headers)
    r = client.post(f"/tasks/{task_id}/submit", headers=headers, data={"submission_text": "My implementation, with notes."})
    assert r.status_code == 200, r.text
    return client.post(f"/agents/mentor/review/{task_id}", headers=headers)


def who(headers, task_id):
    detail = client.get(f"/tasks/{task_id}", headers=headers).json()
    return [m["agent_type"] for m in detail["messages"]], detail


def wait_for_roundtable(headers, task_id, timeout=10):
    """Poll until the background discussion is done, exactly like a real frontend
    does — TestClient is not guaranteed to block on FastAPI BackgroundTasks until
    they finish (confirmed to vary by platform/library version), so a check made the
    instant .post() returns can see the discussion only partway through, or not yet
    started at all."""
    deadline = time.time() + timeout
    detail = client.get(f"/tasks/{task_id}", headers=headers).json()
    while detail.get("roundtable_running") and time.time() < deadline:
        time.sleep(0.05)
        detail = client.get(f"/tasks/{task_id}", headers=headers).json()
    return detail


# ============================ (1) deterministic ==============================================
with patch("app.agents.llm_client._anthropic") as mock_a:
    mock_a.return_value.messages.create.side_effect = fake_create

    h, uid, tid = signup("rt-full@example.com")
    SYSTEMS.clear()
    r = submit_and_review(h, tid)
    check("the Mentor's review is returned (201)", r.status_code == 201 and r.json()["metrics_json"]["verdict"] == "approved")
    wait_for_roundtable(h, tid)
    agents, detail = who(h, tid)
    check("the specialists' discussion was still written (all three, in order)", [a for a in agents if a in SPECIALISTS] == sorted(SPECIALISTS))
    check("...and the Manager's synthesis came last", agents[-1] == "manager")
    check("...after the Mentor's own summary", agents.index("mentor") < agents.index("security_reviewer") if "mentor" in agents else True)
    t = db_task(tid)
    check("the discussion was marked started AND finished in the database", t.roundtable_started_at is not None and t.roundtable_finished_at is not None)
    check("...finished after it started", t.roundtable_finished_at >= t.roundtable_started_at)
    check("...so it is not reported as running", detail["roundtable_running"] is False)
    check("the running flag is part of the task API", "roundtable_running" in detail and all("roundtable_running" in x for x in client.get("/tasks", headers=h).json()))

    h2, _, tid2 = signup("rt-none@example.com", roster=[])
    r = submit_and_review(h2, tid2)
    t = db_task(tid2)
    agents, detail = who(h2, tid2)
    check("no specialists: the review works exactly as before", r.status_code == 201)
    check("...nothing is scheduled (never marked started)", t.roundtable_started_at is None and t.roundtable_finished_at is None)
    check("...so nothing ever shows as running, and no discussion is posted", detail["roundtable_running"] is False and not [a for a in agents if a in SPECIALISTS + ["manager"]])

    # begin_roundtable
    db = SessionLocal()
    task = db.get(Task, tid2)
    task.roundtable_finished_at = datetime.utcnow()
    token = roundtable.begin_roundtable(db, task)
    check("begin_roundtable stamps the start, clears any earlier finish, and returns the run's token",
          task.roundtable_started_at == token and task.roundtable_finished_at is None)
    task.roundtable_started_at = task.roundtable_finished_at = None
    db.commit()
    db.close()

    # the flag, in every state it can be in
    now = datetime.utcnow()
    for label, started, finished, expected in (
        ("never started", None, None, False),
        ("started a moment ago, not finished", now - timedelta(seconds=10), None, True),
        ("started and finished", now - timedelta(seconds=10), now - timedelta(seconds=5), False),
        ("finished at the very instant it started", now - timedelta(seconds=10), now - timedelta(seconds=10), False),
        ("an OLD finish from a previous review, new run started since", now - timedelta(seconds=10), now - timedelta(seconds=60), True),
        ("started long ago and never finished (the worker died)", now - ROUNDTABLE_STALE_AFTER - timedelta(seconds=1), None, False),
        ("just inside the stale limit", now - ROUNDTABLE_STALE_AFTER + timedelta(seconds=5), None, True),
    ):
        probe = Task(title="p", description="d", user_id=uid, roundtable_started_at=started, roundtable_finished_at=finished)
        check(f"roundtable_running is {expected} when: {label}", probe.roundtable_running is expected)
    db = SessionLocal()
    db.get(Task, tid2).roundtable_started_at = now - timedelta(minutes=10)
    db.commit()
    db.close()
    check("a roundtable whose worker died 10 minutes ago reads as not running through the API", client.get(f"/tasks/{tid2}", headers=h2).json()["roundtable_running"] is False)

    # a failing roundtable never breaks the review
    h3, _, tid3 = signup("rt-fail@example.com")
    log_lines = []

    class Grab(logging.Handler):
        def emit(self, record):
            log_lines.append(record.getMessage())

    grab = Grab()
    logging.getLogger("venv.roundtable").addHandler(grab)
    with patch("app.agents.roundtable.run_roundtable", side_effect=RuntimeError("provider exploded")):
        r = submit_and_review(h3, tid3)
        wait_for_roundtable(h3, tid3)
    logging.getLogger("venv.roundtable").removeHandler(grab)
    t = db_task(tid3)
    check("a roundtable that blows up: the review is still delivered (201)", r.status_code == 201)
    check("...the task is reviewed anyway", client.get(f"/tasks/{tid3}", headers=h3).json()["status"] == "reviewed")
    check("...it is marked finished, so the UI never spins forever", t.roundtable_finished_at is not None and client.get(f"/tasks/{tid3}", headers=h3).json()["roundtable_running"] is False)
    check("...and the failure is logged, not swallowed silently", any("failed; the Mentor's review stands" in m for m in log_lines))

    # two discussions for one task: ordered, never interleaved; only the latest can finish it
    h4, uid4, tid4 = signup("rt-overlap@example.com")
    events = []
    gate = {k: threading.Event() for k in ("first_in", "release", "second_in", "release2")}

    def slow_roundtable(db, user, task):
        n = len([e for e in events if e[0] == "enter"]) + 1
        events.append(("enter", n))
        if n == 1:
            gate["first_in"].set()
            gate["release"].wait(5)
        else:
            gate["second_in"].set()
            gate["release2"].wait(5)
        events.append(("exit", n))
        return []

    db = SessionLocal()
    task = db.get(Task, tid4)
    token1 = roundtable.begin_roundtable(db, task)
    time.sleep(0.01)
    with patch("app.agents.roundtable.run_roundtable", side_effect=slow_roundtable):
        th1 = threading.Thread(target=roundtable.run_roundtable_job, args=(tid4, uid4, token1))
        th1.start()
        gate["first_in"].wait(5)
        token2 = roundtable.begin_roundtable(db, task)  # a resubmission's review, while #1 is still talking
        th2 = threading.Thread(target=roundtable.run_roundtable_job, args=(tid4, uid4, token2))
        th2.start()
        time.sleep(0.3)
        check("a second discussion for the same task WAITS for the first (they are not interleaved)", events == [("enter", 1)])
        check("...and the task reads as running throughout", client.get(f"/tasks/{tid4}", headers=h4).json()["roundtable_running"] is True)
        gate["release"].set()
        th1.join(5)
        gate["second_in"].wait(5)  # the newer discussion is now talking; the older one has finished
        check("the OLDER run finishing did NOT mark the task finished - the newer one is still going", db_task(tid4).roundtable_finished_at is None)
        check("...so the task still reads as running", client.get(f"/tasks/{tid4}", headers=h4).json()["roundtable_running"] is True)
        gate["release2"].set()
        th2.join(5)
    check("they ran strictly one after the other", events == [("enter", 1), ("exit", 1), ("enter", 2), ("exit", 2)])
    t = db_task(tid4)
    check("only the LATEST run declares the task finished, once it is done", t.roundtable_started_at == token2 and t.roundtable_finished_at is not None and t.roundtable_finished_at >= token2)
    check("...and then it reads as not running", client.get(f"/tasks/{tid4}", headers=h4).json()["roundtable_running"] is False)
    db.close()

    # the listing costs nothing extra
    statements = []

    def count_reviews(conn, cursor, statement, parameters, context, executemany):
        if "FROM reviews" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_reviews)
    client.get("/tasks", headers=h)
    event.remove(engine, "before_cursor_execute", count_reviews)
    check("listing tasks still loads reviews in at most one query (the new flag adds none)", len(statements) <= 1)

    # language reaches the background
    h5, _, tid5 = signup("rt-ar@example.com", lang="ar")
    SYSTEMS.clear()
    submit_and_review(h5, tid5)
    wait_for_roundtable(h5, tid5)
    check(f"Arabic request: every model call carries the language instruction, INCLUDING the background discussion ({len(SYSTEMS)} calls)",
          len(SYSTEMS) >= 5 and all(MARK in s for s in SYSTEMS))
    h6, _, tid6 = signup("rt-en@example.com")
    SYSTEMS.clear()
    submit_and_review(h6, tid6)
    wait_for_roundtable(h6, tid6)
    check("English request: none of them do (no leak from the Arabic one before it)", len(SYSTEMS) >= 5 and not any(MARK in s for s in SYSTEMS))

# ============================ (2) over a real HTTP server ========================================
def free_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
for _ in range(100):
    if server.started:
        break
    time.sleep(0.1)
check("a real HTTP server is up for the timing test", server.started)

try:
    with patch("app.agents.llm_client._anthropic") as mock_a:
        mock_a.return_value.messages.create.side_effect = fake_create
        DELAY["agentic"] = 1.0  # each specialist turn and the synthesis take a second: 4 seconds in all

        with httpx.Client(base_url=f"http://127.0.0.1:{PORT}", timeout=30) as http:
            email = "rt-wire@example.com"
            http.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Wire Tester"})
            tok = http.post("/auth/login", data={"username": email, "password": "hunter2pass"}).json()["access_token"]
            hh = {"Authorization": f"Bearer {tok}"}
            wire_uid = http.get("/users/me", headers=hh).json()["id"]
            db = SessionLocal()
            for agent_id in SPECIALISTS:
                db.add(UserAgent(user_id=wire_uid, agent_catalog_id=agent_id))
            task = Task(title="Wire task", description="d", user_id=wire_uid)
            db.add(task)
            db.commit()
            wire_tid = task.id
            db.close()
            http.patch(f"/tasks/{wire_tid}/status", json={"status": "in_progress"}, headers=hh)
            http.post(f"/tasks/{wire_tid}/submit", headers=hh, data={"submission_text": "Here is my work."})

            started = time.time()
            r = http.post(f"/agents/mentor/review/{wire_tid}", headers=hh)
            response_time = time.time() - started
            check("[wire] the review response comes back", r.status_code == 201)
            check(f"[wire] ...BEFORE the discussion finishes: {response_time:.2f}s, while the discussion alone takes ~4s (inline it would be 4s+)", response_time < 2.0)

            detail = http.get(f"/tasks/{wire_tid}", headers=hh).json()
            check("[wire] the very next fetch already says the discussion is running", detail["roundtable_running"] is True)
            first_count = len(detail["messages"])

            counts, deadline = [first_count], time.time() + 20
            while time.time() < deadline:
                d = http.get(f"/tasks/{wire_tid}", headers=hh).json()
                counts.append(len(d["messages"]))
                if not d["roundtable_running"]:
                    break
                time.sleep(0.2)
            total_time = time.time() - started
            final = http.get(f"/tasks/{wire_tid}", headers=hh).json()
            check("[wire] the discussion finishes (the flag goes false)", final["roundtable_running"] is False)
            check("[wire] ...taking the seconds the slow models need, i.e. it really ran AFTER the response", total_time > 3.0)
            check("[wire] the thread GREW over time, message by message (never jumped from nothing to everything)",
                  len(set(counts)) >= 3 and counts == sorted(counts))
            final_agents = [m["agent_type"] for m in final["messages"]]
            check("[wire] the final thread has the three specialists and the Manager's synthesis",
                  all(a in final_agents for a in SPECIALISTS) and final_agents[-1] == "manager")
            check("[wire] the Mentor's review itself was delivered and the task reviewed", final["status"] == "reviewed")
finally:
    server.should_exit = True
    thread.join(10)

print("\nAll background-roundtable smoke checks passed.")
