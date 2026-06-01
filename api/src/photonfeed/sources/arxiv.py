"""arXiv source agent: fetch recent papers in the user's fields.

Uses the `arxiv` package, which wraps the export API and handles pagination +
the 3s politeness delay arXiv asks for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final

import arxiv

# Default categories for an optics/photonics researcher.
DEFAULT_CATEGORIES: Final = ["physics.optics", "physics.app-ph"]


class ArxivFetchError(RuntimeError):
    """Raised when the arXiv API can't be reached (e.g. persistent HTTP 429)."""


@dataclass(slots=True)
class ArxivPaper:
    external_id: str  # versionless, e.g. "2401.12345"
    version: str | None  # e.g. "v1"
    title: str
    abstract: str
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    primary_category: str | None = None
    published_at: datetime | None = None
    abs_url: str | None = None
    pdf_url: str | None = None


def _split_id(entry_id: str) -> tuple[str, str | None]:
    """`http://arxiv.org/abs/2401.12345v2` -> ("2401.12345", "v2")."""
    tail = entry_id.rsplit("/", 1)[-1]
    if "v" in tail:
        base, _, ver = tail.rpartition("v")
        if ver.isdigit():
            return base, f"v{ver}"
    return tail, None


def fetch_recent(
    categories: list[str] | None = None,
    max_results: int = 200,
    since_days: int | None = None,
) -> list[ArxivPaper]:
    """Fetch the most recent submissions in the given categories.

    If `since_days` is set, drop papers published before that cutoff.
    """
    cats = categories or DEFAULT_CATEGORIES
    query = " OR ".join(f"cat:{c}" for c in cats)

    # arXiv asks for a 3s politeness delay; bump retries to ride out the
    # occasional HTTP 429 when their export API is busy.
    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=5)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    cutoff: datetime | None = None
    if since_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=since_days)

    papers: list[ArxivPaper] = []
    try:
        for r in client.results(search):
            published = r.published
            if cutoff is not None and published is not None and published < cutoff:
                continue
            base_id, version = _split_id(r.entry_id)
            papers.append(
                ArxivPaper(
                    external_id=base_id,
                    version=version,
                    title=r.title.strip().replace("\n", " "),
                    abstract=r.summary.strip().replace("\n", " "),
                    authors=[a.name for a in r.authors],
                    categories=list(r.categories),
                    primary_category=r.primary_category,
                    published_at=published,
                    abs_url=r.entry_id,
                    pdf_url=r.pdf_url,
                )
            )
    except arxiv.HTTPError as e:
        raise ArxivFetchError(
            f"arXiv API request failed ({e}). This is usually transient "
            "rate-limiting (HTTP 429) — wait a few minutes and retry."
        ) from e
    return papers
