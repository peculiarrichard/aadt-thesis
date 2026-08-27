"""Loads and validates the synthetic case set (Section 11 Phase 1). Claude-drafted,
not yet clinician-reviewed -- see docs/build_plan.md task 5."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.disposition import DispositionClass

_MIN_CASES = 10
_MAX_CASES = 20
_REQUIRED_TEXT_FIELDS = (
    "presenting_complaint",
    "history",
    "examination_findings",
    "doctor_reasoning_notes",
)
DEFAULT_PATH = Path(__file__).parent / "synthetic_cases.yaml"


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    presenting_complaint: str
    history: str
    examination_findings: str
    doctor_disposition: DispositionClass
    doctor_reasoning_notes: str
    related_guideline_conditions: list[str]


def load_synthetic_cases(path: Path = DEFAULT_PATH) -> list[SyntheticCase]:
    """Parse and validate the case set. Raises ValueError on any schema violation
    (unknown disposition, empty required field, duplicate case_id, missing
    disposition class coverage, or a case count outside 10-20) rather than
    returning a partially-valid result."""
    raw_cases = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = [_parse_case(raw) for raw in raw_cases]
    _validate_case_set(cases)
    return cases


def _parse_case(raw: dict[str, Any]) -> SyntheticCase:
    case_id = raw["case_id"]
    try:
        disposition = DispositionClass(raw["doctor_disposition"])
    except ValueError as exc:
        raise ValueError(
            f"case {case_id}: invalid doctor_disposition {raw['doctor_disposition']!r}, "
            f"expected one of {[d.value for d in DispositionClass]}"
        ) from exc

    return SyntheticCase(
        case_id=case_id,
        presenting_complaint=raw["presenting_complaint"],
        history=raw["history"],
        examination_findings=raw["examination_findings"],
        doctor_disposition=disposition,
        doctor_reasoning_notes=raw["doctor_reasoning_notes"],
        related_guideline_conditions=raw.get("related_guideline_conditions", []),
    )


def _validate_case_set(cases: list[SyntheticCase]) -> None:
    if not (_MIN_CASES <= len(cases) <= _MAX_CASES):
        raise ValueError(f"expected {_MIN_CASES}-{_MAX_CASES} cases, got {len(cases)}")

    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case_id values must be unique")

    represented = {case.doctor_disposition for case in cases}
    missing = set(DispositionClass) - represented
    if missing:
        raise ValueError(f"disposition classes with no cases: {sorted(missing)}")

    for case in cases:
        for field_name in _REQUIRED_TEXT_FIELDS:
            if not getattr(case, field_name).strip():
                raise ValueError(f"case {case.case_id}: {field_name} is empty")
