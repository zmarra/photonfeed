import uuid
from datetime import datetime
from typing import Final

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
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
