"""
Reads the content of files a graduate uploaded with a task submission
(TaskAttachment rows, stored on disk via app/storage.py) so an agent can
review what's actually inside them instead of judging by filename.

Shared on purpose: the Mentor, the Security/Data Reviewers, and the
Manager's thread replies all read uploads through here.

What can be read:
- text/code files (.py, .js, requirements.txt, .csv, ...) — as-is
- notebooks (.ipynb) — code cells only
- PDF and Word (.docx) — their text
- .zip archives — the readable files inside (a graduate often zips a
  whole project), each named like "project.zip/src/app.py"
Everything is truncated. Images (the Mentor sees those through vision)
and anything else binary are reported back as unreadable, so the caller
can say so honestly rather than guess from the name.
"""
import io
import json
import zipfile

from app.agents.graph.cv_parsing import extract_cv_text
from app.models import Task
from app.storage import read_attachment

MAX_CHARS_PER_FILE = 4000

# Zip limits: a zipped project can hold hundreds of files (and a crafted
# zip can claim to be tiny and expand to gigabytes), so read at most this
# many members, each at most this big once decompressed, and cap the
# total text taken from one archive at this many files' worth.
MAX_ZIP_MEMBERS = 15
MAX_ZIP_MEMBER_BYTES = 1_000_000
ZIP_TOTAL_FILES_WORTH = 3
_ZIP_SKIP_DIRS = {"__macosx", ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def extract_notebook_code(content: str) -> str | None:
    """Just the code cells' source, joined. Skips markdown cells and
    'outputs' entirely: a notebook's outputs can embed large base64
    images/dataframes that add nothing to a code review and would bloat
    the prompt."""
    try:
        notebook = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    parts = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else source
        if text.strip():
            parts.append(text)
    return "\n\n# ---\n\n".join(parts) if parts else None


def _as_text(filename: str, raw: bytes) -> str | None:
    name = filename.lower()
    if name.endswith((".pdf", ".docx")):
        # Same extraction the CV upload uses (pypdf / python-docx).
        try:
            text = extract_cv_text(filename, raw)
        except Exception:  # a corrupt or encrypted document is just unreadable
            return None
        return text if text.strip() else None
    # A NUL byte or invalid UTF-8 means a binary file, detected from the
    # content itself rather than trusting the extension.
    if b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if name.endswith(".ipynb"):
        return extract_notebook_code(text)
    return text if text.strip() else None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def _read_zip(archive_name: str, raw: bytes, max_chars_per_file: int) -> list[tuple[str, str]]:
    """[(archive/member, text)] for the readable files inside the zip."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return []

    members = sorted(
        (
            info
            for info in archive.infolist()
            if not info.is_dir()
            and not any(part.lower() in _ZIP_SKIP_DIRS for part in info.filename.split("/"))
        ),
        key=lambda info: info.filename,
    )
    readable: list[tuple[str, str]] = []
    budget = max_chars_per_file * ZIP_TOTAL_FILES_WORTH
    for info in members[:MAX_ZIP_MEMBERS]:
        if budget <= 0:
            break
        try:
            with archive.open(info) as member:
                data = member.read(MAX_ZIP_MEMBER_BYTES + 1)
        except (RuntimeError, zipfile.BadZipFile, OSError):  # encrypted / corrupt member
            continue
        if len(data) > MAX_ZIP_MEMBER_BYTES:
            continue
        text = _as_text(info.filename, data)
        if text is None:
            continue
        text = _truncate(text, min(max_chars_per_file, budget))
        budget -= len(text)
        readable.append((f"{archive_name}/{info.filename}", text))
    return readable


def read_submitted_files(
    task: Task, max_chars_per_file: int = MAX_CHARS_PER_FILE
) -> tuple[list[tuple[str, str]], list[str]]:
    """Returns (readable, unreadable): readable is [(filename, text)] for
    every attachment (or file inside an attached zip) whose content could
    be read, unreadable is the names of the attachments that couldn't
    (images, other binaries, empty files, zips with nothing readable)."""
    readable: list[tuple[str, str]] = []
    unreadable: list[str] = []
    for attachment in task.attachments:
        if attachment.content_type.startswith("image/"):
            unreadable.append(attachment.filename)
            continue
        try:
            raw = read_attachment(attachment.storage_path)
        except OSError:
            unreadable.append(attachment.filename)
            continue

        if attachment.filename.lower().endswith(".zip"):
            inside = _read_zip(attachment.filename, raw, max_chars_per_file)
            if inside:
                readable.extend(inside)
            else:
                unreadable.append(attachment.filename)
            continue

        text = _as_text(attachment.filename, raw)
        if text is None:
            unreadable.append(attachment.filename)
            continue
        readable.append((attachment.filename, _truncate(text, max_chars_per_file)))
    return readable, unreadable
