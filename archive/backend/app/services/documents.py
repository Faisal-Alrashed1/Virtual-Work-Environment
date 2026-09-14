from pathlib import Path
from pypdf import PdfReader
from docx import Document

ALLOWED = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def safe_save(upload_dir: str, user_id: str, filename: str, data: bytes) -> str:
    path = Path(upload_dir) / f"{user_id}_{Path(filename).name}"
    path.write_bytes(data)
    return str(path)


def extract_text(data: bytes, mime_type: str) -> str:
    file_path = Path("/tmp/temp_cv")
    file_path.write_bytes(data)
    try:
        if mime_type == "application/pdf" or data[:4] == b"%PDF":
            reader = PdfReader(str(file_path))
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        doc = Document(str(file_path))
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    finally:
        if file_path.exists():
            file_path.unlink()
