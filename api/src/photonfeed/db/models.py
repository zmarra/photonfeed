import uuid
from datetime import datetime
from typing import Any, Final

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Source labels for ingested papers.
SOURCE_OWN: Final = "own"
SOURCE_CITING_ME: Final = "citing_me"
SOURCE_LIBRARY: Final = "library"

# Profile weighting multipliers.
SOURCE_WEIGHTS: Final[dict[str, float]] = {
    SOURCE_OWN: 3.0,
    SOURCE_CITING_ME: 3.0,
    SOURCE_LIBRARY: 1.0,
}

# voyage-3-large embedding dimensions; null for un-embedded papers.
EMBEDDING_DIM: Final = 1024


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Candidate(Base):
    """A paper fetched from a daily source (arXiv etc.), pending triage.

    Kept separate from `papers` (the user's library): candidates are the
    incoming stream we score against the profile, not taste signal.
    """

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="arxiv")
    external_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    version: Mapped[str | None] = mapped_column(String(8), nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    primary_category: Mapped[str | None] = mapped_column(String(32), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    abs_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    triage_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Profile(Base):
    """Single-row table holding the user's weighted-centroid taste vector.

    Refactored into a per-user table when we go multi-tenant in v0.2.
    """

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_sum: Mapped[float] = mapped_column(Float, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
