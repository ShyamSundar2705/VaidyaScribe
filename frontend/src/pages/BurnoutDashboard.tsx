import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { useAuthStore } from "../store/auth.store";
import { api } from "../api";

function getBurnoutColor(score: number) {
  if (score >= 0.75) return "#ef4444";
  if (score >= 0.5)  return "#f59e0b";
  return "#22c55e";
}
function getBurnoutLabel(score: number) {
  if (score >= 0.75) return "High risk";
  if (score >= 0.5)  return "Moderate";
  return "Healthy";
}

export function BurnoutDashboard() {
  const { doctorId, fullName } = useAuthStore();

  const { data, isLoading } = useQuery({
    queryKey: ["burnout-dashboard"],
    queryFn:  () => api.get("/doctors/me/burnout").then(r => r.data),
    refetchInterval: 60_000,
  });

  const weeks = data?.weeks || [];
  const latest = weeks[0];
  const chartData = [...weeks].reverse().map((w: any) => ({
    name:    w.week?.split("-W")[1] ? `W${w.week.split("-W")[1]}` : w.week,
    burnout: Math.round(w.burnout_score * 100),
    hours:   w.total_audio_hours,
    notes:   w.total_notes,
  }));

  return (
    <div style={{ padding: "32px 32px 64px", maxWidth: 800 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: "#0f172a", margin: "0 0 4px" }}>
          Doctor wellness dashboard
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
          Weekly burnout risk · {fullName || doctorId}
        </p>
      </div>

      {isLoading ? (
        <div style={{ color: "#94a3b8", fontSize: 14 }}>Loading metrics...</div>
      ) : (
        <>
          {latest && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
              gap: 12, marginBottom: 28 }}>
              {[
                { label: "Burnout score", value: `${(latest.burnout_score * 100).toFixed(0)}%`,
                  color: getBurnoutColor(latest.burnout_score) },
                { label: "Audio hours",   value: `${latest.total_audio_hours.toFixed(1)}h`,
                  color: "#0f172a" },
                { label: "Notes generated", value: latest.total_notes, color: "#0f172a" },
                { label: "Status", value: getBurnoutLabel(latest.burnout_score),
                  color: getBurnoutColor(latest.burnout_score) },
              ].map(s => (
                <div key={s.label} style={{ background: "#f8fafc", borderRadius: 10,
                  padding: "14px 16px" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>{s.label}</div>
                  <div style={{ fontSize: 22, fontWeight: 600, color: s.color }}>{s.value}</div>
                </div>
              ))}
            </div>
          )}

          {latest?.burnout_score >= 0.75 && (
            <div style={{ background: "#fef2f2", border: "1px solid #fca5a5",
              borderRadius: 10, padding: "14px 18px", marginBottom: 24,
              fontSize: 13, color: "#991b1b" }}>
              High burnout risk detected this week. Consider scheduling a rest day or
              redistributing consultation load.
            </div>
          )}

          <div style={{ background: "#fff", border: "1px solid #e2e8f0",
            borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "#0f172a", marginBottom: 16 }}>
              Weekly burnout score (%)
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} barSize={40}>
                <XAxis dataKey="name" axisLine={false} tickLine={false}
                  tick={{ fontSize: 12, fill: "#94a3b8" }} />
                <YAxis hide domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                  formatter={(v: number) => [`${v}%`, "burnout score"]}
                />
                <Bar dataKey="burnout" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={getBurnoutColor(entry.burnout / 100)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {weeks.length === 0 && (
            <div style={{ color: "#94a3b8", fontSize: 13, marginTop: 24 }}>
              No data yet — complete some consultations to see burnout metrics.
            </div>
          )}
        </>
      )}
    </div>
  );
}
