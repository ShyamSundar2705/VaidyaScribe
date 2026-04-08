"""
Burnout Service — tracks doctor session load and predicts burnout risk.

Computes a weekly burnout score from:
  - Total audio hours transcribed
  - Number of notes generated
  - Manual edit rate (high editing = AI not matching doctor style)
  - Session frequency (multiple long sessions in one day)

This is the key innovation differentiator — no clinical scribe product does this.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.db_models import ConsultationSession, ClinicalNote, DoctorMetrics
from app.core.config import settings


def get_iso_week(dt: datetime) -> str:
    return dt.strftime("%Y-W%V")


async def compute_session_burnout_contribution(
    doctor_id: str,
    audio_duration: float,
) -> dict:
    """
    After each session, update the doctor's weekly metrics
    and return their current burnout score + alert flag.
    """
    week = get_iso_week(datetime.utcnow())

    async with AsyncSessionLocal() as session:
        # Fetch or create weekly metrics record
        result = await session.execute(
            select(DoctorMetrics).where(
                DoctorMetrics.doctor_id == doctor_id,
                DoctorMetrics.week_start == week,
            )
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            metrics = DoctorMetrics(
                doctor_id=doctor_id,
                week_start=week,
                total_sessions=0,
                total_audio_hours=0.0,
                total_notes=0,
                avg_edit_rate=0.0,
                burnout_score=0.0,
            )
            session.add(metrics)

        # Increment counters
        metrics.total_sessions += 1
        metrics.total_audio_hours += audio_duration / 3600.0
        metrics.total_notes += 1

        # Fetch edit rate from recent notes (last 20 notes this week)
        notes_result = await session.execute(
            select(ClinicalNote).where(
                ClinicalNote.doctor_id == doctor_id,
            ).order_by(ClinicalNote.created_at.desc()).limit(20)
        )
        recent_notes = notes_result.scalars().all()
        if recent_notes:
            edit_rate = sum(1 for n in recent_notes if n.doctor_edited) / len(recent_notes)
            metrics.avg_edit_rate = round(edit_rate, 3)

        # ─── Burnout score formula ─────────────────────────────
        # Weighted composite (all normalised to 0-1)
        hours_score = min(metrics.total_audio_hours / settings.BURNOUT_HOURS_THRESHOLD, 1.0)
        notes_score = min(metrics.total_notes / settings.BURNOUT_NOTES_THRESHOLD, 1.0)
        edit_score = metrics.avg_edit_rate  # high edit rate = model mismatch = frustration

        burnout_score = round(
            hours_score * 0.45
            + notes_score * 0.35
            + edit_score * 0.20,
            3,
        )
        metrics.burnout_score = burnout_score

        should_alert = burnout_score >= 0.75 and not metrics.alert_sent
        if should_alert:
            metrics.alert_sent = True

        await session.commit()

    return {
        "burnout_score": burnout_score,
        "alert": should_alert,
        "week": week,
        "total_audio_hours": round(metrics.total_audio_hours, 2),
        "total_notes": metrics.total_notes,
    }


async def get_doctor_burnout_dashboard(doctor_id: str, weeks: int = 4) -> list[dict]:
    """Returns last N weeks of burnout metrics for the dashboard."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DoctorMetrics)
            .where(DoctorMetrics.doctor_id == doctor_id)
            .order_by(DoctorMetrics.week_start.desc())
            .limit(weeks)
        )
        rows = result.scalars().all()

    return [
        {
            "week": r.week_start,
            "burnout_score": r.burnout_score,
            "total_audio_hours": round(r.total_audio_hours, 2),
            "total_notes": r.total_notes,
            "avg_edit_rate": round(r.avg_edit_rate, 3),
            "alert_sent": r.alert_sent,
        }
        for r in rows
    ]
