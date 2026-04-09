import { useRef, useState, useCallback } from "react";

export type PipelineStep =
  | "idle" | "recording" | "stt" | "translation"
  | "ner" | "soap" | "qa" | "done" | "error";

export interface PipelineResult {
  session_id: string;
  note_id: string | null;
  transcript: string;
  transcript_original: string;
  language_mix: string;
  entities: Record<string, any> | null;
  soap_note: {
    subjective: string;
    objective: string;
    assessment: string;
    plan: string;
    icd10_codes: string[];
    confidence: number;
  } | null;
  tamil_summary: string | null;
  qa_result: {
    confidence: number;
    flags: Array<{ field: string; claim: string; reason: string }>;
    needs_review: boolean;
    summary: string;
  } | null;
  needs_review: boolean;
  supervisor_reasoning: string | null;
  burnout_alert: boolean;
  error: string | null;
}

// Map backend step names → frontend PipelineStep type
// "init" is sent on WS open — we keep it as "recording" so Stop button stays visible
const STEP_MAP: Record<string, PipelineStep> = {
  init:        "recording",   // ← KEY FIX: "init" must not dismiss Stop button
  stt:         "stt",
  translation: "translation",
  ner:         "ner",
  soap:        "soap",
  qa:          "qa",
  done:        "done",
};

const STEP_LABELS: Record<string, string> = {
  recording:   "Recording in progress — speak now",
  stt:         "Transcribing audio (Whisper)...",
  translation: "Translating Tamil segments (NLLB-200)...",
  ner:         "Extracting medical entities (scispaCy)...",
  soap:        "Generating SOAP note (Llama 3.1)...",
  qa:          "Running hallucination QA check...",
  done:        "Complete",
};

function getWsUrl(token: string): string {
  if (typeof window === "undefined") return "ws://localhost/ws/consult";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host  = window.location.host;
  return `${proto}//${host}/ws/consult?token=${encodeURIComponent(token)}`;
}

export function useAudioCapture(sessionId: string, doctorId: string) {
  const wsRef       = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef   = useRef<MediaStream | null>(null);

  const [step, setStep]                     = useState<PipelineStep>("idle");
  const [stepLabel, setStepLabel]           = useState("");
  const [result, setResult]                 = useState<PipelineResult | null>(null);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [error, setError]                   = useState<string | null>(null);

  const startRecording = useCallback(async () => {
    setError(null);
    setResult(null);
    setLiveTranscript("");

    // Set recording BEFORE opening WebSocket — stays until user clicks Stop
    setStep("recording");
    setStepLabel("Recording in progress — speak now");

    // Read token directly from localStorage — same as api.ts
    // avoids Zustand rehydration timing issue
    let token: string | null = null;
    try {
      const raw = localStorage.getItem("vaidyascribe-auth");
      if (raw) {
        const parsed = JSON.parse(raw);
        token = parsed?.state?.token ?? parsed?.token ?? null;
      }
    } catch { token = null; }
    if (!token) { setError("Not authenticated — please log in again"); setStep("error"); return; }
    const ws = new WebSocket(getWsUrl(token));
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: "start",
        session_id: sessionId,
        doctor_id: doctorId,
      }));
      // Do NOT change step here — keep it as "recording"
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);

        if (msg.type === "progress") {
          const backendStep: string = msg.step || "";

          // Only advance past "recording" for real pipeline steps (after Stop is clicked)
          // "init" = WS just opened, still recording → keep step as "recording"
          if (backendStep === "init") {
            // stay on "recording", just update the label subtly
            return;
          }

          const mappedStep = STEP_MAP[backendStep] ?? "stt";
          setStep(mappedStep);
          setStepLabel(STEP_LABELS[backendStep] || msg.message || "");

          if (msg.data?.partial_transcript) {
            setLiveTranscript(msg.data.partial_transcript);
          }

        } else if (msg.type === "result") {
          setResult(msg.data);
          setStep("done");
          setStepLabel("Complete");

        } else if (msg.type === "error") {
          setError(msg.message || "Pipeline error");
          setStep("error");
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed — check backend is running");
      setStep("error");
    };

    ws.onclose = (ev) => {
      if (ev.code !== 1000 && ev.code !== 1001) {
        console.warn("WebSocket closed unexpectedly", ev.code, ev.reason);
      }
    };

    // Request microphone access
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };

      recorder.start(1000); // send 1-second chunks
    } catch (micErr: any) {
      setError(`Microphone access denied: ${micErr.message}`);
      setStep("error");
      ws.close();
    }
  }, [sessionId, doctorId]);

  const stopRecording = useCallback(() => {
    // Stop mic and MediaRecorder
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());

    // Now advance to stt — pipeline will take over from here
    setStep("stt");
    setStepLabel(STEP_LABELS.stt);

    // Tell backend to process the accumulated audio
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }
  }, []);

  const reset = useCallback(() => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    wsRef.current?.close();
    setStep("idle");
    setStepLabel("");
    setResult(null);
    setLiveTranscript("");
    setError(null);
  }, []);

  return {
    step, stepLabel, result, liveTranscript, error,
    startRecording, stopRecording, reset,
  };
}
