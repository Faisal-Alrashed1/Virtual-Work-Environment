"""
Extracts raw text from an uploaded CV file. Supports PDF and Word (.docx);
anything else falls back to plain text, so the existing paste-based
POST /users/me/cv keeps working unchanged.
"""
import io

from docx import Document
from pypdf import PdfReader

from app.agents.llm_client import call_with_tool

MAX_CV_BYTES = 5 * 1024 * 1024  # a CV is a few pages; 5 MB is generous


class CVReadError(Exception):
    """A CV upload we can't use. `status_code` is what the API should answer
    with; `str(exc)` is a message safe to show the graduate."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def extract_cv_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    if name.endswith(".docx"):
        return _extract_docx(content)
    return content.decode("utf-8", errors="ignore").strip()


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _extract_docx(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def read_cv_upload(filename: str | None, content: bytes) -> str:
    """The one way every endpoint turns an uploaded CV into text: size-capped,
    and a corrupt or unreadable file becomes a clean 400 instead of a 500
    stack trace from deep inside pypdf / python-docx.

    Reused as-is (despite the name) by the non-CV upload paths too —
    app/materials.py (own-project materials) and routers/company.py
    (a company's knowledge-base uploads) both take any document, not
    specifically a CV, so this function only ever checks that the file
    is *readable*. Whether the content is actually CV-shaped is a
    separate, CV-specific question — see validate_is_cv below, called
    only at the three real CV-intake points (routers/onboarding.py's
    upload_cv, routers/users.py's submit_cv and replace_cv_file)."""
    if len(content) > MAX_CV_BYTES:
        raise CVReadError(f"That file is too large — CVs are limited to {MAX_CV_BYTES // (1024 * 1024)} MB.", 413)
    try:
        text = extract_cv_text(filename or "cv.txt", content)
    except Exception as exc:  # noqa: BLE001 — parser errors vary by library
        raise CVReadError("Couldn't read that file. Try a PDF, Word (.docx) or plain-text CV.") from exc
    if not text.strip():
        raise CVReadError("Couldn't extract any text from that file.")
    return text


# ---------------------------------------------------------------------------
# Is this actually a CV? (docs/CV_VALIDATION.md) — read_cv_upload above only
# confirms *some* text came out of the file; a wrong upload (an invoice, an
# essay, a random PDF someone had lying around) can easily be long and
# text-rich without being remotely CV-shaped, so a length/keyword heuristic
# wouldn't reliably catch it. Judged by a real model instead, the same way
# every other quality judgment in this codebase is (Mentor's review, HR's
# rollup) — not a rubber stamp.
# ---------------------------------------------------------------------------

_CV_CHECK_CHARS = 4000  # enough to tell what a document is; no need for the whole thing

CV_CLASSIFICATION_TOOL = {
    "name": "classify_document",
    "description": (
        "Judge whether this document is genuinely a CV/résumé, or CV-like "
        "professional/academic background (work history, education, "
        "skills, projects) — as opposed to some other kind of document "
        "entirely (an essay, an invoice, a manual, fiction, random notes, "
        "an unrelated PDF)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "is_cv": {
                "type": "boolean",
                "description": "True only if this genuinely reads as a CV/résumé or CV-like background summary.",
            },
            "reason": {
                "type": "string",
                "description": "One brief sentence: if not a CV, what the document actually appears to be instead.",
            },
        },
        "required": ["is_cv", "reason"],
    },
}


def validate_is_cv(text: str) -> None:
    """Raises CVReadError if the text plainly isn't a CV. Judges content
    only — never rejects a real CV for being short, unpolished, or
    written in an unusual format; that's the Manager's and HR's job to
    work with later, not a gate here."""
    if not text.strip():
        raise CVReadError("That CV looks empty. Please provide your actual CV or résumé.")

    result = call_with_tool(
        system=(
            "You are a strict document classifier. Judge only whether the "
            "given text is a CV/résumé or CV-like professional background "
            "— never evaluate its quality, length, or formatting."
        ),
        messages=[{"role": "user", "content": f"Document text:\n\n{text[:_CV_CHECK_CHARS]}"}],
        tools=[CV_CLASSIFICATION_TOOL],
        force_tool="classify_document",
        max_tokens=200,
        tier="small",
    )
    data = result["input"]
    if not data.get("is_cv"):
        reason = data.get("reason") or "it doesn't read like a CV or résumé"
        raise CVReadError(f"That doesn't look like a CV — {reason} Please upload your actual CV or résumé.")

