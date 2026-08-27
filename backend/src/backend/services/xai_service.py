"""Layer 6.4 XAI services (Section 5.6.4): typed, audited access to the
explanation object the agent already computed."""

import uuid

from sqlalchemy.orm import Session

from backend.agents.baseline_agent import AgentOutput
from backend.agents.explanation import Explanation
from backend.services.connector import Connector


def get_explanation(
    session: Session, clinician_id: uuid.UUID, agent_output: AgentOutput
) -> Explanation:
    connector = Connector(session, clinician_id)
    connector.authorize()
    connector.record("xai_explain")
    return agent_output.explanation
