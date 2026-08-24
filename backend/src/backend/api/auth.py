"""Shared service-to-service authentication for the API (docs/security_review.md,
item 1: the ingestion API previously accepted any clinician_id with no check on
who was asking).

A single shared API key, not per-clinician auth: Layer 8 (the console, with real
per-clinician login) doesn't exist yet, so there is no session/identity system to
authenticate a specific clinician against. This only proves the caller is trusted
intake tooling holding the shared secret, not which clinician is using it — the
request body's clinician_id is still just an assertion, checked against the DB
for existence (and, where relevant, consent status) but not cryptographically
tied to the caller's identity. Revisit when the console has real per-clinician
sessions.
"""

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
