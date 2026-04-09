import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuthStore } from "../store/auth.store";

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
  assessment?: string;
  subjective?: string;
  plan?: string;
}
interface SearchPatient {
  patient_id: string;
  total_notes: number;
  last_seen: string;
  notes: NoteRecord[];
}

function QABadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "#16a34a" : pct >= 60 ? "#d97706" : "#dc2626";
  const bg    = pct >= 80 ? "#f0fdf4" : pct >= 60 ? "#fffbeb" : "#fef2f2";
  return (
    <span style={{ background: bg, color, fontSize: 11, fontWeight: 600,
      padding: "2px 8px", borderRadius: 12 }}>QA {pct}%</span>
  );
}

function NoteCard({ note, patientId, expanded, onToggle }: {
  note: NoteRecord; patientId: string; expanded: boolean; onToggle: () => void;
}) {
  const navigate = useNavigate();
  const date = new Date(note.date).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
  const assessment = note.soap?.assessment || note.assessment || "Assessment pending";

  const handlePrescription = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate("/prescription", { state: {
      patientId:  patientId,
      assessment: note.soap?.assessment || note.assessment || "",
      plan:       note.soap?.plan || note.plan || "",
      language:   note.language,
    }});
  };

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 10,
      overflow: "hidden", marginBottom: 8 }}>
      <div onClick={onToggle} style={{ display: "flex", alignItems: "center",
        gap: 12, padding: "12px 16px", cursor: "pointer",
        background: expanded ? "#f8fafc" : "#fff" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "#0f172a", marginBottom: 2 }}>
            {assessment}
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", display: "flex", gap: 10 }}>
            <span>{date}</span>
            <span style={{ textTransform: "capitalize" }}>{note.language}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 5, alignItems: "center", flexShrink: 0 }}>
          {(note.icd10_codes || []).filter(c => c !== "To be coded").map(c => (
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
          {/* Prescription button — only for approved notes */}
          {note.doctor_approved && (
            <button
              onClick={handlePrescription}
              title="Generate prescription from this note"
              style={{ background: "#f1f5f9", color: "#475569", border: "1px solid #e2e8f0",
                borderRadius: 6, padding: "2px 8px", fontSize: 11, cursor: "pointer",
                fontWeight: 500 }}>
              ℞
            </button>
          )}
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
            style={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform .15s" }}>
            <path d="M4 6l4 4 4-4" stroke="#94a3b8" strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.15 }}
            style={{ overflow: "hidden" }}>
            <div style={{ padding: "0 16px 14px", borderTop: "1px solid #f1f5f9" }}>
              {[
                { label: "S — Subjective", text: note.soap?.subjective || note.subjective, color: "#3b82f6" },
                { label: "O — Objective",  text: note.soap?.objective,  color: "#8b5cf6" },
                { label: "A — Assessment", text: note.soap?.assessment || note.assessment, color: "#f59e0b" },
                { label: "P — Plan",       text: note.soap?.plan || note.plan, color: "#10b981" },
              ].map(s => s.text && s.text !== "Not documented" ? (
                <div key={s.label} style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: s.color,
                    borderLeft: `3px solid ${s.color}`, paddingLeft: 7, marginBottom: 4 }}>
                    {s.label}
                  </div>
                  <div style={{ fontSize: 12, color: "#334155", lineHeight: 1.6,
                    background: "#f8fafc", padding: "7px 10px", borderRadius: 6 }}>
                    {s.text}
                  </div>
                </div>
              ) : null)}
              {note.tamil_patient_summary && (
                <div style={{ marginTop: 12, background: "#EEEDFE",
                  border: "1px solid #AFA9EC", borderRadius: 8, padding: "8px 12px" }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: "#3C3489", marginBottom: 4 }}>
                    PATIENT SUMMARY (தமிழ்)
                  </div>
                  <div style={{ fontSize: 12, color: "#26215C", lineHeight: 1.8 }}>
                    {note.tamil_patient_summary}
                  </div>
                </div>
              )}
              {note.doctor_approved && (
                <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                  <button onClick={handlePrescription} style={{
                    background: "#0f172a", color: "#fff", border: "none",
                    borderRadius: 7, padding: "7px 14px", fontSize: 12,
                    cursor: "pointer", fontWeight: 500,
                  }}>
                    ℞ Generate prescription
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function PatientCard({ patient, onSelectPatient }: {
  patient: SearchPatient; onSelectPatient: (id: string) => void;
}) {
  const navigate = useNavigate();
  const [expanded,     setExpanded]     = useState(false);
  const [expandedNote, setExpandedNote] = useState<string | null>(null);
  const lastSeen = new Date(patient.last_seen).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 12,
      overflow: "hidden", marginBottom: 12, background: "#fff" }}>
      <div style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#E6F1FB",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#185FA5" }}>
            {patient.patient_id.slice(0, 2).toUpperCase()}
          </span>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", marginBottom: 2 }}>
            Patient ID: {patient.patient_id}
          </div>
          <div style={{ fontSize: 12, color: "#64748b" }}>
            {patient.total_notes} consultation{patient.total_notes !== 1 ? "s" : ""} · Last seen: {lastSeen}
          </div>
          {patient.notes[0]?.assessment && (
            <div style={{ fontSize: 12, color: "#475569", marginTop: 3, fontStyle: "italic" }}>
              Most recent: {patient.notes[0].assessment}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button onClick={() => onSelectPatient(patient.patient_id)}
            style={{ background: "#0f172a", color: "#fff", border: "none",
              borderRadius: 7, padding: "7px 14px", fontSize: 12, cursor: "pointer", fontWeight: 500 }}>
            View all notes
          </button>
          <button onClick={() => setExpanded(!expanded)}
            style={{ background: "#f1f5f9", color: "#475569", border: "none",
              borderRadius: 7, padding: "7px 12px", fontSize: 12, cursor: "pointer" }}>
            {expanded ? "Hide" : "Preview"}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            style={{ overflow: "hidden" }}>
            <div style={{ padding: "0 16px 14px", borderTop: "1px solid #f1f5f9" }}>
              {patient.notes.map(note => (
                <NoteCard key={note.note_id} note={note} patientId={patient.patient_id}
                  expanded={expandedNote === note.note_id}
                  onToggle={() => setExpandedNote(
                    expandedNote === note.note_id ? null : note.note_id
                  )} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function PatientHistory() {
  const { doctorId } = useAuthStore();
  const [mode,           setMode]           = useState<"id" | "search">("id");
  const [patientId,      setPatientId]      = useState("");
  const [searchId,       setSearchId]       = useState("");
  const [showPending,    setShowPending]     = useState(false);
  const [expandedId,     setExpandedId]     = useState<string | null>(null);
  const [keyword,        setKeyword]        = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const idQuery = useQuery({
    queryKey: ["patientNotes", searchId, showPending],
    queryFn:  () => api.get(`/patients/${searchId}/notes?approved_only=${!showPending}`).then(r => r.data),
    enabled:  !!searchId && mode === "id",
  });

  const keywordQuery = useQuery({
    queryKey: ["noteSearch", submittedQuery],
    queryFn:  () => api.get(`/notes/search?q=${encodeURIComponent(submittedQuery)}`).then(r => r.data),
    enabled:  !!submittedQuery && mode === "search",
  });

  const handleIdSearch   = () => { if (patientId.trim()) { setSearchId(patientId.trim()); setExpandedId(null); } };
  const handleKwSearch   = () => { if (keyword.trim()) setSubmittedQuery(keyword.trim()); };
  const handleSelectPt   = (pid: string) => { setMode("id"); setPatientId(pid); setSearchId(pid); setExpandedId(null); };

  const idNotes: NoteRecord[]          = idQuery.data?.notes || [];
  const searchResults: SearchPatient[] = keywordQuery.data?.results || [];

  return (
    <div style={{ padding: "32px", maxWidth: 900 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 6px" }}>
          Patient history
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
          Look up past notes by patient ID or search by symptoms · Click ℞ on any approved note to generate a prescription
        </p>
      </div>

      {/* Mode toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20,
        background: "#f1f5f9", padding: 4, borderRadius: 10, width: "fit-content" }}>
        {(["id", "search"] as const).map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            padding: "7px 20px", borderRadius: 7, border: "none", fontSize: 13,
            fontWeight: 500, cursor: "pointer",
            background: mode === m ? "#fff" : "transparent",
            color: mode === m ? "#0f172a" : "#64748b",
            boxShadow: mode === m ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
          }}>
            {m === "id" ? "Search by patient ID" : "Search by symptoms / diagnosis"}
          </button>
        ))}
      </div>

      {/* ID mode */}
      {mode === "id" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
            <input value={patientId} onChange={e => setPatientId(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleIdSearch()}
              placeholder="Enter patient ID (e.g. PT-001)"
              style={{ flex: 1, padding: "10px 16px", fontSize: 14,
                border: "1px solid #e2e8f0", borderRadius: 8, color: "#0f172a", background: "#fff" }} />
            <button onClick={handleIdSearch} disabled={!patientId.trim()}
              style={{ background: patientId.trim() ? "#0f172a" : "#94a3b8", color: "#fff",
                border: "none", borderRadius: 8, padding: "10px 24px", fontSize: 14,
                fontWeight: 500, cursor: patientId.trim() ? "pointer" : "not-allowed" }}>
              {idQuery.isFetching ? "Loading..." : "Search"}
            </button>
          </div>
          {searchId && (
            <label style={{ display: "flex", alignItems: "center", gap: 8,
              fontSize: 12, color: "#64748b", cursor: "pointer", marginBottom: 16 }}>
              <input type="checkbox" checked={showPending}
                onChange={e => setShowPending(e.target.checked)}
                style={{ width: 13, height: 13 }} />
              Show pending (unapproved) notes
            </label>
          )}
          {searchId && (idQuery.isLoading ? (
            <div style={{ color: "#94a3b8", fontSize: 14 }}>Loading...</div>
          ) : idNotes.length === 0 ? (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0",
              borderRadius: 10, padding: "28px", textAlign: "center" }}>
              <div style={{ fontSize: 14, color: "#64748b", marginBottom: 6 }}>
                No {showPending ? "" : "approved "}notes for <strong>{searchId}</strong>
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 14 }}>
                {!showPending ? "Notes need approval before appearing here." : "No consultations found."}
              </div>
              <button onClick={() => { setMode("search"); setKeyword(searchId); }}
                style={{ background: "#f1f5f9", color: "#475569", border: "none",
                  borderRadius: 8, padding: "8px 16px", fontSize: 13, cursor: "pointer" }}>
                Try searching by symptoms instead
              </button>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between",
                marginBottom: 12, fontSize: 13, color: "#64748b" }}>
                <span><strong style={{ color: "#0f172a" }}>{idNotes.length}</strong> consultation
                  {idNotes.length !== 1 ? "s" : ""} for <strong style={{ color: "#0f172a" }}>{searchId}</strong></span>
                <span style={{ fontSize: 11, color: "#94a3b8" }}>Most recent first</span>
              </div>
              {idNotes.map(note => (
                <NoteCard key={note.note_id} note={note} patientId={searchId}
                  expanded={expandedId === note.note_id}
                  onToggle={() => setExpandedId(expandedId === note.note_id ? null : note.note_id)} />
              ))}
            </>
          ))}
          {!searchId && (
            <div style={{ background: "#f8fafc", border: "1px dashed #e2e8f0",
              borderRadius: 10, padding: "36px", textAlign: "center" }}>
              <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 6 }}>
                Enter a patient ID to view their consultation history
              </div>
              <button onClick={() => setMode("search")} style={{ marginTop: 8,
                background: "#0f172a", color: "#fff", border: "none",
                borderRadius: 8, padding: "8px 18px", fontSize: 13, cursor: "pointer" }}>
                Search by symptoms instead
              </button>
            </div>
          )}
        </>
      )}

      {/* Keyword search mode */}
      {mode === "search" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
            <input value={keyword} onChange={e => setKeyword(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleKwSearch()}
              placeholder="Type symptoms, diagnosis, or medication (e.g. chest pain, angina, Metformin)"
              style={{ flex: 1, padding: "10px 16px", fontSize: 14,
                border: "1px solid #e2e8f0", borderRadius: 8, color: "#0f172a", background: "#fff" }} />
            <button onClick={handleKwSearch} disabled={!keyword.trim()}
              style={{ background: keyword.trim() ? "#0f172a" : "#94a3b8", color: "#fff",
                border: "none", borderRadius: 8, padding: "10px 24px", fontSize: 14,
                fontWeight: 500, cursor: keyword.trim() ? "pointer" : "not-allowed" }}>
              {keywordQuery.isFetching ? "Searching..." : "Search"}
            </button>
          </div>
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 20 }}>
            Searches assessment, symptoms, plan, and transcript · ℞ button appears on approved notes
          </div>
          {submittedQuery && (keywordQuery.isLoading ? (
            <div style={{ color: "#94a3b8", fontSize: 14 }}>Searching...</div>
          ) : searchResults.length === 0 ? (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0",
              borderRadius: 10, padding: "28px", textAlign: "center" }}>
              <div style={{ fontSize: 14, color: "#64748b" }}>
                No notes found matching <strong>"{submittedQuery}"</strong>
              </div>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 13, color: "#64748b", marginBottom: 14 }}>
                <strong style={{ color: "#0f172a" }}>{searchResults.length}</strong> patient
                {searchResults.length !== 1 ? "s" : ""} found for <strong style={{ color: "#0f172a" }}>"{submittedQuery}"</strong>
              </div>
              {searchResults.map(patient => (
                <PatientCard key={patient.patient_id} patient={patient}
                  onSelectPatient={handleSelectPt} />
              ))}
            </>
          ))}
          {!submittedQuery && (
            <div style={{ background: "#f8fafc", border: "1px dashed #e2e8f0",
              borderRadius: 10, padding: "36px", textAlign: "center" }}>
              <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 8 }}>Search examples</div>
              {["chest pain", "unstable angina", "Metformin", "asthma", "I20.0"].map(ex => (
                <button key={ex} onClick={() => { setKeyword(ex); setSubmittedQuery(ex); }}
                  style={{ background: "#fff", color: "#475569", border: "1px solid #e2e8f0",
                    borderRadius: 20, padding: "5px 14px", fontSize: 12, cursor: "pointer",
                    margin: "0 4px 6px" }}>
                  {ex}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
