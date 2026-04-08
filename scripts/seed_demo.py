"""
scripts/seed_demo.py
====================
Seeds the database with 5 synthetic consultations covering:
  1. Tamil-English mixed — heart failure (HIGH burnout load scenario)
  2. Tamil-only — diabetes follow-up
  3. English-only — hypertension
  4. Tamil-English mixed — paediatric fever
  5. English-only — COPD

Also seeds doctor metrics to populate the burnout dashboard.

Usage:
    docker compose exec backend python scripts/seed_demo.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta
import random

DEMO_SESSIONS = [
    {
        "doctor_id": "DR-DEMO-001",
        "patient_id": "PT-1001",
        "language": "tamil-english",
        "transcript_english": (
            "Patient is a 58 year old male presenting with breathlessness for 3 days. "
            "He says his feet are swollen. Blood pressure is 155 over 90. "
            "Heart rate 98. Weight gain of 3 kg over one week. "
            "He is on Furosemide 40mg daily and Ramipril 5mg. "
            "Assessment: Decompensated heart failure. Plan: increase Furosemide to 80mg, "
            "restrict fluids to 1.5 litres per day, review in 5 days, refer cardiology."
        ),
        "transcript_original": (
            "Patient-ku 3 naal-aa maasam pidichurukkaan. Kaal veekkam irukku. "
            "Blood pressure 155 over 90. Heart rate 98. Weight 3 kg koodindhurukku. "
            "Furosemide 40mg daily edukkiraanga, Ramipril 5mg. "
            "Decompensated heart failure. Furosemide 80mg aakanum, "
            "1.5 litre fluid restriction, 5 naallalay review, cardiology refer."
        ),
        "soap": {
            "subjective": "58M presenting with 3-day history of breathlessness and bilateral pedal oedema. Weight gain of 3kg in one week. Currently on Furosemide 40mg OD and Ramipril 5mg OD.",
            "objective": "BP 155/90 mmHg. HR 98 bpm. Bilateral pedal oedema noted. Weight increased by 3kg.",
            "assessment": "Decompensated heart failure (I50.9). Poorly controlled hypertension (I10).",
            "plan": "1. Increase Furosemide to 80mg OD. 2. Fluid restriction 1.5L/day. 3. Review in 5 days. 4. Refer to cardiology.",
        },
        "icd10": ["I50.9", "I10"],
        "tamil_summary": "உங்கள் இதயம் சரியாக இயங்கவில்லை. மருந்தின் அளவை அதிகரிக்கிறோம். தினமும் 1.5 லிட்டர் மட்டுமே தண்ணீர் குடிக்கவும். 5 நாட்களில் மீண்டும் வரவும்.",
        "qa_confidence": 0.91,
        "qa_flags": [],
    },
    {
        "doctor_id": "DR-DEMO-001",
        "patient_id": "PT-1002",
        "language": "tamil",
        "transcript_english": (
            "45 year old female diabetic patient for review. Fasting blood sugar 180. "
            "HbA1c 8.2%. She reports good medication compliance. "
            "No symptoms of hypoglycaemia. Feet examination normal. "
            "Plan: increase Metformin to 1000mg twice daily, add dietary counselling, review in 3 months."
        ),
        "transcript_original": (
            "45 vayathu pen, sugar patient review-ku vandhurukkaa. "
            "Fasting blood sugar 180. HbA1c 8.2%. Maudhum saaptaanga sollraanga. "
            "Hypoglycaemia symptom illa. Kaal examination normal. "
            "Metformin 1000mg twice daily aakanum, diet counselling, 3 maasathula review."
        ),
        "soap": {
            "subjective": "45F with type 2 diabetes mellitus presenting for routine review. Reports good medication compliance. No hypoglycaemic episodes.",
            "objective": "FBS: 180 mg/dL. HbA1c: 8.2%. Feet examination: NAD.",
            "assessment": "Type 2 diabetes mellitus, suboptimally controlled (E11.9).",
            "plan": "1. Increase Metformin to 1000mg BD. 2. Dietary counselling referral. 3. Review in 3 months with repeat HbA1c.",
        },
        "icd10": ["E11.9"],
        "tamil_summary": "உங்கள் சர்க்கரை அளவு இன்னும் கொஞ்சம் அதிகமாக இருக்கிறது. மெட்ஃபோர்மின் மாத்திரையை இப்போது காலையிலும் இரவிலும் ஒன்று சாப்பிட வேண்டும். உணவு கட்டுப்பாடு முக்கியம். 3 மாதத்தில் மீண்டும் ரத்தப் பரிசோதனை செய்யவும்.",
        "qa_confidence": 0.89,
        "qa_flags": [],
    },
    {
        "doctor_id": "DR-DEMO-001",
        "patient_id": "PT-1003",
        "language": "english",
        "transcript_english": (
            "32 year old male with persistent headache for 2 weeks. BP 148 over 92 on both arms. "
            "No visual changes. No family history of hypertension. "
            "Non-smoker, occasional alcohol. BMI 27. "
            "Plan: start Amlodipine 5mg daily, lifestyle advice, recheck BP in 2 weeks."
        ),
        "transcript_original": (
            "32 year old male with persistent headache for 2 weeks. BP 148 over 92 on both arms. "
            "No visual changes. No family history of hypertension. "
            "Non-smoker, occasional alcohol. BMI 27. "
            "Plan: start Amlodipine 5mg daily, lifestyle advice, recheck BP in 2 weeks."
        ),
        "soap": {
            "subjective": "32M presenting with 2-week history of persistent headache. No visual disturbance. No family history of hypertension. Non-smoker, occasional alcohol. BMI 27.",
            "objective": "BP 148/92 mmHg (both arms). No papilloedema. Neurological exam: normal.",
            "assessment": "Stage 1 hypertension (I10). Tension-type headache (G44.2).",
            "plan": "1. Start Amlodipine 5mg OD. 2. Lifestyle modification: reduce salt, increase exercise. 3. Recheck BP in 2 weeks. 4. If headaches persist, neurology referral.",
        },
        "icd10": ["I10", "G44.2"],
        "tamil_summary": None,
        "qa_confidence": 0.94,
        "qa_flags": [],
    },
    {
        "doctor_id": "DR-DEMO-001",
        "patient_id": "PT-1004",
        "language": "tamil-english",
        "transcript_english": (
            "8 year old child brought by mother with 3 days of fever, 38.5 degrees. "
            "Sore throat and mild cough. No rash. "
            "Throat examination shows mild erythema. Tonsils not enlarged. "
            "Ears normal. Diagnosis viral URTI. "
            "Paracetamol 250mg three times daily for fever, plenty of fluids, review if worse."
        ),
        "transcript_original": (
            "8 vayathu kuzhanthai, 3 naal kaay juram. 38.5 degrees. "
            "Throat valikuthu, mild cough irukku. Rash illa. "
            "Throat erythema irukku, tonsil enlarge aagala. Ears normal. "
            "Viral URTI. Paracetamol 250mg thrice daily fever-ku, "
            "niraiya thanni kudikanum, maaruvaaraa paathukanum."
        ),
        "soap": {
            "subjective": "8-year-old child presenting with 3-day history of fever (38.5°C), sore throat and mild cough. No rash. Mother reports good oral intake.",
            "objective": "Temp 38.5°C. Throat: mild erythema. Tonsils: not enlarged. Ears: NAD. Cervical lymph nodes: not palpable.",
            "assessment": "Viral upper respiratory tract infection (J06.9).",
            "plan": "1. Paracetamol 250mg TDS PRN fever. 2. Adequate oral hydration. 3. Return if fever persists beyond 5 days or child deteriorates. 4. No antibiotics indicated.",
        },
        "icd10": ["J06.9"],
        "tamil_summary": "குழந்தைக்கு வைரஸ் காய்ச்சல். நாளை மறுநாளில் சரியாகிவிடும். காலை மதியம் இரவு பாராசிட்டமால் கொடுங்கள். நிறைய தண்ணீர் கொடுங்கள். 5 நாட்களுக்கும் அதிகமாக காய்ச்சல் இருந்தால் திரும்பி வாருங்கள்.",
        "qa_confidence": 0.87,
        "qa_flags": [{"field": "objective", "claim": "Cervical lymph nodes: not palpable", "reason": "Lymph node exam not mentioned in transcript"}],
    },
    {
        "doctor_id": "DR-DEMO-001",
        "patient_id": "PT-1005",
        "language": "english",
        "transcript_english": (
            "67 year old male with COPD, here for routine review. "
            "Feels more breathless on exertion than last visit. SpO2 94 percent on room air. "
            "Using his Salbutamol inhaler 4 times a day. Tiotropium daily. "
            "No exacerbations in last 6 months. Smoking 10 per day still. "
            "Plan: reinforce smoking cessation, refer pulmonology, check spirometry."
        ),
        "transcript_original": (
            "67 year old male with COPD, here for routine review. "
            "Feels more breathless on exertion than last visit. SpO2 94 percent on room air. "
            "Using his Salbutamol inhaler 4 times a day. Tiotropium daily. "
            "No exacerbations in last 6 months. Smoking 10 per day still. "
            "Plan: reinforce smoking cessation, refer pulmonology, check spirometry."
        ),
        "soap": {
            "subjective": "67M with known COPD presenting for review. Increased exertional dyspnoea since last visit. Using Salbutamol MDI QID. On Tiotropium OD. No acute exacerbations in 6 months. Active smoker — 10 cigarettes/day.",
            "objective": "SpO2 94% on room air. Chest: mild bilateral wheeze. No accessory muscle use.",
            "assessment": "COPD, moderate severity (J44.1). Active smoker.",
            "plan": "1. Reinforce smoking cessation — refer to cessation clinic. 2. Refer pulmonology for spirometry review. 3. Consider adding ICS/LABA inhaler if spirometry confirms deterioration. 4. Flu and pneumococcal vaccination status to be checked.",
        },
        "icd10": ["J44.1"],
        "tamil_summary": None,
        "qa_confidence": 0.92,
        "qa_flags": [],
    },
]


async def seed():
    from app.core.database import AsyncSessionLocal, create_tables
    from app.models.db_models import (
        ConsultationSession, ClinicalNote, DoctorMetrics, AuditLog
    )

    await create_tables()

    async with AsyncSessionLocal() as db:
        for i, demo in enumerate(DEMO_SESSIONS):
            session_id = str(uuid.uuid4())

            # Create session
            session = ConsultationSession(
                id=session_id,
                doctor_id=demo["doctor_id"],
                patient_id=demo["patient_id"],
                language_detected=demo["language"],
                consent_given=True,
                consent_timestamp=datetime.utcnow() - timedelta(hours=i + 1),
                status="approved",
                audio_duration_seconds=random.uniform(120, 480),
                created_at=datetime.utcnow() - timedelta(hours=i + 1),
            )
            db.add(session)

            # Create note
            note = ClinicalNote(
                id=str(uuid.uuid4()),
                session_id=session_id,
                doctor_id=demo["doctor_id"],
                transcript_english=demo["transcript_english"],
                transcript_original=demo["transcript_original"],
                entities={
                    "symptoms": ["breathlessness", "oedema"] if i == 0 else ["hyperglycaemia"] if i == 1 else ["headache"],
                    "vitals": {"bp": "155/90", "hr": "98"} if i == 0 else {"bp": "148/92"} if i == 2 else {},
                    "medications": [],
                    "icd10_codes": demo["icd10"],
                },
                soap_subjective=demo["soap"]["subjective"],
                soap_objective=demo["soap"]["objective"],
                soap_assessment=demo["soap"]["assessment"],
                soap_plan=demo["soap"]["plan"],
                icd10_codes=demo["icd10"],
                tamil_patient_summary=demo.get("tamil_summary"),
                qa_confidence=demo["qa_confidence"],
                qa_flags=demo["qa_flags"],
                qa_status="flagged" if demo["qa_flags"] else "cleared",
                doctor_approved=True,
                doctor_edited=bool(demo["qa_flags"]),
                approved_at=datetime.utcnow() - timedelta(hours=i),
                created_at=datetime.utcnow() - timedelta(hours=i + 1),
            )
            db.add(note)

            db.add(AuditLog(
                session_id=session_id,
                doctor_id=demo["doctor_id"],
                action="CONSENT_GIVEN",
                metadata={"patient_id": demo["patient_id"]},
            ))
            db.add(AuditLog(
                session_id=session_id,
                doctor_id=demo["doctor_id"],
                action="NOTE_APPROVED",
                metadata={"note_id": note.id, "edited": bool(demo["qa_flags"])},
            ))

        # Seed burnout metrics for DR-DEMO-001
        from datetime import date
        for week_offset in range(4):
            dt = datetime.utcnow() - timedelta(weeks=week_offset)
            week_str = dt.strftime("%Y-W%V")
            score = round(0.3 + week_offset * 0.12, 3)
            db.add(DoctorMetrics(
                doctor_id="DR-DEMO-001",
                week_start=week_str,
                total_sessions=5 + week_offset * 3,
                total_audio_hours=round(2.5 + week_offset * 1.8, 2),
                total_notes=5 + week_offset * 3,
                avg_edit_rate=round(0.1 + week_offset * 0.05, 3),
                burnout_score=score,
                alert_sent=score >= 0.75,
            ))

        await db.commit()
        print(f"Seeded {len(DEMO_SESSIONS)} demo consultations + 4 weeks burnout metrics.")
        print("Demo doctor: DR-DEMO-001")
        print("Languages: Tamil-English mixed, Tamil-only, English-only")


if __name__ == "__main__":
    asyncio.run(seed())
