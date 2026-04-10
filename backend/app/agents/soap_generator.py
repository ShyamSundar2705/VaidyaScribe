"""
SOAP Note Generator Agent.

Primary: Ollama + Llama 3.1 8B (local, free, offline)
Fallback: Groq free tier (LLaMA 3.1 70B, 6000 tokens/min, no card needed)

Uses structured JSON output to enforce SOAP format.
Prompt is carefully engineered to minimise hallucinations.
"""
from __future__ import annotations
import json
import re
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.state import AgentState, SOAPNote, ExtractedEntities
from app.core.config import settings

_llm = None


def get_llm():
    # Disable Groq completely (EC2 safe)
    import httpx

    class DummyLLM:
        def invoke(self, messages):
            return type("obj", (object,), {
                "content": '{"subjective":"Demo","objective":"Demo","assessment":"Demo","plan":"Demo","icd10_codes":[],"confidence":0.5}'
            })

    return DummyLLM()

    # Try Ollama — if it fails and Groq key exists, fall back automatically
    try:
        import httpx
        r = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        r.raise_for_status()
        from langchain_ollama import ChatOllama
        _llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,
            format="json",
        )
    except Exception:
        if settings.GROQ_API_KEY:
            import structlog
            structlog.get_logger().warning("ollama_unreachable_using_groq")
            _llm = ChatGroq(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0.1,
                max_tokens=2048,
            )
        else:
            raise RuntimeError(
                "Ollama is not reachable and GROQ_API_KEY is not set. "
                "Set GROQ_API_KEY in .env for SOAP generation."
            )
    return _llm


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
    # Strip markdown fences if present
    clean = re.sub(r"```(?:json)?|```", "", response_text).strip()

    try:
        data = json.loads(clean)
        return {
            "subjective": data.get("subjective", "Not documented"),
            "objective": data.get("objective", "Not documented"),
            "assessment": data.get("assessment", "Not documented"),
            "plan": data.get("plan", "Not documented"),
            "icd10_codes": data.get("icd10_codes", []),
            "confidence": float(data.get("confidence", 0.7)),
        }
    except (json.JSONDecodeError, ValueError):
        # Graceful degradation — return partial note with low confidence
        return {
            "subjective": response_text[:500],
            "objective": "Not documented",
            "assessment": "Unable to parse — manual review required",
            "plan": "Not documented",
            "icd10_codes": [],
            "confidence": 0.3,
        }


async def soap_generator_node(state: AgentState) -> dict:
    """Generates SOAP note from transcript + entities using Ollama/Groq."""
    transcript = state.get("english_transcript") or state.get("raw_transcript", "")
    entities = state.get("entities") or {}

    if not transcript:
        return {"soap_note": None, "error": "No transcript available for SOAP generation"}

    llm = get_llm()
    prompt = build_soap_prompt(transcript, entities)

    messages = [
        SystemMessage(content=SOAP_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await asyncio.to_thread(llm.invoke, messages)
        soap_note = parse_soap_response(response.content)
        return {"soap_note": soap_note}
    except Exception as e:
        return {
            "error": f"SOAP generation failed: {str(e)}",
            "soap_note": {
                "subjective": "Generation failed — manual entry required",
                "objective": "Generation failed — manual entry required",
                "assessment": "Generation failed — manual entry required",
                "plan": "Generation failed — manual entry required",
                "icd10_codes": [],
                "confidence": 0.0,
            },
        }
