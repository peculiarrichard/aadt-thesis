from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV, extra="ignore")

    postgres_user: str = "addt"
    postgres_password: str = "addt_dev_password"
    postgres_db: str = "addt"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Shared service key (backend/api/auth.py), dev-only default -- see docs/security_review.md.
    ingestion_api_key: str = "dev-only-change-me"

    # Below this, the agent escalates rather than returning a disposition (Section 9).
    confidence_threshold: float = 0.5

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
