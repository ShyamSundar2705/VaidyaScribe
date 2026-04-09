import { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAppStore } from "../store/app.store";

const navItems = [
  { label: "Consultation", to: "/" },
  { label: "Patient history", to: "/patients" },
  { label: "Wellness", to: "/wellness" },
];

export function Layout({ children }: { children: ReactNode }) {
  const { doctorId } = useAppStore();

  return (
    <div style={{ display: "flex", minHeight: "100vh",
      fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <aside style={{
        width: 220, background: "#0f172a", color: "#e2e8f0",
        display: "flex", flexDirection: "column",
        padding: "24px 0", flexShrink: 0,
      }}>
        <div style={{ padding: "0 20px 24px", borderBottom: "1px solid #1e293b" }}>
          <div style={{ fontSize: 10, letterSpacing: "0.12em", color: "#64748b", marginBottom: 6 }}>
            COGNIZANT TECHNOVERSE 2026
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#f1f5f9", lineHeight: 1.3 }}>
            VaidyaScribe
          </div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>
            Tamil/English AI scribe
          </div>
        </div>

        <nav style={{ padding: "16px 12px", flex: 1 }}>
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: "block",
                padding: "8px 12px",
                borderRadius: 6,
                fontSize: 13,
                color: isActive ? "#38bdf8" : "#94a3b8",
                background: isActive ? "#0f2744" : "transparent",
                textDecoration: "none",
                marginBottom: 2,
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ padding: "16px 20px", borderTop: "1px solid #1e293b" }}>
          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>DOCTOR</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{doctorId}</div>
          <div style={{ fontSize: 10, color: "#334155", marginTop: 8 }}>
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
