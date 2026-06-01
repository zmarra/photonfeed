from dataclasses import dataclass
from pathlib import Path

from photonfeed.config import settings
from photonfeed.db.models import SOURCE_CITING_ME, SOURCE_LIBRARY, SOURCE_OWN

# Folders inside the user's own-papers root that shouldn't seed the taste profile.
SKIP_DIRS = {"Reviewing Papers", ".Trash", "__MACOSX"}

# Subfolder of own-papers root that should be labeled citing-me instead.
CITING_ME_SUBFOLDER = "Papers Citing me"


@dataclass(slots=True, frozen=True)
class DiscoveredPaper:
    path: Path
    source: str
    year_hint: int | None = None


def _walk_pdfs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.pdf") if not p.name.startswith(".")]


def walk_own_papers(root: Path) -> list[DiscoveredPaper]:
    """Walk the user's own publications folder.

    - `Papers Citing me/` → labeled citing_me
    - Year folders (e.g. `2024/`) → labeled own with year_hint
    - Reviewing Papers / hidden dirs → skipped
    """
    results: list[DiscoveredPaper] = []
    if not root.exists():
        return results

    for item in sorted(root.iterdir()):
        if item.name in SKIP_DIRS or item.name.startswith("."):
            continue

        if item.is_file() and item.suffix.lower() == ".pdf":
            results.append(DiscoveredPaper(path=item, source=SOURCE_OWN))
            continue

        if not item.is_dir():
            continue

        if item.name == CITING_ME_SUBFOLDER:
            for pdf in _walk_pdfs(item):
                results.append(DiscoveredPaper(path=pdf, source=SOURCE_CITING_ME))
            continue

        year_hint: int | None = None
        if item.name.isdigit() and 1990 <= int(item.name) <= 2100:
            year_hint = int(item.name)

        for pdf in _walk_pdfs(item):
            results.append(
                DiscoveredPaper(path=pdf, source=SOURCE_OWN, year_hint=year_hint)
            )

    return results


def walk_library(roots: list[Path]) -> list[DiscoveredPaper]:
    """Walk reference-library folders (ZCRG / uOttawa / AFRL)."""
    results: list[DiscoveredPaper] = []
    for root in roots:
        for pdf in _walk_pdfs(root):
            results.append(DiscoveredPaper(path=pdf, source=SOURCE_LIBRARY))
    return results


def discover_all() -> list[DiscoveredPaper]:
    """Discover every PDF in every configured source, labeled by weight tier."""
    papers: list[DiscoveredPaper] = []
    if settings.own_papers_dir:
        papers.extend(walk_own_papers(settings.own_papers_dir))
    papers.extend(walk_library(settings.library_paths))
    return papers
