import asyncio
from collections import Counter
from typing import Annotated

import typer
from sqlalchemy import func, select

from photonfeed.db import Base, Paper, SessionLocal, engine
from photonfeed.ingest import discover_all, extract_text

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
    """Show counts of ingested papers by source."""

    async def _run() -> None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Paper.source, func.count(Paper.id)).group_by(Paper.source)
            )
            rows = result.all()
            total = sum(n for _, n in rows)
            typer.echo(f"Total papers: {total}")
            for source, n in sorted(rows):
                typer.echo(f"  {source:>12}: {n}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
