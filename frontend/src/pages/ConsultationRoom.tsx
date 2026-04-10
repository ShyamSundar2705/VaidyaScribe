import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAudioCapture, PipelineStep } from "../hooks/useAudioCapture";
import { ConsentBanner } from "../components/ConsentBanner";
import { useAppStore } from "../store/app.store";
import { useAuthStore } from "../store/auth.store";

const STEP_ORDER: PipelineStep[] = [
  "recording", "stt", "translation", "ner", "soap", "qa", "done",
];

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

// Polyfill for crypto.randomUUID — works on HTTP (EC2) and HTTPS
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts (plain HTTP)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

export function ConsultationRoom() {
  const navigate = useNavigate();
  const { sessionId, setSessionId, setLastResult, addToHistory } = useAppStore();
  const { doctorId } = useAuthStore();
  const [activeSessionId, setActiveSessionId] = useState(sessionId || "");
  const [consentDone, setConsentDone] = useState(false);

  const {
    step, stepLabel, result, liveTranscript, error,
    startRecording, stopRecording, reset,
  } = useAudioCapture(activeSessionId, doctorId);

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
    const newId = generateUUID();
    setSessionId(newId);
    setActiveSessionId(newId);
    setConsentDone(false);
    reset();
  };

  const currentStepIndex = STEP_ORDER.indexOf(step);
  const isRecording = step === "recording";
  const isProcessing = !["idle", "recording", "done", "error"].includes(step);
  const isDone = step === "done";
  const isError = step === "error";

  return (
    <div style={{ padding: "32px", maxWidth: 800 }}>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 6px" }}>
          Consultation room
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
          Tamil/English AI scribe — DPDP 2023 compliant · $0 cost
        </p>
      </div>

      {/* Consent step */}
      {!consentDone && (
        <ConsentBanner onConsented={handleConsented} />
      )}

      {/* Main recording UI — only shown after consent */}
      {consentDone && (
        <>
          {/* ── BIG recording control card ────────────────────── */}
          <div style={{
            background: "#fff",
            border: `2px solid ${isRecording ? "#fca5a5" : isProcessing ? "#93c5fd" : isDone ? "#86efac" : "#e2e8f0"}`,
            borderRadius: 16,
            padding: "28px 28px",
            marginBottom: 20,
          }}>

            {/* Status row */}
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>

              {/* Pulsing mic indicator */}
              <div style={{ position: "relative", width: 52, height: 52, flexShrink: 0 }}>
                {isRecording && (
                  <motion.div
                    animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0.1, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1.0 }}
                    style={{
                      position: "absolute", inset: -4, borderRadius: "50%",
                      background: "#ef4444",
                    }}
                  />
                )}
                <div style={{
                  position: "absolute", inset: 0, borderRadius: "50%",
                  background: isRecording ? "#fef2f2" : isProcessing ? "#eff6ff" : "#f8fafc",
                  border: `2px solid ${isRecording ? "#fca5a5" : "#e2e8f0"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                    stroke={isRecording ? "#ef4444" : isProcessing ? "#3b82f6" : "#94a3b8"}
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="9" y="2" width="6" height="12" rx="3"/>
                    <path d="M5 10a7 7 0 0 0 14 0"/>
                    <line x1="12" y1="19" x2="12" y2="22"/>
                    <line x1="8" y1="22" x2="16" y2="22"/>
                  </svg>
                </div>
              </div>

              {/* Status text */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: "#0f172a", marginBottom: 3 }}>
                  {isRecording  && "Recording in progress — speak now"}
                  {isProcessing && (stepLabel || "Processing...")}
                  {isDone       && "Processing complete"}
                  {isError      && "An error occurred"}
                  {step === "idle" && "Ready to start"}
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>
                  Session: {activeSessionId.slice(0, 8)} · Doctor: {doctorId}
                </div>
              </div>

              {/* Live recording indicator badge */}
              {isRecording && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                  background: "#fef2f2", border: "1px solid #fca5a5",
                  borderRadius: 20, padding: "4px 12px",
                  fontSize: 12, fontWeight: 600, color: "#dc2626",
                  flexShrink: 0,
                }}>
                  <motion.div
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ repeat: Infinity, duration: 1.0 }}
                    style={{ width: 8, height: 8, borderRadius: "50%", background: "#dc2626" }}
                  />
                  LIVE
                </div>
              )}
            </div>

            {/* ── ACTION BUTTONS — always clearly visible ──────── */}
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>

              {/* Start button — shown when idle */}
              {step === "idle" && (
                <button
                  onClick={startRecording}
                  style={{
                    flex: 1, minWidth: 160,
                    background: "#ef4444", color: "#fff",
                    border: "none", borderRadius: 10,
                    padding: "14px 28px", fontSize: 15, fontWeight: 600,
                    cursor: "pointer", letterSpacing: "0.01em",
                  }}
                >
                  Start recording
                </button>
              )}

              {/* STOP button — shown when recording */}
              {isRecording && (
                <button
                  onClick={stopRecording}
                  style={{
                    flex: 1, minWidth: 200,
                    background: "#0f172a", color: "#fff",
                    border: "none", borderRadius: 10,
                    padding: "14px 28px", fontSize: 15, fontWeight: 600,
                    cursor: "pointer", letterSpacing: "0.01em",
                  }}
                >
                  Stop & generate note
                </button>
              )}

              {/* Processing indicator — shown during pipeline */}
              {isProcessing && (
                <div style={{
                  flex: 1, minWidth: 200,
                  background: "#eff6ff", color: "#1d4ed8",
                  border: "1px solid #bfdbfe", borderRadius: 10,
                  padding: "14px 28px", fontSize: 14, fontWeight: 500,
                  display: "flex", alignItems: "center", gap: 10,
                }}>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                    style={{
                      width: 16, height: 16, borderRadius: "50%",
                      border: "2px solid #bfdbfe",
                      borderTopColor: "#3b82f6",
                      flexShrink: 0,
                    }}
                  />
                  {stepLabel || "Processing..."}
                </div>
              )}

              {/* New consultation — shown when done or error */}
              {(isDone || isError) && (
                <button
                  onClick={handleStartNew}
                  style={{
                    background: "#fff", color: "#0f172a",
                    border: "1px solid #e2e8f0", borderRadius: 10,
                    padding: "14px 24px", fontSize: 14, fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  New consultation
                </button>
              )}
            </div>

            {/* Hint text shown while recording */}
            {isRecording && (
              <div style={{
                marginTop: 14, fontSize: 12, color: "#94a3b8",
                padding: "8px 12px", background: "#f8fafc",
                borderRadius: 6, lineHeight: 1.5,
              }}>
                Speak your consultation. Mix Tamil and English naturally.
                Click <strong style={{ color: "#0f172a" }}>Stop & generate note</strong> when finished.
              </div>
            )}
          </div>

          {/* ── Pipeline progress steps ───────────────────────── */}
          {step !== "idle" && (
            <div style={{
              background: "#fff", border: "1px solid #e2e8f0",
              borderRadius: 12, padding: "16px 20px", marginBottom: 20,
            }}>
              <div style={{
                fontSize: 10, fontWeight: 600, color: "#94a3b8",
                letterSpacing: "0.08em", marginBottom: 14,
              }}>
                PIPELINE PROGRESS
              </div>
              <div style={{ display: "flex", alignItems: "center" }}>
                {STEP_ORDER.map((s, i) => {
                  const sDone    = currentStepIndex > i;
                  const sActive  = s === step;
                  const sPending = currentStepIndex < i;
                  return (
                    <div key={s} style={{ display: "flex", alignItems: "center", flex: i < STEP_ORDER.length - 1 ? 1 : 0 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}>
                        <motion.div
                          animate={sActive ? { scale: [1, 1.2, 1] } : {}}
                          transition={{ repeat: Infinity, duration: 0.7 }}
                          style={{
                            width: 26, height: 26, borderRadius: "50%",
                            background: sDone ? "#1D9E75" : sActive ? "#3b82f6" : "#f1f5f9",
                            border: `2px solid ${sDone ? "#1D9E75" : sActive ? "#3b82f6" : "#e2e8f0"}`,
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}
                        >
                          {sDone ? (
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          ) : (
                            <div style={{
                              width: 7, height: 7, borderRadius: "50%",
                              background: sActive ? "#fff" : "#cbd5e1",
                            }} />
                          )}
                        </motion.div>
                        <div style={{
                          fontSize: 10,
                          color: sActive ? "#3b82f6" : sDone ? "#1D9E75" : "#94a3b8",
                          whiteSpace: "nowrap",
                        }}>
                          {STEP_LABELS[s]}
                        </div>
                      </div>
                      {i < STEP_ORDER.length - 1 && (
                        <div style={{
                          flex: 1, height: 2, margin: "0 4px", marginBottom: 18,
                          background: sDone ? "#1D9E75" : "#e2e8f0",
                        }} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Live transcript preview ───────────────────────── */}
          <AnimatePresence>
            {liveTranscript && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  background: "#f8fafc", border: "1px solid #e2e8f0",
                  borderRadius: 12, padding: 20,
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 600, color: "#94a3b8", marginBottom: 8, letterSpacing: "0.08em" }}>
                  LIVE TRANSCRIPT
                </div>
                <div style={{ fontSize: 13, color: "#334155", lineHeight: 1.7 }}>
                  {liveTranscript}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error display */}
          {isError && error && (
            <div style={{
              background: "#fef2f2", border: "1px solid #fca5a5",
              borderRadius: 10, padding: "14px 18px", marginTop: 16,
              fontSize: 13, color: "#dc2626",
            }}>
              {error}
            </div>
          )}
        </>
      )}
    </div>
  );
}
