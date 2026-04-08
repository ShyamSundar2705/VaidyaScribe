import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";
import { useAudioCapture, PipelineStep } from "../hooks/useAudioCapture";
import { ConsentBanner } from "../components/ConsentBanner";
import { useAppStore } from "../store/app.store";

const STEP_ORDER: PipelineStep[] = ["recording", "stt", "translation", "ner", "soap", "qa", "done"];
const STEP_LABELS: Record<PipelineStep, string> = {
  idle:        "Ready",
  recording:   "Recording",
  stt:         "Transcribing",
  translation: "Translating",
  ner:         "Extracting entities",
  soap:        "Generating note",
  qa:          "QA check",
  done:        "Complete",
  error:       "Error",
};

const PULSE_COLORS: Partial<Record<PipelineStep, string>> = {
  recording:   "#ef4444",
  stt:         "#3b82f6",
  translation: "#8b5cf6",
  ner:         "#f59e0b",
  soap:        "#10b981",
  qa:          "#06b6d4",
};

export function ConsultationRoom() {
  const navigate = useNavigate();
  const { doctorId, sessionId, setSessionId, setLastResult, addToHistory } = useAppStore();
  const [activeSessionId, setActiveSessionId] = useState(sessionId || "");
  const [consentDone, setConsentDone] = useState(false);

  const { step, stepLabel, result, liveTranscript, error, startRecording, stopRecording, reset } =
    useAudioCapture(activeSessionId, doctorId);

  // Navigate to note editor when result arrives
  useEffect(() => {
    if (result) {
      setLastResult(result);
      addToHistory(result);
      toast.success("Note generated — review and approve");
      navigate(`/review/${activeSessionId}`);
    }
  }, [result]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const handleConsented = (sid: string) => {
    setActiveSessionId(sid);
    setConsentDone(true);
  };

  const handleStartNew = () => {
    const newId = uuidv4();
    setSessionId(newId);
    setActiveSessionId(newId);
    setConsentDone(false);
    reset();
  };

  const currentStepIndex = STEP_ORDER.indexOf(step);
  const pulseColor = PULSE_COLORS[step] || "#94a3b8";

  return (
    <div style={{ padding: "32px 32px 64px", maxWidth: 800 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 6px" }}>
          Consultation room
        </h1>
        <p style={{ color: "#64748b", fontSize: 14, margin: 0 }}>
          Tamil/English AI scribe — DPDP 2023 compliant · $0 cost
        </p>
      </div>

      {!consentDone && <ConsentBanner onConsented={handleConsented} />}

      {consentDone && (
        <>
          {/* Recording control */}
          <div style={{
            background: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            padding: 24,
            marginBottom: 24,
            display: "flex",
            alignItems: "center",
            gap: 20,
          }}>
            {/* Animated mic indicator */}
            <div style={{ position: "relative", width: 56, height: 56, flexShrink: 0 }}>
              {step === "recording" && (
                <motion.div
                  animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0.1, 0.6] }}
                  transition={{ repeat: Infinity, duration: 1.2 }}
                  style={{
                    position: "absolute", inset: 0, borderRadius: "50%",
                    background: pulseColor, opacity: 0.3,
                  }}
                />
              )}
              <div style={{
                position: "absolute", inset: 6, borderRadius: "50%",
                background: step === "recording" ? "#fef2f2" : step === "done" ? "#f0fdf4" : "#f8fafc",
                display: "flex", alignItems: "center", justifyContent: "center",
                border: `1.5px solid ${step === "recording" ? "#fca5a5" : "#e2e8f0"}`,
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={step === "recording" ? "#ef4444" : "#94a3b8"} strokeWidth="2">
                  <rect x="9" y="2" width="6" height="12" rx="3"/>
                  <path d="M5 10a7 7 0 0 0 14 0"/>
                  <line x1="12" y1="19" x2="12" y2="22"/>
                  <line x1="8" y1="22" x2="16" y2="22"/>
                </svg>
              </div>
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 500, color: "#0f172a", marginBottom: 2 }}>
                {step === "idle" ? "Ready to record" : stepLabel || STEP_LABELS[step]}
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>
                Session: {activeSessionId.slice(0, 8)} · Doctor: {doctorId}
              </div>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              {step === "idle" && (
                <button
                  onClick={startRecording}
                  style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: 8, padding: "10px 22px", fontSize: 14, cursor: "pointer" }}
                >
                  Start recording
                </button>
              )}
              {step === "recording" && (
                <button
                  onClick={stopRecording}
                  style={{ background: "#0f172a", color: "#fff", border: "none", borderRadius: 8, padding: "10px 22px", fontSize: 14, cursor: "pointer" }}
                >
                  Stop & process
                </button>
              )}
              {(step === "done" || step === "error") && (
                <button
                  onClick={handleStartNew}
                  style={{ background: "#fff", color: "#0f172a", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 22px", fontSize: 14, cursor: "pointer" }}
                >
                  New consultation
                </button>
              )}
            </div>
          </div>

          {/* Pipeline progress steps */}
          {step !== "idle" && (
            <div style={{
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "16px 20px",
              marginBottom: 24,
            }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 14, letterSpacing: "0.07em" }}>
                PIPELINE PROGRESS
              </div>
              <div style={{ display: "flex", gap: 0, alignItems: "center" }}>
                {STEP_ORDER.filter(s => s !== "idle" && s !== "error").map((s, i, arr) => {
                  const isDone = currentStepIndex > STEP_ORDER.indexOf(s);
                  const isActive = s === step;
                  const isPending = currentStepIndex < STEP_ORDER.indexOf(s);
                  return (
                    <div key={s} style={{ display: "flex", alignItems: "center", flex: i < arr.length - 1 ? 1 : 0 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                        <motion.div
                          animate={isActive ? { scale: [1, 1.15, 1] } : {}}
                          transition={{ repeat: Infinity, duration: 0.8 }}
                          style={{
                            width: 28, height: 28, borderRadius: "50%",
                            background: isDone ? "#1D9E75" : isActive ? "#3b82f6" : "#f1f5f9",
                            border: `2px solid ${isDone ? "#1D9E75" : isActive ? "#3b82f6" : "#e2e8f0"}`,
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}
                        >
                          {isDone ? (
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          ) : (
                            <div style={{ width: 6, height: 6, borderRadius: "50%", background: isActive ? "#fff" : "#cbd5e1" }} />
                          )}
                        </motion.div>
                        <div style={{ fontSize: 10, color: isActive ? "#3b82f6" : isDone ? "#1D9E75" : "#94a3b8", whiteSpace: "nowrap" }}>
                          {STEP_LABELS[s]}
                        </div>
                      </div>
                      {i < arr.length - 1 && (
                        <div style={{ flex: 1, height: 2, background: isDone ? "#1D9E75" : "#e2e8f0", margin: "0 4px", marginBottom: 20 }} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Live transcript preview */}
          <AnimatePresence>
            {liveTranscript && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 12,
                  padding: 20,
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 8 }}>
                  LIVE TRANSCRIPT
                </div>
                <div style={{ fontSize: 13, color: "#334155", lineHeight: 1.7 }}>
                  {liveTranscript}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}
