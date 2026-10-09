import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev proxy: the SPA calls same-origin `/api/...`, forwarded to the FastAPI backend, so no CORS
// config or secrets are needed in the browser (UI-005). Dev-only; prod uses VITE_API_BASE_URL.
// The target is configurable so the dev server works both locally (localhost:8000) and inside
// docker-compose, where it must reach the `api` service (VITE_DEV_PROXY_TARGET=http://api:8000).
const apiTarget = process.env.VITE_DEV_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // listen on 0.0.0.0 so the dev server is reachable from outside the container
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
  build: {
    // Keep Recharts/React-Query in their own chunks so route-level splitting stays effective.
    chunkSizeWarningLimit: 900,
  },
});
