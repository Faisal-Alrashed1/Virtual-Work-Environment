"""
Extracts raw text from an uploaded CV file. Supports PDF and Word (.docx);
anything else falls back to plain text, so the existing paste-based
POST /users/me/cv keeps working unchanged.
"""
import io

from docx import Document
from pypdf import PdfReader


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
