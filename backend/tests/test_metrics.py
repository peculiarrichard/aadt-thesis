from backend.disposition import DispositionClass
from backend.evaluation.metrics import (
    cohens_kappa,
    disposition_concordance,
    per_class_breakdown,
    severity_weight,
    summarize,
)

SELF_CARE = DispositionClass.SELF_CARE_ADVICE
SCHEDULED = DispositionClass.SCHEDULED_APPOINTMENT
URGENT = DispositionClass.URGENT_REFERRAL


def test_concordance_is_one_for_perfect_agreement():
    predictions = [SELF_CARE, SCHEDULED, URGENT]
    actuals = [SELF_CARE, SCHEDULED, URGENT]

    assert disposition_concordance(predictions, actuals) == 1.0


def test_concordance_is_fraction_correct():
    predictions = [SELF_CARE, SCHEDULED, URGENT, URGENT]
    actuals = [SELF_CARE, URGENT, URGENT, URGENT]

    assert disposition_concordance(predictions, actuals) == 0.75


def test_concordance_of_empty_input_is_zero():
    assert disposition_concordance([], []) == 0.0


def test_kappa_is_one_for_perfect_agreement():
    predictions = [SELF_CARE, SCHEDULED, URGENT, URGENT, URGENT]
    actuals = [SELF_CARE, SCHEDULED, URGENT, URGENT, URGENT]

    assert cohens_kappa(predictions, actuals) == 1.0


def test_kappa_is_less_than_concordance_when_chance_agreement_exists():
    # Skewed toward URGENT (matches the real 3/7/24 imbalance) -- chance agreement
    # is high, so kappa should be noticeably below raw concordance.
    actuals = [URGENT] * 24 + [SCHEDULED] * 7 + [SELF_CARE] * 3
    predictions = [URGENT] * 34  # always predicts the majority class

    concordance = disposition_concordance(predictions, actuals)
    kappa = cohens_kappa(predictions, actuals)

    assert concordance == 24 / 34
    assert kappa < concordance


def test_severity_weight_is_zero_for_exact_match():
    assert severity_weight(URGENT, URGENT) == 0.0


def test_under_triage_is_weighted_more_than_over_triage_at_equal_distance():
    under_triage = severity_weight(SELF_CARE, URGENT)  # predicted too low
    over_triage = severity_weight(URGENT, SELF_CARE)  # predicted too high

    assert under_triage > over_triage


def test_severity_weight_grows_with_distance():
    one_step_under = severity_weight(SCHEDULED, URGENT)
    two_steps_under = severity_weight(SELF_CARE, URGENT)

    assert two_steps_under > one_step_under


def test_per_class_breakdown_reports_support_and_accuracy_separately():
    predictions = [SELF_CARE, SELF_CARE, URGENT]
    actuals = [SELF_CARE, URGENT, URGENT]

    results = {r.disposition: r for r in per_class_breakdown(predictions, actuals)}

    assert results[SELF_CARE].support == 1
    assert results[SELF_CARE].correct == 1
    assert results[URGENT].support == 2
    assert results[URGENT].correct == 1
    assert results[URGENT].accuracy == 0.5
    assert results[SCHEDULED].support == 0
    assert results[SCHEDULED].accuracy == 0.0


def test_summarize_produces_a_complete_summary():
    predictions = [SELF_CARE, SCHEDULED, URGENT]
    actuals = [SELF_CARE, SCHEDULED, URGENT]

    summary = summarize("guideline_only", predictions, actuals)

    assert summary.config_label == "guideline_only"
    assert summary.n == 3
    assert summary.concordance == 1.0
    assert summary.kappa == 1.0
    assert summary.mean_severity_weighted_error == 0.0
    assert len(summary.per_class) == 3
