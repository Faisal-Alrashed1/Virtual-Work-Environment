"""
Reads the content of files a graduate uploaded with a task submission
(TaskAttachment rows, stored on disk via app/storage.py) so an agent can
review what's actually inside them instead of judging by filename.

Shared on purpose: the Security Reviewer and Data Reviewer use it today.
The Mentor and Manager still only see attachment names (mentor.py reads
images only), and could adopt this the same way.

Text-like files are read as-is (truncated); notebooks are reduced to
their code cells; images and anything that isn't valid UTF-8 text (zip,
pdf, docx, binaries) are reported back as unreadable, so the caller can
say so honestly rather than guess from the name.
"""
import json

from app.models import Task
from app.storage import read_attachment

MAX_CHARS_PER_FILE = 4000


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
    # A NUL byte or invalid UTF-8 means a binary file (zip, pdf, docx...),
    # detected from the content itself rather than trusting the extension.
    if b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if filename.lower().endswith(".ipynb"):
        return extract_notebook_code(text)
    return text if text.strip() else None


def read_submitted_files(
    task: Task, max_chars_per_file: int = MAX_CHARS_PER_FILE
) -> tuple[list[tuple[str, str]], list[str]]:
    """Returns (readable, unreadable): readable is [(filename, text)] for
    every attachment whose content could be read, unreadable is the names
    of the ones that couldn't (images, archives, binaries, empty files)."""
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
        text = _as_text(attachment.filename, raw)
        if text is None:
            unreadable.append(attachment.filename)
            continue
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n... (truncated)"
        readable.append((attachment.filename, text))
    return readable, unreadable
