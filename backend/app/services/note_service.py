"""
Note persistence service — saves pipeline output to SQLite after processing.
"""
from __future__ import annotations
import uuid
import traceback
from datetime import datetime
from sqlalchemy import select
import structlog

from app.agents.state import AgentState
from app.core.database import AsyncSessionLocal
from app.models.db_models import ConsultationSession, ClinicalNote, AuditLog

log = structlog.get_logger()


async def save_consultation_result(state: AgentState) -> str | None:
    """
    Persist the pipeline's final state to SQLite.
    Returns the note_id on success, None on failure.
    """
    session_id = state.get("session_id")
    if not session_id:
        log.error("save_failed", reason="no session_id in state")
        return None

    soap     = state.get("soap_note") or {}
    qa       = state.get("qa_result") or {}
    entities = state.get("entities") or {}

    try:
        async with AsyncSessionLocal() as db:
            # Look up session — may be None if consent was skipped
            result = await db.execute(
                select(ConsultationSession).where(ConsultationSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            # Update session status if it exists
            patient_id = None
            if session:
                session.language_detected = state.get("language_mix", "english")
                session.status = "review" if qa.get("needs_review", True) else "draft"
                patient_id = session.patient_id
            else:
                log.warning("session_not_found", session_id=session_id,
                            note="note will still be saved without session link")

            # Create clinical note
            note_id = str(uuid.uuid4())
            note = ClinicalNote(
                id=note_id,
                session_id=session_id,
                doctor_id=state.get("doctor_id", "unknown"),
                patient_id=patient_id,
                transcript_english=state.get("english_transcript") or state.get("raw_transcript", ""),
                transcript_original=state.get("raw_transcript", ""),
                entities=entities,
                soap_subjective=soap.get("subjective", ""),
                soap_objective=soap.get("objective", ""),
                soap_assessment=soap.get("assessment", ""),
                soap_plan=soap.get("plan", ""),
                icd10_codes=soap.get("icd10_codes", []),
                tamil_patient_summary=state.get("tamil_patient_summary"),
                qa_confidence=qa.get("confidence", 0.0),
                qa_flags=qa.get("flags", []),
                qa_status="flagged" if qa.get("flags") else "cleared",
                doctor_approved=state.get("next_step") == "auto_approve",
            )
            db.add(note)

            db.add(AuditLog(
                session_id=session_id,
                doctor_id=state.get("doctor_id", "unknown"),
                action="NOTE_GENERATED",
                meta_data={
                    "note_id": note_id,
                    "qa_confidence": qa.get("confidence", 0.0),
                    "needs_review": qa.get("needs_review", True),
                    "language_mix": state.get("language_mix"),
                },
            ))

            await db.commit()
            log.info("note_saved", note_id=note_id, session_id=session_id)
            return note_id

    except Exception as e:
        log.error("save_consultation_failed", error=str(e), trace=traceback.format_exc())
        return None
