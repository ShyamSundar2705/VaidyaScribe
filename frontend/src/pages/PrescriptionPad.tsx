/**
 * Prescription Pad — generates a printable prescription from an approved SOAP note.
 * Extracts medications and instructions from the Plan section.
 * Doctor can edit before printing.
 */
import { useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth.store";
import toast from "react-hot-toast";

interface PrescriptionItem {
  id:           string;
  drug:         string;
  dose:         string;
  frequency:    string;
  duration:     string;
  instructions: string;
}

// ─── Regex patterns to parse plan text ───────────────────────────
const DRUG_PATTERNS = [
  // "Aspirin 325mg stat" / "Metformin 500mg twice daily for 30 days"
  /([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)?)\s+(\d+(?:\.\d+)?(?:mg|mcg|ml|g|IU))\s*((?:once|twice|thrice|three times|four times)?\s*(?:daily|BD|TID|QID|OD|SOS|stat|PRN|at night|in the morning|at bedtime)?)/gi,
];

function parsePlanToMedications(planText: string): PrescriptionItem[] {
  const meds: PrescriptionItem[] = [];
  const lines = planText.split(/[.\n;]/).map(l => l.trim()).filter(Boolean);

  lines.forEach((line, idx) => {
    // Look for lines that contain a dosage indicator
    if (!/\d+\s*mg|mcg|ml\b/i.test(line) && !/inhaler|tablet|capsule|syrup|drops/i.test(line)) return;

    // Extract drug name — capitalised word before dosage
    const doseMatch = line.match(/(\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units))/i);
    const dose      = doseMatch ? doseMatch[1] : "";

    const beforeDose = doseMatch ? line.slice(0, line.indexOf(doseMatch[0])).trim() : line;
    // Get last 1-2 words before dose as drug name
    const words      = beforeDose.split(/\s+/).filter(Boolean);
    const drug       = words.slice(-2).join(" ").replace(/^[-–•*\d.]+\s*/, "");

    // Frequency patterns
    const freqMatch = line.match(/\b(once|twice|thrice|three times|OD|BD|TID|QID|stat|SOS|PRN|at night|in the morning|at bedtime|daily|every \d+ hours?)/i);
    const frequency = freqMatch ? freqMatch[1] : "as directed";

    // Duration
    const durMatch = line.match(/(?:for\s+)?(\d+\s*(?:days?|weeks?|months?))/i);
    const duration = durMatch ? durMatch[1] : "";

    if (drug.length > 2) {
      meds.push({
        id:           String(idx),
        drug:         drug.trim(),
        dose,
        frequency,
        duration,
        instructions: line.replace(/^\d+\.\s*/, ""),
      });
    }
  });

  return meds;
}

function RxItem({
  item, onChange, onRemove,
}: {
  item: PrescriptionItem;
  onChange: (updated: PrescriptionItem) => void;
  onRemove: () => void;
}) {
  const inp = (field: keyof PrescriptionItem, placeholder: string, width = "100%") => (
    <input
      value={item[field]}
      placeholder={placeholder}
      onChange={e => onChange({ ...item, [field]: e.target.value })}
      style={{ width, padding: "5px 8px", fontSize: 12, border: "1px solid #e2e8f0",
        borderRadius: 6, color: "#0f172a", background: "#fff", boxSizing: "border-box" as const }}
    />
  );

  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 2fr auto",
      gap: 8, alignItems: "center", padding: "8px 12px",
      background: "#f8fafc", borderRadius: 8, marginBottom: 6 }}>
      {inp("drug",         "Drug name")}
      {inp("dose",         "Dose")}
      {inp("frequency",    "Frequency")}
      {inp("duration",     "Duration")}
      {inp("instructions", "Instructions")}
      <button onClick={onRemove} style={{ background: "none", border: "none",
        color: "#ef4444", cursor: "pointer", fontSize: 16, padding: "0 4px" }}>
        ×
      </button>
    </div>
  );
}

export function PrescriptionPad() {
  const navigate  = useNavigate();
  const location  = useLocation();
  const printRef  = useRef<HTMLDivElement>(null);
  const { fullName, doctorId, specialisation } = useAuthStore();

  // Accept note data passed via navigate state
  const noteData = location.state as {
    patientId?:  string;
    assessment?: string;
    plan?:       string;
    language?:   string;
  } | null;

  const [patientId,   setPatientId]   = useState(noteData?.patientId  || "");
  const [patientName, setPatientName] = useState("");
  const [patientAge,  setPatientAge]  = useState("");
  const [diagnosis,   setDiagnosis]   = useState(noteData?.assessment || "");
  const [notes,       setNotes]       = useState("");
  const [meds, setMeds] = useState<PrescriptionItem[]>(() =>
    noteData?.plan ? parsePlanToMedications(noteData.plan) : []
  );

  const addMed = () => setMeds(m => [...m, {
    id: String(Date.now()), drug: "", dose: "", frequency: "once daily", duration: "5 days", instructions: "",
  }]);

  const handlePrint = () => {
    if (!printRef.current) return;
    const w = window.open("", "_blank");
    if (!w) { toast.error("Allow popups to print"); return; }
    w.document.write(`
      <html><head><title>Prescription — VaidyaScribe</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 12pt; color: #1a1a1a; margin: 0; padding: 24px; }
        .header { border-bottom: 2px solid #0C3B6B; padding-bottom: 12px; margin-bottom: 16px; }
        .doctor-name { font-size: 16pt; font-weight: bold; color: #0C3B6B; }
        .doctor-sub { font-size: 10pt; color: #666; margin-top: 2px; }
        .patient-row { display: flex; gap: 32px; background: #f8f8f8; padding: 10px 14px; border-radius: 4px; margin-bottom: 14px; font-size: 11pt; }
        .rx-symbol { font-size: 28pt; color: #0C3B6B; font-style: italic; margin: 8px 0; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
        th { background: #0C3B6B; color: white; padding: 6px 10px; font-size: 10pt; text-align: left; }
        td { padding: 6px 10px; font-size: 11pt; border-bottom: 1px solid #eee; }
        tr:nth-child(even) td { background: #f8f8f8; }
        .diag { font-size: 11pt; margin-bottom: 8px; }
        .notes-section { border-top: 1px dashed #ccc; padding-top: 10px; font-size: 10pt; color: #555; }
        .footer { border-top: 1px solid #ccc; margin-top: 32px; padding-top: 10px; font-size: 9pt; color: #888; display: flex; justify-content: space-between; }
        .sign-line { border-top: 1px solid #333; width: 180px; margin-top: 40px; font-size: 10pt; text-align: center; padding-top: 4px; }
        @media print { body { padding: 0; } }
      </style></head><body>
      ${printRef.current.innerHTML}
      </body></html>
    `);
    w.document.close();
    w.focus();
    setTimeout(() => { w.print(); w.close(); }, 400);
  };

  const today = new Date().toLocaleDateString("en-IN", {
    day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div style={{ padding: "32px", maxWidth: 900 }}>
      <div style={{ display: "flex", justifyContent: "space-between",
        alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 4px" }}>
            Prescription pad
          </h1>
          <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
            Generated from approved SOAP note — edit before printing
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => navigate(-1)} style={{ background: "#f1f5f9",
            color: "#475569", border: "none", borderRadius: 8,
            padding: "10px 18px", fontSize: 13, cursor: "pointer" }}>
            ← Back
          </button>
          <button onClick={handlePrint} style={{ background: "#0f172a", color: "#fff",
            border: "none", borderRadius: 8, padding: "10px 22px",
            fontSize: 13, fontWeight: 500, cursor: "pointer" }}>
            🖨 Print prescription
          </button>
        </div>
      </div>

      {/* Editor */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          { label: "Patient ID", val: patientId, set: setPatientId, ph: "PT-001" },
          { label: "Patient name", val: patientName, set: setPatientName, ph: "Full name" },
          { label: "Age / Sex", val: patientAge, set: setPatientAge, ph: "e.g. 55 years / Male" },
          { label: "Diagnosis", val: diagnosis, set: setDiagnosis, ph: "Primary diagnosis" },
        ].map(f => (
          <div key={f.label}>
            <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>{f.label}</div>
            <input value={f.val} onChange={e => f.set(e.target.value)} placeholder={f.ph}
              style={{ width: "100%", padding: "8px 12px", fontSize: 13,
                border: "1px solid #e2e8f0", borderRadius: 8, color: "#0f172a",
                background: "#fff", boxSizing: "border-box" as const }} />
          </div>
        ))}
      </div>

      {/* Medications */}
      <div style={{ background: "#fff", border: "1px solid #e2e8f0",
        borderRadius: 12, padding: "16px 20px", marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between",
          alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a" }}>
            Medications ({meds.length})
          </div>
          <button onClick={addMed} style={{ background: "#f1f5f9", color: "#475569",
            border: "none", borderRadius: 7, padding: "6px 14px",
            fontSize: 12, cursor: "pointer" }}>
            + Add medication
          </button>
        </div>
        {meds.length === 0 ? (
          <div style={{ fontSize: 13, color: "#94a3b8", textAlign: "center", padding: "16px 0" }}>
            No medications parsed — add manually
          </div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 2fr auto",
              gap: 8, padding: "4px 12px", marginBottom: 4 }}>
              {["Drug name", "Dose", "Frequency", "Duration", "Instructions", ""].map(h => (
                <div key={h} style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600 }}>{h}</div>
              ))}
            </div>
            {meds.map((med, i) => (
              <RxItem key={med.id} item={med}
                onChange={updated => setMeds(m => m.map((x, j) => j === i ? updated : x))}
                onRemove={() => setMeds(m => m.filter((_, j) => j !== i))}
              />
            ))}
          </>
        )}
      </div>

      <div>
        <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>
          Additional instructions / advice
        </div>
        <textarea value={notes} onChange={e => setNotes(e.target.value)}
          placeholder="e.g. Rest for 3 days. Avoid spicy food. Return if symptoms worsen."
          rows={2}
          style={{ width: "100%", padding: "8px 12px", fontSize: 13,
            border: "1px solid #e2e8f0", borderRadius: 8, color: "#0f172a",
            background: "#fff", resize: "vertical", boxSizing: "border-box" as const,
            fontFamily: "inherit" }} />
      </div>

      {/* Hidden print preview */}
      <div ref={printRef} style={{ display: "none" }}>
        <div className="header">
          <div className="doctor-name">Dr. {fullName}</div>
          <div className="doctor-sub">
            {specialisation || "General Physician"} · Reg. No: {doctorId}
          </div>
          <div className="doctor-sub">VaidyaScribe AI-Assisted Clinical Documentation</div>
        </div>

        <div className="patient-row">
          <span><strong>Patient ID:</strong> {patientId || "—"}</span>
          <span><strong>Name:</strong> {patientName || "—"}</span>
          <span><strong>Age/Sex:</strong> {patientAge || "—"}</span>
          <span><strong>Date:</strong> {today}</span>
        </div>

        {diagnosis && (
          <div className="diag">
            <strong>Diagnosis:</strong> {diagnosis}
          </div>
        )}

        <div className="rx-symbol">℞</div>

        {meds.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>#</th><th>Drug</th><th>Dose</th>
                <th>Frequency</th><th>Duration</th><th>Instructions</th>
              </tr>
            </thead>
            <tbody>
              {meds.map((m, i) => (
                <tr key={m.id}>
                  <td>{i + 1}</td>
                  <td><strong>{m.drug}</strong></td>
                  <td>{m.dose}</td>
                  <td>{m.frequency}</td>
                  <td>{m.duration}</td>
                  <td>{m.instructions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {notes && (
          <div className="notes-section">
            <strong>Instructions:</strong> {notes}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div className="sign-line">
            Dr. {fullName}<br />
            <span style={{ fontSize: "9pt", color: "#888" }}>{specialisation || "Physician"}</span>
          </div>
        </div>

        <div className="footer">
          <span>Generated by VaidyaScribe · AI-assisted documentation · Not valid without doctor signature</span>
          <span>{today}</span>
        </div>
      </div>
    </div>
  );
}
