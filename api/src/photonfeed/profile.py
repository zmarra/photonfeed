"""Weighted-centroid taste profile from ingested papers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photonfeed.db import EMBEDDING_DIM, SOURCE_WEIGHTS, Paper, Profile


@dataclass(slots=True)
class ProfileBuildResult:
    paper_count: int
    weight_sum: float
    per_source: dict[str, int]
    top_papers: list[tuple[str, float, str]]  # (file_path, similarity, source)


def _weighted_centroid(
    embeddings: Sequence[Sequence[float]], weights: Sequence[float]
) -> np.ndarray:
    if not embeddings:
        raise ValueError("Cannot build profile from zero embeddings.")
    arr = np.asarray(embeddings, dtype=np.float32)
    w = np.asarray(weights, dtype=np.float32).reshape(-1, 1)
    weighted = arr * w
    centroid = weighted.sum(axis=0) / w.sum()
    # L2-normalize so cosine and dot product agree downstream.
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid /= norm
    return centroid


async def build_profile(
    session: AsyncSession, top_k_sample: int = 10
) -> ProfileBuildResult:
    """Compute weighted-centroid embedding from all embedded papers and persist
    to the single-row profile table. Returns build stats including the top
    papers by similarity to the resulting profile (sanity-check signal:
    your own papers should dominate).
    """
    result = await session.execute(
        select(Paper.file_path, Paper.source, Paper.embedding).where(
            Paper.embedding.is_not(None)
        )
    )
    rows = result.all()
    if not rows:
        raise RuntimeError(
            "No embedded papers found. Run `photonfeed embed` first."
        )

    weights = [SOURCE_WEIGHTS[r.source] for r in rows]
    embeddings = [r.embedding for r in rows]

    centroid = _weighted_centroid(embeddings, weights)

    per_source: dict[str, int] = {}
    for r in rows:
        per_source[r.source] = per_source.get(r.source, 0) + 1

    # Cosine similarity sanity check: rank papers vs profile.
    arr = np.asarray(embeddings, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    arr_normed = arr / np.clip(norms, 1e-8, None)
    sims = arr_normed @ centroid
    top_idx = np.argsort(-sims)[:top_k_sample]
    top_papers = [(rows[i].file_path, float(sims[i]), rows[i].source) for i in top_idx]

    # Persist (single-row upsert).
    existing = await session.get(Profile, 1)
    if existing:
        existing.embedding = centroid.tolist()
        existing.paper_count = len(rows)
        existing.weight_sum = float(sum(weights))
        existing.stats = {"per_source": per_source}
    else:
        session.add(
            Profile(
                id=1,
                embedding=centroid.tolist(),
                paper_count=len(rows),
                weight_sum=float(sum(weights)),
                stats={"per_source": per_source},
            )
        )
    await session.commit()

    return ProfileBuildResult(
        paper_count=len(rows),
        weight_sum=float(sum(weights)),
        per_source=per_source,
        top_papers=top_papers,
    )


# Reference value so callers (and tests) can confirm centroid dimensions match
# the schema without importing the SQLAlchemy model directly.
PROFILE_DIM = EMBEDDING_DIM
