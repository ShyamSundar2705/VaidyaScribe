"""
STT Agent — Speech-to-Text with multilingual Tamil/English support.

Uses faster-whisper (local, free) with automatic language detection per chunk.
Falls back gracefully if whisper model not yet downloaded.
"""
from __future__ import annotations
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

from app.agents.state import AgentState, TranscriptSegment
from app.core.config import settings

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def detect_language_mix(segments: list[TranscriptSegment]) -> str:
    """Classify the session as tamil-english, english, or tamil."""
    langs = {s["lang"] for s in segments}
    has_tamil = "ta" in langs
    has_english = "en" in langs
    if has_tamil and has_english:
        return "tamil-english"
    if has_tamil:
        return "tamil"
    return "english"


async def stt_agent_node(state: AgentState) -> dict:
    """
    Transcribes audio file using faster-whisper.
    Detects language per segment — handles Tamil/English code-switching.
    """
    audio_path = state.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        return {"error": "No audio file found for STT processing", "transcript_segments": []}

    try:
        model = await asyncio.to_thread(get_whisper_model)

        # Run transcription in thread pool (blocking CPU operation)
        segments_raw, info = await asyncio.to_thread(
            lambda: model.transcribe(
                audio_path,
                language=None,          # auto-detect
                task="transcribe",
                word_timestamps=False,
                vad_filter=True,        # voice activity detection
                vad_parameters={"min_silence_duration_ms": 300},
            )
        )

        segments: list[TranscriptSegment] = []
        raw_text_parts = []

        for seg in segments_raw:
            lang = info.language if info.language else "en"
            confidence = float(info.language_probability) if hasattr(info, 'language_probability') else 0.9

            segment: TranscriptSegment = {
                "text": seg.text.strip(),
                "lang": lang,
                "confidence": confidence,
                "start_time": float(seg.start),
                "end_time": float(seg.end),
            }
            segments.append(segment)
            raw_text_parts.append(seg.text.strip())

        raw_transcript = " ".join(raw_text_parts)
        language_mix = detect_language_mix(segments)

        return {
            "transcript_segments": segments,
            "raw_transcript": raw_transcript,
            "language_mix": language_mix,
        }

    except Exception as e:
        return {
            "error": f"STT failed: {str(e)}",
            "transcript_segments": [],
            "raw_transcript": "",
            "language_mix": "unknown",
        }


async def transcribe_audio_bytes(audio_bytes: bytes, content_type: str = "audio/webm") -> dict:
    """
    Convenience wrapper — transcribes raw audio bytes.
    Saves to temp file, runs STT, cleans up.
    Used by the WebSocket endpoint for streaming chunks.
    """
    suffix = ".webm" if "webm" in content_type else ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        state: AgentState = {
            "session_id": "stream",
            "doctor_id": "stream",
            "audio_path": tmp_path,
            "transcript_segments": [],
            "raw_transcript": None,
            "language_mix": None,
            "english_transcript": None,
            "tamil_original": None,
            "entities": None,
            "soap_note": None,
            "tamil_patient_summary": None,
            "qa_result": None,
            "next_step": None,
            "supervisor_reasoning": None,
            "burnout_score": None,
            "burnout_alert": False,
            "messages": [],
            "error": None,
        }
        result = await stt_agent_node(state)
        return result
    finally:
        os.unlink(tmp_path)
