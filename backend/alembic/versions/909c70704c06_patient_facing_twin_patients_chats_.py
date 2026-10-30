"""patient facing twin: patients, chats, reviews

Revision ID: 909c70704c06
Revises: 88f4329e360f
Create Date: 2026-10-30 12:30:11.623097

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "909c70704c06"
down_revision: str | Sequence[str] | None = "88f4329e360f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Patient-facing digital twin (further work, outside the thesis's evaluated
    methodology, simulated patients only): a separate patient identity, a
    real-time chat intake session, and a human-in-the-loop review gate.

    Same enum gotcha as every prior migration that extended an existing
    Postgres ENUM type -- autogenerate doesn't detect new values, added by
    hand, using the Python enum MEMBER NAME (uppercase), not its .value.
    """
    op.add_column("clinicians", sa.Column("hospital", sa.String(length=255), nullable=True))
    op.add_column("clinicians", sa.Column("location", sa.String(length=255), nullable=True))

    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'PATIENT_CHAT_FEEDBACK'")
    op.execute("ALTER TYPE interaction_mode ADD VALUE IF NOT EXISTS 'PATIENT_CONSULT'")

    op.create_table(
        "patients",
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("patient_id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "patient_chat_sessions",
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("clinician_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "PENDING_DOCTOR_REVIEW", "RESOLVED", name="patient_chat_status"),
            nullable=False,
        ),
        sa.Column("patient_age", sa.String(length=50), nullable=True),
        sa.Column("patient_sex", sa.String(length=50), nullable=True),
        sa.Column("temperature", sa.String(length=50), nullable=True),
        sa.Column("blood_pressure", sa.String(length=50), nullable=True),
        sa.Column("pulse_rate", sa.String(length=50), nullable=True),
        sa.Column("respiratory_rate", sa.String(length=50), nullable=True),
        sa.Column("oxygen_saturation", sa.String(length=50), nullable=True),
        sa.Column("case_text", sa.Text(), nullable=True),
        sa.Column("interaction_id", sa.UUID(), nullable=True),
        sa.Column("draft_report", postgresql.JSONB(), nullable=True),
        sa.Column("final_report", postgresql.JSONB(), nullable=True),
        sa.Column(
            "clinician_action",
            postgresql.ENUM(name="clinician_action", create_type=False),
            nullable=True,
        ),
        sa.Column("clinician_correction_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"]),
        sa.ForeignKeyConstraint(["clinician_id"], ["clinicians.clinician_id"]),
        sa.ForeignKeyConstraint(["interaction_id"], ["interaction_log.interaction_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_patient_chat_sessions_patient_id"),
        "patient_chat_sessions",
        ["patient_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_chat_sessions_clinician_id"),
        "patient_chat_sessions",
        ["clinician_id"],
        unique=False,
    )

    op.create_table(
        "patient_chat_messages",
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Enum("PATIENT", "TWIN", name="chat_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["patient_chat_sessions.session_id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        op.f("ix_patient_chat_messages_session_id"),
        "patient_chat_messages",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "reviews",
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("clinician_id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.UUID(), nullable=False),
        sa.Column("patient_chat_session_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinician_id"], ["clinicians.clinician_id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"]),
        sa.ForeignKeyConstraint(["patient_chat_session_id"], ["patient_chat_sessions.session_id"]),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("patient_chat_session_id", name="uq_review_per_chat_session"),
    )
    op.create_index(op.f("ix_reviews_clinician_id"), "reviews", ["clinician_id"], unique=False)
    op.create_index(op.f("ix_reviews_patient_id"), "reviews", ["patient_id"], unique=False)
    op.create_index(
        op.f("ix_reviews_patient_chat_session_id"),
        "reviews",
        ["patient_chat_session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    Postgres has no simple "drop one enum value" -- same limitation noted in
    every prior migration that added one; not implemented here since nothing
    in this migration writes data using the new source_type/interaction_mode
    values before a downgrade. Table/column drops are real, safe rollbacks.
    """
    op.drop_index(op.f("ix_reviews_patient_chat_session_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_patient_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_clinician_id"), table_name="reviews")
    op.drop_table("reviews")

    op.drop_index(op.f("ix_patient_chat_messages_session_id"), table_name="patient_chat_messages")
    op.drop_table("patient_chat_messages")

    op.drop_index(op.f("ix_patient_chat_sessions_clinician_id"), table_name="patient_chat_sessions")
    op.drop_index(op.f("ix_patient_chat_sessions_patient_id"), table_name="patient_chat_sessions")
    op.drop_table("patient_chat_sessions")

    op.drop_table("patients")

    op.drop_column("clinicians", "location")
    op.drop_column("clinicians", "hospital")

    bind = op.get_bind()
    postgresql.ENUM(name="chat_role").drop(bind, checkfirst=True)
    postgresql.ENUM(name="patient_chat_status").drop(bind, checkfirst=True)
