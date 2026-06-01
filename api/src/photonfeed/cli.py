import asyncio
from collections import Counter
from typing import Annotated

import typer
from sqlalchemy import func, select

from photonfeed.db import Base, Candidate, Paper, SessionLocal, engine
from photonfeed.embed import embed_documents
from photonfeed.ingest import discover_all, extract_text
from photonfeed.profile import build_profile
from photonfeed.sources import DEFAULT_CATEGORIES, fetch_recent
from photonfeed.sources.arxiv import ArxivFetchError

app = typer.Typer(
    name="photonfeed",
    help="Multi-agent personalized photonics research feed.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Photonfeed CLI."""


@app.command()
def version() -> None:
    """Print the photonfeed version."""
    from photonfeed import __version__

    typer.echo(__version__)


@app.command("init-db")
def init_db() -> None:
    """Create database tables (idempotent — safe to re-run)."""

    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        typer.echo("Tables created.")

    asyncio.run(_run())


@app.command()
def seed(
    limit: Annotated[
        int | None,
        typer.Option(help="Cap number of PDFs to ingest (smoke testing)"),
    ] = None,
    batch_size: Annotated[int, typer.Option(help="Commit every N papers")] = 25,
) -> None:
    """Walk PDF source folders, extract text, store papers in DB.

    Idempotent: papers already in DB (matched by file_path) are skipped.
    """

    async def _run() -> None:
        discovered = discover_all()
        by_source = Counter(p.source for p in discovered)
        typer.echo(f"Discovered {len(discovered)} PDFs:")
        for src, n in sorted(by_source.items()):
            typer.echo(f"  {src:>12}: {n}")

        if limit is not None:
            discovered = discovered[:limit]
            typer.echo(f"Limiting to first {limit} for this run.")

        n_inserted = 0
        n_skipped = 0
        n_failed = 0

        async with SessionLocal() as session:
            for i, dp in enumerate(discovered, start=1):
                file_path_str = str(dp.path)

                existing = await session.execute(
                    select(Paper.id).where(Paper.file_path == file_path_str)
                )
                if existing.scalar_one_or_none() is not None:
                    n_skipped += 1
                    continue

                text = extract_text(dp.path)
                if text is None or len(text) < 50:
                    n_failed += 1
                    continue

                session.add(
                    Paper(
                        file_path=file_path_str,
                        source=dp.source,
                        full_text=text,
                        year=dp.year_hint,
                    )
                )
                n_inserted += 1

                if n_inserted % batch_size == 0:
                    await session.commit()
                    typer.echo(f"  ... {i}/{len(discovered)} processed, {n_inserted} inserted")

            await session.commit()

        typer.echo(
            f"\nInserted: {n_inserted}, Skipped (already in DB): {n_skipped}, "
            f"Failed (unreadable / too short): {n_failed}"
        )

    asyncio.run(_run())


@app.command("papers-status")
def papers_status() -> None:
    """Show counts of ingested papers by source (and how many are embedded)."""

    async def _run() -> None:
        async with SessionLocal() as session:
            total_q = select(Paper.source, func.count(Paper.id)).group_by(Paper.source)
            embed_q = (
                select(Paper.source, func.count(Paper.id))
                .where(Paper.embedding.is_not(None))
                .group_by(Paper.source)
            )
            total_rows = (await session.execute(total_q)).all()
            embed_rows = dict((await session.execute(embed_q)).all())

            total = sum(n for _, n in total_rows)
            embedded = sum(embed_rows.values())
            typer.echo(f"Total papers: {total} ({embedded} embedded)")
            for source, n in sorted(total_rows):
                e = embed_rows.get(source, 0)
                typer.echo(f"  {source:>12}: {n:>4} ({e:>4} embedded)")

    asyncio.run(_run())


@app.command()
def embed(
    batch_size: Annotated[
        int, typer.Option(help="Voyage batch size (max 128)")
    ] = 64,
) -> None:
    """Embed all papers that don't yet have an embedding (idempotent)."""

    async def _run() -> None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Paper.id, Paper.full_text).where(
                    Paper.embedding.is_(None), Paper.full_text.is_not(None)
                )
            )
            rows = result.all()
            if not rows:
                typer.echo("Nothing to embed — all papers already have embeddings.")
                return

            typer.echo(f"Embedding {len(rows)} papers in batches of {batch_size}...")
            n_done = 0
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                texts = [r.full_text or "" for r in batch]
                vectors = embed_documents(texts)
                for r, vec in zip(batch, vectors, strict=True):
                    paper = await session.get(Paper, r.id)
                    if paper is not None:
                        paper.embedding = vec
                await session.commit()
                n_done += len(batch)
                typer.echo(f"  {n_done}/{len(rows)} embedded")
            typer.echo(f"Done. {n_done} papers embedded.")

    asyncio.run(_run())


@app.command("fetch-arxiv")
def fetch_arxiv(
    max_results: Annotated[
        int, typer.Option(help="Max papers to pull from arXiv")
    ] = 200,
    days: Annotated[
        int | None, typer.Option(help="Only keep papers published in the last N days")
    ] = None,
) -> None:
    """Fetch recent arXiv papers in the user's fields into the candidates table.

    Idempotent: candidates already present (matched by external_id) are skipped.
    """

    async def _run() -> None:
        typer.echo(
            f"Fetching up to {max_results} from arXiv "
            f"({', '.join(DEFAULT_CATEGORIES)})..."
        )
        try:
            papers = fetch_recent(max_results=max_results, since_days=days)
        except ArxivFetchError as e:
            typer.secho(str(e), fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(code=1) from e
        typer.echo(f"arXiv returned {len(papers)} papers.")

        n_inserted = 0
        n_skipped = 0
        async with SessionLocal() as session:
            for p in papers:
                existing = await session.execute(
                    select(Candidate.id).where(Candidate.external_id == p.external_id)
                )
                if existing.scalar_one_or_none() is not None:
                    n_skipped += 1
                    continue
                session.add(
                    Candidate(
                        source="arxiv",
                        external_id=p.external_id,
                        version=p.version,
                        title=p.title,
                        abstract=p.abstract,
                        authors=p.authors,
                        categories=p.categories,
                        primary_category=p.primary_category,
                        published_at=p.published_at,
                        abs_url=p.abs_url,
                        pdf_url=p.pdf_url,
                    )
                )
                n_inserted += 1
            await session.commit()

        typer.echo(f"Inserted: {n_inserted}, Skipped (already present): {n_skipped}")

    asyncio.run(_run())


profile_app = typer.Typer(help="Build & inspect the user taste profile.")
app.add_typer(profile_app, name="profile")


@profile_app.command("build")
def profile_build() -> None:
    """Compute weighted-centroid taste profile from embedded papers."""

    async def _run() -> None:
        async with SessionLocal() as session:
            result = await build_profile(session)
        typer.echo(f"Profile built from {result.paper_count} papers.")
        typer.echo(f"Total weight: {result.weight_sum:.1f}")
        typer.echo("Sources:")
        for src, n in sorted(result.per_source.items()):
            typer.echo(f"  {src:>12}: {n}")
        typer.echo("\nTop papers by similarity to profile (sanity check):")
        for path, sim, src in result.top_papers:
            short = path.rsplit("/", 1)[-1][:80]
            typer.echo(f"  {sim:.3f}  [{src:>9}]  {short}")

    asyncio.run(_run())


@profile_app.command("show")
def profile_show() -> None:
    """Print the current persisted profile stats."""
    from photonfeed.db import Profile

    async def _run() -> None:
        async with SessionLocal() as session:
            p = await session.get(Profile, 1)
            if p is None:
                typer.echo("No profile yet — run `photonfeed profile build`.")
                return
            typer.echo(f"Profile id={p.id}, updated_at={p.updated_at.isoformat()}")
            typer.echo(f"Papers: {p.paper_count}, weight sum: {p.weight_sum:.1f}")
            typer.echo(f"Stats: {p.stats}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
