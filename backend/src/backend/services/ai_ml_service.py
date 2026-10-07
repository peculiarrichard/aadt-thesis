"""Layer 6.3 AI/ML services (Section 5.6.3).

`propose_disposition` (the original Section 6.2 three-field shape: presenting
complaint/history/examination findings, wrapping the guideline-only baseline
agent) predates the walkthrough-case data model and is now orphaned -- nothing
in this codebase calls it except its own tests and `cognitive_services.py`,
which nothing else calls either. Left in place, not deleted, since it's still
correct for that shape of input; not wired to anything real. Still open: delete
it, or migrate `cognitive_services.py` onto `twin_agent.py` properly.

`propose_disposition_for_case` is the real path: wraps `agents.twin_agent`
(retrieval-augmented persona conditioning, Section 5.4) against a real `Case`
row instead of three free-text fields.
"""

import uuid

from sqlalchemy.orm import Session

from backend.agents.baseline_agent import AgentOutput, run_baseline_agent
from backend.agents.twin_agent import AgentConfig, run_twin_agent
from backend.agents.twin_agent import AgentOutput as TwinAgentOutput
from backend.db.models import Case
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


def propose_disposition_for_case(
    session: Session,
    clinician_id: uuid.UUID,
    case: Case,
    config: AgentConfig,
) -> TwinAgentOutput:
    """Excludes the case from its own precedent pool -- a case retrieving itself
    as a worked example would trivially "solve" itself, the same hygiene the
    LOOCV harness applies per fold."""
    Connector(session, clinician_id).authorize()
    return run_twin_agent(
        session,
        clinician_id,
        case.transcript_or_summary,
        config,
        exclude_case_id=case.case_id,
    )
