"""
Turns pasted text plus zero or more uploaded files into one combined,
capped block of text — real material for the Manager to plan real
subtasks from, instead of a one-line description. Originally
routers/projects.py's own-project upload only; Stage 3's company
projects (routers/company.py) needed the exact same shape, so it lives
here instead of being duplicated. See docs/STAGE2_OWN_PROJECT.md and
docs/STAGE3_COMPANY_RAG.md.
"""
from fastapi import HTTPException, UploadFile

from app.agents.graph.cv_parsing import CVReadError, read_cv_upload
from app.agents.task_bank import MAX_MATERIALS_CHARS

MAX_MATERIALS_FILES = 3
_TRUNCATION_NOTE = "\n\n[...materials truncated to the first {cap} characters...]"


def combine_materials(materials_text: str | None, files: list[UploadFile]) -> str | None:
    """Pasted notes plus every uploaded file's extracted text, one block per file
    (so the Manager can tell them apart), combined and capped — see
    MAX_MATERIALS_CHARS. None if there is nothing at all. Raises
    HTTPException (400/413) on a bad file, via read_cv_upload — reused as-is: it
    is already a generic "turn an upload into text, cleanly" helper, not
    CV-specific despite its module name."""
    parts = []
    if materials_text and materials_text.strip():
        parts.append(materials_text.strip())
    real_files = [f for f in files if f.filename]
    if len(real_files) > MAX_MATERIALS_FILES:
        raise HTTPException(400, f"Up to {MAX_MATERIALS_FILES} files.")
    for f in real_files:
        try:
            text = read_cv_upload(f.filename, f.file.read())
        except CVReadError as exc:
            raise HTTPException(exc.status_code, f"{f.filename}: {exc}")
        parts.append(f"--- {f.filename} ---\n{text}")
    if not parts:
        return None
    combined = "\n\n".join(parts)
    if len(combined) > MAX_MATERIALS_CHARS:
        note = _TRUNCATION_NOTE.format(cap=MAX_MATERIALS_CHARS)
        combined = combined[: MAX_MATERIALS_CHARS - len(note)] + note
    return combined
