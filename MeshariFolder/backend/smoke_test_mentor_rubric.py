"""
Smoke test for the Mentor's rubric v2 (docs/MENTOR_RUBRIC.md).

Covers the rubric as data (anchors, the verdict rule, the tool schema staying in
step with it), the enforcement rule (apply_rubric_rules) including the malformed
shapes real models return, and the two things the Mentor now gets on every
review - the graduate's context, and (on a resubmission) its OWN previous
feedback - checked through the real endpoint with only the model call faked.

Run: python smoke_test_mentor_rubric.py
"""
import os
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./smoke_test_mentor_rubric.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402

from app.agents import rubric  # noqa: E402
from app.agents.mentor import SYSTEM_PROMPT  # noqa: E402
from app.agents.tools import SUBMIT_REVIEW_TOOL  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.language import current_language  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Project, Task, Week  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def cats(correctness, code_quality=4, testing=3, documentation=3):
    return [
        {"key": "correctness", "label": "Meets requirements", "score": correctness},
        {"key": "code_quality", "label": "Code quality", "score": code_quality},
        {"key": "testing", "label": "Testing", "score": testing},
        {"key": "documentation", "label": "Documentation", "score": documentation},
    ]


# ---- the rubric as data ---------------------------------------------------------
schema = SUBMIT_REVIEW_TOOL["input_schema"]["properties"]
check("rubric keys match the tool schema's category enum (they can't drift apart)",
      rubric.CATEGORY_KEYS == schema["categories"]["items"]["properties"]["key"]["enum"])
check("the tool requires exactly four categories", schema["categories"]["minItems"] == 4 and schema["categories"]["maxItems"] == 4)
check("the tool caps the comment list", schema["comments"]["maxItems"] == rubric.MAX_COMMENTS)
check("the Mentor's prompt IS the rubric prompt", SYSTEM_PROMPT == rubric.system_prompt())
for c in rubric.CATEGORIES:
    check(f"prompt names '{c['name']}' ({c['key']}) with anchors for 1, 3 and 5",
          c["name"] in SYSTEM_PROMPT and c["key"] in SYSTEM_PROMPT and all(k in c["anchors"] for k in (1, 3, 5)))
check("only 'meets requirements' can block", [c["key"] for c in rubric.CATEGORIES if c["blocking"]] == ["correctness"])
check("the prompt states the verdict rule with the bar", f"below {rubric.APPROVAL_BAR}" in SYSTEM_PROMPT and "VERDICT RULE" in SYSTEM_PROMPT)
check("the prompt tells the Mentor it cannot run code (no invented test results)", "cannot run the code" in SYSTEM_PROMPT)
check("the prompt covers resubmissions", "RESUBMISSIONS" in SYSTEM_PROMPT)
check("the prompt tells the Mentor what it is really shown of a repo (file list + README, not the code)",
      "README" in SYSTEM_PROMPT and "not the code itself" in SYSTEM_PROMPT and "first 25 files" in SYSTEM_PROMPT)
check("...and to ask for evidence rather than assume it's missing from the code", "what evidence to add" in SYSTEM_PROMPT)
check("the bar is 3 and the version is '2'", rubric.APPROVAL_BAR == 3 and rubric.RUBRIC_VERSION == "2")

# ---- enforcement -----------------------------------------------------------------
base = {"verdict": "approved", "summary": "Looks fine overall.", "categories": cats(2), "comments": []}
out, adj = rubric.apply_rubric_rules(base)
check("approved with 'meets requirements' 2 -> flipped to needs_changes", out["verdict"] == "needs_changes" and adj is True)
check("...the original summary is kept and the adjustment is explained", out["summary"].startswith("Looks fine overall.") and "Verdict adjusted" in out["summary"] and "2/5" in out["summary"])
check("...the input dict was not mutated", base["verdict"] == "approved")
out, adj = rubric.apply_rubric_rules({**base, "categories": cats(1)})
check("approved with correctness 1 -> flipped", out["verdict"] == "needs_changes" and adj)
out, adj = rubric.apply_rubric_rules({**base, "categories": cats(3)})
check("approved with correctness 3 (exactly the bar) -> stays approved", out["verdict"] == "approved" and adj is False)
out, adj = rubric.apply_rubric_rules({**base, "categories": cats(5, testing=1, documentation=1, code_quality=1)})
check("approved with correctness 5 but weak tests/docs/quality -> stays approved (they never block)", out["verdict"] == "approved" and not adj)
out, adj = rubric.apply_rubric_rules({**base, "verdict": "needs_changes", "categories": cats(5)})
check("needs_changes with high scores is left alone (may be a blocker the scores miss)", out["verdict"] == "needs_changes" and not adj)
check("dict-shaped categories {key: score} (a common model slip) are understood",
      rubric.apply_rubric_rules({**base, "categories": {"correctness": 2, "testing": 3}})[0]["verdict"] == "needs_changes")
check("...including {key: {score: n}}",
      rubric.apply_rubric_rules({**base, "categories": {"correctness": {"score": 2}}})[0]["verdict"] == "needs_changes")
for label, bad in (("missing", None), ("junk strings", ["correctness", "testing"]), ("a number", 4), ("no correctness entry", [{"key": "testing", "score": 1}])):
    out, adj = rubric.apply_rubric_rules({**base, "categories": bad})
    check(f"malformed categories ({label}) never crash and never flip", out["verdict"] == "approved" and adj is False)
out, adj = rubric.apply_rubric_rules({**base, "categories": [{"key": "correctness", "score": True}]})
check("a boolean 'score' is not mistaken for the number 1", out["verdict"] == "approved" and not adj)
out, _ = rubric.apply_rubric_rules({**base, "categories": cats(4), "comments": [{"category": "testing", "content": str(i)} for i in range(7)]})
check(f"a wall of comments is capped at {rubric.MAX_COMMENTS}", len(out["comments"]) == rubric.MAX_COMMENTS)
token = current_language.set("ar")
try:
    out, adj = rubric.apply_rubric_rules(base)
finally:
    current_language.reset(token)
check("the adjustment note is written in Arabic for an Arabic request", adj and any("\u0600" <= ch <= "\u06ff" for ch in out["summary"].split("\n\n")[-1]))

# ---- through the real endpoint: what the Mentor is actually sent -------------------
r = client.post("/auth/register", json={"email": "rubric@example.com", "password": "hunter2pass", "full_name": "Rubric Tester"})
r = client.post("/auth/login", data={"username": "rubric@example.com", "password": "hunter2pass"})
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
user_id = client.get("/users/me", headers=headers).json()["id"]

db = SessionLocal()
project = Project(user_id=user_id, title="Landing page", description="d")
db.add(project)
db.commit()
week = Week(project_id=project.id, user_id=user_id, week_number=2, big_task_title="Ship it", big_task_description="d",
            target_end_at=datetime.utcnow() + timedelta(days=5), subtasks_plan_json=[])
db.add(week)
db.commit()
task_ids = []
for title in ("Build the hero section", "Add the contact form", "Write the footer"):
    t = Task(title=title, description="Per the design spec.", user_id=user_id, week_id=week.id, deadline=datetime.utcnow() + timedelta(days=1))
    db.add(t)
    db.commit()
    task_ids.append(t.id)
db.close()
t1, t2, t3 = task_ids

CALLS = []


def mentor(task_id, verdict, summary, categories, comments=None):
    fake = {"verdict": verdict, "summary": summary, "categories": categories, "comments": comments or []}
    with patch("app.agents.mentor.call_with_tool", side_effect=lambda **kw: (CALLS.append(kw), {"tool_name": "submit_review", "input": fake})[1]):
        return client.post(f"/agents/mentor/review/{task_id}", headers=headers)


def submit(task_id):
    return client.post(f"/tasks/{task_id}/submit", headers=headers, data={"submission_text": "Here is my work, with notes on how to run it."})


def get(task_id):
    return client.get(f"/tasks/{task_id}", headers=headers).json()


# first submission
submit(t1)
r = mentor(t1, "needs_changes", "The hero breaks on mobile.", cats(2),
           [{"category": "correctness", "content": "Layout breaks under 400px in hero.css."}, {"category": "testing", "content": "No visual check was done."}])
check("review 1 accepted", r.status_code == 201)
first = CALLS[-1]
prompt = first["messages"][0]["content"]
check("the Mentor is sent the rubric prompt", first["system"] == rubric.system_prompt())
check("...the graduate's track", "Graduate's track: junior_dev" in prompt)
check("...the program week", "Program week: 2" in prompt)
check("...that it is a first submission, with no old feedback", "first submission" in prompt and "previous review" not in prompt)
m = r.json()["metrics_json"]
check("the stored review records the rubric version", m["rubric_version"] == "2")
check("...and that the verdict was not adjusted", m["verdict_adjusted"] is False)
check("the bounced task is flagged needs_changes", get(t1)["needs_changes"] is True)

# resubmission: the Mentor must see its own previous feedback
submit(t1)
r = mentor(t1, "approved", "Fixed, thanks.", cats(4))
prompt = CALLS[-1]["messages"][0]["content"]
check("resubmission: the prompt shows the Mentor's previous feedback", "Your previous review asked for changes" in prompt)
check("...the previous summary", "The hero breaks on mobile." in prompt)
check("...and each previous comment, with its category", "[correctness] Layout breaks under 400px in hero.css." in prompt and "[testing] No visual check was done." in prompt)
check("...and that this is revision 2", "revision 2" in prompt)
check("the approved resubmission completes the task", get(t1)["status"] == "reviewed")

# a fresh task carries no old feedback
submit(t2)
mentor(t2, "approved", "Nice work.", cats(4))
check("a different task never sees another task's feedback", "previous review" not in CALLS[-1]["messages"][0]["content"])

# a contradictory review is brought in line, and the effect is real
submit(t3)
r = mentor(t3, "approved", "Great job overall!", cats(2))
m = r.json()["metrics_json"]
check("a contradictory 'approved' (correctness 2) is stored as needs_changes", m["verdict"] == "needs_changes")
check("...flagged as adjusted, for traceability", m["verdict_adjusted"] is True)
check("...with the reason in the summary the graduate reads", "Verdict adjusted" in r.json()["content"])
t = get(t3)
check("...and the TASK is bounced accordingly (the adjusted verdict drives the status)", t["status"] == "in_progress" and t["needs_changes"] is True)

# models that return plain-string comments must not break the next review
submit(t3)
r = mentor(t3, "needs_changes", "Still not there.", cats(2), comments=["Fix the layout.", "Add tests."])
check("plain-string comments are stored without error", r.status_code == 201)
submit(t3)
r = mentor(t3, "approved", "Better.", cats(4))
prompt = CALLS[-1]["messages"][0]["content"]
check("...and the next review still shows them as previous feedback", r.status_code == 201 and "- Fix the layout." in prompt and "revision 3" in prompt)

print("\nAll Mentor rubric smoke checks passed.")
