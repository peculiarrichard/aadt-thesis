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

    # Shared secret the intake tooling presents to the ingestion API (see
    # backend/src/backend/api/auth.py). A single shared key, not per-clinician,
    # because Layer 8 (console, with real per-clinician login) doesn't exist yet
    # — see docs/security_review.md. The default is dev-only; set a real value in
    # .env before this is ever reachable from outside localhost.
    ingestion_api_key: str = "dev-only-change-me"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
