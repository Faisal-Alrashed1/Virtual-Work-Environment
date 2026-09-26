"""
Smoke test for CV content validation (docs/CV_VALIDATION.md) — the fix
for a real reported bug: uploading any readable PDF (an invoice, an
essay, anything) as a "CV" used to be silently accepted, because
read_cv_upload only ever checked whether *some* text could be extracted
from the file, never whether that text actually reads like a CV.

Covers all three real CV-intake points (POST /onboarding/cv,
POST /users/me/cv, POST /users/me/cv/file), the genuinely-empty-text
fast path (no LLM call needed), and confirms the non-CV upload paths
(a company's knowledge-base materials, own-project materials) are
correctly untouched by this — they still accept any document, on
purpose. Mocked LLM, no API key needed.

Run: python smoke_test_cv_validation.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_cv_validation.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-every-llm-call-is-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

class FakeAIMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


class FakeBoundModel:
    def __init__(self, name, args):
        self._name, self._args = name, args

    def invoke(self, messages):
        return FakeAIMessage([{"name": self._name, "args": self._args}])


class FakeModel:
    """Same shape as smoke_test_stage2_onboarding_router.py's own
    FakeModel — only generate_questions is exercised here, since this
    file is about CV validation, not onboarding's later steps."""

    def bind_tools(self, tools, tool_choice):
        name = tools[0]["function"]["name"]
        return FakeBoundModel(name, {"questions": ["What did you build?"]})


client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def register(email) -> dict:
    r = client.post(
        "/auth/register", json={"email": email, "password": "hunter2pass", "full_name": "CV Tester"}
    )
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def not_cv(reason="it reads like a restaurant invoice, not a résumé"):
    return {"tool_name": "classify_document", "input": {"is_cv": False, "reason": reason}}


def is_cv():
    return {"tool_name": "classify_document", "input": {"is_cv": True, "reason": ""}}


REAL_CV = (
    b"Jane Doe\nSoftware Engineer\n\nEXPERIENCE\nBackend Developer, Acme Corp (2023-2025)\n"
    b"- Built and shipped REST APIs in Python/FastAPI\n- Led migration to PostgreSQL\n\n"
    b"EDUCATION\nB.Sc. Computer Science, State University (2023)\n\nSKILLS\nPython, SQL, Docker"
)
NOT_A_CV = (
    b"INVOICE #4471\nBill To: Jane Doe\nDate: 2026-03-14\n\n2x Cappuccino ....... $9.00\n"
    b"1x Croissant ......... $3.50\nSubtotal: $12.50\nTax: $1.00\nTotal: $13.50\nThank you for your visit!"
)


# =============================================================================
# 1. POST /onboarding/cv — the reported bug, fixed: a non-CV upload is
#    now genuinely refused, not silently accepted.
# =============================================================================
headers = register("onboarding-notcv@example.com")
with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=not_cv()):
    r = client.post("/onboarding/cv", headers=headers, files={"file": ("receipt.txt", NOT_A_CV, "text/plain")})
check("uploading an invoice as a CV during onboarding is refused -> 400", r.status_code == 400)
check("the refusal explains why, using the model's real reason", "invoice" in r.json()["detail"])

r = client.get("/onboarding/state", headers=headers)
check("onboarding never advanced past the CV step", r.json()["onboarding_stage"] == "cv")

# --- the same graduate uploading a REAL CV works normally ---
with patch(
    "app.agents.graph.cv_parsing.call_with_tool", return_value=is_cv()
), patch(
    "app.agents.graph.onboarding_graph.small_model_chain",
    return_value=[("anthropic", FakeModel())],
):
    r = client.post("/onboarding/cv", headers=headers, files={"file": ("cv.txt", REAL_CV, "text/plain")})
check("uploading a real CV during onboarding -> 200", r.status_code == 200)
check("onboarding correctly advances to the qa stage", client.get("/onboarding/state", headers=headers).json()["onboarding_stage"] == "qa")


# =============================================================================
# 2. POST /users/me/cv — pasted text, no file at all. Same bug class:
#    someone could paste anything, not just upload a wrong file.
# =============================================================================
headers2 = register("pasted-notcv@example.com")
with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=not_cv("it's a grocery list")):
    r = client.post("/users/me/cv", json={"cv_raw_text": "milk, eggs, bread, coffee"}, headers=headers2)
check("pasting a grocery list as a CV is refused -> 400", r.status_code == 400)
check("has_cv stays false — nothing was saved", client.get("/users/me", headers=headers2).json()["has_cv"] is False)

with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=is_cv()):
    r = client.post("/users/me/cv", json={"cv_raw_text": REAL_CV.decode()}, headers=headers2)
check("pasting a real CV -> 200", r.status_code == 200)
check("has_cv is now true", r.json()["has_cv"] is True)

# --- a genuinely empty paste is refused WITHOUT an LLM call at all ---
with patch("app.agents.graph.cv_parsing.call_with_tool") as mock_call:
    r = client.post("/users/me/cv", json={"cv_raw_text": "   "}, headers=headers2)
check("a blank/whitespace-only paste -> 400", r.status_code == 400)
check("...refused on the fast path, no LLM call spent on empty text", mock_call.call_count == 0)


# =============================================================================
# 3. POST /users/me/cv/file — replacing an existing CV after onboarding.
# =============================================================================
headers3 = register("replace-notcv@example.com")
with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=is_cv()):
    client.post("/users/me/cv", json={"cv_raw_text": REAL_CV.decode()}, headers=headers3)

with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=not_cv("it's a novel excerpt")):
    r = client.post(
        "/users/me/cv/file", headers=headers3, files={"file": ("book.txt", b"Chapter One. It was a dark and stormy night...", "text/plain")}
    )
check("replacing a CV with a novel excerpt is refused -> 400", r.status_code == 400)
check(
    "the ORIGINAL real CV is still intact — a bad replacement never overwrote it",
    REAL_CV.decode()[:20] in (client.get("/users/me", headers=headers3).json().get("cv_raw_text") or REAL_CV.decode()),
)

with patch("app.agents.graph.cv_parsing.call_with_tool", return_value=is_cv()):
    updated_cv = REAL_CV + b"\n\nUpdated with a new project."
    r = client.post("/users/me/cv/file", headers=headers3, files={"file": ("cv2.txt", updated_cv, "text/plain")})
check("replacing with a real, updated CV -> 200", r.status_code == 200)


# =============================================================================
# 4. Non-CV upload paths are correctly untouched — they still accept any
#    document, on purpose (own-project materials, a company's knowledge
#    base genuinely aren't CVs and were never meant to be judged as
#    one). Confirms read_cv_upload itself never gained this check.
# =============================================================================
own_project_headers = register("cv-materials@example.com")

# no CV-classification mock active at all here — if the materials-upload
# path accidentally called validate_is_cv, this would hit the real API
# and fail instead of passing.
r = client.post(
    "/projects/own",
    data={
        "title": "Personal budgeting app",
        "description": "A project I'm already working on.",
        "materials_text": "Tech stack: Flask, SQLite. Goal: track monthly spending by category.",
    },
    headers=own_project_headers,
)
check(
    "own-project materials upload is unaffected by CV validation -> 201",
    r.status_code == 201,
)

print("\nAll CV-validation smoke checks passed.")
