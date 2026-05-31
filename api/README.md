# photonfeed (api)

Python backend: multi-agent pipeline, ingestion CLI, and FastAPI server.

See the [top-level README](../README.md) and [architecture doc](../docs/architecture.md)
for project context.

## Layout

```
src/photonfeed/
├── cli.py          Typer CLI entry (photonfeed ...)
├── config.py       Pydantic settings (env + .env)
├── agents/         Claude Agent SDK agent definitions
├── ingest/         PDF parsing + GROBID + profile builder
├── sources/        Daily source agents (arXiv, ...)
├── db/             SQLAlchemy models + session
└── api/            FastAPI app
```

## Quick start

```bash
uv sync
uv run photonfeed --help
```
