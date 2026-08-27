"""Shared service-to-service API key auth, not per-clinician login (still missing
— docs/security_review.md item 1)."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from backend.config import get_settings

API_KEY_HEADER = "X-Service-Api-Key"


def require_service_api_key(
    x_service_api_key: Annotated[str | None, Header()] = None,
) -> None:
    if x_service_api_key != get_settings().ingestion_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid service API key")


RequireServiceApiKey = Annotated[None, Depends(require_service_api_key)]
