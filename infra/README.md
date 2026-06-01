# infra

Local dev infrastructure: Postgres (with pgvector) + GROBID.

## Bring up

```bash
cd infra
docker compose up -d
docker compose ps             # wait until both are 'healthy'
docker compose logs -f grobid # grobid takes ~30-60s to be ready on first run
```

## Tear down

```bash
docker compose down              # stop, keep data
docker compose down -v           # stop + wipe pg-data volume
```

## Notes

- **Postgres:** `pgvector/pgvector:pg16`, exposes 5432. Default credentials
  `photonfeed/photonfeed/photonfeed` (user/password/db). `init.sql` creates the
  `vector` and `pg_trgm` extensions on first boot.
- **GROBID:** `grobid/grobid:0.8.1`, exposes 8070. First boot pulls a ~3GB image
  and warms up the JVM (~30-60s). Used only at PDF-ingest time, so it's fine to
  shut down between ingest runs.
- **Volume:** `photonfeed-pg-data` persists Postgres data across `compose down`.
