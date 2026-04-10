import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, JSON, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id             = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id      = Column(String(100), unique=True, nullable=False, index=True)
    email          = Column(String(200), unique=True, nullable=False, index=True)
    full_name      = Column(String(200), nullable=False)
    specialisation = Column(String(100), nullable=True)
    hashed_password = Column(String(200), nullable=False)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    last_login     = Column(DateTime, nullable=True)


class ConsultationSession(Base):
    __tablename__ = "consultation_sessions"

    id                     = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id              = Column(String(100), nullable=False, index=True)
    patient_id             = Column(String(100), nullable=True)
    language_detected      = Column(String(20))
    audio_duration_seconds = Column(Float)
    consent_given          = Column(Boolean, default=False)
    consent_timestamp      = Column(DateTime, nullable=True)
    consent_ip_hash        = Column(String(64), nullable=True)
    status                 = Column(String(30), default="recording")
    created_at             = Column(DateTime, default=datetime.utcnow)
    updated_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes      = relationship("ClinicalNote", back_populates="session")
    audit_logs = relationship("AuditLog",     back_populates="session")


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id                    = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id            = Column(String(36), ForeignKey("consultation_sessions.id"), nullable=False)
    doctor_id             = Column(String(100), nullable=False, index=True)
    patient_id            = Column(String(100), nullable=True, index=True)
    transcript_english    = Column(Text)
    transcript_original   = Column(Text)
    entities              = Column(JSON)
    soap_subjective       = Column(Text)
    soap_objective        = Column(Text)
    soap_assessment       = Column(Text)
    soap_plan             = Column(Text)
    icd10_codes           = Column(JSON, default=list)
    tamil_patient_summary = Column(Text, nullable=True)
    qa_confidence         = Column(Float)
    qa_flags              = Column(JSON, default=list)
    qa_status             = Column(String(20), default="pending")
    doctor_approved       = Column(Boolean, default=False)
    doctor_edited         = Column(Boolean, default=False)
    approved_at           = Column(DateTime, nullable=True)
    model_version         = Column(String(20), default="v1.0")
    created_at            = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConsultationSession", back_populates="notes")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # session_id is nullable — auth events (login/register) have no session
    session_id = Column(String(36), ForeignKey("consultation_sessions.id"), nullable=True)
    doctor_id  = Column(String(100), index=True)
    action     = Column(String(100))
    meta_data  = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Use passive_deletes and lazy=False to avoid loading session for null session_id
    session = relationship(
        "ConsultationSession",
        back_populates="audit_logs",
        foreign_keys=[session_id],
        lazy="select",
    )


class DoctorMetrics(Base):
    __tablename__ = "doctor_metrics"

    id                 = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id          = Column(String(100), nullable=False, index=True)
    week_start         = Column(String(20))
    total_sessions     = Column(Integer, default=0)
    total_audio_hours  = Column(Float, default=0.0)
    total_notes        = Column(Integer, default=0)
    avg_edit_rate      = Column(Float, default=0.0)
    burnout_score      = Column(Float, default=0.0)
    alert_sent         = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
