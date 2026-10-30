"""Email+password sign-in for simulated patients (further work, outside the
thesis's evaluated methodology) -- a separate identity space from Clinician,
which uses Google OAuth (api/google_auth.py). Session state lives in the same
signed cookie (Starlette's SessionMiddleware, main.py), under a different
session-dict key ("patient_id") so a clinician session and a patient session
never collide.
"""

import uuid
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Patient
from backend.db.session import get_session

router = APIRouter(prefix="/auth/patient", tags=["patient-auth"])

SessionDep = Annotated[Session, Depends(get_session)]


class SignupRequest(BaseModel):
    email: str
    password: str
    username: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PatientMe(BaseModel):
    patient_id: str
    email: str
    username: str


@router.post("/signup", response_model=PatientMe)
def signup(body: SignupRequest, request: Request, session: SessionDep) -> PatientMe:
    if session.execute(select(Patient).where(Patient.email == body.email)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="an account with this email already exists")
    if session.execute(
        select(Patient).where(Patient.username == body.username)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="that username is taken")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    patient = Patient(email=body.email, password_hash=password_hash, username=body.username)
    session.add(patient)
    session.commit()

    request.session["patient_id"] = str(patient.patient_id)
    return PatientMe(
        patient_id=str(patient.patient_id), email=patient.email, username=patient.username
    )


@router.post("/login", response_model=PatientMe)
def login(body: LoginRequest, request: Request, session: SessionDep) -> PatientMe:
    patient = session.execute(
        select(Patient).where(Patient.email == body.email)
    ).scalar_one_or_none()
    if patient is None or not bcrypt.checkpw(
        body.password.encode(), patient.password_hash.encode()
    ):
        raise HTTPException(status_code=401, detail="invalid email or password")

    request.session["patient_id"] = str(patient.patient_id)
    return PatientMe(
        patient_id=str(patient.patient_id), email=patient.email, username=patient.username
    )


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.pop("patient_id", None)
    return {"logged_out": True}


@router.get("/me", response_model=PatientMe)
def me(request: Request, session: SessionDep) -> PatientMe:
    patient_id = _require_session_patient(request)
    patient = session.get(Patient, uuid.UUID(patient_id))
    if patient is None:
        request.session.pop("patient_id", None)
        raise HTTPException(status_code=401, detail="session patient no longer exists")
    return PatientMe(
        patient_id=str(patient.patient_id), email=patient.email, username=patient.username
    )


def _require_session_patient(request: Request) -> str:
    patient_id = request.session.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=401, detail="not logged in")
    return patient_id


def require_patient_session(request: Request) -> uuid.UUID:
    """FastAPI dependency for patient-facing routes (mirrors
    google_auth.require_console_session for clinicians)."""
    return uuid.UUID(_require_session_patient(request))
