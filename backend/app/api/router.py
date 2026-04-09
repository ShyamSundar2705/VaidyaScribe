"""FastAPI REST router — all routes protected by JWT authentication.
Doctor can only see their own patients and notes.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.auth import get_current_doctor
from app.models.db_models import (
    ConsultationSession, ClinicalNote, AuditLog, DoctorMetrics, Doctor
)

api_router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────

class ConsentRequest(BaseModel):
    patient_id:    Optional[str] = None
    consent_given: bool

class ApproveRequest(BaseModel):
    note_id:         Optional[str] = None
    soap_subjective: Optional[str] = None
    soap_objective:  Optional[str] = None
    soap_assessment: Optional[str] = None
    soap_plan:       Optional[str] = None
    edited:          bool = False


# ─── Full-text note search (MUST be before /notes/{id}) ──────────

@api_router.get("/notes/search")
async def search_notes(
    q: str,
    approved_only: bool = False,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Search notes by symptom/diagnosis keywords — doctor sees only their own notes."""
    from sqlalchemy import cast, String

    words = [w.strip() for w in q.lower().split() if len(w.strip()) >= 3]
    if not words:
        words = [q.lower().strip()]

    def word_in_note(word: str):
        w = f"%{word}%"
        return or_(
            func.lower(ClinicalNote.soap_assessment).like(w),
            func.lower(ClinicalNote.soap_subjective).like(w),
            func.lower(ClinicalNote.soap_plan).like(w),
            func.lower(ClinicalNote.soap_objective).like(w),
            func.lower(ClinicalNote.patient_id).like(w),
            cast(ClinicalNote.icd10_codes, String).like(w),
            func.lower(ClinicalNote.transcript_english).like(w),
        )

    from sqlalchemy import and_
    word_conditions = and_(*[word_in_note(w) for w in words])

    approval_filter = (
        ClinicalNote.doctor_approved == True
        if approved_only
        else ClinicalNote.doctor_approved.in_([True, False])
    )

    result = await db.execute(
        select(ClinicalNote, ConsultationSession)
        .join(ConsultationSession, ConsultationSession.id == ClinicalNote.session_id)
        .where(ClinicalNote.doctor_id == doctor.doctor_id)   # ← own notes only
        .where(approval_filter)
        .where(word_conditions)
        .order_by(ClinicalNote.created_at.desc())
        .limit(30)
    )
    rows = result.fetchall()

    patients: dict[str, dict] = {}
    for note, session in rows:
        pid = note.patient_id or f"unknown-{note.session_id[:8]}"
        if pid not in patients:
            patients[pid] = {
                "patient_id":  pid,
                "total_notes": 0,
                "last_seen":   note.created_at.isoformat(),
                "notes":       [],
            }
        patients[pid]["total_notes"] += 1
        patients[pid]["notes"].append({
            "note_id":       note.id,
            "date":          note.created_at.isoformat(),
            "assessment":    note.soap_assessment or "",
            "subjective":    note.soap_subjective or "",
            "plan":          note.soap_plan or "",
            "icd10_codes":   note.icd10_codes or [],
            "language":      session.language_detected or "english",
            "qa_confidence": note.qa_confidence,
        })

    return {"query": q, "results": list(patients.values()), "total": len(patients)}


# ─── Session endpoints ────────────────────────────────────────────

@api_router.post("/sessions/consent")
async def record_consent(
    req: ConsentRequest,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    session_id = str(uuid.uuid4())
    session = ConsultationSession(
        id=session_id,
        doctor_id=doctor.doctor_id,
        patient_id=req.patient_id,
        consent_given=req.consent_given,
        consent_timestamp=datetime.utcnow() if req.consent_given else None,
        status="consent_logged",
    )
    db.add(session)
    db.add(AuditLog(
        session_id=session_id,
        doctor_id=doctor.doctor_id,
        action="CONSENT_GIVEN" if req.consent_given else "CONSENT_DECLINED",
        meta_data={"patient_id": req.patient_id, "timestamp": datetime.utcnow().isoformat()},
    ))
    await db.commit()
    return {"session_id": session_id, "consent_given": req.consent_given}


@api_router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ConsultationSession).where(
            ConsultationSession.id == session_id,
            ConsultationSession.doctor_id == doctor.doctor_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id, "doctor_id": session.doctor_id,
        "status": session.status, "language_detected": session.language_detected,
        "consent_given": session.consent_given,
        "created_at": session.created_at.isoformat(),
    }


# ─── Notes endpoints ──────────────────────────────────────────────

@api_router.get("/notes/{session_id}")
async def get_note(
    session_id: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicalNote).where(
            ClinicalNote.session_id == session_id,
            ClinicalNote.doctor_id == doctor.doctor_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {
        "id": note.id, "session_id": note.session_id,
        "transcript_english": note.transcript_english,
        "transcript_original": note.transcript_original,
        "entities": note.entities,
        "soap": {
            "subjective": note.soap_subjective, "objective": note.soap_objective,
            "assessment": note.soap_assessment, "plan": note.soap_plan,
        },
        "icd10_codes": note.icd10_codes,
        "tamil_patient_summary": note.tamil_patient_summary,
        "qa_confidence": note.qa_confidence, "qa_flags": note.qa_flags,
        "qa_status": note.qa_status, "doctor_approved": note.doctor_approved,
        "created_at": note.created_at.isoformat(),
    }


@api_router.post("/notes/{note_id}/approve")
async def approve_note(
    note_id: str,
    req: ApproveRequest,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicalNote).where(
            or_(ClinicalNote.id == note_id, ClinicalNote.session_id == note_id),
            ClinicalNote.doctor_id == doctor.doctor_id,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if req.soap_subjective is not None: note.soap_subjective = req.soap_subjective
    if req.soap_objective  is not None: note.soap_objective  = req.soap_objective
    if req.soap_assessment is not None: note.soap_assessment = req.soap_assessment
    if req.soap_plan       is not None: note.soap_plan       = req.soap_plan

    note.doctor_approved = True
    note.doctor_edited   = req.edited
    note.approved_at     = datetime.utcnow()

    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    session = sess_result.scalar_one_or_none()
    if session:
        session.status = "approved"

    db.add(AuditLog(
        session_id=note.session_id, doctor_id=doctor.doctor_id,
        action="NOTE_EDITED_AND_APPROVED" if req.edited else "NOTE_APPROVED",
        meta_data={"note_id": note.id, "edited": req.edited},
    ))
    await db.commit()
    return {"approved": True, "note_id": note.id, "session_id": note.session_id}


# ─── Export endpoints ─────────────────────────────────────────────

@api_router.get("/notes/{note_id}/export/pdf")
async def export_pdf(
    note_id: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicalNote).where(
            or_(ClinicalNote.id == note_id, ClinicalNote.session_id == note_id),
            ClinicalNote.doctor_id == doctor.doctor_id,
            ClinicalNote.doctor_approved == True,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Approved note not found")

    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    from app.services.pdf_service import generate_pdf
    pdf_path = await generate_pdf(note, sess_result.scalar_one_or_none())
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"soap_{note.id[:8]}.pdf")


@api_router.get("/notes/{note_id}/export/fhir")
async def export_fhir(
    note_id: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicalNote).where(
            or_(ClinicalNote.id == note_id, ClinicalNote.session_id == note_id),
            ClinicalNote.doctor_id == doctor.doctor_id,
            ClinicalNote.doctor_approved == True,
        )
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Approved note not found")

    sess_result = await db.execute(
        select(ConsultationSession).where(ConsultationSession.id == note.session_id)
    )
    from app.services.fhir_service import export_fhir_json
    fhir_path = await export_fhir_json(note, sess_result.scalar_one_or_none())
    return FileResponse(fhir_path, media_type="application/json",
                        filename=f"fhir_{note.id[:8]}.json")


# ─── Burnout dashboard ────────────────────────────────────────────

@api_router.get("/doctors/me/burnout")
async def get_my_burnout(doctor: Doctor = Depends(get_current_doctor)):
    from app.services.burnout_service import get_doctor_burnout_dashboard
    data = await get_doctor_burnout_dashboard(doctor.doctor_id)
    return {"doctor_id": doctor.doctor_id, "weeks": data}


@api_router.get("/doctors/me/notes/recent")
async def get_my_recent_notes(
    limit: int = 10,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClinicalNote)
        .where(ClinicalNote.doctor_id == doctor.doctor_id)
        .order_by(ClinicalNote.created_at.desc())
        .limit(limit)
    )
    notes = result.scalars().all()
    return [
        {
            "id": n.id, "session_id": n.session_id,
            "created_at": n.created_at.isoformat(),
            "doctor_approved": n.doctor_approved,
            "qa_confidence": n.qa_confidence,
            "icd10_codes": n.icd10_codes,
        }
        for n in notes
    ]


# ─── Patient history ──────────────────────────────────────────────

@api_router.get("/patients/{patient_id}/notes")
async def get_patient_notes(
    patient_id: str,
    approved_only: bool = True,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Returns notes for a patient — only those created by the logged-in doctor."""
    query = (
        select(ClinicalNote, ConsultationSession)
        .join(ConsultationSession, ConsultationSession.id == ClinicalNote.session_id)
        .where(
            ClinicalNote.patient_id == patient_id,
            ClinicalNote.doctor_id  == doctor.doctor_id,   # ← own patients only
        )
    )
    if approved_only:
        query = query.where(ClinicalNote.doctor_approved == True)

    result = await db.execute(query.order_by(ClinicalNote.created_at.desc()))
    rows   = result.fetchall()

    if not rows:
        return {"patient_id": patient_id, "notes": [], "total": 0}

    notes = []
    for note, session in rows:
        notes.append({
            "note_id":               note.id,
            "session_id":            note.session_id,
            "date":                  note.created_at.isoformat(),
            "doctor_id":             note.doctor_id,
            "language":              session.language_detected or "english",
            "doctor_approved":       note.doctor_approved,
            "qa_confidence":         note.qa_confidence,
            "icd10_codes":           note.icd10_codes or [],
            "soap": {
                "subjective": note.soap_subjective,
                "objective":  note.soap_objective,
                "assessment": note.soap_assessment,
                "plan":       note.soap_plan,
            },
            "tamil_patient_summary": note.tamil_patient_summary,
        })

    return {"patient_id": patient_id, "notes": notes, "total": len(notes)}


@api_router.get("/patients/search")
async def search_patients(
    q: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import distinct
    result = await db.execute(
        select(distinct(ClinicalNote.patient_id))
        .where(
            ClinicalNote.doctor_id == doctor.doctor_id,
            ClinicalNote.patient_id.ilike(f"{q}%"),
        )
        .limit(10)
    )
    return {"results": [r[0] for r in result.fetchall() if r[0]]}
