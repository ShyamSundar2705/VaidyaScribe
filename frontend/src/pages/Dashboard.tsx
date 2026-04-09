import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../api";
import { useAuthStore } from "../store/auth.store";

interface RecentNote {
  id: string;
  session_id: string;
  created_at: string;
  doctor_approved: boolean;
  qa_confidence: number;
  icd10_codes: string[];
}

interface BurnoutWeek {
  week: string;
  burnout_score: number;
  total_audio_hours: number;
  total_notes: number;
}

function StatCard({ label, value, sub, color = "#0f172a" }: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e8f0",
      borderRadius: 12, padding: "18px 20px" }}>
      <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function BurnoutBar({ score }: { score: number }) {
  const pct   = Math.round(score * 100);
  const color = score >= 0.75 ? "#ef4444" : score >= 0.5 ? "#f59e0b" : "#22c55e";
  const label = score >= 0.75 ? "High risk" : score >= 0.5 ? "Moderate" : "Healthy";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between",
        fontSize: 12, color: "#64748b", marginBottom: 6 }}>
        <span>This week</span>
        <span style={{ color, fontWeight: 600 }}>{label} — {pct}%</span>
      </div>
      <div style={{ height: 8, background: "#f1f5f9", borderRadius: 4, overflow: "hidden" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          style={{ height: "100%", background: color, borderRadius: 4 }}
        />
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate  = useNavigate();
  const { fullName, doctorId } = useAuthStore();

  const { data: recentData } = useQuery({
    queryKey: ["recentNotes"],
    queryFn:  () => api.get("/doctors/me/notes/recent?limit=5").then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: burnoutData } = useQuery({
    queryKey: ["burnout"],
    queryFn:  () => api.get("/doctors/me/burnout").then(r => r.data),
    refetchInterval: 60_000,
  });

  const notes: RecentNote[]  = recentData || [];
  const burnoutWeeks: BurnoutWeek[] = burnoutData?.weeks || [];
  const latestBurnout = burnoutWeeks[0];

  const todayNotes   = notes.filter(n => {
    const d = new Date(n.created_at);
    const today = new Date();
    return d.getDate() === today.getDate() && d.getMonth() === today.getMonth();
  });
  const pendingNotes = notes.filter(n => !n.doctor_approved);
  const approvedToday = todayNotes.filter(n => n.doctor_approved).length;

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  };

  return (
    <div style={{ padding: "32px", maxWidth: 900 }}>
      {/* Greeting */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: "#0f172a", margin: "0 0 4px" }}>
          {greeting()}, {fullName?.split(" ")[0] || "Doctor"}
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
          {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          {" · "}{doctorId}
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 28 }}>
        <StatCard label="TODAY'S CONSULTATIONS" value={todayNotes.length} sub="sessions recorded today" />
        <StatCard label="PENDING APPROVAL" value={pendingNotes.length}
          sub="notes awaiting review"
          color={pendingNotes.length > 0 ? "#d97706" : "#0f172a"} />
        <StatCard label="APPROVED TODAY" value={approvedToday} sub="notes signed off" color="#16a34a" />
        <StatCard
          label="BURNOUT SCORE"
          value={latestBurnout ? `${Math.round(latestBurnout.burnout_score * 100)}%` : "—"}
          sub={latestBurnout ? `${latestBurnout.total_audio_hours.toFixed(1)}h audio this week` : "No data yet"}
          color={latestBurnout?.burnout_score >= 0.75 ? "#ef4444" : latestBurnout?.burnout_score >= 0.5 ? "#d97706" : "#16a34a"}
        />
      </div>

      {/* Burnout bar */}
      {latestBurnout && (
        <div style={{ background: "#fff", border: "1px solid #e2e8f0",
          borderRadius: 12, padding: "18px 20px", marginBottom: 28 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#0f172a", marginBottom: 12 }}>
            Weekly wellness
          </div>
          <BurnoutBar score={latestBurnout.burnout_score} />
          {latestBurnout.burnout_score >= 0.75 && (
            <div style={{ marginTop: 10, padding: "8px 12px", background: "#fef2f2",
              borderRadius: 8, fontSize: 12, color: "#dc2626" }}>
              High burnout risk — consider reducing session load this week.
            </div>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Quick actions */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0",
          borderRadius: 12, padding: "18px 20px" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#0f172a", marginBottom: 14 }}>
            Quick actions
          </div>
          {[
            { label: "New consultation", sub: "Start recording", to: "/consult",
              bg: "#0f172a", color: "#fff" },
            { label: "Patient history", sub: "Search past notes", to: "/patients",
              bg: "#f1f5f9", color: "#0f172a" },
            { label: "Wellness dashboard", sub: "View burnout trends", to: "/wellness",
              bg: "#f1f5f9", color: "#0f172a" },
          ].map(a => (
            <button key={a.label} onClick={() => navigate(a.to)} style={{
              width: "100%", display: "flex", alignItems: "center",
              justifyContent: "space-between", padding: "11px 14px",
              background: a.bg, color: a.color, border: "none",
              borderRadius: 8, cursor: "pointer", marginBottom: 8, textAlign: "left",
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{a.label}</div>
                <div style={{ fontSize: 11, opacity: 0.65, marginTop: 1 }}>{a.sub}</div>
              </div>
              <span style={{ fontSize: 16, opacity: 0.6 }}>→</span>
            </button>
          ))}
        </div>

        {/* Recent notes */}
        <div style={{ background: "#fff", border: "1px solid #e2e8f0",
          borderRadius: 12, padding: "18px 20px" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#0f172a", marginBottom: 14 }}>
            Recent notes
          </div>
          {notes.length === 0 ? (
            <div style={{ fontSize: 13, color: "#94a3b8", textAlign: "center", padding: "20px 0" }}>
              No consultations yet today
            </div>
          ) : (
            notes.slice(0, 5).map(note => {
              const time = new Date(note.created_at).toLocaleTimeString("en-IN", {
                hour: "2-digit", minute: "2-digit",
              });
              return (
                <div key={note.id}
                  onClick={() => navigate(`/review/${note.session_id}`)}
                  style={{ display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 10px", borderRadius: 8, cursor: "pointer",
                    marginBottom: 4, transition: "background .15s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#f8fafc")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: "#0f172a" }}>
                      {(note.icd10_codes || []).join(", ") || "No ICD codes"}
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{time}</div>
                  </div>
                  <span style={{
                    fontSize: 10, padding: "2px 8px", borderRadius: 10,
                    background: note.doctor_approved ? "#f0fdf4" : "#fff7ed",
                    color: note.doctor_approved ? "#16a34a" : "#c2410c",
                    fontWeight: 500,
                  }}>
                    {note.doctor_approved ? "Approved" : "Pending"}
                  </span>
                </div>
              );
            })
          )}
          {pendingNotes.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: "#d97706",
              background: "#fffbeb", padding: "6px 10px", borderRadius: 6 }}>
              {pendingNotes.length} note{pendingNotes.length > 1 ? "s" : ""} pending your approval
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
