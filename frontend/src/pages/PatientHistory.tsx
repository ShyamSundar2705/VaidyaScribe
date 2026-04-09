import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api";

interface NoteRecord {
  note_id: string;
  session_id: string;
  date: string;
  doctor_id: string;
  language: string;
  doctor_approved: boolean;
  qa_confidence: number;
  icd10_codes: string[];
  soap: { subjective: string; objective: string; assessment: string; plan: string };
  tamil_patient_summary: string | null;
}

function QABadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "#16a34a" : pct >= 60 ? "#d97706" : "#dc2626";
  const bg    = pct >= 80 ? "#f0fdf4" : pct >= 60 ? "#fffbeb" : "#fef2f2";
  return (
    <span style={{ background: bg, color, fontSize: 11, fontWeight: 600,
      padding: "2px 8px", borderRadius: 12 }}>
      QA {pct}%
    </span>
  );
}

function NoteCard({ note, expanded, onToggle }: {
  note: NoteRecord; expanded: boolean; onToggle: () => void;
}) {
  const date = new Date(note.date).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 10,
      overflow: "hidden", marginBottom: 10 }}>
      <div onClick={onToggle} style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "14px 16px", cursor: "pointer",
        background: expanded ? "#f8fafc" : "#fff",
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "#0f172a", marginBottom: 3 }}>
            {note.soap.assessment && note.soap.assessment !== "Not documented"
              ? note.soap.assessment
              : "Assessment pending"}
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", display: "flex", gap: 12 }}>
            <span>{date}</span>
            <span>Dr: {note.doctor_id}</span>
            <span style={{ textTransform: "capitalize" }}>{note.language}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
          {note.icd10_codes.filter(c => c !== "To be coded").map(c => (
            <span key={c} style={{ background: "#E6F1FB", color: "#0C447C",
              fontSize: 10, padding: "2px 6px", borderRadius: 10 }}>{c}</span>
          ))}
          <QABadge score={note.qa_confidence} />
          <span style={{
            background: note.doctor_approved ? "#f0fdf4" : "#fff7ed",
            color: note.doctor_approved ? "#16a34a" : "#c2410c",
            fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 12,
          }}>
            {note.doctor_approved ? "Approved" : "Pending"}
          </span>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
            style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
            <path d="M4 6l4 4 4-4" stroke="#94a3b8" strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            style={{ overflow: "hidden" }}>
            <div style={{ padding: "0 16px 16px", borderTop: "1px solid #f1f5f9" }}>
              {[
                { label: "S — Subjective", text: note.soap.subjective, color: "#3b82f6" },
                { label: "O — Objective",  text: note.soap.objective,  color: "#8b5cf6" },
                { label: "A — Assessment", text: note.soap.assessment, color: "#f59e0b" },
                { label: "P — Plan",       text: note.soap.plan,       color: "#10b981" },
              ].map(s => (
                <div key={s.label} style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: s.color,
                    borderLeft: `3px solid ${s.color}`, paddingLeft: 7, marginBottom: 5 }}>
                    {s.label}
                  </div>
                  <div style={{ fontSize: 13, color: "#334155", lineHeight: 1.6,
                    background: "#f8fafc", padding: "8px 12px", borderRadius: 6 }}>
                    {s.text || "Not documented"}
                  </div>
                </div>
              ))}
              {note.tamil_patient_summary && (
                <div style={{ marginTop: 14, background: "#EEEDFE",
                  border: "1px solid #AFA9EC", borderRadius: 8, padding: "10px 14px" }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: "#3C3489", marginBottom: 6 }}>
                    PATIENT SUMMARY (தமிழ்)
                  </div>
                  <div style={{ fontSize: 13, color: "#26215C", lineHeight: 1.8 }}>
                    {note.tamil_patient_summary}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function PatientHistory() {
  const [patientId,   setPatientId]   = useState("");
  const [searchId,    setSearchId]    = useState("");
  const [expandedId,  setExpandedId]  = useState<string | null>(null);
  const [showPending, setShowPending] = useState(false);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["patientNotes", searchId, showPending],
    queryFn:  () => api.get(
      `/patients/${searchId}/notes?approved_only=${!showPending}`
    ).then(r => r.data),
    enabled: !!searchId,
  });

  const handleSearch = () => {
    if (patientId.trim()) {
      setSearchId(patientId.trim());
      setExpandedId(null);
    }
  };

  const notes: NoteRecord[] = data?.notes || [];

  return (
    <div style={{ padding: "32px", maxWidth: 900 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 6px" }}>
          Patient history
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
          Look up all approved consultation notes for a patient by their ID
        </p>
      </div>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <input
          value={patientId}
          onChange={e => setPatientId(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSearch()}
          placeholder="Enter patient ID (e.g. PT-001)"
          style={{ flex: 1, padding: "10px 16px", fontSize: 14,
            border: "1px solid #e2e8f0", borderRadius: 8,
            color: "#0f172a", background: "#fff" }}
        />
        <button onClick={handleSearch} disabled={!patientId.trim()}
          style={{ background: patientId.trim() ? "#0f172a" : "#94a3b8",
            color: "#fff", border: "none", borderRadius: 8,
            padding: "10px 24px", fontSize: 14, fontWeight: 500,
            cursor: patientId.trim() ? "pointer" : "not-allowed" }}>
          {isFetching ? "Loading..." : "Search"}
        </button>
      </div>

      {/* Filter toggle */}
      {searchId && (
        <label style={{ display: "flex", alignItems: "center", gap: 8,
          fontSize: 13, color: "#64748b", cursor: "pointer", marginBottom: 16 }}>
          <input type="checkbox" checked={showPending}
            onChange={e => setShowPending(e.target.checked)}
            style={{ width: 14, height: 14 }} />
          Show pending (unapproved) notes
        </label>
      )}

      {/* Results */}
      {searchId && (
        isLoading ? (
          <div style={{ color: "#94a3b8", fontSize: 14 }}>Loading notes...</div>
        ) : notes.length === 0 ? (
          <div style={{ background: "#fff", border: "1px solid #e2e8f0",
            borderRadius: 10, padding: "32px", textAlign: "center" }}>
            <div style={{ fontSize: 14, color: "#64748b", marginBottom: 6 }}>
              No {showPending ? "" : "approved "}notes found for patient{" "}
              <strong>{searchId}</strong>
            </div>
            {!showPending && (
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
                Notes must be approved by the doctor before appearing here.
                Check "Show pending notes" to see all drafts.
              </div>
            )}
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between",
              alignItems: "center", marginBottom: 14 }}>
              <div style={{ fontSize: 13, color: "#64748b" }}>
                <strong style={{ color: "#0f172a" }}>{notes.length}</strong> consultation
                {notes.length !== 1 ? "s" : ""} for{" "}
                <strong style={{ color: "#0f172a" }}>{searchId}</strong>
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>Most recent first</div>
            </div>
            {notes.map(note => (
              <NoteCard key={note.note_id} note={note}
                expanded={expandedId === note.note_id}
                onToggle={() => setExpandedId(
                  expandedId === note.note_id ? null : note.note_id
                )} />
            ))}
          </>
        )
      )}

      {!searchId && (
        <div style={{ background: "#f8fafc", border: "1px dashed #e2e8f0",
          borderRadius: 10, padding: "40px", textAlign: "center" }}>
          <div style={{ fontSize: 14, color: "#94a3b8" }}>
            Enter a patient ID above to view their consultation history
          </div>
          <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 6 }}>
            Only doctor-approved notes are shown by default
          </div>
        </div>
      )}
    </div>
  );
}
