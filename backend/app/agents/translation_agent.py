"""
Translation Agent — Tamil/English code-switch handler.

When Groq Whisper is used (GROQ_API_KEY set):
  Groq's whisper-large-v3 already handles Tamil/English code-switching
  and outputs a coherent mixed-language or English transcript.
  Running NLLB on top produces garbage — skip it.
  Just pass the transcript through and detect language.

When local Whisper is used (no GROQ_API_KEY):
  NLLB-200 translates Tamil segments → English.
  Preserves Tamil original for patient summary generation.
"""
from __future__ import annotations
import asyncio
import re
from app.agents.state import AgentState, TranscriptSegment
from app.core.config import settings

_translator = None
_tokenizer  = None


def get_translator():
    global _translator, _tokenizer
    if _translator is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        _tokenizer   = AutoTokenizer.from_pretrained(settings.NLLB_MODEL)
        _translator  = AutoModelForSeq2SeqLM.from_pretrained(settings.NLLB_MODEL)
    return _translator, _tokenizer


def translate_tamil_to_english(text: str) -> str:
    """Translate Tamil text to English using NLLB-200."""
    if not text.strip():
        return text
    try:
        model, tokenizer = get_translator()
        inputs = tokenizer(
            text, return_tensors="pt",
            src_lang="tam_Taml", max_length=512, truncation=True,
        )
        forced_bos = tokenizer.lang_code_to_id["eng_Latn"]
        outputs = model.generate(**inputs, forced_bos_token_id=forced_bos,
                                 max_new_tokens=512, num_beams=4)
        return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    except Exception:
        return text


def translate_english_to_tamil(text: str) -> str:
    """Translate English clinical plan to Tamil for patient summary."""
    if not text.strip():
        return text
    try:
        model, tokenizer = get_translator()
        inputs = tokenizer(
            text, return_tensors="pt",
            src_lang="eng_Latn", max_length=512, truncation=True,
        )
        forced_bos = tokenizer.lang_code_to_id["tam_Taml"]
        outputs = model.generate(**inputs, forced_bos_token_id=forced_bos,
                                 max_new_tokens=512, num_beams=4)
        return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    except Exception:
        return text


def detect_language_mix(transcript: str, segments: list[TranscriptSegment]) -> str:
    """Detect if transcript is tamil-english, tamil, or english."""
    # Check for Tamil Unicode characters in the transcript
    has_tamil_unicode = bool(re.search(r"[\u0B80-\u0BFF]", transcript))
    # Check segment language tags
    langs = {s["lang"] for s in segments}
    has_tamil_lang = "ta" in langs

    if has_tamil_unicode or has_tamil_lang:
        # If it also has a lot of English, it's mixed
        english_words = len(re.findall(r"\b[a-zA-Z]{3,}\b", transcript))
        total_words   = len(transcript.split())
        if total_words > 0 and english_words / total_words > 0.3:
            return "tamil-english"
        return "tamil"
    return "english"


async def translation_agent_node(state: AgentState) -> dict:
    """
    Handles translation of Tamil/English mixed transcripts.

    If Groq was used for STT: transcript is already clean — pass through directly.
    If local Whisper was used: apply NLLB for Tamil segments.
    """
    segments:     list[TranscriptSegment] = state.get("transcript_segments", [])
    raw_transcript: str                   = state.get("raw_transcript", "")

    language_mix = detect_language_mix(raw_transcript, segments)

    # ── Groq path: transcript already coherent, no NLLB needed ───
    if settings.GROQ_API_KEY:
        # Groq Whisper outputs readable English/mixed text directly
        # Running NLLB on it produces garbage — skip translation entirely
        return {
            "english_transcript": raw_transcript,
            "tamil_original":     raw_transcript if "tamil" in language_mix else None,
            "language_mix":       language_mix,
        }

    # ── Local Whisper path: apply NLLB for Tamil segments ─────────
    if not segments:
        return {
            "english_transcript": raw_transcript,
            "tamil_original":     None,
            "language_mix":       language_mix,
        }

    english_parts = []
    tamil_parts   = []

    for seg in segments:
        text = seg["text"]
        lang = seg["lang"]

        if lang == "ta":
            tamil_parts.append(text)
            translated = await asyncio.to_thread(translate_tamil_to_english, text)
            english_parts.append(translated)
        else:
            english_parts.append(text)

    english_transcript = " ".join(english_parts).strip()
    tamil_original     = " ".join(tamil_parts).strip() if tamil_parts else None

    return {
        "english_transcript": english_transcript,
        "tamil_original":     tamil_original,
        "language_mix":       language_mix,
    }


async def generate_tamil_patient_summary(soap_plan: str) -> str:
    """Translate SOAP Plan section to Tamil for the patient."""
    if not soap_plan:
        return ""
    simplified = (soap_plan
                  .replace("PRN", "as needed")
                  .replace("QD", "once daily")
                  .replace("BID", "twice daily"))
    return await asyncio.to_thread(translate_english_to_tamil, simplified)
