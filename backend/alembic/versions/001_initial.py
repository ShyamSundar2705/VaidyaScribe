"""Initial schema — consultation_sessions, clinical_notes, audit_logs, doctor_metrics

Revision ID: 001_initial
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultation_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doctor_id", sa.String(100), nullable=False, index=True),
        sa.Column("patient_id", sa.String(100), nullable=True),
        sa.Column("language_detected", sa.String(20)),
        sa.Column("audio_duration_seconds", sa.Float),
        sa.Column("consent_given", sa.Boolean, default=False),
        sa.Column("consent_timestamp", sa.DateTime, nullable=True),
        sa.Column("consent_ip_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), default="recording"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "clinical_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("consultation_sessions.id")),
        sa.Column("doctor_id", sa.String(100), nullable=False, index=True),
        sa.Column("transcript_english", sa.Text),
        sa.Column("transcript_original", sa.Text),
        sa.Column("entities", sa.JSON),
        sa.Column("soap_subjective", sa.Text),
        sa.Column("soap_objective", sa.Text),
        sa.Column("soap_assessment", sa.Text),
        sa.Column("soap_plan", sa.Text),
        sa.Column("icd10_codes", sa.JSON, default=list),
        sa.Column("tamil_patient_summary", sa.Text, nullable=True),
        sa.Column("qa_confidence", sa.Float),
        sa.Column("qa_flags", sa.JSON, default=list),
        sa.Column("qa_status", sa.String(20), default="pending"),
        sa.Column("doctor_approved", sa.Boolean, default=False),
        sa.Column("doctor_edited", sa.Boolean, default=False),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("model_version", sa.String(20), default="v1.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("consultation_sessions.id")),
        sa.Column("doctor_id", sa.String(100), index=True),
        sa.Column("action", sa.String(100)),
        sa.Column("metadata", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "doctor_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doctor_id", sa.String(100), nullable=False, index=True),
        sa.Column("week_start", sa.String(20)),
        sa.Column("total_sessions", sa.Integer, default=0),
        sa.Column("total_audio_hours", sa.Float, default=0.0),
        sa.Column("total_notes", sa.Integer, default=0),
        sa.Column("avg_edit_rate", sa.Float, default=0.0),
        sa.Column("burnout_score", sa.Float, default=0.0),
        sa.Column("alert_sent", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("doctor_metrics")
    op.drop_table("audit_logs")
    op.drop_table("clinical_notes")
    op.drop_table("consultation_sessions")
