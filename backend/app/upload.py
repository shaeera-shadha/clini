"""Text extraction from uploaded documents (PDF, DOCX, TXT)."""

from __future__ import annotations

import io
from pathlib import PurePosixPath

from fastapi import UploadFile

from app.errors import PipelineError

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


async def extract_text_from_file(file: UploadFile) -> str:
    suffix = PurePosixPath(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise PipelineError(
            "unsupported_file",
            f"Unsupported file type ({suffix or 'unknown'}). Upload a PDF, DOCX or TXT file.",
        )
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise PipelineError("file_too_large", "File exceeds the 10 MB limit.")
    if not data:
        raise PipelineError("empty_file", "The uploaded file is empty.")
    try:
        if suffix == ".txt":
            return _decode_text(data)
        if suffix == ".pdf":
            return _extract_pdf(data)
        return _extract_docx(data)
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(
            "extraction_failed", "Could not read the file. It may be corrupted."
        ) from exc


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = data.decode(encoding).strip()
            if text:
                return text
        except UnicodeDecodeError:
            continue
    raise PipelineError("empty_file", "The file contains no readable text.")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [p.extract_text() or "" for p in reader.pages]
    text = "\n\n".join(chunk.strip() for chunk in pages if chunk.strip())
    if not text:
        raise PipelineError("empty_file", "No readable text found in the PDF.")
    return text


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    if not text:
        raise PipelineError("empty_file", "No readable text found in the document.")
    return text
