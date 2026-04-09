import { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth.store";

const navItems = [
  { label: "Dashboard",      to: "/",         end: true },
  { label: "Consultation",   to: "/consult",  end: false },
  { label: "Patient history",to: "/patients", end: false },
  { label: "Wellness",       to: "/wellness", end: false },
];

export function Layout({ children }: { children: ReactNode }) {
  const { fullName, doctorId, specialisation, clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => { clearAuth(); navigate("/login"); };

  return (
    <div style={{ display: "flex", minHeight: "100vh",
      fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <aside style={{ width: 220, background: "#0f172a", color: "#e2e8f0",
        display: "flex", flexDirection: "column", padding: "24px 0", flexShrink: 0 }}>
        <div style={{ padding: "0 20px 24px", borderBottom: "1px solid #1e293b" }}>
          <div style={{ fontSize: 10, letterSpacing: "0.12em", color: "#64748b", marginBottom: 6 }}>
            COGNIZANT TECHNOVERSE 2026
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#f1f5f9" }}>VaidyaScribe</div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>Tamil/English AI scribe</div>
        </div>

        <nav style={{ padding: "16px 12px", flex: 1 }}>
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end}
              style={({ isActive }) => ({
                display: "block", padding: "8px 12px", borderRadius: 6, fontSize: 13,
                color: isActive ? "#38bdf8" : "#94a3b8",
                background: isActive ? "#0f2744" : "transparent",
                textDecoration: "none", marginBottom: 2,
              })}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ padding: "16px 20px", borderTop: "1px solid #1e293b" }}>
          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>SIGNED IN AS</div>
          <div style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 500 }}>
            {fullName || doctorId}
          </div>
          {specialisation && (
            <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{specialisation}</div>
          )}
          <div style={{ fontSize: 10, color: "#334155", marginTop: 4 }}>{doctorId}</div>
          <button onClick={handleLogout} style={{ marginTop: 12, width: "100%", padding: "7px 0",
            background: "transparent", color: "#64748b", border: "1px solid #1e293b",
            borderRadius: 7, fontSize: 12, cursor: "pointer" }}>
            Sign out
          </button>
          <div style={{ fontSize: 10, color: "#334155", marginTop: 10 }}>
            LangGraph · Whisper · NLLB · Llama 3.1
          </div>
        </div>
      </aside>

      <main style={{ flex: 1, background: "#f8fafc", overflow: "auto" }}>
        {children}
      </main>
    </div>
  );
}
