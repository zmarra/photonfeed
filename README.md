# photonfeed

Personalized, multi-agent daily research feed for photonics and optics researchers.

Drop in your own publications and reference library; photonfeed builds a weighted taste
profile, then runs a daily multi-agent pipeline over fresh arXiv papers to surface what
you actually care about — with TL;DRs, novelty critiques, and links back to your own work.

## Status

Pre-v0.1. Building toward a single-user MVP:

- [ ] PDF ingestion (own work, citing-me, reference library)
- [ ] Weighted taste profile (pgvector)
- [ ] Daily arXiv pipeline (physics.optics + physics.app-ph)
- [ ] Multi-agent: triage → summarize → critique → connect → editor
- [ ] Web feed with thumbs feedback
- [ ] Nightly profile reweight from feedback
- [ ] Morning email digest
- [ ] Deploy

After v0.1: multi-tenant, OSA/USPTO sources, conferences vertical.

## Architecture

```
INGESTION (one-time, per user)
  PDFs → parser → metadata + refs (GROBID) → weighted profile vector

DAILY PIPELINE (cron)
  arXiv → triage agent → top-N candidates
                                  ├─ summarizer
                                  ├─ critic
                                  └─ connector  → editor → today's feed
                                                              ↓
                                                  web + email + thumbs
                                                              ↓
                                              nightly profile reweight
```

## Stack

- Python 3.12 + FastAPI + Claude Agent SDK (agent orchestration)
- Postgres 16 + pgvector (relational + vector store)
- GROBID (reference extraction from PDFs)
- Next.js 15 (web app)
- Resend (email)
- Fly.io / Railway (deploy)

## Layout

```
photonfeed/
├── api/      Python backend + agents + CLI
├── web/      Next.js frontend
├── infra/    docker-compose, scripts
└── docs/     architecture, decisions
```

## Development

See [docs/development.md](docs/development.md) once the scaffold lands.
