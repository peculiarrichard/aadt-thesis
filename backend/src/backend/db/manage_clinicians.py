"""Admin-only clinician management (Phase I): create or look up a clinician
from the backend. Replaces the one-off WALKTHROUGH_CLINICIAN_NAME/_EMAIL
pattern as the general "add a doctor" mechanism -- used for the pilot doctor
too, not a special case for her alone. CLI only, no admin UI, no public
signup: the user adds clinicians themselves from a terminal.
"""

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Clinician
from backend.db.session import SessionLocal


def create_or_get_clinician(
    session: Session,
    name: str,
    email: str,
    consent_status: str = "granted",
    specialty: str | None = None,
) -> Clinician:
    """Idempotent by email -- find-or-create. consent_status defaults to
    "granted" since this is an admin-initiated action (the person running
    this already decided to onboard this doctor), unlike a self-service
    Google login, which starts "pending" (api/google_auth.py)."""
    existing = session.execute(
        select(Clinician).where(Clinician.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    clinician = Clinician(
        name=name, email=email, consent_status=consent_status, specialty=specialty
    )
    session.add(clinician)
    session.commit()
    return clinician


def _main() -> None:
    parser = argparse.ArgumentParser(description="Create or look up a clinician by email.")
    parser.add_argument("name")
    parser.add_argument("email")
    parser.add_argument("--consent-status", default="granted")
    parser.add_argument("--specialty", default=None)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        clinician = create_or_get_clinician(
            session, args.name, args.email, args.consent_status, args.specialty
        )
        print(f"Clinician: {clinician.clinician_id} ({clinician.name}, {clinician.email})")
    finally:
        session.close()


if __name__ == "__main__":
    _main()
