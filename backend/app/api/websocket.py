"""
WebSocket endpoint — real-time audio streaming and pipeline progress.

Flow:
  1. Client sends JSON: {"type":"start","session_id":"...","doctor_id":"..."}
  2. Client streams binary audio chunks (WebM/Opus via MediaRecorder)
  3. Client sends JSON: {"type":"stop"} when recording ends
  4. Server runs full LangGraph pipeline
  5. Server SAVES result to SQLite and returns note_id
  6. Server sends {"type":"result","data":{...,"note_id":"..."}}
"""
import os
import uuid
import tempfile
import json
import structlog

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.graph import run_pipeline
from app.services.note_service import save_consultation_result

log = structlog.get_logger()
ws_router = APIRouter()


@ws_router.websocket("/ws/consult")
async def consultation_websocket(websocket: WebSocket):
    # Authenticate via token query param: ws://host/ws/consult?token=<jwt>
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    from app.core.auth import decode_token
    try:
        payload   = decode_token(token)
        doctor_id = payload.get("sub", "unknown")
    except Exception:
        await websocket.close(code=4003, reason="Invalid token")
        return

    await websocket.accept()
    session_id = None
    audio_chunks: list[bytes] = []

    async def send_progress(step: str, message: str, data: dict | None = None):
        await websocket.send_text(json.dumps({
            "type":    "progress",
            "step":    step,
            "message": message,
            "data":    data or {},
        }))

    try:
        while True:
            msg = await websocket.receive()

            if "text" in msg:
                control  = json.loads(msg["text"])
                msg_type = control.get("type")

                if msg_type == "start":
                    session_id   = control.get("session_id", str(uuid.uuid4()))
                    doctor_id    = control.get("doctor_id", "DR-DEMO-001")
                    audio_chunks = []
                    await send_progress("init", "Recording started — listening...")

                elif msg_type == "stop":
                    if not audio_chunks:
                        await websocket.send_text(json.dumps({
                            "type":    "error",
                            "message": "No audio received — please record again",
                        }))
                        continue

                    # Check minimum audio size — too small = mic not captured
                    total_bytes = sum(len(c) for c in audio_chunks)
                    if total_bytes < 5000:  # < ~5KB means barely any audio
                        await websocket.send_text(json.dumps({
                            "type":    "error",
                            "message": (
                                "Recording too short or microphone not capturing audio. "
                                "Please speak clearly for at least 5 seconds and try again."
                            ),
                        }))
                        audio_chunks = []
                        continue

                    # Write accumulated audio chunks to temp file
                    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                        for chunk in audio_chunks:
                            tmp.write(chunk)
                        audio_path = tmp.name

                    audio_path_ref = audio_path  # keep ref for finally block
                    note_id = None

                    try:
                        # ── Step 1: STT ──────────────────────────────────
                        await send_progress("stt", "Transcribing audio (Whisper/Groq)...")
                        final_state = await run_pipeline(
                            session_id=session_id or str(uuid.uuid4()),
                            doctor_id=doctor_id,
                            audio_path=audio_path,
                        )

                        # ── Step 2-4: send progress for completed steps ───
                        await send_progress("translation", "Translating Tamil segments...")
                        await send_progress("ner",         "Extracting medical entities...")
                        await send_progress("soap",        "Generating SOAP note...")
                        await send_progress("qa",          "Running QA hallucination check...")

                        # ── Step 5: Persist to SQLite ────────────────────
                        if not final_state.get("error"):
                            note_id = await save_consultation_result(final_state)
                            log.info("note_saved", note_id=note_id, session_id=session_id)

                        # ── Step 6: Send result with note_id ─────────────
                        await websocket.send_text(json.dumps({
                            "type": "result",
                            "data": {
                                "session_id":           session_id,
                                "note_id":              note_id,     # ← used for approve endpoint
                                "transcript":           final_state.get("english_transcript", ""),
                                "transcript_original":  final_state.get("raw_transcript", ""),
                                "language_mix":         final_state.get("language_mix", "english"),
                                "entities":             final_state.get("entities"),
                                "soap_note":            final_state.get("soap_note"),
                                "tamil_summary":        final_state.get("tamil_patient_summary"),
                                "qa_result":            final_state.get("qa_result"),
                                "needs_review":         (final_state.get("qa_result") or {}).get("needs_review", True),
                                "supervisor_reasoning": final_state.get("supervisor_reasoning"),
                                "burnout_alert":        final_state.get("burnout_alert", False),
                                "error":                final_state.get("error"),
                            },
                        }))

                    except Exception as e:
                        log.error("pipeline_error", error=str(e), session_id=session_id)
                        await websocket.send_text(json.dumps({
                            "type":    "error",
                            "message": f"Pipeline error: {str(e)}",
                        }))
                    finally:
                        # DPDP compliance: delete audio immediately after processing
                        if os.path.exists(audio_path_ref):
                            os.unlink(audio_path_ref)

            elif "bytes" in msg:
                audio_chunks.append(msg["bytes"])

    except WebSocketDisconnect:
        log.info("websocket_disconnected", session_id=session_id)
    except Exception as e:
        log.error("websocket_error", error=str(e))
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
