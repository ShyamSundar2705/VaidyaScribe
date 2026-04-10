"""
SOAP Note Generator Agent.

Calls Groq LLM directly via httpx — no langchain_groq SDK needed.
This avoids the proxies conflict with httpx versions on EC2.

Fallback: Ollama if GROQ_API_KEY not set (local dev only).
"""
from __future__ import annotations
import json
import re
import asyncio
from app.agents.state import AgentState, SOAPNote, ExtractedEntities
from app.core.config import settings


SOAP_SYSTEM_PROMPT = """You are a clinical documentation assistant generating structured SOAP notes.
You will receive:
1. A doctor-patient consultation transcript (already translated to English)
2. Pre-extracted medical entities (symptoms, medications, vitals, ICD-10 codes)

CRITICAL RULES:
- ONLY include information explicitly stated in the transcript
- Do NOT invent, infer, or add clinical details not present in the transcript
- If information for a section is not in the transcript, write "Not documented"
- Use standard medical abbreviations (BP, HR, PRN, QD, BID, TID)
- Keep language clinical but concise

Respond ONLY with valid JSON in this exact format:
{
  "subjective": "Chief complaint and patient-reported symptoms, history of present illness",
  "objective": "Vital signs, physical examination findings, lab results if mentioned",
  "assessment": "Diagnosis or differential diagnoses with ICD-10 codes",
  "plan": "Treatment plan, medications with doses, follow-up instructions",
  "icd10_codes": ["code1", "code2"],
  "confidence": 0.0 to 1.0
}"""


def build_soap_prompt(transcript: str, entities: ExtractedEntities) -> str:
    entities_summary = f"""
Pre-extracted entities:
- Chief complaint: {entities.get('chief_complaint', 'Not identified')}
- Symptoms: {', '.join(entities.get('symptoms', [])[:8]) or 'None identified'}
- Medications: {', '.join(m['name'] for m in entities.get('medications', [])[:6]) or 'None identified'}
- Vitals: {json.dumps(entities.get('vitals', {})) or 'Not documented'}
- Duration: {entities.get('duration', '') or 'Not mentioned'}
- Allergies: {', '.join(entities.get('allergies', [])) or 'NKDA'}
- ICD-10 codes: {', '.join(entities.get('icd10_codes', [])) or 'To be coded'}
"""
    return f"""CONSULTATION TRANSCRIPT:
{transcript}

{entities_summary}

Generate the SOAP note using ONLY the information above. Respond with JSON only."""


def parse_soap_response(response_text: str) -> SOAPNote:
    """Parse LLM response into SOAPNote structure."""
    clean = re.sub(r"```(?:json)?|```", "", response_text).strip()
    try:
        data = json.loads(clean)
        return {
            "subjective": data.get("subjective", "Not documented"),
            "objective":  data.get("objective",  "Not documented"),
            "assessment": data.get("assessment", "Not documented"),
            "plan":       data.get("plan",        "Not documented"),
            "icd10_codes": data.get("icd10_codes", []),
            "confidence":  float(data.get("confidence", 0.7)),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "subjective":  response_text[:500],
            "objective":   "Not documented",
            "assessment":  "Unable to parse — manual review required",
            "plan":        "Not documented",
            "icd10_codes": [],
            "confidence":  0.3,
        }


async def _call_groq(prompt: str) -> str:
    """
    Call Groq chat completion directly via httpx.
    Bypasses the groq SDK entirely — no proxies conflict.
    """
    import httpx
    payload = {
        "model": settings.GROQ_MODEL or "llama-3.1-70b-versatile",
        "messages": [
            {"role": "system", "content": SOAP_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens":  2048,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def _call_ollama(prompt: str) -> str:
    """
    Call Ollama local LLM via httpx.
    Used as fallback when GROQ_API_KEY is not set (local dev).
    """
    import httpx
    payload = {
        "model":  settings.OLLAMA_MODEL or "llama3.1:8b",
        "prompt": f"{SOAP_SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "")


async def soap_generator_node(state: AgentState) -> dict:
    """Generates SOAP note from transcript + entities using Groq or Ollama."""
    transcript = state.get("english_transcript") or state.get("raw_transcript", "")
    entities   = state.get("entities") or {}

    if not transcript:
        return {"soap_note": None, "error": "No transcript available for SOAP generation"}

    prompt = build_soap_prompt(transcript, entities)

    try:
        if settings.GROQ_API_KEY:
            response_text = await _call_groq(prompt)
        else:
            response_text = await _call_ollama(prompt)

        soap_note = parse_soap_response(response_text)
        return {"soap_note": soap_note}

    except Exception as e:
        import structlog
        structlog.get_logger().error("soap_generation_failed", error=str(e))
        return {
            "error": f"SOAP generation failed: {str(e)}",
            "soap_note": {
                "subjective":  "Generation failed — manual entry required",
                "objective":   "Generation failed — manual entry required",
                "assessment":  "Generation failed — manual entry required",
                "plan":        "Generation failed — manual entry required",
                "icd10_codes": [],
                "confidence":  0.0,
            },
        }
