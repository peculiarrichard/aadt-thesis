"""Leave-one-out cross-validation harness (Section 10): for each walkthrough
case, exclude it from the precedent pool, run every agent configuration, and
compare against the doctor's actual disposition for that case. n cases x 4
configs = 4n logged interactions (currently 34 cases, 136 interactions), each
an independent prediction from a twin that never saw the case it's being
tested on. The fold count tracks the dataset size automatically -- nothing
here hardcodes it.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents.twin_agent import ALL_CONFIGS, AgentConfig, run_twin_agent
from backend.db.enums import Mode
from backend.db.import_walkthrough_cases import WALKTHROUGH_CLINICIAN_NAME
from backend.db.models import Case, Clinician, InteractionLog
from backend.db.session import SessionLocal
from backend.disposition import DispositionClass
from backend.evaluation.metrics import EvaluationSummary, summarize
from backend.services import data_services


def _load_walkthrough_cases(session: Session) -> tuple[Clinician, list[Case]]:
    clinician = session.execute(
        select(Clinician).where(Clinician.name == WALKTHROUGH_CLINICIAN_NAME)
    ).scalar_one()
    cases = list(
        session.execute(select(Case).where(Case.clinician_id == clinician.clinician_id))
        .scalars()
        .all()
    )
    return clinician, cases


def run_loocv(
    session: Session | None = None,
    configs: tuple[AgentConfig, ...] = ALL_CONFIGS,
) -> dict[str, EvaluationSummary]:
    owns_session = session is None
    session = session or SessionLocal()
    try:
        clinician, cases = _load_walkthrough_cases(session)
        predictions_by_config: dict[str, list[DispositionClass]] = {c.label: [] for c in configs}
        actuals_by_config: dict[str, list[DispositionClass]] = {c.label: [] for c in configs}

        for held_out in cases:
            actual = DispositionClass(held_out.doctor_disposition)
            for config in configs:
                output = run_twin_agent(
                    session,
                    clinician.clinician_id,
                    held_out.transcript_or_summary,
                    config,
                    exclude_case_id=held_out.case_id,
                )
                predictions_by_config[config.label].append(output.disposition)
                actuals_by_config[config.label].append(actual)

                data_services.create_interaction_log_entry(
                    session,
                    clinician.clinician_id,
                    mode=Mode.CONSULTING_SANDBOX,
                    input_case_ref=held_out.external_case_ref or str(held_out.case_id),
                    draft_disposition=output.draft_disposition.value,
                    final_disposition=output.disposition.value,
                    confidence_score=output.confidence,
                    escalated=output.escalated,
                    model_version=config.label,
                )

        return {
            label: summarize(label, predictions_by_config[label], actuals_by_config[label])
            for label in predictions_by_config
        }
    finally:
        if owns_session:
            session.close()


def load_results_from_log(
    session: Session, clinician_id: uuid.UUID
) -> dict[str, EvaluationSummary]:
    """Reconstructs summaries from already-logged interaction_log rows (mode=
    consulting_sandbox), without re-running any LLM calls. What the console's
    results view reads -- run_loocv() is the slow, LLM-calling batch job that
    populates this; this function is the fast read path."""
    cases_by_ref: dict[str, Case] = {}
    for case in session.execute(select(Case).where(Case.clinician_id == clinician_id)).scalars():
        ref = case.external_case_ref or str(case.case_id)
        cases_by_ref[ref] = case

    entries = (
        session.execute(
            select(InteractionLog)
            .where(
                InteractionLog.clinician_id == clinician_id,
                InteractionLog.mode == Mode.CONSULTING_SANDBOX,
            )
            .order_by(InteractionLog.created_at)
        )
        .scalars()
        .all()
    )

    # InteractionLog rows are append-only (never overwritten), so a re-run of the
    # LOOCV batch leaves the previous run's rows in place alongside the new ones.
    # Keep only the most recent row per (config, case) pair -- ordering by
    # created_at above and overwriting on each visit means the last write wins.
    latest_by_key: dict[tuple[str, str], InteractionLog] = {}
    for entry in entries:
        if entry.input_case_ref not in cases_by_ref:
            continue
        if entry.final_disposition is None or entry.model_version is None:
            continue
        latest_by_key[(entry.model_version, entry.input_case_ref)] = entry

    predictions_by_config: dict[str, list[DispositionClass]] = {}
    actuals_by_config: dict[str, list[DispositionClass]] = {}
    for (label, case_ref), entry in latest_by_key.items():
        case = cases_by_ref[case_ref]
        predictions_by_config.setdefault(label, []).append(
            DispositionClass(entry.final_disposition)
        )
        actuals_by_config.setdefault(label, []).append(DispositionClass(case.doctor_disposition))

    return {
        label: summarize(label, predictions_by_config[label], actuals_by_config[label])
        for label in predictions_by_config
    }


def print_summary(results: dict[str, EvaluationSummary]) -> None:
    for label, summary in results.items():
        print(f"\n=== {label} (n={summary.n}) ===")
        print(f"Concordance: {summary.concordance:.2%}")
        print(f"Cohen's kappa: {summary.kappa:.3f}")
        print(f"Mean severity-weighted error: {summary.mean_severity_weighted_error:.3f}")
        for per_class in summary.per_class:
            print(
                f"  {per_class.disposition.value}: {per_class.correct}/{per_class.support} "
                f"({per_class.accuracy:.2%})"
            )


if __name__ == "__main__":
    print_summary(run_loocv())
