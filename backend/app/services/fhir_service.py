"""
FHIR R4 Service — builds a FHIR DocumentReference bundle from an approved SOAP note.

Output is a valid FHIR R4 JSON bundle that can be pushed to any FHIR-compliant EHR.
For the hackathon demo: saves to a local JSON file and returns it for download.
In production: POST to Epic/Cerner FHIR endpoint.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from app.models.db_models import ClinicalNote, ConsultationSession


def build_fhir_bundle(note: ClinicalNote, session: ConsultationSession) -> dict:
    """Build a FHIR R4 DocumentReference + Composition bundle."""
    bundle_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    soap_text = "\n\n".join([
        f"SUBJECTIVE:\n{note.soap_subjective or 'Not documented'}",
        f"OBJECTIVE:\n{note.soap_objective or 'Not documented'}",
        f"ASSESSMENT:\n{note.soap_assessment or 'Not documented'}",
        f"PLAN:\n{note.soap_plan or 'Not documented'}",
    ])

    # Base64 encode the SOAP note content
    import base64
    soap_b64 = base64.b64encode(soap_text.encode()).decode()

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "lastUpdated": now,
            "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
        },
        "type": "document",
        "timestamp": now,
        "entry": [
            {
                "fullUrl": f"urn:uuid:{note.id}",
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": note.id,
                    "status": "current",
                    "docStatus": "final",
                    "type": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "11488-4",
                            "display": "Consult note",
                        }]
                    },
                    "subject": {
                        "reference": f"Patient/{session.patient_id or 'unknown'}",
                    },
                    "date": now,
                    "author": [{"reference": f"Practitioner/{session.doctor_id}"}],
                    "content": [{
                        "attachment": {
                            "contentType": "text/plain",
                            "data": soap_b64,
                            "title": "SOAP Clinical Note",
                            "creation": now,
                        }
                    }],
                    "context": {
                        "period": {
                            "start": session.created_at.isoformat(),
                            "end": now,
                        }
                    },
                },
            },
            # ICD-10 codes as Condition resources
            *[
                {
                    "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                    "resource": {
                        "resourceType": "Condition",
                        "code": {
                            "coding": [{
                                "system": "http://hl7.org/fhir/sid/icd-10",
                                "code": code,
                            }]
                        },
                        "subject": {"reference": f"Patient/{session.patient_id or 'unknown'}"},
                        "recordedDate": now,
                    },
                }
                for code in (note.icd10_codes or [])
            ],
        ],
    }

    return bundle


async def export_fhir_json(note: ClinicalNote, session: ConsultationSession) -> str:
    """Saves FHIR bundle to data/ and returns the file path."""
    import os
    bundle = build_fhir_bundle(note, session)
    path = f"data/fhir_{note.id}.json"
    os.makedirs("data", exist_ok=True)
    with open(path, "w") as f:
        json.dump(bundle, f, indent=2)
    return path
