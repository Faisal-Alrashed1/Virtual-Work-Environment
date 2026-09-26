"""
Smoke test for Stage 3's company side (docs/STAGE3_COMPANY_RAG.md):
registering/joining a company account, free-text job titles, material
upload, and the RAG knowledge base's actual retrieval ranking. Embeddings
are mocked with a small deterministic fake so retrieval ranking is a real
assertion, not just "didn't crash" — see fake_vector below.

Run: python smoke_test_company_rag.py
"""
import os
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_company_rag.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-embeddings-are-mocked-below")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


# A tiny, deterministic fake embedding space: each dimension is "does this
# text mention keyword X". Real retrieval ranking (a Python-heavy chunk
# should outrank a Kubernetes-heavy one for a "python" query) becomes a
# real, checkable assertion instead of just "the call didn't crash".
_KEYWORDS = ["python", "kubernetes", "figma"]


def fake_vector(text: str) -> list[float]:
    lowered = text.lower()
    return [1.0 if kw in lowered else 0.0 for kw in _KEYWORDS]


class _FakeItem:
    def __init__(self, embedding):
        self.embedding = embedding


class _FakeResponse:
    def __init__(self, vectors):
        self.data = [_FakeItem(v) for v in vectors]


class _FakeEmbeddings:
    def create(self, model, input):
        return _FakeResponse([fake_vector(t) for t in input])


class _FakeOpenAIClient:
    def __init__(self):
        self.embeddings = _FakeEmbeddings()


fake_client = _FakeOpenAIClient()


def register_company(email, company_name=None, join_code=None, role=None, field=None):
    payload = {"email": email, "password": "hunter2pass", "full_name": "Rep " + email}
    if company_name:
        payload["company_name"] = company_name
        if field:
            payload["field"] = field
    if join_code:
        payload["join_code"] = join_code
        payload["role"] = role
    return client.post("/company/register", json=payload)


def login(email):
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- a student account is unaffected: account_type defaults to student ---
r = client.post(
    "/auth/register",
    json={"email": "student-a@example.com", "password": "hunter2pass", "full_name": "Student A"},
)
check("student register unaffected", r.status_code == 201)
check("student account_type defaults to student", r.json()["account_type"] == "student")
student_headers = login("student-a@example.com")

# --- founding a new company ---
r = register_company("admin@acme.com", company_name="Acme Robotics", field="Robotics")
check("found new company -> 201", r.status_code == 201)
body = r.json()
check("founder role is admin", body["user"]["company_role"] == "admin")
check("founder account_type is company", body["user"]["account_type"] == "company")
check("org field is free text (not an IT track)", body["organization"]["field"] == "Robotics")
join_code = body["organization"]["join_code"]
check("a join_code was generated", bool(join_code))
org_id = body["user"]["organization_id"]
admin_headers = login("admin@acme.com")

# --- founding without a company_name is rejected ---
r = register_company("bad@acme.com")
check("register with neither company_name nor join_code -> 400", r.status_code == 400)

# --- a student account can't touch company endpoints ---
r = client.get("/company/job-titles", headers=student_headers)
check("student account refused on a company endpoint -> 403", r.status_code == 403)

# --- GET /company/me reflects the org just created ---
r = client.get("/company/me", headers=admin_headers)
check("company/me -> 200", r.status_code == 200)
check("company/me shows the right org", r.json()["name"] == "Acme Robotics")

# --- a second rep joins via join_code, with a role ---
r = register_company("hr@acme.com", join_code=join_code, role="hr")
check("join via join_code -> 201", r.status_code == 201)
check("joiner shares the same organization_id", r.json()["user"]["organization_id"] == org_id)
check("joiner got the role they asked for", r.json()["user"]["company_role"] == "hr")

# --- joining requires a role ---
r = register_company("norole@acme.com", join_code=join_code, role=None)
check("join without a role -> 400", r.status_code == 400)

# --- a bad join_code 404s ---
r = register_company("nowhere@acme.com", join_code="NOTREAL", role="admin")
check("join with an invalid join_code -> 404", r.status_code == 404)

# --- create a free-text job title (not one of the six IT tracks) ---
r = client.post(
    "/company/job-titles",
    json={"title": "Robotics Field Technician", "description": "On-site maintenance."},
    headers=admin_headers,
)
check("create job title -> 201", r.status_code == 201)
job_title = r.json()
check("job title is free text", job_title["title"] == "Robotics Field Technician")
check("starts with no materials", job_title["material_count"] == 0 and job_title["chunk_count"] == 0)
job_title_id = job_title["id"]

r = client.get("/company/job-titles", headers=admin_headers)
check("list job titles includes it", any(jt["id"] == job_title_id for jt in r.json()))

# --- upload two materials with distinct fake-embedding "topics" ---
with patch("app.rag.openai_client_for_embeddings", return_value=fake_client):
    r = client.post(
        f"/company/job-titles/{job_title_id}/materials",
        data={"text": "This role writes a lot of Python for the robot control software. " * 3},
        headers=admin_headers,
    )
check("upload pasted-text material -> 201", r.status_code == 201)
check("material chunked into at least one chunk", r.json()["chunk_count"] >= 1)
py_material_id = r.json()["id"]

with patch("app.rag.openai_client_for_embeddings", return_value=fake_client):
    r = client.post(
        f"/company/job-titles/{job_title_id}/materials",
        data={"text": "This role manages our Kubernetes cluster and deployment pipeline. " * 3},
        headers=admin_headers,
    )
check("upload second material -> 201", r.status_code == 201)
k8s_material_id = r.json()["id"]

r = client.get(f"/company/job-titles/{job_title_id}/materials", headers=admin_headers)
check("materials list has both uploads", len(r.json()) == 2)
check("material preview is present and truncated marker style", "Python" in r.json()[0]["preview"] or "Kubernetes" in r.json()[0]["preview"])

r = client.get(f"/company/job-titles/{job_title_id}", headers=admin_headers)
check("job title now reports 2 materials", r.json()["material_count"] == 2)
check("job title now reports chunks > 0", r.json()["chunk_count"] >= 2)

# --- real retrieval ranking: a "python" query should surface the Python
#     material's chunk first, with a strictly higher score ---
with patch("app.rag.openai_client_for_embeddings", return_value=fake_client):
    r = client.post(
        f"/company/job-titles/{job_title_id}/query",
        json={"query": "Tell me about the Python work", "k": 5},
        headers=admin_headers,
    )
check("query -> 200", r.status_code == 200)
result = r.json()
check("query returns both chunks", len(result["chunks"]) == 2)
top = result["chunks"][0]
check("top result comes from the Python material", top["material_id"] == py_material_id)
check("top result scores strictly higher than the second", result["chunks"][0]["score"] > result["chunks"][1]["score"])
check("top score is a real cosine similarity (~1.0, exact keyword match)", top["score"] > 0.9)

# --- cross-org isolation: a second company can't see the first's data ---
register_company("admin@othercorp.com", company_name="OtherCorp", field="Finance")
other_headers = login("admin@othercorp.com")
r = client.get(f"/company/job-titles/{job_title_id}", headers=other_headers)
check("other company can't read Acme's job title -> 404", r.status_code == 404)
r = client.get("/company/job-titles", headers=other_headers)
check("other company's job-titles list is empty (isolated)", r.json() == [])

# --- missing OPENAI_API_KEY gives a clean 503, not a raw 500 ---
r2 = client.post(
    "/company/job-titles",
    json={"title": "Temp title for the no-key test"},
    headers=other_headers,
)
temp_job_title_id = r2.json()["id"]
r = client.post(
    f"/company/job-titles/{temp_job_title_id}/materials",
    data={"text": "Some material text, uploaded with no OPENAI_API_KEY configured."},
    headers=other_headers,
)
check("no OPENAI_API_KEY -> clean 503, not a raw 500", r.status_code == 503)

print("\nAll company/RAG smoke checks passed.")
