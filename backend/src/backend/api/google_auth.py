"""Per-clinician console login via Google OAuth -- the console previously had
no way to authenticate which clinician a browser tab belonged to; api/auth.py's
shared service key only proves "trusted intake tooling," never a specific
person. Session state lives in a signed cookie
(Starlette's SessionMiddleware, added in main.py), not a database table -- the
`clinicians` row is the durable identity, the cookie just carries which one is
currently logged in.

Signing in with Google authenticates identity. It does not, by itself, grant
consent for clinical-data use -- a new clinician created here starts with
consent_status="pending" (Section 5.6.2's separate consent-status scoping still
applies to every data service call).
"""

import secrets
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.models import Clinician
from backend.db.session import get_session

router = APIRouter(prefix="/auth/google", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]

_GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_SCOPES = "openid email profile"


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured (GOOGLE_OAUTH_CLIENT_ID unset)",
        )

    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state

    params = httpx.QueryParams(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return RedirectResponse(f"{_GOOGLE_AUTH_ENDPOINT}?{params}")


@router.get("/callback")
def callback(request: Request, code: str, state: str, session: SessionDep) -> RedirectResponse:
    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="invalid or missing OAuth state")

    settings = get_settings()
    token_response = httpx.post(
        _GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10.0,
    )
    if token_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Google token exchange failed")

    raw_id_token = token_response.json().get("id_token")
    if not raw_id_token:
        raise HTTPException(status_code=502, detail="Google response had no id_token")

    claims = id_token.verify_oauth2_token(
        raw_id_token, google_requests.Request(), settings.google_oauth_client_id
    )

    google_sub = claims["sub"]
    email = claims.get("email")
    name = claims.get("name") or email or "Unnamed clinician"

    clinician = session.execute(
        select(Clinician).where(Clinician.google_sub == google_sub)
    ).scalar_one_or_none()

    if clinician is None and email:
        # A clinician row can exist before its owner ever logs in (e.g. the
        # walkthrough-imported doctor, db/import_walkthrough_cases.py) --
        # claim it by email rather than creating a second, case-less row.
        unclaimed = session.execute(
            select(Clinician).where(Clinician.email == email, Clinician.google_sub.is_(None))
        ).scalar_one_or_none()
        if unclaimed is not None:
            unclaimed.google_sub = google_sub
            clinician = unclaimed
            session.commit()

    if clinician is None:
        clinician = Clinician(
            name=name, email=email, google_sub=google_sub, consent_status="pending"
        )
        session.add(clinician)
        session.commit()

    request.session["clinician_id"] = str(clinician.clinician_id)
    return RedirectResponse(settings.frontend_url)


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"logged_out": True}


@router.get("/me")
def me(request: Request, session: SessionDep) -> dict[str, str]:
    clinician_id = _require_session_clinician(request)
    clinician = session.get(Clinician, uuid.UUID(clinician_id))
    if clinician is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="session clinician no longer exists")
    return {
        "clinician_id": str(clinician.clinician_id),
        "name": clinician.name,
        "email": clinician.email or "",
        "consent_status": clinician.consent_status,
    }


def _require_session_clinician(request: Request) -> str:
    clinician_id = request.session.get("clinician_id")
    if not clinician_id:
        raise HTTPException(status_code=401, detail="not logged in")
    return clinician_id


def require_console_session(request: Request) -> uuid.UUID:
    """FastAPI dependency for console-facing routes: the logged-in clinician's ID,
    or 401. Use this (not api.auth.require_service_api_key) for anything a
    browser tab calls directly."""
    return uuid.UUID(_require_session_clinician(request))
