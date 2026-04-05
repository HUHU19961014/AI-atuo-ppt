from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def extract_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    if suffix in {".html", ".htm"}:
        return _extract_html_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    return path.read_text(encoding="utf-8")


def _extract_html_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def _extract_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip())


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            chunks.append(page_text)
    return "\n\n".join(chunks)
