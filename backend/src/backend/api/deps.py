"""Shared FastAPI dependency aliases for console-facing routes (authenticated
via the logged-in clinician's session, not the shared service API key)."""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.api.google_auth import require_console_session
from backend.db.session import get_session

ClinicianIdDep = Annotated[uuid.UUID, Depends(require_console_session)]
SessionDep = Annotated[Session, Depends(get_session)]
