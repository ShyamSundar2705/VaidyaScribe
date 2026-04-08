"""
WebSocket endpoint — real-time audio streaming and pipeline progress.

Flow:
  1. Client sends JSON: {"type":"start","session_id":"...","doctor_id":"..."}
  2. Client streams binary audio chunks (WebM/Opus via MediaRecorder)
  3. Client sends JSON: {"type":"stop"} when recording ends
  4. Server runs full 5-agent pipeline, streaming progress events
  5. Server sends {"type":"result","data":{...}} when complete
"""
import os
import uuid
import tempfile
import json
import structlog

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.graph import run_pipeline

log = structlog.get_logger()
ws_router = APIRouter()


@ws_router.websocket("/ws/consult")
async def consultation_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    doctor_id = "demo_doctor"
    audio_chunks: list[bytes] = []

    async def send_progress(step: str, message: str, data: dict | None = None):
        await websocket.send_text(json.dumps({
            "type": "progress",
            "step": step,
            "message": message,
            "data": data or {},
        }))

    try:
        while True:
            # Receive either text (control) or binary (audio)
            msg = await websocket.receive()

            if "text" in msg:
                control = json.loads(msg["text"])
                msg_type = control.get("type")

                if msg_type == "start":
                    session_id = control.get("session_id", str(uuid.uuid4()))
                    doctor_id = control.get("doctor_id", "demo_doctor")
                    audio_chunks = []
                    await send_progress("init", "Recording started — listening...")

                elif msg_type == "stop":
                    if not audio_chunks:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "No audio received",
                        }))
                        continue

                    # Save accumulated audio to temp file
                    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                        for chunk in audio_chunks:
                            tmp.write(chunk)
                        audio_path = tmp.name

                    await send_progress("stt", "Transcribing audio (Whisper)...")

                    try:
                        # Run the full LangGraph pipeline
                        # Pipeline emits progress via state transitions
                        final_state = await run_pipeline(
                            session_id=session_id or str(uuid.uuid4()),
                            doctor_id=doctor_id,
                            audio_path=audio_path,
                        )

                        await send_progress("translation", "Translating Tamil segments...")
                        await send_progress("ner", "Extracting medical entities...")
                        await send_progress("soap", "Generating SOAP note...")
                        await send_progress("qa", "Running QA hallucination check...")

                        # Send the full result
                        await websocket.send_text(json.dumps({
                            "type": "result",
                            "data": {
                                "session_id": session_id,
                                "transcript": final_state.get("english_transcript", ""),
                                "transcript_original": final_state.get("raw_transcript", ""),
                                "language_mix": final_state.get("language_mix", "english"),
                                "entities": final_state.get("entities"),
                                "soap_note": final_state.get("soap_note"),
                                "tamil_summary": final_state.get("tamil_patient_summary"),
                                "qa_result": final_state.get("qa_result"),
                                "needs_review": final_state.get("qa_result", {}).get("needs_review", True),
                                "supervisor_reasoning": final_state.get("supervisor_reasoning"),
                                "burnout_alert": final_state.get("burnout_alert", False),
                                "error": final_state.get("error"),
                            }
                        }))

                    except Exception as e:
                        log.error("pipeline_error", error=str(e))
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Pipeline error: {str(e)}",
                        }))
                    finally:
                        if os.path.exists(audio_path):
                            os.unlink(audio_path)  # DPDP: delete audio after processing

            elif "bytes" in msg:
                # Accumulate audio chunks
                audio_chunks.append(msg["bytes"])

    except WebSocketDisconnect:
        log.info("websocket_disconnected", session_id=session_id)
    except Exception as e:
        log.error("websocket_error", error=str(e))
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
