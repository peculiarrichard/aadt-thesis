"""Layer 5/8: assembles a formatted doctor's report from an already-computed
AgentOutput (Section 5.5 explainability, surfaced in the application layer's
Consult Your Twin screen). Deterministic -- reuses whatever the agent already
produced (persona narrative, guideline matches, disposition, escalation),
no second LLM call. Structure (biodata, presenting complaint, history,
examination, diagnosis, plan, sign-off) follows the common shape of Nigerian
clerking/medical-report formats; no single official national template exists
publicly, so this is a representative structure, not an official standard.

Clerical entries are deliberately anonymized-only (patient_reference, age, sex
as free text, never a real name/hospital number) -- Consult Mode has no
institutional-ethics gate, unlike the real-patient recording paths, so it must
stay out of real-patient-data territory.
"""

import datetime
from dataclasses import dataclass

from backend.agents.twin_agent import AgentOutput
from backend.disposition import DispositionClass

_DISCLAIMER = (
    "This report was drafted with AI assistance (ADDT) from a text description of "
    "the case. It is not based on a physical examination and has not yet been "
    "reviewed or signed by the attending clinician. It must be reviewed, corrected "
    "if needed, and signed before it is treated as a clinical record."
)

_PLAN_TEXT = {
    DispositionClass.SELF_CARE_ADVICE: (
        "Advise self-care at home. Provide safety-net advice: return if symptoms "
        "worsen or any red-flag feature develops."
    ),
    DispositionClass.SCHEDULED_APPOINTMENT: (
        "Book a scheduled, non-urgent clinic appointment for further assessment."
    ),
    DispositionClass.URGENT_REFERRAL: (
        "Refer urgently. Do not delay pending a routine appointment slot."
    ),
}

_NO_NARRATIVE_FALLBACK = (
    "The twin could not produce a narrative assessment for this case; the "
    "conclusions below rest on guideline and precedent matching only."
)


@dataclass(frozen=True)
class ClericalDetails:
    patient_reference: str | None = None
    age: str | None = None
    sex: str | None = None
    temperature: str | None = None
    blood_pressure: str | None = None
    pulse_rate: str | None = None
    respiratory_rate: str | None = None
    oxygen_saturation: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    generated_at: datetime.datetime
    clinician_name: str
    clerical: ClericalDetails
    presenting_complaint: str
    history_and_impression: str
    guideline_considerations: list[str]
    assessment: str
    plan: str
    disclaimer: str = _DISCLAIMER


def build_doctor_report(
    clinician_name: str,
    case_text: str,
    clerical: ClericalDetails,
    output: AgentOutput,
) -> DoctorReport:
    history_and_impression = _reasoning_text(output) or _NO_NARRATIVE_FALLBACK

    if output.escalated:
        reasons = ", ".join(output.escalation_reasons) or "low confidence"
        assessment = (
            f"Escalated for clinician review -- no disposition is given automatically. "
            f"Reason(s): {reasons}."
        )
        plan = "Pending clinician review of the escalated case above."
    else:
        assessment = (
            f"Likely disposition: {_disposition_label(output.disposition)} "
            f"(twin confidence {output.confidence:.0%})."
        )
        plan = _PLAN_TEXT[output.disposition]

    return DoctorReport(
        generated_at=datetime.datetime.now(datetime.UTC),
        clinician_name=clinician_name,
        clerical=clerical,
        presenting_complaint=case_text.strip(),
        history_and_impression=history_and_impression,
        guideline_considerations=output.explanation.guideline_evidence,
        assessment=assessment,
        plan=plan,
    )


def _reasoning_text(output: AgentOutput) -> str:
    """The persona's own narrative is prefixed onto explanation.reasoning_summary
    by twin_agent (see run_twin_agent) -- split it back off so the report doesn't
    repeat the boilerplate guideline-match sentence twice."""
    summary = output.explanation.reasoning_summary
    for boilerplate in (
        "Guideline evidence found for:",
        "No matching guideline condition found in the corpus for this case;",
        "Escalated: case text tripped red flag rule(s)",
    ):
        if boilerplate in summary:
            return summary.split(boilerplate, 1)[0].strip()
    return summary.strip()


def _disposition_label(disposition: DispositionClass) -> str:
    return disposition.value.replace("_", " ")
