"""
End-to-end check with REAL LLM providers — the counterpart to the smoke
suites, which mock every model call. Run this before a demo to find out what
only real models can tell you: slow calls, malformed tool output, a provider
that doesn't support images, a wrong key, a failover that doesn't fail over.

It drives the real API in-process (no server needed) against a throwaway
SQLite file, using the keys in backend/.env, and walks the demo path:

  register -> onboarding (CV, Q&A, track, team) -> Manager plans a week ->
  submit work (link + text, optionally an image) -> Mentor review (+ the
  roundtable of your optional agents) -> meeting-room chat -> HR rollup
  [-> with --full-week: all five subtasks and the end-of-week cascade]

then prints a report: per-step result and time, which provider answered how
many calls, and every failover.

Run (from backend/, with your venv active):

  python e2e_real_llm.py                       # providers as configured in .env
  python e2e_real_llm.py --provider qwen       # force ONE provider for every call
  python e2e_real_llm.py --provider qwen --with-image
  python e2e_real_llm.py --full-week --repo https://github.com/<you>/<repo>
  python e2e_real_llm.py --language ar         # do the agents really answer in Arabic?
  python e2e_real_llm.py --full-week --force-approve   # exercise the end-of-week cascade even if the Mentor keeps bouncing
  python e2e_real_llm.py --save-report run1.json       # keep what the models produced, to review or share

Real calls cost real (small) money. The default run makes roughly 10-25 calls.

Notes
  * GitHub: each review costs 3 requests against an anonymous limit of 60/hour/IP.
    Set GITHUB_TOKEN in backend/.env (no scopes needed) for anything beyond a quick run.
  * The Mentor reads the GitHub repo you submit. The default (psf/requests) is
    just a harmless public repo, so the Mentor will often say "needs changes"
    because it doesn't match the task — that is fine for checking the
    pipeline. For --full-week pass --repo with a repo that really fits, or the
    Mentor may never approve and the week can't finish.
  * Exit code: 0 = every hard check passed, 1 = a check failed, 2 = setup problem.
"""
import argparse
import json
import logging
import os
import re
import struct
import sys
import time
import zlib
from collections import Counter

# ---------------------------------------------------------------- arguments
parser = argparse.ArgumentParser(description="End-to-end check with real LLM providers.")
parser.add_argument("--provider", choices=["anthropic", "openai", "deepseek", "qwen"],
                    help="force this one provider for every call (ignores the priority lists in .env)")
parser.add_argument("--full-week", action="store_true",
                    help="work through all 5 subtasks so the end-of-week cascade runs (needs --repo that fits the task)")
parser.add_argument("--subtasks", type=int, default=1, help="how many subtasks to submit+review (default 1; --full-week = 5)")
parser.add_argument("--max-resubmits", type=int, default=2, help="resubmissions after 'needs changes' (default 2)")
parser.add_argument("--with-image", action="store_true", help="attach a small PNG to the first submission (tests vision)")
parser.add_argument("--no-specialists", action="store_true", help="skip adding the optional agents (skips the roundtable)")
parser.add_argument("--repo", default="https://github.com/psf/requests", help="GitHub repo to submit")
parser.add_argument("--force-approve", action="store_true",
                    help="if the Mentor keeps bouncing a subtask (it will, if the repo is unchanged between attempts), "
                         "record a synthetic approval so the week can finish and the end-of-week cascade (Manager + HR + "
                         "Mentor consult, real models) still gets exercised. Clearly marked FORCED in the report.")
parser.add_argument("--save-report", metavar="FILE",
                    help="also write everything the models produced (the project, the week plan, every Mentor review with its "
                         "scores and comments) plus timings and provider stats to this JSON file - send it to whoever is tuning the prompts")
parser.add_argument("--keep-db", action="store_true", help="keep the throwaway database afterwards")
parser.add_argument("--language", choices=["en", "ar"], default="en",
                    help="send X-Venv-Language, like the frontend does; with 'ar' the check also FAILS if the agents' "
                         "questions, plan, review or chat replies come back without Arabic text")
args = parser.parse_args()
if args.full_week:
    args.subtasks = 5

# ------------------------------------------- configure BEFORE importing the app
DB_FILE = "e2e_real_llm.db"
for suffix in ("", "-journal"):
    if os.path.exists(DB_FILE + suffix):
        os.remove(DB_FILE + suffix)
os.environ["DATABASE_URL"] = f"sqlite:///./{DB_FILE}"
if args.provider:
    os.environ["LLM_PROVIDER_PRIORITY"] = args.provider
    os.environ["LLM_PROVIDER_PRIORITY_MAIN"] = ""
    os.environ["LLM_PROVIDER_PRIORITY_SMALL"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.llm_client import resolve_provider_chain  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

# ------------------------------------------------------------------ pre-flight
KEYS = {
    "anthropic": settings.anthropic_api_key, "openai": settings.openai_api_key,
    "deepseek": settings.deepseek_api_key, "qwen": settings.qwen_api_key,
}
print("Providers (a key is 'set' if present in .env / the environment):")
for name, key in KEYS.items():
    print(f"  {name:<10} {'set' if key else 'missing'}")
try:
    chain_main, chain_small = resolve_provider_chain("main"), resolve_provider_chain("small")
except Exception as exc:  # noqa: BLE001
    print(f"\n[SETUP] Could not resolve the provider chain: {exc}")
    sys.exit(2)
if not chain_main or not chain_small:
    print("\n[SETUP] No usable provider: none of the providers in the priority list has an API key.")
    print("        Put a key in backend/.env (e.g. ANTHROPIC_API_KEY=...) or pass --provider for one that has one.")
    sys.exit(2)
print(f"  {'github':<10} " + ("token set" if settings.github_token else "no token: anonymous limit is 60 requests/hour and each review costs 3 (--full-week uses ~45) - set GITHUB_TOKEN in .env"))
print(f"\nLanguage sent to the agents: {args.language}")
print(f"Main-tier chain (Mentor reviews, Manager plans): {' -> '.join(chain_main)}")
print(f"Small-tier chain (onboarding, roundtable comments): {' -> '.join(chain_small)}\n")


# ----------------------------------------------------- watch the LLM client's log
class LLMWatcher(logging.Handler):
    def __init__(self):
        super().__init__()
        self.calls, self.failovers = Counter(), []
        self.repairs, self.malformed = [], []  # what real models got wrong (see agents/tool_output.py)

    def emit(self, record):
        msg = record.getMessage()
        if not msg.startswith("[LLM]"):
            return
        if "failing over" in msg:
            self.failovers.append(msg)
        elif "repaired tool output" in msg:
            self.repairs.append(msg)
        elif "returned malformed output" in msg:
            self.malformed.append(msg)
        else:
            parts = msg.split()
            if len(parts) > 1:
                self.calls[parts[1]] += 1


watcher = LLMWatcher()
logging.getLogger("venv.llm").addHandler(watcher)

client = TestClient(app)
if args.language != "en":
    client.headers["X-Venv-Language"] = args.language  # what the frontend sends on every call
client.__enter__()  # runs the startup event (migrations + agent catalog), like a real server

# ----------------------------------------------------------------- tiny helpers
results = []  # (step, status, seconds, note)
S = {}  # shared state between steps


class HardFail(AssertionError):
    pass


def expect(condition, message):
    if not condition:
        raise HardFail(message)


ARABIC_LETTER = re.compile("[\u0600-\u06FF]")


def expect_language(text, what):
    """With --language ar: the model must actually have written Arabic."""
    if args.language == "ar":
        expect(ARABIC_LETTER.search(text or ""), f"{what} has no Arabic text - the model ignored the language instruction")


_wire = {}


def wire():
    """A real HTTP client to a real (local, in-process) server. The in-process test client always
    waits for background work, so it can't show what a graduate actually waits for; this can."""
    if "http" not in _wire:
        import socket
        import threading

        import httpx
        import uvicorn

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        _wire.update(server=server, thread=thread, http=httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=300, headers=dict(client.headers)))
    return _wire["http"]


def stop_wire():
    if "server" in _wire:
        _wire["http"].close()
        _wire["server"].should_exit = True
        _wire["thread"].join(10)


def call(method, path, expected=(200, 201), **kw):
    r = client.request(method, path, **kw)
    if r.status_code not in (expected if isinstance(expected, tuple) else (expected,)):
        detail = r.text[:300].replace("\n", " ")
        raise HardFail(f"{method} {path} -> HTTP {r.status_code}: {detail}")
    return r


def step(name, fn, fatal=True):
    started = time.time()
    note = ""
    try:
        note = fn() or ""
        status = "OK"
    except HardFail as exc:
        status, note = "FAIL", str(exc)
    except Exception as exc:  # noqa: BLE001
        status, note = "FAIL", f"{type(exc).__name__}: {exc}"
    took = time.time() - started
    results.append((name, status, took, note))
    tag = {"OK": "[ OK ]", "FAIL": "[FAIL]"}[status]
    print(f"{tag} {name}  ({took:.1f}s){'  - ' + note if note else ''}", flush=True)
    if status == "FAIL" and fatal:
        finish()
    return status == "OK"


def tiny_png(w=96, h=96):
    """A small valid PNG (gradient) without needing Pillow."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"".join(bytes([x * 255 // w, y * 255 // h, 160]) for x in range(w)) for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


SAMPLE_CV = b"""Aya Al-Harbi - Junior Full-Stack Developer
BSc Information Systems, King Saud University (2026)

Projects
- Capstone: campus events app (FastAPI + PostgreSQL + React). Built the REST API, JWT login and a booking flow.
- Personal: Flask URL shortener with pytest tests, deployed with Docker.

Skills: Python, JavaScript, SQL, Git, REST APIs, basic Docker. Some exposure to CI with GitHub Actions.
Interests: web security, cloud deployment.
"""


# ---------------------------------------------------------------------- steps
def s_register():
    email = f"e2e-{int(time.time())}@example.com"
    call("POST", "/auth/register", 201, json={"email": email, "password": "hunter2pass", "full_name": "E2E Tester"})
    r = call("POST", "/auth/login", 200, data={"username": email, "password": "hunter2pass"})
    S["h"] = {"Authorization": f"Bearer {r.json()['access_token']}"}


def s_onboarding_cv():
    r = call("POST", "/onboarding/cv", 200, headers=S["h"], files={"file": ("cv.txt", SAMPLE_CV, "text/plain")})
    qs = r.json()["questions"]
    expect(1 <= len(qs) <= 4, f"expected 1-4 questions, got {len(qs)}")
    expect(all(isinstance(q, str) and len(q.strip()) > 8 for q in qs), "a question was empty or too short")
    expect_language(" ".join(qs), "the onboarding questions")
    S["questions"] = qs
    return f"{len(qs)} questions"


def s_onboarding_qa():
    answers = {"0": "I built the API and the login flow; a teammate did the React side."}
    r = call("POST", "/onboarding/qa", 200, headers=S["h"], json={"answers": answers, "intro_text": "I want to grow in web security."})
    body = r.json()
    valid = {"software_engineering", "data_science_ai", "cybersecurity", "networks_infrastructure", "information_systems", "cloud_devops"}
    expect(body["suggested_track"] in valid, f"suggested track {body['suggested_track']!r} is not a Stage 2 track")
    expect(len(body["reasoning"].strip()) > 10, "the track suggestion came with no reasoning")
    expect_language(body["reasoning"], "the track reasoning")
    return f"track suggested: {body['suggested_track']}"


def s_onboarding_track():
    r = call("POST", "/onboarding/track", 200, headers=S["h"], json={})
    ids = [a["id"] for a in r.json()["suggested_agents"]]
    S["suggested_agents"] = ids
    return f"suggested agents: {ids or 'none'}"


def s_onboarding_agents():
    catalog = {a["id"] for a in call("GET", "/onboarding/catalog", 200).json()}
    chosen = [] if args.no_specialists else sorted(catalog & {"data_reviewer", "devops", "security_reviewer"})
    r = call("POST", "/onboarding/agents", 200, headers=S["h"], json={"agent_ids": chosen})
    S["specialists"] = chosen
    expect(r.json()["track"] != "junior_dev", "track was not applied")
    return f"team: Manager, Mentor, HR + {chosen or 'no specialists'}"


def s_plan_week():
    r = call("POST", "/agents/manager/assign-task", 201, headers=S["h"])
    task = r.json()
    expect(len(task["title"].strip()) > 3 and len(task["description"].strip()) > 30, "the first task looks empty or too short")
    expect(task["deadline"] is not None, "the task has no deadline")
    expect_language(task["title"] + " " + task["description"], "the Manager's task")
    S["task"] = task
    p = call("GET", "/projects/me", 200, headers=S["h"]).json()
    plan = p["weeks"][0]["subtasks_plan_json"]
    expect(len(plan) == 5, f"the week plan has {len(plan)} subtasks, expected 5")
    expect(len({s["title"] for s in plan}) == 5, "the plan has duplicate subtask titles")
    S["produced_plan"] = {"project": p["title"], "description": p["description"], "seed_id": p.get("seed_id"),
                          "big_task": p["weeks"][0]["big_task_title"], "subtasks": [{"title": s["title"], "description": s["description"]} for s in plan]}
    return f"project: {p['title']!r} (seed: {p.get('seed_id') or 'none'}); subtask 1: {task['title']!r}"


def submit_and_review(task, text, with_image):
    data = {"github_link": args.repo, "submission_text": text}
    files = [("files", ("mockup.png", tiny_png(), "image/png"))] if with_image else None
    call("POST", f"/tasks/{task['id']}/submit", 200, headers=S["h"], data=data, files=files)
    # Over real HTTP so the timing is what a graduate would actually wait: the Mentor's review comes
    # back first; the specialists' discussion then finishes in the background (docs/BACKGROUND_ROUNDTABLE.md).
    started = time.time()
    r = wire().post(f"/agents/mentor/review/{task['id']}", headers=S["h"])
    mentor_seconds = time.time() - started
    if r.status_code != 201:
        raise HardFail(f"POST /agents/mentor/review/... -> HTTP {r.status_code}: {r.text[:300]}")
    review = r.json()
    detail = wire().get(f"/tasks/{task['id']}", headers=S["h"]).json()
    while detail["roundtable_running"] and time.time() - started < 300:
        time.sleep(0.5)
        detail = wire().get(f"/tasks/{task['id']}", headers=S["h"]).json()
    S.setdefault("timings", []).append({"task": task["title"], "mentor_seconds": round(mentor_seconds, 1),
                                        "discussion_done_seconds": round(time.time() - started, 1) if S.get("specialists") else None})
    m = review["metrics_json"] or {}
    expect(m.get("verdict") in ("approved", "needs_changes"), f"unexpected Mentor verdict {m.get('verdict')!r}")
    expect(len(review["content"].strip()) > 30, "the Mentor's review text is empty or tiny")
    expect_language(review["content"], "the Mentor's review")
    scores = {c.get("key"): c.get("score") for c in (m.get("categories") or []) if isinstance(c, dict)}
    S.setdefault("produced_reviews", []).append({
        "task": task["title"], "verdict": m["verdict"], "scores": scores, "verdict_adjusted": bool(m.get("verdict_adjusted")),
        "summary": review["content"], "comments": m.get("comments") or [],
    })
    return review


def force_approve(task):
    """Record a synthetic Mentor approval directly in the throwaway database, so a week can
    finish when the real Mentor won't approve an unchanged submission."""
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import AgentType, Review, ReviewKind, Task, TaskStatus

    db = SessionLocal()
    try:
        t = db.get(Task, task["id"])
        t.status, t.completed_at = TaskStatus.REVIEWED, datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(Review(
            user_id=t.user_id, task_id=t.id, week_id=t.week_id, agent_type=AgentType.MENTOR, kind=ReviewKind.TASK_REVIEW,
            content="(Approval recorded by e2e_real_llm.py --force-approve, not by the Mentor.)",
            metrics_json={"verdict": "approved", "forced": True, "comments": [],
                          "categories": [{"key": k, "label": k, "score": 4} for k in ("correctness", "code_quality", "testing", "documentation")]},
        ))
        db.commit()
    finally:
        db.close()


def s_week():
    current, notes, approved_count = S["task"], [], 0
    for i in range(1, args.subtasks + 1):
        approved = False
        for attempt in range(1, args.max_resubmits + 2):
            text = ("Here is my implementation, with tests and a short README on how to run it."
                    if attempt == 1 else "Resubmitting for another review. (Automated check: nothing was changed.)")
            review = submit_and_review(current, text, with_image=(args.with_image and i == 1 and attempt == 1))
            verdict = review["metrics_json"]["verdict"]
            if review["metrics_json"].get("verdict_adjusted"):
                notes.append(f"subtask {i}: the model said 'approved' but scored 'meets requirements' below the bar - the rubric rule bounced it")
            if i == 1 and attempt == 1:
                S["first_review"], S["first_task_id"] = review, current["id"]
            if verdict == "approved":
                approved = True
                break
        notes.append(f"subtask {i}: {'approved' if approved else 'needs changes'} after {attempt} submission(s)")
        if not approved and args.force_approve:
            force_approve(current)
            notes.append(f"subtask {i}: FORCED approval (--force-approve) - the Mentor kept asking for changes")
            approved = True
        if not approved:
            notes.append("(Mentor kept asking for changes - expected if --repo doesn't fit the task or the repo is unchanged between attempts; "
                         "the pipeline itself worked. Use --force-approve to still exercise the end-of-week cascade.)")
            break
        approved_count += 1
        r = call("POST", "/agents/manager/assign-task", 201, headers=S["h"])
        current = r.json()
    S["approved_count"] = approved_count
    return "; ".join(notes)


def s_roundtable_visible():
    detail = call("GET", f"/tasks/{S['first_task_id']}", 200, headers=S["h"]).json()
    who = Counter(m["agent_type"] for m in detail["messages"] if m.get("agent_type"))
    if S["specialists"]:
        spoke = [a for a in S["specialists"] if who.get(a)]
        expect(spoke, f"none of your optional agents ({S['specialists']}) posted in the task thread - roundtable didn't run")
        return f"thread agents: {dict(who)}"
    return f"thread agents: {dict(who)} (no specialists chosen)"


def s_meeting():
    r = call("POST", "/meeting/mentor", 201, headers=S["h"], json={"content": "In one sentence, what should I focus on next?"})
    expect(len(r.json()["content"].strip()) > 5, "the Mentor's chat reply was empty")
    expect_language(r.json()["content"], "the Mentor's chat reply")
    if S["specialists"]:
        agent = S["specialists"][0]
        r = call("POST", f"/meeting/{agent}", 201, headers=S["h"], json={"content": "What is the biggest risk in my work so far?"})
        expect(len(r.json()["content"].strip()) > 5, f"{agent}'s chat reply was empty")
        return f"mentor + {agent} replied"
    return "mentor replied"


def s_hr_rollup():
    r = call("POST", "/agents/hr/rollup", 201, headers=S["h"])
    expect(len(r.json()["content"].strip()) > 10, "HR's rollup was empty")


def s_cascade():
    reviews = call("GET", "/users/me/reviews", 200, headers=S["h"]).json()
    kinds = Counter(r["kind"] for r in reviews)
    expect(kinds["week_progress"] >= 1, f"no Manager week-progress review after week 1 (have {dict(kinds)})")
    expect(kinds["behavioral"] >= 1, f"no HR behavioral review after week 1 (have {dict(kinds)})")
    weeks = call("GET", "/projects/me", 200, headers=S["h"]).json()["weeks"]
    expect(len(weeks) >= 2 and weeks[0]["status"] == "completed", "week 1 didn't complete / week 2 didn't start")
    return f"reviews: {dict(kinds)}; week 2 started"


# ------------------------------------------------------------------- report
def finish():
    print("\n" + "=" * 68)
    print(f"{'Step':<38}{'Result':<8}{'Time':>8}")
    print("-" * 68)
    for name, status, took, _ in results:
        print(f"{name:<38}{status:<8}{took:>7.1f}s")
    print("-" * 68)
    total = sum(t for _, _, t, _ in results)
    print(f"Total wall time: {total:.0f}s")
    if watcher.calls:
        print("LLM calls by provider: " + ", ".join(f"{p}={n}" for p, n in watcher.calls.most_common()))
    if watcher.failovers:
        print(f"\nFAILOVERS ({len(watcher.failovers)}) - a provider failed and the next one was used:")
        for line in watcher.failovers[:8]:
            print("  " + line)
    else:
        print("Failovers: none")
    if watcher.repairs:
        print(f"\nREPAIRED model output ({len(watcher.repairs)}) - the model answered oddly and we fixed it (this used to crash):")
        for line in watcher.repairs[:8]:
            print("  " + line)
    if watcher.malformed:
        print(f"\nMALFORMED model output ({len(watcher.malformed)}) - unusable answers that were retried / failed over:")
        for line in watcher.malformed[:8]:
            print("  " + line)
    timings = S.get("timings") or []
    if timings:
        slowest_wait = max(t["mentor_seconds"] for t in timings)
        print("\nWHAT A GRADUATE WAITS FOR A REVIEW (real HTTP):")
        for i, t in enumerate(timings[:6], 1):
            tail = f", specialists + Manager synthesis done after {t['discussion_done_seconds']}s" if t["discussion_done_seconds"] is not None else ", no specialists on the team"
            print(f"  review {i}: Mentor's verdict after {t['mentor_seconds']}s{tail}")
        if any(t["discussion_done_seconds"] for t in timings):
            avg_total = sum(t["discussion_done_seconds"] for t in timings if t["discussion_done_seconds"]) / len([1 for t in timings if t["discussion_done_seconds"]])
            avg_mentor = sum(t["mentor_seconds"] for t in timings) / len(timings)
            print(f"  -> the graduate now waits ~{avg_mentor:.0f}s instead of ~{avg_total:.0f}s; the discussion appears in the thread while they read the review")
    plan = S.get("produced_plan")
    if plan:
        print("\nWHAT THE MANAGER PRODUCED (judge the quality yourself):")
        print(f"  Project: {plan['project']}   [seed: {plan['seed_id'] or 'none'}]")
        print(f"  This week's big task: {plan['big_task']}")
        for i, st in enumerate(plan["subtasks"], 1):
            print(f"    {i}. {st['title']}")
    reviews = S.get("produced_reviews") or []
    if reviews:
        print("\nWHAT THE MENTOR PRODUCED:")
        for i, rv in enumerate(reviews[:6], 1):
            adj = "  (verdict adjusted by the rubric rule)" if rv["verdict_adjusted"] else ""
            print(f"  review {i}: {rv['verdict'].upper()}{adj}  scores {rv['scores']}")
        first = reviews[0]
        print(f"  first review says: {first['summary'][:360].strip()}{'...' if len(first['summary']) > 360 else ''}")
    if args.save_report:
        with open(args.save_report, "w", encoding="utf-8") as fh:
            json.dump({"language": args.language, "steps": [{"step": n, "status": s, "seconds": round(t, 1), "note": nt} for n, s, t, nt in results],
                       "plan": plan, "reviews": reviews, "review_timings": S.get("timings"), "llm_calls_by_provider": dict(watcher.calls),
                       "failovers": len(watcher.failovers), "repairs": watcher.repairs, "malformed": watcher.malformed},
                      fh, ensure_ascii=False, indent=2)
        print(f"\nFull report saved to {args.save_report}")
    failed = [r for r in results if r[1] == "FAIL"]
    print("\n" + ("RESULT: some checks FAILED" if failed else "RESULT: all hard checks passed"))
    stop_wire()
    if not args.keep_db:
        client.__exit__(None, None, None)
        for suffix in ("", "-journal"):
            try:
                os.remove(DB_FILE + suffix)
            except OSError:
                pass
    sys.exit(1 if failed else 0)


# --------------------------------------------------------------------- run
print("Running (real models - each LLM step can take 5-60 seconds)...\n", flush=True)
step("register + login", s_register)
step("onboarding: CV -> questions", s_onboarding_cv)
step("onboarding: answers -> track", s_onboarding_qa)
step("onboarding: track -> team suggestion", s_onboarding_track)
step("onboarding: team approved", s_onboarding_agents)
step("Manager plans the week", s_plan_week)
step(f"submit + Mentor review ({args.subtasks} subtask{'s' if args.subtasks > 1 else ''})", s_week)
if S.get("first_task_id"):
    step("roundtable spoke in the task thread", s_roundtable_visible, fatal=False)
step("meeting-room chat", s_meeting, fatal=False)
step("HR rollup", s_hr_rollup, fatal=False)
if args.full_week:
    if S.get("approved_count") == 5:
        step("end-of-week cascade (Manager + HR)", s_cascade, fatal=False)
    else:
        results.append(("end-of-week cascade (Manager + HR)", "SKIP", 0.0, "not all 5 subtasks were approved"))
        print("[SKIP] end-of-week cascade - not all 5 subtasks were approved (add --force-approve to run the cascade anyway, or use a --repo that fits the task)")
finish()
