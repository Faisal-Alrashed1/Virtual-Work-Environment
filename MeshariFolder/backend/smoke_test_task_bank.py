"""
Smoke test for the Manager's task bank (docs/TASK_BANK.md).

Two halves. (1) The bank itself: rules any seed must satisfy, so nobody can later add
a half-written one (every track has seeds, every seed has a four-week arc, every week
a focus and a concrete deliverable, no placeholders). (2) The wiring, through the real
endpoints with only the model faked so the test can read exactly what the Manager is
shown: its track's seeds (and no one else's), the arc step for the week being planned,
the shaping principles; and what is stored: Project.seed_id, never a made-up one.

Run: python smoke_test_task_bank.py
"""
import json
import os
import re
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_task_bank.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from app.agents import manager, task_bank  # noqa: E402
from app.agents.tools import CREATE_PROJECT_TOOL  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Project, TrackEnum, User  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


REAL_TRACKS = [t for t in TrackEnum if t != TrackEnum.JUNIOR_DEV]

# ---- the bank: integrity ------------------------------------------------------------
check("the bank has at least 15 seeds", len(task_bank.SEEDS) >= 15)
for track in REAL_TRACKS:
    check(f"track {track.value}: at least two seeds", len(task_bank.seeds_for(track)) >= 2)
for track in (TrackEnum.SOFTWARE_ENGINEERING, TrackEnum.DATA_SCIENCE_AI, TrackEnum.CYBERSECURITY):
    check(f"the most-used track {track.value} has three seeds", len(task_bank.seeds_for(track)) >= 3)
check("cybersecurity includes a DEFENSIVE (monitoring / incident response) seed, not only offence and hardening",
      any("monitoring" in s.title.lower() or "incident" in s.title.lower() for s in task_bank.seeds_for(TrackEnum.CYBERSECURITY)))
check("the legacy junior_dev track gets the software-engineering seeds",
      [s.id for s in task_bank.seeds_for(TrackEnum.JUNIOR_DEV)] == [s.id for s in task_bank.seeds_for(TrackEnum.SOFTWARE_ENGINEERING)])
ids = [s.id for s in task_bank.SEEDS]
check("seed ids are unique", len(ids) == len(set(ids)))
check("seed titles are unique", len({s.title for s in task_bank.SEEDS}) == len(task_bank.SEEDS))
check("seed ids are simple slugs (they go in a tool enum and a DB column)", all(re.fullmatch(r"[a-z0-9-]{3,60}", i) for i in ids))
check("every seed belongs to a real track", all(s.track in REAL_TRACKS for s in task_bank.SEEDS))
check("every seed has exactly a four-week arc", all(len(s.arc) == 4 for s in task_bank.SEEDS))
check("every brief is a real description", all(80 <= len(s.brief) <= 400 for s in task_bank.SEEDS))
check("every seed lists at least three skills", all(len(s.skills) >= 3 and all(x.strip() for x in s.skills) for s in task_bank.SEEDS))
check("every arc week has a focus and a deliverable of sensible length",
      all(20 <= len(w.focus) <= 220 and 20 <= len(w.deliverable) <= 260 for s in task_bank.SEEDS for w in s.arc))
check("every seed says what evidence to submit, in a sensible length", all(40 <= len(s.evidence) <= 320 for s in task_bank.SEEDS))
check("...and every one puts that evidence where the Mentor can SEE it: the repository README (the Mentor is not shown the code)",
      all("README" in s.evidence and "GitHub" in s.evidence for s in task_bank.SEEDS))
check("the shaping principles tell the Manager the Mentor reads the file list and README, not the code",
      "README" in task_bank.SUBTASK_PRINCIPLES and "not the code itself" in task_bank.SUBTASK_PRINCIPLES)
check("no placeholder text anywhere", not re.search(r"todo|tbd|xxx|lorem|fixme", json.dumps([[s.title, s.brief, [w.focus + w.deliverable for w in s.arc]] for s in task_bank.SEEDS]), re.I))
check("the first week of every arc starts from foundations/setup (a graduate isn't dropped in the middle)",
      all(re.search(r"found|scope|understand|requirement|design|baseline|ingest|contain|build the lab|start", s.arc[0].focus, re.I) for s in task_bank.SEEDS))
check("the last week of every arc is about finishing (ship/report/hand over/operate/prove)",
      all(re.search(r"ship|report|communicate|hand over|operate|prove|watch|roll out|cost", s.arc[-1].focus, re.I) for s in task_bank.SEEDS))

# ---- helpers ---------------------------------------------------------------------------
cyber = task_bank.seeds_for(TrackEnum.CYBERSECURITY)
block = task_bank.seeds_prompt_block(TrackEnum.CYBERSECURITY)
check("the seeds prompt lists every seed of the track, with ids", all(s.id in block and s.title in block for s in cyber))
check("...and none from other tracks", not any(s.id in block for s in task_bank.SEEDS if s.track != TrackEnum.CYBERSECURITY))
check("...and tells the Manager to adapt, not copy", "ADAPT" in block and "not a script" in block)
seed = cyber[0]
for w in range(1, 5):
    b = task_bank.week_arc_block(seed.id, w)
    check(f"arc block for week {w} names the focus, the deliverable and the evidence to submit",
          seed.arc[w - 1].focus in b and seed.arc[w - 1].deliverable in b and f"week {w} of 4" in b and seed.evidence in b)
check("past the arc: the Manager is told to extend and polish", "arc is complete" in task_bank.week_arc_block(seed.id, 5) and "Extend" in task_bank.week_arc_block(seed.id, 9))
check("...and still told what evidence to ask for", seed.evidence in task_bank.week_arc_block(seed.id, 5))
check("no seed (your own project): no arc block at all", task_bank.week_arc_block(None, 1) == "" and task_bank.week_arc_block("nope", 1) == "")
check("get_seed: known / unknown / empty", task_bank.get_seed(seed.id) is seed and task_bank.get_seed("nope") is None and task_bank.get_seed(None) is None)
tool = task_bank.create_project_tool_for(TrackEnum.CYBERSECURITY)
check("the create_project tool's seed_id is restricted to the track's seeds", tool["input_schema"]["properties"]["seed_id"]["enum"] == [s.id for s in cyber])
check("...and seed_id is optional", "seed_id" not in tool["input_schema"]["required"])
check("...and the shared tool definition is never mutated", "seed_id" not in CREATE_PROJECT_TOOL["input_schema"]["properties"])

# ---- through the real endpoints ---------------------------------------------------------
CALLS = []
CHOICE = {"seed": None}


def gen(schema, key=""):
    if "enum" in schema:
        return schema["enum"][0]
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
    tool = next(t for t in kw["tools"] if t["name"] == kw["tool_choice"]["name"])
    CALLS.append({"tool": tool["name"], "prompt": kw["messages"][0]["content"], "schema": tool["input_schema"]})
    data = gen(tool["input_schema"])
    if tool["name"] == "create_project":
        data["seed_id"] = CHOICE["seed"]
    block = MagicMock(type="tool_use")
    block.name, block.input = tool["name"], data
    return MagicMock(content=[block])


client = TestClient(app)
client.__enter__()


def signup(email, track=None):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Bank Tester"})
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    if track:
        db = SessionLocal()
        db.query(User).filter(User.email == email).one().track = track
        db.commit()
        db.close()
    return headers


def calls_of(tool):
    return [c for c in CALLS if c["tool"] == tool]


with patch("app.agents.llm_client._anthropic") as mock_a:
    mock_a.return_value.messages.create.side_effect = fake_create

    # a cybersecurity graduate: the model picks the SECOND seed
    h = signup("bank-cyber@example.com", TrackEnum.CYBERSECURITY)
    CHOICE["seed"] = cyber[1].id
    CALLS.clear()
    r = client.post("/agents/manager/assign-task", headers=h)
    check("assign-task works with the bank in the prompt", r.status_code == 201)
    cp, pw = calls_of("create_project")[0], calls_of("plan_week")[0]
    check("create_project is shown the graduate's track's seeds", all(s.id in cp["prompt"] and s.title in cp["prompt"] for s in cyber))
    check("...and NOT another track's seeds", not any(s.id in cp["prompt"] for s in task_bank.SEEDS if s.track != TrackEnum.CYBERSECURITY))
    check("the tool the model was given restricts seed_id to those seeds", cp["schema"]["properties"]["seed_id"]["enum"] == [s.id for s in cyber])
    project = client.get("/projects/me", headers=h).json()
    check("the chosen seed is stored on the project and returned by the API", project["seed_id"] == cyber[1].id)
    check("plan_week is told the project's arc, week 1 of 4", f"PROJECT ARC ({cyber[1].title}, week 1 of 4)" in pw["prompt"])
    check("...with week 1's focus and deliverable", cyber[1].arc[0].focus in pw["prompt"] and cyber[1].arc[0].deliverable in pw["prompt"])
    check("...and the subtask-shaping principles", "HOW TO SHAPE THE FIVE SUBTASKS" in pw["prompt"] and "done when" in pw["prompt"])
    check("...including the evidence to submit and that the Mentor reads the README, not the code",
          cyber[1].evidence in pw["prompt"] and "not the code itself" in pw["prompt"])
    check("the project got its 5 subtasks as before", len(project["weeks"][0]["subtasks_plan_json"]) == 5)

    # week 2 builds on the arc (planned directly: it only needs the project to exist)
    db = SessionLocal()
    u = db.query(User).filter(User.email == "bank-cyber@example.com").one()
    p = db.query(Project).filter(Project.user_id == u.id).one()
    CALLS.clear()
    manager.plan_week(db, u, p)
    w2 = calls_of("plan_week")[0]["prompt"]
    check("week 2 is told it is week 2 of 4, with week 2's focus", "week 2 of 4" in w2 and cyber[1].arc[1].focus in w2)
    check("...and sees what week 1 was", "Week 1:" in w2)
    for _ in range(2):
        manager.plan_week(db, u, p)  # weeks 3 and 4
    CALLS.clear()
    manager.plan_week(db, u, p)  # week 5: past the arc
    w5 = calls_of("plan_week")[0]["prompt"]
    check("week 5 (past the arc) is told to extend the project, not repeat it", "arc is complete" in w5 and "Extend" in w5)
    db.close()

    # a made-up seed id is never stored, and nothing breaks
    h2 = signup("bank-fake@example.com")
    CHOICE["seed"] = "not-a-real-seed"
    CALLS.clear()
    r = client.post("/agents/manager/assign-task", headers=h2)
    project = client.get("/projects/me", headers=h2).json()
    check("a made-up seed_id from the model still yields a working project", r.status_code == 201 and len(project["weeks"][0]["subtasks_plan_json"]) == 5)
    check("...but it is NOT stored (would silently break the arc)", project["seed_id"] is None)
    check("...and with no seed there is no arc block, but the principles remain",
          "PROJECT ARC" not in calls_of("plan_week")[0]["prompt"] and "HOW TO SHAPE THE FIVE SUBTASKS" in calls_of("plan_week")[0]["prompt"])
    check("a Stage 1 (junior_dev) graduate is offered the software-engineering seeds",
          all(s.id in calls_of("create_project")[0]["prompt"] for s in task_bank.seeds_for(TrackEnum.SOFTWARE_ENGINEERING)))

    # a graduate's own project: no seed, no create_project, planned as before
    h3 = signup("bank-own@example.com", TrackEnum.DATA_SCIENCE_AI)
    r = client.post("/projects/own", headers=h3, data={"title": "My weather app", "description": "A small app that shows the forecast for my city."})
    CALLS.clear()
    r = client.post("/agents/manager/assign-task", headers=h3)
    project = client.get("/projects/me", headers=h3).json()
    check("own project: the Manager plans it (201)", r.status_code == 201 and project["title"] == "My weather app")
    check("...create_project (and so the bank) is never involved", calls_of("create_project") == [])
    check("...no seed, no arc block", project["seed_id"] is None and "PROJECT ARC" not in calls_of("plan_week")[0]["prompt"])

check("the seed_id column exists in the database", "seed_id" in {c["name"] for c in inspect(engine).get_columns("projects")})
check("the shared create_project tool is still unmutated after all of that", "seed_id" not in CREATE_PROJECT_TOOL["input_schema"]["properties"])

print("\nAll task-bank smoke checks passed.")
