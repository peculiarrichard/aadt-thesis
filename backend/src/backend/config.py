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

    # Shared service key (backend/api/auth.py), dev-only default.
    ingestion_api_key: str = "dev-only-change-me"

    # Below this, the agent escalates rather than returning a disposition (Section 9).
    confidence_threshold: float = 0.5

    # LLM inference (Section 8): any OpenAI-compatible server. Dev default points at
    # local Ollama; swap to a vLLM+AWQ endpoint for prod by changing these three env
    # vars only. No code change either way.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.1:8b"
    llm_api_key: str = "ollama"  # Ollama ignores this; the client library requires some string.

    # Google OAuth for per-clinician console login.
    # Empty by default -- login is unusable until these are set.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    session_secret_key: str = "dev-only-change-me"

    # Where the console frontend actually lives -- used both as the OAuth
    # callback's post-login redirect target and as the CORS-allowed origin for
    # its session-cookie-aware fetch calls (api.ts). These must be the frontend's
    # real, single origin: `vite.config.ts` sets `strictPort: true` specifically
    # so the dev server fails loudly instead of silently drifting to a different
    # port when 5173 is taken, which would otherwise break login in a confusing
    # way (redirect lands on the wrong origin; CORS silently blocks the session
    # check).
    frontend_url: str = "http://localhost:5173"

    # The walkthrough-imported clinician row (db/import_walkthrough_cases.py) is
    # created before she ever logs in, with no google_sub. Set this to her real
    # Google account email so her first login claims that existing row (and its
    # real cases) instead of creating an unrelated, case-less one -- see
    # api/google_auth.py's callback. Empty by default: unset until you have it.
    walkthrough_clinician_email: str = ""

    # Phase J: a single, system-wide gate on any real-patient-related action
    # (recording a live consultation, uploading a de-identified case) --
    # deliberately NOT per-clinician and NOT exposed in any UI. This has to
    # already be true (your university's IRB/ethics approval exists) before
    # any doctor-level consent screen can unlock anything patient-related; a
    # doctor's own consent is necessary but never sufficient on its own.
    institutional_ethics_clearance_granted: bool = False

    # Phase N: minimum qualifying cases (walkthrough, elicitation, or
    # de-identified real-consultation) before a clinician can build her twin --
    # intentionally a variable, not a constant, so it's easy to change.
    min_cases_to_build_twin: int = 20

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
