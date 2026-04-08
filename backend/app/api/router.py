"""FastAPI REST router — sessions, notes, approve, export, burnout."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.db_models import ConsultationSession, ClinicalNote, AuditLog, DoctorMetrics
from app.core.config import settings

api_router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────

class ConsentRequest(BaseModel):
    doctor_id: str
    patient_id: Optional[str] = None
    consent_given: bool

class ApproveRequest(BaseModel):
    note_id: str
    doctor_id: str
    soap_subjective: Optional[str] = None
    soap_objective: Optional[str] = None
    soap_assessment: Optional[str] = None
    soap_plan: Optional[str] = None
    edited: bool = False


# ─── Session endpoints ────────────────────────────────────────────

@api_router.post("/sessions/consent")
async def record_consent(req: ConsentRequest, db: AsyncSession = Depends(get_db)):
    """Log explicit patient consent before recording starts. DPDP 2023 compliant."""
    session_id = str(uuid.uuid4())
    session = ConsultationSession(
        id=session_id,
        doctor_id=req.doctor_id,
        patient_id=req.patient_id,
        consent_given=req.consent_given,
        consent_timestamp=datetime.utcnow() if req.consent_given else None,
        status="consent_logged",
    )
    db.add(session)
    log_entry = AuditLog(
        session_id=session_id,
        doctor_id=req.doctor_id,
        action="CONSENT_GIVEN" if req.consent_given else "CONSENT_DECLINED",
        metadata={"patient_id": req.patient_id, "timestamp": datetime.utcnow().isoformat()},
    )
    db.add(log_entry)
    await db.commit()
    return {"session_id": session_id, "consent_given": req.consent_given}


@api_router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "doctor_id": session.doctor_id,
        "status": session.status,
        "language_detected": session.language_detected,
        "consent_given": session.consent_given,
        "created_at": session.created_at.isoformat(),
    }


# ─── Notes endpoints ──────────────────────────────────────────────

@api_router.get("/notes/{session_id}")
async def get_note(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the generated SOAP note for a session."""
    result = await db.execute(
        select(ClinicalNote).where(ClinicalNote.session_id == session_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {
        "id": note.id,
        "session_id": note.session_id,
        "transcript_english": note.transcript_english,
        "transcript_original": note.transcript_original,
        "entities": note.entities,
        "soap": {
            "subjective": note.soap_subjective,
            "objective": note.soap_objective,
            "assessment": note.soap_assessment,
            "plan": note.soap_plan,
        },
        "icd10_codes": note.icd10_codes,
        "tamil_patient_summary": note.tamil_patient_summary,
        "qa_confidence": note.qa_confidence,
        "qa_flags": note.qa_flags,
        "qa_status": note.qa_status,
        "doctor_approved": note.doctor_approved,
        "created_at": note.created_at.isoformat(),
    }


@api_router.post("/notes/{note_id}/approve")
async def approve_note(req: ApproveRequest, db: AsyncSession = Depends(get_db)):
    """Doctor approves (and optionally edits) the SOAP note."""
    result = await db.execute(
        select(ClinicalNote).where(ClinicalNote.id == req.note_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Apply any edits from the doctor
    if req.soap_subjective:
        note.soap_subjective = req.soap_subjective
    if req.soap_objective:
        note.soap_objective = req.soap_objective
    if req.soap_assessment:
        note.soap_assessment = req.soap_assessment
    if req.soap_plan:
        note.soap_plan = req.soap_plan

    note.doctor_approved = True
    note.doctor_edited = req.edited
    note.approved_at = datetime.utcnow()

    # Update session status
    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if session:
        session.status = "approved"

    # Audit log
    db.add(AuditLog(
        session_id=note.session_id,
        doctor_id=req.doctor_id,
        action="NOTE_APPROVED" if not req.edited else "NOTE_EDITED_AND_APPROVED",
        metadata={"note_id": note.id, "edited": req.edited},
    ))
    await db.commit()
    return {"approved": True, "note_id": note.id, "edited": req.edited}


# ─── Export endpoints ─────────────────────────────────────────────

@api_router.get("/notes/{note_id}/export/pdf")
async def export_pdf(note_id: str, db: AsyncSession = Depends(get_db)):
    """Generate and download a PDF of the approved SOAP note."""
    note_result = await db.execute(select(ClinicalNote).where(ClinicalNote.id == note_id))
    note = note_result.scalar_one_or_none()
    if not note or not note.doctor_approved:
        raise HTTPException(status_code=404, detail="Approved note not found")

    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    session = sess_result.scalar_one_or_none()

    from app.services.pdf_service import generate_pdf
    pdf_path = await generate_pdf(note, session)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"soap_note_{note_id[:8]}.pdf")


@api_router.get("/notes/{note_id}/export/fhir")
async def export_fhir(note_id: str, db: AsyncSession = Depends(get_db)):
    """Export FHIR R4 DocumentReference bundle."""
    note_result = await db.execute(select(ClinicalNote).where(ClinicalNote.id == note_id))
    note = note_result.scalar_one_or_none()
    if not note or not note.doctor_approved:
        raise HTTPException(status_code=404, detail="Approved note not found")

    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    session = sess_result.scalar_one_or_none()

    from app.services.fhir_service import export_fhir_json
    fhir_path = await export_fhir_json(note, session)
    return FileResponse(fhir_path, media_type="application/json", filename=f"fhir_{note_id[:8]}.json")


# ─── Burnout dashboard ────────────────────────────────────────────

@api_router.get("/doctors/{doctor_id}/burnout")
async def get_burnout(doctor_id: str):
    """Return the last 4 weeks of burnout metrics for a doctor."""
    from app.services.burnout_service import get_doctor_burnout_dashboard
    data = await get_doctor_burnout_dashboard(doctor_id)
    return {"doctor_id": doctor_id, "weeks": data}


@api_router.get("/doctors/{doctor_id}/notes/recent")
async def get_recent_notes(doctor_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Fetch a doctor's recent notes for the history panel."""
    result = await db.execute(
        select(ClinicalNote)
        .where(ClinicalNote.doctor_id == doctor_id)
        .order_by(ClinicalNote.created_at.desc())
        .limit(limit)
    )
    notes = result.scalars().all()
    return [
        {
            "id": n.id,
            "session_id": n.session_id,
            "created_at": n.created_at.isoformat(),
            "doctor_approved": n.doctor_approved,
            "qa_confidence": n.qa_confidence,
            "icd10_codes": n.icd10_codes,
        }
        for n in notes
    ]
