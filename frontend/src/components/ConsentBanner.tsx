import { useState } from "react";
import { api } from "../api";
import toast from "react-hot-toast";

export function ConsentBanner({ onConsented }: { onConsented: (sessionId: string) => void }) {
  const [patientId,    setPatientId]    = useState("");
  const [consentGiven, setConsentGiven] = useState(false);
  const [loading,      setLoading]      = useState(false);

  const handleConsent = async () => {
    if (!consentGiven) { toast.error("Patient consent must be given before recording"); return; }
    setLoading(true);
    try {
      const { data } = await api.post("/sessions/consent", {
        patient_id:    patientId || null,
        consent_given: true,
      });
      onConsented(data.session_id);
      toast.success("Consent recorded — you may now start recording");
    } catch (err: any) {
      toast.error(`Failed to record consent: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: "#fff", border: "1px solid #e2e8f0",
      borderRadius: 12, padding: "20px 24px", marginBottom: 24,
    }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: "#0f172a", marginBottom: 4 }}>
        Patient consent — DPDP 2023
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginBottom: 16, lineHeight: 1.6 }}>
        Audio is transcribed locally and deleted immediately after processing.
        No audio is stored or transmitted to external servers.
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Patient ID (optional)</div>
          <input value={patientId} onChange={e => setPatientId(e.target.value)}
            placeholder="PT-XXXX"
            style={{ width: "100%", padding: "8px 12px", fontSize: 13,
              borderRadius: 8, border: "1px solid #e2e8f0", color: "#0f172a", background: "#fff" }} />
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8,
          cursor: "pointer", paddingBottom: 8 }}>
          <input type="checkbox" checked={consentGiven}
            onChange={e => setConsentGiven(e.target.checked)}
            style={{ width: 16, height: 16, cursor: "pointer" }} />
          <span style={{ fontSize: 13, color: "#334155" }}>
            Patient has given explicit verbal consent to AI transcription
          </span>
        </label>
        <button onClick={handleConsent} disabled={!consentGiven || loading} style={{
          background: consentGiven ? "#0f172a" : "#94a3b8", color: "#fff",
          border: "none", borderRadius: 8, padding: "9px 20px",
          fontSize: 13, cursor: consentGiven && !loading ? "pointer" : "not-allowed",
          minWidth: 140, marginBottom: 8,
        }}>
          {loading ? "Saving..." : "Confirm consent ↗"}
        </button>
      </div>
    </div>
  );
}
