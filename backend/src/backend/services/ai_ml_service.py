"""Layer 6.3 AI/ML services (Section 5.6.3): thin wrapper around the baseline
agent -- persona/precedent aren't built yet (need clinician data)."""

import uuid

from sqlalchemy.orm import Session

from backend.agents.baseline_agent import AgentOutput, run_baseline_agent
from backend.services.connector import Connector


def propose_disposition(
    session: Session,
    clinician_id: uuid.UUID,
    presenting_complaint: str,
    history: str,
    examination_findings: str,
    confidence_threshold: float | None = None,
) -> AgentOutput:
    Connector(session, clinician_id).authorize()
    return run_baseline_agent(
        session, presenting_complaint, history, examination_findings, confidence_threshold
    )
