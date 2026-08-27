"""The three disposition classes (Section 10); see docs/build_log.md task 5."""

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
