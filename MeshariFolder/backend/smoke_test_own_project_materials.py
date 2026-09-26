"""
Smoke test for own-project materials (docs/STAGE2_OWN_PROJECT.md, "Materials").

A graduate bringing their own project used to give the Manager a one-line title and
description to plan five weeks of work from. Now they can also paste notes and/or
upload files (PDF/Word/text); the extracted text is stored on Project.materials_text
and reaches the Manager's plan_week prompt, grounding real subtasks in real material.

Covers: creating with pasted text, with files, with both, with neither (unchanged
behaviour); the per-file and combined caps; bad/oversized/too-many files; that
materials never leak into GET responses (has_materials only) or into a Manager-authored
project; and, through the real endpoint with only the model faked, exactly what
plan_week is (and is NOT) told.

Run: python smoke_test_own_project_materials.py
"""
import io
import os
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_own_project_materials.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-faked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.task_bank import MAX_MATERIALS_CHARS  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Project  # noqa: E402
from app.routers.projects import MAX_MATERIALS_FILES  # noqa: E402


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


client = TestClient(app)
client.__enter__()


def signup(email):
    client.post("/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "Materials Tester"})
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def txt(name, content):
    return (name, io.BytesIO(content.encode()), "text/plain")


def db_project(project_id):
    db = SessionLocal()
    try:
        p = db.get(Project, project_id)
        db.expunge(p)
        return p
    finally:
        db.close()


# ---- no materials at all: unchanged behaviour ---------------------------------------
h = signup("mat-none@example.com")
r = client.post("/projects/own", headers=h, data={"title": "Weather app", "description": "Shows the forecast."})
check("no materials -> still 201", r.status_code == 201)
check("has_materials is false", r.json()["has_materials"] is False)
check("...and materials_text is not stored", db_project(r.json()["id"]).materials_text is None)

# ---- pasted text only -----------------------------------------------------------------
h = signup("mat-pasted@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d", "materials_text": "  Built with FastAPI and a Postgres database.  "})
check("pasted materials -> 201, has_materials true", r.status_code == 201 and r.json()["has_materials"] is True)
p = db_project(r.json()["id"])
check("...stored trimmed", p.materials_text == "Built with FastAPI and a Postgres database.")
check("whitespace-only materials_text is treated as none", client.post("/projects/own", headers=signup("mat-blank@example.com"), data={"title": "T", "description": "d", "materials_text": "   "}).json()["has_materials"] is False)

# ---- a file only ------------------------------------------------------------------------
h = signup("mat-file@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d"}, files={"files": txt("notes.txt", "Uses Stripe for payments.")})
check("one file -> 201, has_materials true", r.status_code == 201 and r.json()["has_materials"] is True)
p = db_project(r.json()["id"])
check("...the file's name and content are both in the stored text", "notes.txt" in p.materials_text and "Stripe" in p.materials_text)

# ---- pasted text AND files, several of them, combined in order ----------------------------
h = signup("mat-both@example.com")
r = client.post(
    "/projects/own", headers=h, data={"title": "T", "description": "d", "materials_text": "Top-level notes."},
    files=[("files", txt("a.txt", "Content A.")), ("files", txt("b.txt", "Content B."))],
)
check("text + 2 files -> 201", r.status_code == 201)
p = db_project(r.json()["id"])
check("all three pieces are present", "Top-level notes." in p.materials_text and "Content A." in p.materials_text and "Content B." in p.materials_text)
check("pasted notes come first, then files in the order sent", p.materials_text.index("Top-level notes.") < p.materials_text.index("a.txt") < p.materials_text.index("b.txt"))

# ---- limits -----------------------------------------------------------------------------
h = signup("mat-toomany@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d"}, files=[("files", txt(f"f{i}.txt", "x")) for i in range(MAX_MATERIALS_FILES + 1)])
check(f"more than {MAX_MATERIALS_FILES} files -> 400, project not created", r.status_code == 400)
check("...no project was left behind by the rejected attempt", client.get("/projects/me", headers=h).status_code == 404)

h = signup("mat-huge@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d"}, files={"files": txt("huge.txt", "x" * (6 * 1024 * 1024))})
check("an oversized single file -> 413", r.status_code == 413)

h = signup("mat-corrupt@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d"}, files={"files": ("broken.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")})
check("a corrupt file -> clean 400, not a 500", r.status_code == 400)
check("...the error names the file", "broken.pdf" in r.json()["detail"])

h = signup("mat-cap@example.com")
r = client.post("/projects/own", headers=h, data={"title": "T", "description": "d", "materials_text": "y" * (MAX_MATERIALS_CHARS * 2)})
check("combined materials longer than the cap -> still 201 (truncated, not rejected)", r.status_code == 201)
p = db_project(r.json()["id"])
check(f"...stored text is at most the cap ({MAX_MATERIALS_CHARS} chars)", len(p.materials_text) <= MAX_MATERIALS_CHARS)
check("...and says it was truncated", "truncated" in p.materials_text)

# ---- materials never appear in an API response, only the boolean --------------------------
h = signup("mat-hidden@example.com")
client.post("/projects/own", headers=h, data={"title": "T", "description": "d", "materials_text": "SECRET_MARKER_TEXT"})
raw_me = client.get("/projects/me", headers=h)
check("GET /projects/me never includes the materials text itself", "SECRET_MARKER_TEXT" not in raw_me.text and "materials_text" not in raw_me.json())
check("...only has_materials", raw_me.json()["has_materials"] is True)

# ---- a Manager-authored project never has materials ----------------------------------------
h = signup("mat-manager@example.com")
with patch("app.agents.manager.call_with_tool") as mock_manager:
    mock_manager.return_value = {"tool_name": "create_project", "input": {"title": "T", "description": "d", "seed_id": None}}
    from app.agents import manager as manager_module

    db = SessionLocal()
    from app.models import User

    user = db.query(User).filter(User.email == "mat-manager@example.com").one()
    project = manager_module.create_project(db, user)
    db.close()
check("a Manager-created project has no materials at all", project.has_materials is False and project.materials_text is None)

# ---- through the real endpoint: what plan_week is (and isn't) told -----------------------
CALLS = []


def gen(schema, key=""):
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "string":
        gen.n += 1
        return f"Sample {key or 'text'} #{gen.n} long enough to pass."
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
    CALLS.append({"tool": tool["name"], "prompt": kw["messages"][0]["content"]})
    block = MagicMock(type="tool_use")
    block.name, block.input = tool["name"], gen(tool["input_schema"])
    return MagicMock(content=[block])


with patch("app.agents.llm_client._anthropic") as mock_a:
    mock_a.return_value.messages.create.side_effect = fake_create

    h = signup("mat-wired@example.com")
    client.post("/projects/own", headers=h, data={"title": "Recipe box", "description": "d", "materials_text": "Uses SwiftUI and CoreData for offline storage."})
    CALLS.clear()
    r = client.post("/agents/manager/assign-task", headers=h)
    check("assign-task with own+materials -> 201", r.status_code == 201)
    check("create_project is skipped (a project already exists)", not [c for c in CALLS if c["tool"] == "create_project"])
    pw = next(c for c in CALLS if c["tool"] == "plan_week")
    check("plan_week is shown the materials", "OWN PROJECT MATERIALS" in pw["prompt"] and "SwiftUI" in pw["prompt"] and "CoreData" in pw["prompt"])
    check("...and told to ground subtasks in them", "don't invent details" in pw["prompt"])
    check("...the shaping principles are still there too", "HOW TO SHAPE THE FIVE SUBTASKS" in pw["prompt"])

    h2 = signup("mat-nomat@example.com")
    client.post("/projects/own", headers=h2, data={"title": "Plain project", "description": "d"})
    CALLS.clear()
    client.post("/agents/manager/assign-task", headers=h2)
    check("own project with NO materials: plan_week is not shown an empty/odd block", "OWN PROJECT MATERIALS" not in next(c for c in CALLS if c["tool"] == "plan_week")["prompt"])

    h3 = signup("mat-empty-token@example.com")
    r = client.post("/projects/own", headers=h3, data={"title": "T", "description": "d", "materials_text": ""})
    check("an empty (not omitted) materials_text field is accepted and treated as none", r.status_code == 201 and r.json()["has_materials"] is False)

print("\nAll own-project-materials smoke checks passed.")
