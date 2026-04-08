/**
 * API client.
 *
 * Always uses relative URLs (/api/v1/...) so the browser sends
 * requests to whatever host served the page — nginx on localhost:80.
 * Nginx then proxies /api/ → backend:8000 internally.
 *
 * Never use an absolute URL like http://localhost:8000 — that bypasses
 * nginx and hits the backend directly, causing CORS and empty-response
 * errors when the backend crashes or restarts.
 */
import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  withCredentials: false,
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message;
    console.error("[API Error]", msg, err.config?.url);
    return Promise.reject(err);
  }
);
