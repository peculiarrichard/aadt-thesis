import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.db.enums import (
    AuditActor,
    ClinicianAction,
    ConsentSubjectType,
    GraphNodeType,
    GraphRelationType,
    IngestionStatus,
    Mode,
    SourceType,
)

# BGE-M3 (Section 8) produces 1024-dimensional dense embeddings.
EMBEDDING_DIM = 1024


class Clinician(Base):
    """A clinician tenant. clinician_id is the tenant key referenced by every other
    tenant-scoped table."""

    __tablename__ = "clinicians"

    clinician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    specialty: Mapped[str | None] = mapped_column(String(255))
    credentials: Mapped[str | None] = mapped_column(Text)
    standing_protocols_ref: Mapped[str | None] = mapped_column(Text)
    consent_status: Mapped[str] = mapped_column(String(50), default="pending")
    consent_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class Consultation(Base):
    """A single case: a real consultation transcript or a structured elicitation session."""

    __tablename__ = "consultations"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    patient_ref: Mapped[str] = mapped_column(String(255))
    transcript_or_summary: Mapped[str] = mapped_column(Text)
    doctor_disposition: Mapped[str | None] = mapped_column(String(255))
    doctor_reasoning_notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType, name="source_type"), nullable=False
    )
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    used_for_training: Mapped[bool] = mapped_column(Boolean, default=False)
    used_for_holdout: Mapped[bool] = mapped_column(Boolean, default=False)


class GuidelineDocument(Base):
    """A source guideline document. No clinician_id: shared, not tenant-owned (Section 7)."""

    __tablename__ = "guideline_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500))
    edition: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(255))
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GuidelineChunk(Base):
    """A retrievable, embedded passage from a guideline document. Shared, not tenant-scoped."""

    __tablename__ = "guideline_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guideline_documents.document_id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class GuidelineGraphNode(Base):
    """A condition/symptom/recommendation node (Section 5.3's graph-based retrieval;
    not in Section 7's printed schema). Shared, not tenant-scoped."""

    __tablename__ = "guideline_graph_nodes"
    __table_args__ = (
        UniqueConstraint("document_id", "node_type", "label", name="uq_graph_node_identity"),
    )

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guideline_documents.document_id"), nullable=False, index=True
    )
    node_type: Mapped[GraphNodeType] = mapped_column(
        SQLEnum(GraphNodeType, name="graph_node_type"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(500))


class GuidelineGraphEdge(Base):
    """A relationship between two graph nodes (e.g. condition presents_with symptom),
    with provenance back to the chunk it was extracted from."""

    __tablename__ = "guideline_graph_edges"

    edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guideline_graph_nodes.node_id"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guideline_graph_nodes.node_id"), nullable=False, index=True
    )
    relation_type: Mapped[GraphRelationType] = mapped_column(
        SQLEnum(GraphRelationType, name="graph_relation_type"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guideline_chunks.chunk_id"), nullable=False, index=True
    )


class CasePrecedentVector(Base):
    """Embedding of a past case, used as precedent memory at inference time."""

    __tablename__ = "case_precedent_vectors"

    vector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultations.consultation_id"), nullable=False, index=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class InteractionLog(Base):
    """The primary record for every evaluation metric (Section 10). Never overwritten;
    corrections create a new row rather than mutating the original."""

    __tablename__ = "interaction_log"

    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    mode: Mapped[Mode] = mapped_column(SQLEnum(Mode, name="interaction_mode"), nullable=False)
    input_case_ref: Mapped[str] = mapped_column(String(255))
    draft_disposition: Mapped[str | None] = mapped_column(Text)
    final_disposition: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    guideline_conflict_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation_ref: Mapped[str | None] = mapped_column(String(255))
    clinician_action: Mapped[ClinicianAction | None] = mapped_column(
        SQLEnum(ClinicianAction, name="clinician_action")
    )
    clinician_correction_notes: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConsentRegistry(Base):
    """Tracks consent grants/revocations for a clinician or a batch of patient data."""

    __tablename__ = "consent_registry"

    consent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    subject_type: Mapped[ConsentSubjectType] = mapped_column(
        SQLEnum(ConsentSubjectType, name="consent_subject_type"), nullable=False
    )
    scope: Mapped[str] = mapped_column(Text)
    granted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    """Append-only record of who did what, for every clinician-scoped action."""

    __tablename__ = "audit_log"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    actor: Mapped[AuditActor] = mapped_column(
        SQLEnum(AuditActor, name="audit_actor"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(255))
    reference_table: Mapped[str | None] = mapped_column(String(100))
    reference_id: Mapped[str | None] = mapped_column(String(255))
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngestionQueueItem(Base):
    """Durable landing zone for a raw uploaded transcript (Layer 2, Section 5.2).
    Not part of Section 7's printed schema; see docs/build_log.md task 6."""

    __tablename__ = "ingestion_queue"
    __table_args__ = (
        UniqueConstraint(
            "clinician_id", "idempotency_key", name="uq_ingestion_queue_clinician_idempotency_key"
        ),
    )

    ingestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinicians.clinician_id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Reuses consultations.source_type's Postgres enum; must use PGEnum directly since
    # generic sqlalchemy.Enum's create_type=False isn't reliably forwarded.
    source_type: Mapped[SourceType] = mapped_column(
        PGEnum(SourceType, name="source_type", create_type=False), nullable=False
    )
    # Always de-identified before storage; redaction_summary holds category counts only.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    redaction_summary: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[IngestionStatus] = mapped_column(
        SQLEnum(IngestionStatus, name="ingestion_status"),
        nullable=False,
        default=IngestionStatus.RECEIVED,
    )
    received_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
