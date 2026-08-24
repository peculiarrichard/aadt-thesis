"""The three disposition classes referenced throughout Section 10's evaluation
design (concordance, Cohen's kappa, severity-weighted error matrix), which the
solution design never names explicitly.

Not a database enum: `consultations.doctor_disposition` and
`interaction_log.draft_disposition`/`final_disposition` (Section 7) are free-text
columns, but their value is expected to be one of these three canonical strings.

Ordered by severity (ascending) so an under-triage error — predicting a lower
index than the true disposition — is easy to detect: `predicted_index < true_index`.
"""

import enum


class DispositionClass(enum.StrEnum):
    MANAGE_AT_PRIMARY_CARE = "manage_at_primary_care"
    REFER_ROUTINE = "refer_routine"
    REFER_URGENT_EMERGENCY = "refer_urgent_emergency"


DISPOSITION_SEVERITY_ORDER = [
    DispositionClass.MANAGE_AT_PRIMARY_CARE,
    DispositionClass.REFER_ROUTINE,
    DispositionClass.REFER_URGENT_EMERGENCY,
]
