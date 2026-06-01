"""Voyage AI embedding wrapper.

voyage-3-large: 1024 dims (matches the schema), 32K token context, best-in-class
for scientific text per Voyage's MIRACL/MTEB benchmarks (as of 2025).
"""

from __future__ import annotations

from typing import Final

import voyageai

from photonfeed.config import settings

EMBEDDING_MODEL: Final = "voyage-3-large"
MAX_BATCH_SIZE: Final = 128
# Voyage limits per-text to 32K tokens; chars≈4 tokens of slack for scientific PDFs.
MAX_CHARS_PER_TEXT: Final = 28_000


def _client() -> voyageai.Client:
    if not settings.voyage_api_key:
        raise RuntimeError(
            "VOYAGE_API_KEY is not set. Add it to .env or your environment."
        )
    return voyageai.Client(api_key=settings.voyage_api_key)


def _truncate(text: str) -> str:
    return text[:MAX_CHARS_PER_TEXT]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of documents. Returns one 1024-dim vector per input.

    Caller is responsible for batching at MAX_BATCH_SIZE granularity if needed —
    this helper splits transparently to stay under that limit.
    """
    client = _client()
    out: list[list[float]] = []
    for start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = [_truncate(t) for t in texts[start : start + MAX_BATCH_SIZE]]
        result = client.embed(texts=batch, model=EMBEDDING_MODEL, input_type="document")
        out.extend(result.embeddings)
    return out


def embed_query(text: str) -> list[float]:
    """Embed a single query string (different input_type tuning vs documents)."""
    client = _client()
    result = client.embed(
        texts=[_truncate(text)], model=EMBEDDING_MODEL, input_type="query"
    )
    return result.embeddings[0]
