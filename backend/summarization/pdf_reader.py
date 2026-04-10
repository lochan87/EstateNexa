"""PDF reading utilities for summarization workflows."""

from __future__ import annotations

from pathlib import Path

from PyPDF2 import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_pdf(file_path: str) -> str:
    """Read a PDF file and return combined text from all pages.

    Returns an empty string if the file cannot be opened or parsed.
    """

    try:
        pdf_path = Path(file_path)
        if not pdf_path.is_absolute():
            candidate_path = PROJECT_ROOT / pdf_path
            if candidate_path.is_file():
                pdf_path = candidate_path

        if not pdf_path.is_file():
            return ""

        with pdf_path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            page_text = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    page_text.append(text)

        return "\n".join(page_text).strip()
    except Exception:
        return ""
