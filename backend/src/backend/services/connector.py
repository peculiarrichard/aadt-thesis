"""Layer 6.1 Connector (Section 3.6, 5.6.1): typed, audited, policy-governed join
between two twins. Design notes: docs/build_log.md task 10."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.db.enums import AuditActor
from backend.db.models import AuditLog, Clinician

_CONSENTED_STATUS = "granted"


class ConnectorError(Exception):
    """The referenced clinician does not exist."""


class ConnectorPolicyError(Exception):
    """The clinician exists but has not granted consent."""


@dataclass(frozen=True)
class TwinRef:
    kind: str  # e.g. "AHDT", "DDT"


AHDT = TwinRef(kind="AHDT")
DDT = TwinRef(kind="DDT")


class Connector:
    """A single Connector instance joins two twins for one clinician."""

    def __init__(
        self,
        session: Session,
        clinician_id: uuid.UUID,
        source: TwinRef = AHDT,
        target: TwinRef = DDT,
    ) -> None:
        self.session = session
        self.clinician_id = clinician_id
        self.source = source
        self.target = target

    def authorize(self) -> Clinician:
        """Raises ConnectorError if unknown, ConnectorPolicyError if not consented."""
        clinician = self.session.get(Clinician, self.clinician_id)
        if clinician is None:
            raise ConnectorError(f"unknown clinician {self.clinician_id}")
        if clinician.consent_status != _CONSENTED_STATUS:
            raise ConnectorPolicyError(f"clinician {self.clinician_id} has not granted consent")
        return clinician

    def record(
        self, action: str, reference_table: str | None = None, reference_id: str | None = None
    ) -> None:
        """Does not commit -- callers own the transaction."""
        self.session.add(
            AuditLog(
                clinician_id=self.clinician_id,
                actor=AuditActor.SYSTEM,
                action=f"connector:{self.source.kind}->{self.target.kind}:{action}",
                reference_table=reference_table,
                reference_id=reference_id,
            )
        )
