"""Evaluation metrics (Section 10): disposition concordance, Cohen's kappa, and a
severity-weighted error view. Per-class breakdown is required, not optional --
with a heavily imbalanced disposition distribution (currently 3/7/24), a single
accuracy figure would hide weakness on the rarer classes.
"""

from collections import Counter
from dataclasses import dataclass

from backend.disposition import DISPOSITION_SEVERITY_ORDER, DispositionClass

# Lookup table, not hardcoded conditionals (Section 10). Weight grows with how many
# severity steps the error crosses; at equal distance, under-triage (predicted less
# severe than actual) is weighted heavier than over-triage, since under-triage is
# the clinically dangerous direction.
UNDER_TRIAGE_STEP_WEIGHT = 2.0
OVER_TRIAGE_STEP_WEIGHT = 1.0


def severity_weight(predicted: DispositionClass, actual: DispositionClass) -> float:
    predicted_index = DISPOSITION_SEVERITY_ORDER.index(predicted)
    actual_index = DISPOSITION_SEVERITY_ORDER.index(actual)
    steps = actual_index - predicted_index
    if steps == 0:
        return 0.0
    if steps > 0:  # predicted less severe than actual -- under-triage
        return steps * UNDER_TRIAGE_STEP_WEIGHT
    return -steps * OVER_TRIAGE_STEP_WEIGHT


def disposition_concordance(
    predictions: list[DispositionClass], actuals: list[DispositionClass]
) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for p, a in zip(predictions, actuals, strict=True) if p == a)
    return correct / len(predictions)


def cohens_kappa(predictions: list[DispositionClass], actuals: list[DispositionClass]) -> float:
    n = len(predictions)
    if n == 0:
        return 0.0
    observed_agreement = disposition_concordance(predictions, actuals)

    pred_counts = Counter(predictions)
    actual_counts = Counter(actuals)
    expected_agreement = sum(
        (pred_counts.get(cls, 0) / n) * (actual_counts.get(cls, 0) / n) for cls in DispositionClass
    )

    if expected_agreement >= 1.0:
        return 1.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


@dataclass(frozen=True)
class PerClassResult:
    disposition: DispositionClass
    support: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.support if self.support else 0.0


def per_class_breakdown(
    predictions: list[DispositionClass], actuals: list[DispositionClass]
) -> list[PerClassResult]:
    results = []
    for cls in DispositionClass:
        indices = [i for i, actual in enumerate(actuals) if actual == cls]
        support = len(indices)
        correct = sum(1 for i in indices if predictions[i] == actuals[i])
        results.append(PerClassResult(disposition=cls, support=support, correct=correct))
    return results


@dataclass(frozen=True)
class EvaluationSummary:
    config_label: str
    n: int
    concordance: float
    kappa: float
    mean_severity_weighted_error: float
    per_class: list[PerClassResult]


def summarize(
    config_label: str,
    predictions: list[DispositionClass],
    actuals: list[DispositionClass],
) -> EvaluationSummary:
    n = len(predictions)
    weights = [severity_weight(p, a) for p, a in zip(predictions, actuals, strict=True)]
    mean_weight = sum(weights) / n if n else 0.0
    return EvaluationSummary(
        config_label=config_label,
        n=n,
        concordance=disposition_concordance(predictions, actuals),
        kappa=cohens_kappa(predictions, actuals),
        mean_severity_weighted_error=mean_weight,
        per_class=per_class_breakdown(predictions, actuals),
    )
