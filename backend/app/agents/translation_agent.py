"""
Translation Agent — Tamil/English code-switch handler using NLLB-200.

Meta's NLLB-200 (No Language Left Behind) distilled 600M model.
Free, Apache 2.0, runs fully offline.

Strategy:
  1. Group transcript segments by language
  2. Tamil segments → NLLB → English
  3. English segments pass through
  4. Merge into unified English transcript
  5. Preserve original Tamil for patient summary generation
"""
from __future__ import annotations
import asyncio
from app.agents.state import AgentState, TranscriptSegment
from app.core.config import settings

_translator = None
_tokenizer = None


def get_translator():
    global _translator, _tokenizer
    if _translator is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained(settings.NLLB_MODEL)
        _translator = AutoModelForSeq2SeqLM.from_pretrained(settings.NLLB_MODEL)
    return _translator, _tokenizer


def translate_tamil_to_english(text: str) -> str:
    """Translate a Tamil text segment to English using NLLB-200."""
    if not text.strip():
        return text
    try:
        model, tokenizer = get_translator()
        inputs = tokenizer(
            text,
            return_tensors="pt",
            src_lang="tam_Taml",    # Tamil in Tamil script
            max_length=512,
            truncation=True,
        )
        forced_bos_token_id = tokenizer.lang_code_to_id["eng_Latn"]
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_new_tokens=512,
            num_beams=4,
        )
        return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    except Exception as e:
        # Fallback: return original text with a note
        return f"[Translation pending: {text}]"


def translate_english_to_tamil(text: str) -> str:
    """Translate English clinical plan to Tamil for patient summary."""
    if not text.strip():
        return text
    try:
        model, tokenizer = get_translator()
        inputs = tokenizer(
            text,
            return_tensors="pt",
            src_lang="eng_Latn",
            max_length=512,
            truncation=True,
        )
        forced_bos_token_id = tokenizer.lang_code_to_id["tam_Taml"]
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_new_tokens=512,
            num_beams=4,
        )
        return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    except Exception as e:
        return text


async def translation_agent_node(state: AgentState) -> dict:
    """
    Processes transcript segments:
    - Tamil segments are translated to English via NLLB-200
    - English segments pass through unchanged
    - Produces unified English transcript + preserved Tamil original
    """
    segments: list[TranscriptSegment] = state.get("transcript_segments", [])

    if not segments:
        raw = state.get("raw_transcript", "")
        return {
            "english_transcript": raw,
            "tamil_original": None,
        }

    english_parts = []
    tamil_parts = []

    for seg in segments:
        text = seg["text"]
        lang = seg["lang"]

        if lang == "ta":
            tamil_parts.append(text)
            # Translate to English in thread pool
            translated = await asyncio.to_thread(translate_tamil_to_english, text)
            english_parts.append(translated)
        else:
            # English — pass through directly
            english_parts.append(text)

    english_transcript = " ".join(english_parts).strip()
    tamil_original = " ".join(tamil_parts).strip() if tamil_parts else None

    return {
        "english_transcript": english_transcript,
        "tamil_original": tamil_original,
    }


async def generate_tamil_patient_summary(soap_plan: str) -> str:
    """
    Translates the SOAP Plan section into Tamil for the patient.
    Called after SOAP generation, not in the main agent pipeline.
    """
    if not soap_plan:
        return ""

    # Simplify clinical language before translating
    simplified = soap_plan.replace("PRN", "as needed").replace("QD", "once daily").replace("BID", "twice daily")
    tamil_summary = await asyncio.to_thread(translate_english_to_tamil, simplified)
    return tamil_summary
