import enum


class SourceType(enum.StrEnum):
    REAL_CONSULTATION = "real_consultation"
    ELICITATION_SESSION = "elicitation_session"
    # This doctor's clinician-specific data (Section 6.1). Kept alongside the other
    # two values, not replacing them, so a future doctor who consents to live
    # ingestion still has those paths available.
    WALKTHROUGH = "walkthrough"
    # A case a clinician's correction created during an ad-hoc consult (Phase O) --
    # distinguishable from the original onboarding data (walkthrough import, bulk
    # upload, recording) that built her starting precedent memory.
    CONSULT_FEEDBACK = "consult_feedback"
    # A case a clinician's correction created from the patient-facing chat's
    # human-in-the-loop review (simulated patients only) -- distinguishable from
    # CONSULT_FEEDBACK, which comes from her own ad-hoc Consult Mode corrections.
    PATIENT_CHAT_FEEDBACK = "patient_chat_feedback"


class Mode(enum.StrEnum):
    LEARNING = "learning"
    CONSULTING_SANDBOX = "consulting_sandbox"
    # A real-time patient-chat consult (simulated patients only), distinct from
    # CONSULTING_SANDBOX (the clinician's own ad-hoc Consult Mode) so patient-chat
    # interactions can be aggregated separately for the twin's patient-facing stats.
    PATIENT_CONSULT = "patient_consult"


class ClinicianAction(enum.StrEnum):
    APPROVED = "approved"
    CORRECTED = "corrected"
    ESCALATED_REVIEW = "escalated_review"


class ConsentSubjectType(enum.StrEnum):
    CLINICIAN = "clinician"
    # Consent to upload an already de-identified patient case (text/document,
    # not a live recording) -- Phase J.
    PATIENT_DATA_BATCH = "patient_data_batch"
    # The clinician's own consent to have her walkthrough narration recorded --
    # no patient involved, distinct from both patient-related consents below.
    WALKTHROUGH_RECORDING = "walkthrough_recording"
    # Per-session consent immediately before recording one live patient
    # consultation -- always paired with the global institutional ethics
    # clearance setting (config.py), never sufficient on its own.
    PATIENT_RECORDING_SESSION = "patient_recording_session"


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


class PatientChatStatus(enum.StrEnum):
    """Lifecycle of a patient-facing chat consult (simulated patients only) --
    PENDING_DOCTOR_REVIEW is the human-in-the-loop gate: a patient sees the
    twin's draft report while in this state, but it isn't final until the
    clinician acts on it (see api/patient_review.py)."""

    IN_PROGRESS = "in_progress"
    PENDING_DOCTOR_REVIEW = "pending_doctor_review"
    RESOLVED = "resolved"


class ChatRole(enum.StrEnum):
    PATIENT = "patient"
    TWIN = "twin"
