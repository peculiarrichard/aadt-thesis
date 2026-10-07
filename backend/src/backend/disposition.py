"""The three disposition classes used throughout the twin (Section 10). Named to
match the real walkthrough data's own labels exactly
(backend/data/walkthrough_cases_structured.json `disposition`/`disposition_class`
fields): "self-care advice", "scheduled appointment", "urgent referral".
"""

import enum


class DispositionClass(enum.StrEnum):
    SELF_CARE_ADVICE = "self_care_advice"
    SCHEDULED_APPOINTMENT = "scheduled_appointment"
    URGENT_REFERRAL = "urgent_referral"


DISPOSITION_SEVERITY_ORDER = [
    DispositionClass.SELF_CARE_ADVICE,
    DispositionClass.SCHEDULED_APPOINTMENT,
    DispositionClass.URGENT_REFERRAL,
]

# Maps the walkthrough JSON's human-readable strings to the enum, for the import script.
FROM_WALKTHROUGH_LABEL = {
    "self-care advice": DispositionClass.SELF_CARE_ADVICE,
    "scheduled appointment": DispositionClass.SCHEDULED_APPOINTMENT,
    "urgent referral": DispositionClass.URGENT_REFERRAL,
}

# The reverse of the above -- needed wherever an already-parsed, enum-valued
# record (e.g. post case_upload_parsing.parse_record()) has to be redisplayed
# in the walkthrough JSON's own label shape (e.g. a scanned draft shown back
# to the doctor before she confirms it).
TO_WALKTHROUGH_LABEL = {value: label for label, value in FROM_WALKTHROUGH_LABEL.items()}
