from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(title="ADDT Backend")
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret_key)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
