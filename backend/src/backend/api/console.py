"""HTTP surface for the console (Layer 8, Section 5.8), authenticated via the
logged-in clinician's session (api.google_auth.require_console_session) -- not
the shared service API key, which is for server-to-server ingestion only.

Scope boundary: exposes cases and already-computed LOOCV results (read-only).
Recording a live clinician_action (approve/correct/escalate) on a review-queue
item needs its own design once real practice starts generating pending drafts
to review -- the LOOCV results here are retrospective, already-dispositioned
held-out predictions (Section 4), not a live queue.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.agents.twin_agent import ALL_CONFIGS
from backend.api.deps import ClinicianIdDep, SessionDep
from backend.evaluation.loocv import load_results_from_log
from backend.evaluation.metrics import EvaluationSummary
from backend.services import ai_ml_service, data_services

router = APIRouter(prefix="/console", tags=["console"])

# guideline_plus_precedent, not full_system, is the default for this *live*,
# click-driven endpoint: it's deterministic (no LLM call), so browsing cases
# can't trigger the same memory-heavy inference path the batch LOOCV run
# needs. The LLM-based configs (guideline_plus_persona, full_system) are
# reachable via ?config=... for whenever that's safe to run.
_DEFAULT_LIVE_CONFIG_LABEL = "guideline_plus_precedent"
_CONFIGS_BY_LABEL = {config.label: config for config in ALL_CONFIGS}


class CaseSummary(BaseModel):
    case_id: str
    external_case_ref: str | None
    presenting_summary: str
    doctor_disposition: str | None
    source_type: str


class PerClassSummary(BaseModel):
    disposition: str
    support: int
    correct: int
    accuracy: float


class ConfigSummary(BaseModel):
    config_label: str
    n: int
    concordance: float
    kappa: float
    mean_severity_weighted_error: float
    per_class: list[PerClassSummary]


class ExplanationSummary(BaseModel):
    matched_conditions: list[str]
    guideline_evidence: list[str]
    constraint_rules_triggered: list[str]
    reasoning_summary: str


class CaseResult(BaseModel):
    config_label: str
    draft_disposition: str
    disposition: str | None
    confidence: float
    escalated: bool
    escalation_reasons: list[str]
    precedent_case_refs: list[str]
    explanation: ExplanationSummary


def _to_config_summary(summary: EvaluationSummary) -> ConfigSummary:
    return ConfigSummary(
        config_label=summary.config_label,
        n=summary.n,
        concordance=summary.concordance,
        kappa=summary.kappa,
        mean_severity_weighted_error=summary.mean_severity_weighted_error,
        per_class=[
            PerClassSummary(
                disposition=pc.disposition.value,
                support=pc.support,
                correct=pc.correct,
                accuracy=pc.accuracy,
            )
            for pc in summary.per_class
        ],
    )


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(clinician_id: ClinicianIdDep, session: SessionDep) -> list[CaseSummary]:
    cases = data_services.list_cases(session, clinician_id)
    return [
        CaseSummary(
            case_id=str(case.case_id),
            external_case_ref=case.external_case_ref,
            presenting_summary=case.transcript_or_summary,
            doctor_disposition=case.doctor_disposition,
            source_type=case.source_type.value,
        )
        for case in cases
    ]


@router.get("/cases/{case_id}/result", response_model=CaseResult)
def get_case_result(
    case_id: uuid.UUID,
    clinician_id: ClinicianIdDep,
    session: SessionDep,
    config: str = Query(default=_DEFAULT_LIVE_CONFIG_LABEL),
) -> CaseResult:
    """Runs the twin agent live against one case (Section 5.6.5's perceive ->
    reason -> act, now against real Case data) -- not a replay of a past LOOCV
    row, a fresh call every time this is requested."""
    agent_config = _CONFIGS_BY_LABEL.get(config)
    if agent_config is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown config '{config}', expected one of {sorted(_CONFIGS_BY_LABEL)}",
        )

    case = data_services.get_case(session, clinician_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    output = ai_ml_service.propose_disposition_for_case(session, clinician_id, case, agent_config)

    # Section 9: an escalated draft is never shown as a normal disposition output.
    disposition = None if output.escalated else output.disposition.value

    return CaseResult(
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


@router.get("/results", response_model=list[ConfigSummary])
def get_results(clinician_id: ClinicianIdDep, session: SessionDep) -> list[ConfigSummary]:
    """The LOOCV comparison (Section 10's central experiment + ablations), read
    from already-logged interaction_log rows -- does not trigger a new (slow,
    LLM-calling) evaluation run. Run `python -m backend.evaluation.loocv`
    separately to (re)populate it."""
    results = load_results_from_log(session, clinician_id)
    return [_to_config_summary(summary) for summary in results.values()]
