/**
 * API client — relative URLs through nginx.
 * Automatically injects JWT token from auth store on every request.
 */
import axios from "axios";
import { useAuthStore } from "./store/auth.store";

export const api = axios.create({
  baseURL:         "/api/v1",
  headers:         { "Content-Type": "application/json" },
  withCredentials: false,
});

// Inject token on every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — clear auth and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().clearAuth();
      window.location.href = "/login";
    }
    const msg = err.response?.data?.detail || err.message;
    console.error("[API Error]", msg, err.config?.url);
    return Promise.reject(err);
  }
);
