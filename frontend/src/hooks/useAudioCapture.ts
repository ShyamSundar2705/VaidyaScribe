import { useRef, useState, useCallback } from "react";

export type PipelineStep =
  | "idle" | "recording" | "stt" | "translation"
  | "ner" | "soap" | "qa" | "done" | "error";

export interface PipelineResult {
  session_id: string;
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

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const STEP_LABELS: Record<string, string> = {
  init:        "Recording started — listening...",
  stt:         "Transcribing audio (Whisper)...",
  translation: "Translating Tamil segments (NLLB-200)...",
  ner:         "Extracting medical entities (scispaCy)...",
  soap:        "Generating SOAP note (Llama 3.1)...",
  qa:          "Running hallucination QA check...",
};

export function useAudioCapture(sessionId: string, doctorId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [step, setStep] = useState<PipelineStep>("idle");
  const [stepLabel, setStepLabel] = useState("");
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const startRecording = useCallback(async () => {
    setError(null);
    setResult(null);
    setLiveTranscript("");
    setStep("recording");
    setStepLabel("Recording — speak clearly...");

    // Open WebSocket
    const ws = new WebSocket(`${WS_URL}/ws/consult`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "start", session_id: sessionId, doctor_id: doctorId }));
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "progress") {
        setStep(msg.step as PipelineStep);
        setStepLabel(STEP_LABELS[msg.step] || msg.message);
        if (msg.data?.partial_transcript) {
          setLiveTranscript(msg.data.partial_transcript);
        }
      } else if (msg.type === "result") {
        setResult(msg.data);
        setStep("done");
        setStepLabel("Complete");
      } else if (msg.type === "error") {
        setError(msg.message);
        setStep("error");
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
      setStep("error");
    };

    // Get microphone
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
        ws.send(e.data);
      }
    };

    recorder.start(1000); // send 1-second chunks
  }, [sessionId, doctorId]);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setStep("stt");
    setStepLabel(STEP_LABELS.stt);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }
  }, []);

  const reset = useCallback(() => {
    wsRef.current?.close();
    setStep("idle");
    setStepLabel("");
    setResult(null);
    setLiveTranscript("");
    setError(null);
  }, []);

  return { step, stepLabel, result, liveTranscript, error, startRecording, stopRecording, reset };
}
