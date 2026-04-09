/**
 * API client — relative URLs through nginx.
 * Token is read directly from localStorage on every request so it works
 * regardless of Zustand store rehydration timing.
 */
import axios from "axios";

const STORAGE_KEY = "vaidyascribe-auth";

function getToken(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Zustand persist wraps state under a "state" key
    return parsed?.state?.token ?? parsed?.token ?? null;
  } catch {
    return null;
  }
}

export const api = axios.create({
  baseURL:         "/api/v1",
  headers:         { "Content-Type": "application/json" },
  withCredentials: false,
});

// Inject token on every request — reads localStorage directly, no store dependency
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — clear stored auth and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(STORAGE_KEY);
      window.location.href = "/login";
    }
    const msg = err.response?.data?.detail || err.message;
    console.error("[API Error]", msg, err.config?.url);
    return Promise.reject(err);
  }
);
