from backend.disposition import DispositionClass
from backend.fixtures.loader import load_synthetic_cases


def test_loads_between_ten_and_twenty_cases():
    cases = load_synthetic_cases()

    assert 10 <= len(cases) <= 20


def test_all_three_disposition_classes_are_represented():
    cases = load_synthetic_cases()

    represented = {case.doctor_disposition for case in cases}

    assert represented == set(DispositionClass)


def test_case_ids_are_unique():
    cases = load_synthetic_cases()

    ids = [case.case_id for case in cases]

    assert len(ids) == len(set(ids))


def test_required_text_fields_are_non_empty():
    cases = load_synthetic_cases()

    for case in cases:
        assert case.presenting_complaint.strip()
        assert case.history.strip()
        assert case.examination_findings.strip()
        assert case.doctor_reasoning_notes.strip()
