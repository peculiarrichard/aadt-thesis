"""Phase O: ad-hoc consult (free text, not tied to an existing Case row) and
feedback on it. A CORRECTED verdict is the one path that writes a new Case
(source_type=consult_feedback) and immediately embeds it into precedent
memory -- the "corrections fold back into memory so the next consult sees
them" behavior confirmed with the user before this was planned. An APPROVED
or ESCALATED_REVIEW verdict only updates the interaction_log row; nothing new
to add to memory if she just agreed with the draft.
"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.twin_agent import FULL_SYSTEM, run_twin_agent
from backend.api.deps import ClinicianIdDep, SessionDep
from backend.db.enums import ClinicianAction, Mode, SourceType
from backend.disposition import FROM_WALKTHROUGH_LABEL
from backend.services import data_services

router = APIRouter(prefix="/console/consult", tags=["consult"])


class ExplanationSummary(BaseModel):
    matched_conditions: list[str]
    guideline_evidence: list[str]
    constraint_rules_triggered: list[str]
    reasoning_summary: str


class ConsultRequest(BaseModel):
    case_text: str


class ConsultResponse(BaseModel):
    interaction_id: str
    config_label: str
    draft_disposition: str
    disposition: str | None
    confidence: float
    escalated: bool
    escalation_reasons: list[str]
    precedent_case_refs: list[str]
    explanation: ExplanationSummary


@router.post("", response_model=ConsultResponse)
def consult_the_twin(
    body: ConsultRequest, clinician_id: ClinicianIdDep, session: SessionDep
) -> ConsultResponse:
    if not data_services.has_precedent_memory(session, clinician_id):
        raise HTTPException(
            status_code=400,
            detail="your twin hasn't been built yet -- see /console/twin/status",
        )

    output = run_twin_agent(session, clinician_id, body.case_text, FULL_SYSTEM)

    # Ad-hoc, interactive use of the full twin -- not a LOOCV batch row, but
    # the existing Mode enum has no separate value for it; CONSULTING_SANDBOX
    # is the closer fit of the two that exist (Section 4's "consulting mode").
    entry = data_services.create_interaction_log_entry(
        session,
        clinician_id,
        mode=Mode.CONSULTING_SANDBOX,
        input_case_ref=f"consult-{uuid.uuid4()}",
        draft_disposition=output.draft_disposition.value,
        final_disposition=output.disposition.value,
        confidence_score=output.confidence,
        escalated=output.escalated,
        model_version=output.config_label,
    )
    session.commit()

    disposition = None if output.escalated else output.disposition.value
    return ConsultResponse(
        interaction_id=str(entry.interaction_id),
        config_label=output.config_label,
        draft_disposition=output.draft_disposition.value,
        disposition=disposition,
        confidence=output.confidence,
        escalated=output.escalated,
        escalation_reasons=output.escalation_reasons,
        precedent_case_refs=output.precedent_case_refs,
        explanation=ExplanationSummary(
            matched_conditions=output.explanation.matched_conditions,
            guideline_evidence=output.explanation.guideline_evidence,
            constraint_rules_triggered=output.explanation.constraint_rules_triggered,
            reasoning_summary=output.explanation.reasoning_summary,
        ),
    )


class FeedbackRequest(BaseModel):
    action: ClinicianAction
    case_text: str  # resent by the client -- interaction_log doesn't store raw case text
    corrected_disposition: str | None = None  # required when action == corrected
    corrected_reasoning: str | None = None
    correction_notes: str | None = None


class FeedbackResponse(BaseModel):
    logged: bool
    new_case_id: str | None


@router.post("/{interaction_id}/feedback", response_model=FeedbackResponse)
def give_feedback(
    interaction_id: uuid.UUID,
    body: FeedbackRequest,
    clinician_id: ClinicianIdDep,
    session: SessionDep,
) -> FeedbackResponse:
    entry = data_services.get_interaction_log_entry(session, clinician_id, interaction_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="interaction not found")

    new_case_id: str | None = None

    if body.action == ClinicianAction.CORRECTED:
        valid_disposition = body.corrected_disposition in FROM_WALKTHROUGH_LABEL
        if not body.corrected_disposition or not valid_disposition:
            raise HTTPException(
                status_code=400,
                detail=f"corrected_disposition must be one of {sorted(FROM_WALKTHROUGH_LABEL)}",
            )
        disposition = FROM_WALKTHROUGH_LABEL[body.corrected_disposition]
        case = data_services.create_case(
            session,
            clinician_id,
            transcript_or_summary=body.case_text,
            source_type=SourceType.CONSULT_FEEDBACK,
            doctor_disposition=disposition.value,
            doctor_reasoning_notes=body.corrected_reasoning,
        )
        session.flush()

        from backend.db.embed_walkthrough_cases import embed_single_case

        embed_single_case(session, clinician_id, case)
        new_case_id = str(case.case_id)

    data_services.record_clinician_feedback(
        session, clinician_id, interaction_id, body.action, body.correction_notes
    )
    session.commit()

    return FeedbackResponse(logged=True, new_case_id=new_case_id)
