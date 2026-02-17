import re
import logging
import pdfplumber
from docx import Document

log = logging.getLogger(__name__)

CHUNK_SIZE = 3000
SCANNED_PDF_CHAR_THRESHOLD = 50


class EmptyDocumentError(Exception):
    """Raised when a document has no extractable text."""


class ScannedPDFError(Exception):
    """Raised when a PDF appears to be scanned (image-only, < threshold chars)."""


def parse_pdf(filepath: str) -> list[dict]:
    """Extract text page-by-page from PDF."""
    pages = []
    with pdfplumber.open(filepath) as pdf:
        if len(pdf.pages) == 0:
            raise EmptyDocumentError("PDF has no pages")

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i + 1, "text": text.strip()})

    total_chars = sum(len(p["text"]) for p in pages)

    if total_chars == 0:
        raise EmptyDocumentError("PDF has no extractable text")

    if total_chars < SCANNED_PDF_CHAR_THRESHOLD:
        raise ScannedPDFError(
            f"PDF appears to be scanned — only {total_chars} characters extracted. "
            "Please upload a text-based PDF."
        )

    return pages


def parse_docx(filepath: str) -> list[dict]:
    """Extract text from DOCX as a single page list."""
    doc = Document(filepath)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if not full_text.strip():
        raise EmptyDocumentError("DOCX has no extractable text")
    # Split into pseudo-pages of ~3000 chars
    chunks = chunk_text(full_text, CHUNK_SIZE)
    return [{"page": i + 1, "text": c} for i, c in enumerate(chunks)]


def parse_document(filepath: str) -> list[dict]:
    """Parse PDF or DOCX, returns list of {page, text}."""
    lower = filepath.lower()
    if lower.endswith(".pdf"):
        return parse_pdf(filepath)
    elif lower.endswith(".docx"):
        return parse_docx(filepath)
    raise ValueError(f"Unsupported file type: {filepath}")


def detect_chapters(pages: list[dict]) -> list[dict]:
    """Try to group pages by chapter headings, fallback to chunks."""
    chapter_pattern = re.compile(
        r"^(chapter|section|part)\s+\d+", re.IGNORECASE | re.MULTILINE
    )
    sections = []
    current = {"start_page": 1, "text": ""}

    for page in pages:
        if chapter_pattern.search(page["text"]) and current["text"]:
            sections.append(current)
            current = {"start_page": page["page"], "text": ""}
        current["text"] += "\n" + page["text"]

    if current["text"].strip():
        sections.append(current)

    # If no chapters found, fall back to chunking
    if len(sections) <= 1:
        full_text = "\n".join(p["text"] for p in pages)
        chunks = chunk_text(full_text, CHUNK_SIZE)
        sections = [{"start_page": i + 1, "text": c} for i, c in enumerate(chunks)]

    return sections


def chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    chunks = []
    while len(text) > max_chars:
        # Find last sentence end before max_chars
        cut = text[:max_chars].rfind(". ")
        if cut == -1 or cut < max_chars // 2:
            cut = max_chars
        else:
            cut += 1  # include the period
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks
