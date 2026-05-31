from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3].parent / ".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")

    database_url: str = Field(
        default="postgresql+asyncpg://photonfeed:photonfeed@localhost:5432/photonfeed",
        alias="DATABASE_URL",
    )
    grobid_url: str = Field(default="http://localhost:8070", alias="GROBID_URL")

    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")

    own_papers_dir: Path | None = Field(default=None, alias="PHOTONFEED_OWN_PAPERS_DIR")
    library_dirs: str = Field(default="", alias="PHOTONFEED_LIBRARY_DIRS")

    @property
    def library_paths(self) -> list[Path]:
        return [Path(p.strip()) for p in self.library_dirs.split(",") if p.strip()]


settings = Settings()
