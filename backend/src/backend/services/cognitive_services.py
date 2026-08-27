"""Layer 6.5 cognitive services (Section 5.6.5): perceive/reason/act, each
Connector-audited. Design notes: docs/build_log.md task 10."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.agents.baseline_agent import AgentOutput
from backend.agents.explanation import Explanation
from backend.agents.perceive import PerceivedCase
from backend.agents.perceive import perceive as _perceive
from backend.disposition import DispositionClass
from backend.services import ai_ml_service, xai_service
from backend.services.connector import Connector


@dataclass(frozen=True)
class ActResult:
    disposition: DispositionClass | None
    escalated: bool
    confidence: float
    explanation: Explanation


def perceive(
    session: Session,
    clinician_id: uuid.UUID,
    presenting_complaint: str,
    history: str,
    examination_findings: str,
) -> PerceivedCase:
    connector = Connector(session, clinician_id)
    connector.authorize()
    case = _perceive(presenting_complaint, history, examination_findings)
    connector.record("cognitive_perceive")
    return case


def reason(
    session: Session,
    clinician_id: uuid.UUID,
    perceived_case: PerceivedCase,
    confidence_threshold: float | None = None,
) -> AgentOutput:
    connector = Connector(session, clinician_id)
    connector.authorize()
    output = ai_ml_service.propose_disposition(
        session,
        clinician_id,
        perceived_case.presenting_complaint,
        perceived_case.history,
        perceived_case.examination_findings,
        confidence_threshold,
    )
    connector.record("cognitive_reason")
    return output


def act(session: Session, clinician_id: uuid.UUID, agent_output: AgentOutput) -> ActResult:
    """Withholds disposition (None) when escalated -- Section 9."""
    connector = Connector(session, clinician_id)
    connector.authorize()
    explanation = xai_service.get_explanation(session, clinician_id, agent_output)
    connector.record("cognitive_act")
    return ActResult(
        disposition=None if agent_output.escalated else agent_output.disposition,
        escalated=agent_output.escalated,
        confidence=agent_output.confidence,
        explanation=explanation,
    )


def run_consultation(
    session: Session,
    clinician_id: uuid.UUID,
    presenting_complaint: str,
    history: str,
    examination_findings: str,
    confidence_threshold: float | None = None,
) -> ActResult:
    """perceive -> reason -> act, composed."""
    perceived = perceive(session, clinician_id, presenting_complaint, history, examination_findings)
    output = reason(session, clinician_id, perceived, confidence_threshold)
    return act(session, clinician_id, output)
