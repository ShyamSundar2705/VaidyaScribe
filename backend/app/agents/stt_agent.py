"""
STT Agent — Speech-to-Text with Tamil/English support.

Primary:  Groq Whisper API (free tier — 7200 audio seconds/day, ~2s latency)
Fallback: faster-whisper local (slow on CPU, use only if no Groq key)

Set GROQ_API_KEY in .env to use Groq (strongly recommended for CPU machines).
Leave GROQ_API_KEY empty to use local Whisper.

Model performance on CPU vs Groq:
  local tiny    ~32x real-time  → 30s audio = ~1s      (low accuracy)
  local small   ~6x real-time   → 30s audio = ~5min    (was causing hang)
  local medium  ~2x real-time   → 30s audio = ~15min
  Groq cloud    instant         → 30s audio = ~2s      (large-v3 accuracy)
"""
from __future__ import annotations
import asyncio
import os
import tempfile

from app.agents.state import AgentState, TranscriptSegment
from app.core.config import settings

_whisper_model = None
STT_TIMEOUT_SECONDS = 300  # 5 min hard timeout for local fallback


# ─── Groq Whisper (primary — fast, free) ─────────────────────────

async def _transcribe_groq(audio_path: str) -> tuple[str, str]:
    """
    Transcribe via Groq Whisper API.
    Returns (transcript_text, detected_language).
    Free tier: 7200 audio seconds/day. Get key: console.groq.com (no card).
    """
    from groq import Groq

    client = Groq(api_key=settings.GROQ_API_KEY)

    with open(audio_path, "rb") as f:
        response = await asyncio.to_thread(
            client.audio.transcriptions.create,
            file=(os.path.basename(audio_path), f),
            model="whisper-large-v3",
            response_format="verbose_json",
            language="en",        # force English output — Tamil words are
                                  # phonetically transliterated (vandhu, valikuthu)
                                  # NOT converted to Tamil script (which breaks pipeline)
        )

    text = response.text or ""
    # When forcing language="en", Groq always reports "en"
    # Detect Tamil-English mix from the actual words instead
    lang = "en"
    return text, lang


# ─── Local Whisper fallback ───────────────────────────────────────

def _get_local_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def _run_local_transcribe(audio_path: str) -> tuple[list, object]:
    model = _get_local_model()
    segments_raw, info = model.transcribe(
        audio_path,
        language=None,
        task="transcribe",
        word_timestamps=False,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        beam_size=1,
        best_of=1,
        temperature=0.0,
    )
    return list(segments_raw), info


# ─── Language helpers ─────────────────────────────────────────────

def _detect_mix(segments: list[TranscriptSegment]) -> str:
    langs = {s["lang"] for s in segments}
    if "ta" in langs and "en" in langs:
        return "tamil-english"
    if "ta" in langs:
        return "tamil"
    return "english"


# Tamil words that appear in transliterated Tamil-English speech
_TAMIL_MARKERS = {
    "vandhu", "valikuthu", "sollraanga", "irukku", "sollkiraanga",
    "neram", "kashtam", "konjam", "edukka", "paakanum", "irundhu",
    "venum", "aachu", "illai", "thaane", "theriyum", "sollu",
    "pathu", "nalla", "seri", "enna", "evlo", "engge", "eppadi",
    "romba", "kொnjam", "aama", "illama", "vendam", "kuduthutten",
    "la", "ku", "nu", "nga", "nga", "raanga", "kaanga", "taanga",
}

def _lang_from_text(text: str, detected_lang: str) -> str:
    """
    Detect Tamil-English mix from transliterated words.
    Since we force Groq to output English, Tamil words appear in
    Latin script (vandhu, valikuthu) not Tamil Unicode.
    """
    # Check for Tamil Unicode (local Whisper path)
    tamil_unicode = any("\u0B80" <= c <= "\u0BFF" for c in text)
    if tamil_unicode:
        return "tamil-english"

    # Check for common Tamil transliterations (Groq path)
    words_lower = set(text.lower().split())
    if words_lower & _TAMIL_MARKERS:
        return "tamil-english"

    return "english"


# ─── Main agent node ──────────────────────────────────────────────

async def stt_agent_node(state: AgentState) -> dict:
    audio_path = state.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        return {
            "error": "No audio file found for STT",
            "transcript_segments": [],
            "raw_transcript": "",
            "language_mix": "unknown",
        }

    # ── Try Groq first (fast, free, recommended) ──────────────────
    if settings.GROQ_API_KEY:
        try:
            text, lang = await asyncio.wait_for(
                _transcribe_groq(audio_path),
                timeout=30,  # Groq should respond in <5s
            )
            language_mix = _lang_from_text(text, lang)
            segment: TranscriptSegment = {
                "text":       text,
                "lang":       lang,
                "confidence": 0.95,
                "start_time": 0.0,
                "end_time":   0.0,
            }
            return {
                "transcript_segments": [segment],
                "raw_transcript":      text,
                "language_mix":        language_mix,
            }
        except Exception as e:
            # Groq failed — fall through to local Whisper
            import structlog
            structlog.get_logger().warning("groq_stt_failed_falling_back", error=str(e))

    # ── Local Whisper fallback (slow on CPU) ──────────────────────
    try:
        segments_raw, info = await asyncio.wait_for(
            asyncio.to_thread(_run_local_transcribe, audio_path),
            timeout=STT_TIMEOUT_SECONDS,
        )

        segments: list[TranscriptSegment] = []
        parts = []
        for seg in segments_raw:
            lang = getattr(info, "language", "en") or "en"
            conf = float(getattr(info, "language_probability", 0.9))
            segments.append({
                "text":       seg.text.strip(),
                "lang":       lang,
                "confidence": conf,
                "start_time": float(seg.start),
                "end_time":   float(seg.end),
            })
            parts.append(seg.text.strip())

        return {
            "transcript_segments": segments,
            "raw_transcript":      " ".join(parts),
            "language_mix":        _detect_mix(segments),
        }

    except asyncio.TimeoutError:
        return {
            "error": (
                f"STT timed out after {STT_TIMEOUT_SECONDS}s. "
                "Set GROQ_API_KEY in .env for fast cloud transcription "
                "(free at console.groq.com, no card needed)."
            ),
            "transcript_segments": [],
            "raw_transcript": "",
            "language_mix": "unknown",
        }
    except Exception as e:
        return {
            "error": f"STT failed: {str(e)}",
            "transcript_segments": [],
            "raw_transcript": "",
            "language_mix": "unknown",
        }
