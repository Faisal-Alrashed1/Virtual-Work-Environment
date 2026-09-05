import io
from pathlib import Path
from docx import Document
from pypdf import PdfReader


ALLOWED = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def extract_text(data: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if content_type.endswith("wordprocessingml.document"):
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    raise ValueError("صيغة الملف غير مدعومة")


def safe_save(root: str, user_id: str, filename: str, data: bytes) -> str:
    folder = Path(root) / user_id
    folder.mkdir(parents=True, exist_ok=True)
    safe = Path(filename).name.replace(" ", "_")
    path = folder / safe
    path.write_bytes(data)
    return str(path)
