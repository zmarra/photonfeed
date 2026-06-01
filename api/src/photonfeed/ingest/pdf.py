import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# pypdf logs many benign 'Ignoring wrong pointing object' messages on slightly
# malformed but still readable PDFs — suppress at module import.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# First few pages of a paper typically carry the title, authors, abstract, and
# intro — enough signal for an embedding-based taste profile.
DEFAULT_MAX_PAGES = 5


def extract_text(path: Path, max_pages: int = DEFAULT_MAX_PAGES) -> str | None:
    """Extract text from the first N pages of a PDF. Returns None on hard failure."""
    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError):
        return None

    chunks: list[str] = []
    for page in reader.pages[:max_pages]:
        try:
            text = page.extract_text() or ""
        except Exception:  # pypdf raises a zoo of exceptions on malformed PDFs
            continue
        if text:
            chunks.append(text)

    combined = "\n".join(chunks).strip()
    return combined or None
