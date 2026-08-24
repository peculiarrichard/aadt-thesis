import enum


class SourceType(enum.StrEnum):
    REAL_CONSULTATION = "real_consultation"
    ELICITATION_SESSION = "elicitation_session"


class Mode(enum.StrEnum):
    LEARNING = "learning"
    CONSULTING_SANDBOX = "consulting_sandbox"


class ClinicianAction(enum.StrEnum):
    APPROVED = "approved"
    CORRECTED = "corrected"
    ESCALATED_REVIEW = "escalated_review"


class ConsentSubjectType(enum.StrEnum):
    CLINICIAN = "clinician"
    PATIENT_DATA_BATCH = "patient_data_batch"


class AuditActor(enum.StrEnum):
    SYSTEM = "system"
    CLINICIAN = "clinician"
    ADMIN = "admin"


class GraphNodeType(enum.StrEnum):
    CONDITION = "condition"
    SYMPTOM = "symptom"
    RECOMMENDATION = "recommendation"


class GraphRelationType(enum.StrEnum):
    PRESENTS_WITH = "presents_with"
    RECOMMENDS = "recommends"


class IngestionStatus(enum.StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"
