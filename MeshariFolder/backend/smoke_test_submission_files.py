"""
Unit test for app/agents/submission_files.py: what the agents can read
from an upload (docs/TEAM_CHANGES.md #7) — text/code files, notebooks,
PDF and Word text, and the readable files inside a .zip — and the limits
that keep a zipped project from flooding the prompt.

No LLM involved. Run: python smoke_test_submission_files.py
"""
import io
import json
import os
import zipfile

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_submission_files.db"
)

from docx import Document  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskAttachment, TaskStatus, User  # noqa: E402
from app.storage import save_attachment  # noqa: E402
from app.agents.submission_files import (  # noqa: E402
    MAX_ZIP_MEMBER_BYTES,
    MAX_ZIP_MEMBERS,
    read_submitted_files,
)

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


client.post("/auth/register", json={"email": "files@example.com", "password": "hunter2pass", "full_name": "F"})
db = SessionLocal()
user = db.query(User).filter(User.email == "files@example.com").first()


def read(*uploads, max_chars=4000):
    task = Task(user_id=user.id, title="t", description="d", status=TaskStatus.SUBMITTED)
    db.add(task)
    db.commit()
    db.refresh(task)
    for filename, content_type, content in uploads:
        db.add(
            TaskAttachment(
                task_id=task.id,
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                storage_path=save_attachment(task.id, filename, content),
            )
        )
    db.commit()
    db.refresh(task)
    return read_submitted_files(task, max_chars_per_file=max_chars)


def make_pdf(text: str) -> bytes:
    """A minimal one-page PDF with real text, no extra libraries needed."""
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj".encode() + body + b"endobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def make_docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


# --- plain .py ---
readable, unreadable = read(("app.py", "text/x-python", b"print('hello')\n"))
check(".py is read", readable == [("app.py", "print('hello')\n")])

# --- PDF / Word ---
readable, unreadable = read(("report.pdf", "application/pdf", make_pdf("Churn model results")))
check("PDF text is read", len(readable) == 1 and "Churn model results" in readable[0][1])

readable, unreadable = read(("plan.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", make_docx("My project plan")))
check("Word (.docx) text is read", len(readable) == 1 and "My project plan" in readable[0][1])

readable, unreadable = read(("broken.pdf", "application/pdf", b"%PDF-1.4\x00\x01not really a pdf"))
check("a corrupt PDF is unreadable, not a crash", readable == [] and unreadable == ["broken.pdf"])

# --- zip: a zipped project ---
notebook = json.dumps({"cells": [{"cell_type": "markdown", "source": ["# notes"]}, {"cell_type": "code", "source": ["model.fit(X, y)"]}]})
project = make_zip({
    "project/src/app.py": 'DB_PASSWORD = "secret123"\n',
    "project/requirements.txt": "flask==2.0.0\n",
    "project/train.ipynb": notebook,
    "project/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00binary",
    "project/__pycache__/app.cpython-311.pyc": b"\x00\x01compiled",
    "project/.git/config": "[core]\n",
})
readable, unreadable = read(("project.zip", "application/zip", project))
names = [n for n, _ in readable]
check(".py inside a zip is read", "project.zip/project/src/app.py" in names)
check("files inside a zip are named archive/path", all(n.startswith("project.zip/") for n in names))
check("requirements.txt inside a zip is read", "project.zip/project/requirements.txt" in names)
check("notebooks inside a zip give code cells only", any("model.fit" in t and "# notes" not in t for n, t in readable if n.endswith(".ipynb")))
check("binary files inside a zip are skipped", not any(n.endswith((".png", ".pyc")) for n in names))
check(".git/ and __pycache__/ are skipped", not any("/.git/" in n or "__pycache__" in n for n in names))
check("a zip with readable files isn't listed as unreadable", unreadable == [])

# --- zip limits ---
many = make_zip({f"src/file_{i:02d}.py": f"x = {i}\n" for i in range(40)})
readable, _ = read(("many.zip", "application/zip", many))
check(f"at most {MAX_ZIP_MEMBERS} files are read from one zip", len(readable) == MAX_ZIP_MEMBERS)

bomb = make_zip({"huge.txt": "a" * (MAX_ZIP_MEMBER_BYTES + 10), "small.py": "ok = True\n"})
check("the zip itself is small", len(bomb) < 50_000)
readable, _ = read(("bomb.zip", "application/zip", bomb))
check("a member that decompresses past the limit is skipped", [n for n, _ in readable] == ["bomb.zip/small.py"])

big = make_zip({f"f{i}.py": "y = 1\n" * 2000 for i in range(10)})
readable, _ = read(("big.zip", "application/zip", big), max_chars=1000)
check("total text from one zip stays within its budget", sum(len(t) for _, t in readable) <= 3 * 1000 + 3 * len("\n... (truncated)"))

readable, unreadable = read(("images.zip", "application/zip", make_zip({"a.png": b"\x89PNG\x00", "b.jpg": b"\xff\xd8\x00"})))
check("a zip with nothing readable is listed as unreadable", readable == [] and unreadable == ["images.zip"])

readable, unreadable = read(("fake.zip", "application/zip", b"not a zip at all"))
check("a corrupt zip is unreadable, not a crash", readable == [] and unreadable == ["fake.zip"])

# --- images still aren't "read" as text ---
readable, unreadable = read(("screen.png", "image/png", b"\x89PNG\r\n\x1a\n\x00"))
check("images are left to the Mentor's vision, not read as text", unreadable == ["screen.png"])

db.close()
print("\nAll submission-file reading smoke checks passed.")
