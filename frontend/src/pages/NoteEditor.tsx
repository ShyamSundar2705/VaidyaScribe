import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../api";
import toast from "react-hot-toast";
import { useAppStore } from "../store/app.store";
import { useAuthStore } from "../store/auth.store";


function QAFlag({ flag }: { flag: { field: string; claim: string; reason: string } }) {
  return (
    <div style={{
      background: "#fffbeb",
      border: "1px solid #fcd34d",
      borderRadius: 8,
      padding: "8px 12px",
      marginBottom: 6,
      fontSize: 12,
    }}>
      <div style={{ fontWeight: 500, color: "#92400e", marginBottom: 2 }}>
        {flag.field.toUpperCase()} — review required
      </div>
      <div style={{ color: "#78350f", lineHeight: 1.5 }}>{flag.claim}</div>
      <div style={{ color: "#a16207", marginTop: 2, fontStyle: "italic" }}>{flag.reason}</div>
    </div>
  );
}

function SOAPSection({
  title, value, onChange, flagged,
}: {
  title: string; value: string; onChange: (v: string) => void; flagged?: boolean;
}) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 11, fontWeight: 600, letterSpacing: "0.07em",
        color: flagged ? "#d97706" : "#3b82f6",
        borderLeft: `3px solid ${flagged ? "#fcd34d" : "#3b82f6"}`,
        paddingLeft: 8, marginBottom: 6,
      }}>
        {title} {flagged && "⚠ flagged"}
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        style={{
          width: "100%",
          padding: "10px 14px",
          fontSize: 13,
          lineHeight: 1.7,
          border: `1px solid ${flagged ? "#fcd34d" : "#e2e8f0"}`,
          borderRadius: 8,
          background: flagged ? "#fffbeb" : "#fff",
          color: "#0f172a",
          resize: "vertical",
          fontFamily: "inherit",
          boxSizing: "border-box",
        }}
      />
    </div>
  );
}

export function NoteEditor() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { lastResult } = useAppStore();
  const { doctorId } = useAuthStore();
  const [approving, setApproving] = useState(false);

  // Editable SOAP state
  const [soap, setSoap] = useState({
    subjective: lastResult?.soap_note?.subjective || "",
    objective: lastResult?.soap_note?.objective || "",
    assessment: lastResult?.soap_note?.assessment || "",
    plan: lastResult?.soap_note?.plan || "",
  });
  const [originalSoap] = useState({ ...soap });
  const isEdited = JSON.stringify(soap) !== JSON.stringify(originalSoap);

  const qa = lastResult?.qa_result;
  const flaggedSections = new Set(qa?.flags?.map(f => f.field) || []);

  const handleApprove = async () => {
    if (!lastResult) return;
    setApproving(true);
    try {
      const noteId = lastResult?.note_id || sessionId;
      await api.post(`/notes/${noteId}/approve`, {
        note_id: noteId,
        doctor_id: doctorId,
        ...soap,
        edited: isEdited,
      });
      toast.success("Note approved and saved");
      navigate("/");
    } catch {
      toast.error("Approval failed");
    } finally {
      setApproving(false);
    }
  };

  if (!lastResult) {
    return (
      <div style={{ padding: 32, color: "#64748b" }}>
        No note found. <button onClick={() => navigate("/")} style={{ color: "#3b82f6", background: "none", border: "none", cursor: "pointer" }}>Go back</button>
      </div>
    );
  }

  return (
    <div style={{ padding: "32px 32px 80px", maxWidth: 900 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "#0f172a", margin: "0 0 4px" }}>
            Review SOAP note
          </h1>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>
            Session: {sessionId?.slice(0, 8)} ·
            Language: {lastResult.language_mix} ·
            QA confidence: {qa ? (qa.confidence * 100).toFixed(0) + "%" : "—"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          {lastResult?.doctor_approved === true || soap.assessment ? (
            <button
              onClick={() => navigate("/prescription", { state: {
                patientId:  lastResult?.session_id,
                assessment: soap.assessment,
                plan:       soap.plan,
                language:   lastResult?.language_mix,
              }})}
              style={{ background: "#fff", color: "#0f172a",
                border: "1px solid #e2e8f0", borderRadius: 10,
                padding: "12px 18px", fontSize: 13, cursor: "pointer" }}
            >
              ℞ Prescription
            </button>
          ) : null}
          <button
            onClick={handleApprove}
            disabled={approving}
            style={{
              background: qa?.needs_review ? "#f59e0b" : "#1D9E75",
              color: "#fff", border: "none", borderRadius: 10,
              padding: "12px 28px", fontSize: 14, fontWeight: 500,
              cursor: approving ? "not-allowed" : "pointer",
            }}
          >
            {approving ? "Saving..." : qa?.needs_review ? "Approve with flags ↗" : "Approve ↗"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 24 }}>
        {/* Left — SOAP editor */}
        <div>
          {/* QA summary banner */}
          {qa && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                background: qa.needs_review ? "#fffbeb" : "#f0fdf4",
                border: `1px solid ${qa.needs_review ? "#fcd34d" : "#86efac"}`,
                borderRadius: 10,
                padding: "10px 16px",
                marginBottom: 20,
                fontSize: 12,
              }}
            >
              <div style={{ fontWeight: 500, color: qa.needs_review ? "#92400e" : "#14532d", marginBottom: 2 }}>
                {qa.needs_review ? "⚠ QA review required" : "✓ QA passed"}
              </div>
              <div style={{ color: qa.needs_review ? "#78350f" : "#166534" }}>{qa.summary}</div>
            </motion.div>
          )}

          {/* QA flags */}
          {qa?.flags && qa.flags.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 8 }}>
                FLAGGED CLAIMS — verify before approving
              </div>
              {qa.flags.map((f, i) => <QAFlag key={i} flag={f} />)}
            </div>
          )}

          <SOAPSection
            title="S — Subjective"
            value={soap.subjective}
            onChange={(v) => setSoap(s => ({ ...s, subjective: v }))}
            flagged={flaggedSections.has("subjective")}
          />
          <SOAPSection
            title="O — Objective"
            value={soap.objective}
            onChange={(v) => setSoap(s => ({ ...s, objective: v }))}
            flagged={flaggedSections.has("objective")}
          />
          <SOAPSection
            title="A — Assessment"
            value={soap.assessment}
            onChange={(v) => setSoap(s => ({ ...s, assessment: v }))}
            flagged={flaggedSections.has("assessment")}
          />
          <SOAPSection
            title="P — Plan"
            value={soap.plan}
            onChange={(v) => setSoap(s => ({ ...s, plan: v }))}
            flagged={flaggedSections.has("plan")}
          />

          {isEdited && (
            <div style={{ fontSize: 11, color: "#f59e0b", marginTop: -8, marginBottom: 16 }}>
              Note has been edited — changes will be saved on approval
            </div>
          )}
        </div>

        {/* Right — Sidebar: transcript, entities, Tamil summary */}
        <div>
          {/* ICD-10 codes */}
          {(lastResult.soap_note?.icd10_codes?.length ?? 0) > 0 && (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 8 }}>ICD-10 CODES</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(lastResult.soap_note?.icd10_codes ?? []).map(c => (
                  <span key={c} style={{ background: "#E6F1FB", color: "#0C447C", fontSize: 11, padding: "2px 8px", borderRadius: 12 }}>
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tamil patient summary */}
          {lastResult.tamil_summary && (
            <div style={{ background: "#EEEDFE", border: "1px solid #AFA9EC", borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "#3C3489", marginBottom: 8 }}>
                PATIENT SUMMARY (தமிழ்)
              </div>
              <div style={{ fontSize: 13, color: "#26215C", lineHeight: 1.8 }}>
                {lastResult.tamil_summary}
              </div>
            </div>
          )}

          {/* Original transcript */}
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 8 }}>TRANSCRIPT</div>
            <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.7, maxHeight: 200, overflow: "auto" }}>
              {lastResult.transcript || "No transcript available"}
            </div>
          </div>

          {/* Entities */}
          {lastResult.entities && (
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: "#94a3b8", marginBottom: 8 }}>EXTRACTED ENTITIES</div>
              {lastResult.entities.symptoms?.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 3 }}>SYMPTOMS</div>
                  {lastResult.entities.symptoms.map((s: string) => (
                    <span key={s} style={{ display: "inline-block", background: "#fee2e2", color: "#991b1b", fontSize: 10, padding: "1px 6px", borderRadius: 10, marginRight: 4, marginBottom: 3 }}>{s}</span>
                  ))}
                </div>
              )}
              {lastResult.entities.vitals && Object.keys(lastResult.entities.vitals).length > 0 && (
                <div>
                  <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 3 }}>VITALS</div>
                  {Object.entries(lastResult.entities.vitals).map(([k, v]) => (
                    <div key={k} style={{ fontSize: 11, color: "#475569" }}>{k}: {String(v)}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
