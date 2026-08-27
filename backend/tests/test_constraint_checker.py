import pytest
import yaml

from backend.constraints.checker import (
    ConstraintRule,
    check_constraints,
    load_rules,
)
from backend.disposition import DispositionClass
from backend.fixtures.loader import load_synthetic_cases


def _case_text(case) -> str:
    return f"{case.presenting_complaint} {case.history} {case.examination_findings}"


def _write_rules(tmp_path, rules: list[dict]):
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(rules), encoding="utf-8")
    return path


# --- rule set loading/validation -------------------------------------------------


def test_default_rules_load_without_error():
    rules = load_rules()
    assert len(rules) >= 1
    assert all(isinstance(rule, ConstraintRule) for rule in rules)


def test_load_rules_rejects_duplicate_rule_id(tmp_path):
    path = _write_rules(
        tmp_path,
        [
            {
                "rule_id": "RF-DUP",
                "description": "a",
                "source_condition": "X",
                "source_document": "nigeria_stg",
                "minimum_disposition": "refer_urgent_emergency",
                "trigger_clauses": [["flag"]],
            },
            {
                "rule_id": "RF-DUP",
                "description": "b",
                "source_condition": "Y",
                "source_document": "nigeria_stg",
                "minimum_disposition": "refer_urgent_emergency",
                "trigger_clauses": [["flag"]],
            },
        ],
    )

    with pytest.raises(ValueError, match="unique"):
        load_rules(path)


def test_load_rules_rejects_unknown_minimum_disposition(tmp_path):
    path = _write_rules(
        tmp_path,
        [
            {
                "rule_id": "RF-BAD",
                "description": "a",
                "source_condition": "X",
                "source_document": "nigeria_stg",
                "minimum_disposition": "not_a_real_class",
                "trigger_clauses": [["flag"]],
            }
        ],
    )

    with pytest.raises(ValueError, match="invalid minimum_disposition"):
        load_rules(path)


def test_load_rules_rejects_keyword_rule_with_no_clauses(tmp_path):
    path = _write_rules(
        tmp_path,
        [
            {
                "rule_id": "RF-EMPTY",
                "description": "a",
                "source_condition": "X",
                "source_document": "nigeria_stg",
                "minimum_disposition": "refer_urgent_emergency",
            }
        ],
    )

    with pytest.raises(ValueError, match="trigger_clauses"):
        load_rules(path)


def test_load_rules_rejects_empty_rule_set(tmp_path):
    path = _write_rules(tmp_path, [])

    with pytest.raises(ValueError, match="empty"):
        load_rules(path)


# --- isolated red-flag trip tests -------------------------------------------------


def test_severe_malaria_danger_sign_trips_red_flag():
    text = "Fever and impaired consciousness noted on review."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert result.escalation_required
    assert any(v.rule_id == "RF-001" for v in result.violations)


def test_uncomplicated_malaria_does_not_trip_red_flag():
    text = "Fever and headache. No pallor, no jaundice, no neck stiffness. RDT positive."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert result.passed
    assert result.violations == []


def test_eclampsia_signs_trip_red_flag_in_pregnancy():
    text = "34 weeks pregnant, witnessed generalised seizure, heavy proteinuria on urinalysis."
    result = check_constraints(text, DispositionClass.REFER_ROUTINE)

    assert not result.passed
    assert any(v.rule_id == "RF-002" for v in result.violations)


def test_seizure_without_pregnancy_context_does_not_trip_eclampsia_rule():
    text = "Known epileptic presents with a witnessed generalised seizure."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert all(v.rule_id != "RF-002" for v in result.violations)


def test_acute_mi_signs_trip_red_flag():
    text = "Crushing central chest pain; ECG shows ST-segment elevation in the anterior leads."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert any(v.rule_id == "RF-003" for v in result.violations)


def test_hypertensive_emergency_signs_trip_red_flag():
    text = "Severe headache, blurred vision, and confusion. Fundoscopy shows papilloedema."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert any(v.rule_id == "RF-004" for v in result.violations)


def test_blood_pressure_threshold_trips_red_flag():
    text = "Patient is alert and comfortable. BP 224/130."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert any(v.rule_id == "RF-005" for v in result.violations)


def test_normal_blood_pressure_does_not_trip_red_flag():
    text = "BP 148/94 on this visit, 150/92 one week prior."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert all(v.rule_id != "RF-005" for v in result.violations)


def test_tetanus_signs_trip_red_flag():
    text = "Trismus present, neck rigidity, generalised muscle spasms following a puncture wound."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert any(v.rule_id == "RF-006" for v in result.violations)


def test_testicular_torsion_signs_trip_red_flag():
    text = "Sudden severe scrotal pain. Left testis high-riding with absent cremasteric reflex."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert not result.passed
    assert any(v.rule_id == "RF-007" for v in result.violations)


def test_violation_not_raised_when_draft_already_meets_minimum():
    text = "Trismus present, neck rigidity, generalised muscle spasms."
    result = check_constraints(text, DispositionClass.REFER_URGENT_EMERGENCY)

    assert result.passed
    assert result.violations == []


def test_negation_guard_prevents_false_positive():
    text = "Patient denies chest pain and has no ST elevation on ECG."
    result = check_constraints(text, DispositionClass.MANAGE_AT_PRIMARY_CARE)

    assert all(v.rule_id != "RF-003" for v in result.violations)


# --- against the real synthetic case set ------------------------------------------


def test_all_synthetic_cases_pass_against_their_own_doctor_disposition():
    """No red flag should trip when the checker is run with the disposition the
    doctor actually gave -- a false positive here would mean a rule is too broad."""
    for case in load_synthetic_cases():
        result = check_constraints(_case_text(case), case.doctor_disposition)
        assert result.passed, f"{case.case_id} unexpectedly failed: {result.violations}"


def test_emergency_cases_trip_red_flag_when_under_triaged():
    """Every refer_urgent_emergency case should be caught if a draft under-triages it
    down to manage_at_primary_care."""
    emergency_cases = [
        case
        for case in load_synthetic_cases()
        if case.doctor_disposition == DispositionClass.REFER_URGENT_EMERGENCY
    ]
    assert len(emergency_cases) == 5

    for case in emergency_cases:
        result = check_constraints(_case_text(case), DispositionClass.MANAGE_AT_PRIMARY_CARE)
        assert not result.passed, f"{case.case_id} should have tripped a red flag"
