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
    """Extract text from the first N pages of a PDF. Returns None on hard failure.

    Catches the long tail of pypdf failures (malformed PDFs, encrypted PDFs we
    don't have keys for, dependency errors) so a single bad file can't kill
    a batch ingest of hundreds of papers.
    """
    try:
        reader = PdfReader(str(path))
        # Some PDFs are encrypted with an empty password — pypdf can open them.
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return None
        pages = list(reader.pages[:max_pages])
    except (PdfReadError, OSError, ValueError, Exception):
        return None

    chunks: list[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        if text:
            chunks.append(text)

    combined = "\n".join(chunks).strip()
    if not combined:
        return None
    # Postgres TEXT rejects NUL bytes; pypdf occasionally surfaces them from
    # malformed PDFs. Strip the few control chars Postgres flat-out won't accept.
    return combined.replace("\x00", "")
