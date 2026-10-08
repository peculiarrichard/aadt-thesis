from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from backend.api.case_intake import router as case_intake_router
from backend.api.case_recording import router as case_recording_router
from backend.api.consent import router as consent_router
from backend.api.console import router as console_router
from backend.api.consult import router as consult_router
from backend.api.google_auth import router as google_auth_router
from backend.api.ingestion import router as ingestion_router
from backend.api.twin import router as twin_router
from backend.config import get_settings
from backend.services.connector import ConnectorError, ConnectorPolicyError

app = FastAPI(title="ADDT Backend")
# same_site="none" + https_only=True are required for the session cookie to
# survive a cross-origin fetch (e.g. frontend and backend on two different
# onrender.com subdomains) -- the default same_site="lax" is silently dropped
# on cross-site XHR/fetch, which looks exactly like "login succeeded but /me
# still says not logged in". Only safe to force when frontend_url is https --
# browsers reject SameSite=None without Secure, and Secure cookies aren't set
# over plain http (local dev), so this falls back to the old lax/non-secure
# behavior there.
_frontend_is_https = get_settings().frontend_url.startswith("https://")
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().session_secret_key,
    same_site="none" if _frontend_is_https else "lax",
    https_only=_frontend_is_https,
)
# The console (frontend_url) calls this API cross-origin with credentials:
# 'include' (api.ts) to carry the session cookie from Google login -- without
# this, the browser silently blocks that fetch and the console looks logged
# out even after a successful login. allow_credentials requires a single
# explicit origin, not "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ingestion_router)
app.include_router(google_auth_router)
app.include_router(console_router)
app.include_router(consent_router)
app.include_router(case_intake_router)
app.include_router(case_recording_router)
app.include_router(twin_router)
app.include_router(consult_router)


# Without these, an unconsented/unknown clinician hitting any data-service
# endpoint gets an opaque 500 (Connector.authorize() raises a plain Exception
# subclass, which FastAPI otherwise lets propagate unhandled) instead of a
# clean, actionable response -- e.g. a self-service login's consent_status
# defaults to "pending" until granted, which is the expected, common case,
# not a server fault.
@app.exception_handler(ConnectorPolicyError)
def _handle_connector_policy_error(request: Request, exc: ConnectorPolicyError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ConnectorError)
def _handle_connector_error(request: Request, exc: ConnectorError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
