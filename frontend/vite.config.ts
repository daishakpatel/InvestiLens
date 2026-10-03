import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev proxy: the SPA calls same-origin `/api/...`, forwarded to the FastAPI backend, so no CORS
// config or secrets are needed in the browser (UI-005). Dev-only; prod uses VITE_API_BASE_URL.
const apiTarget = "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
  build: {
    // Keep Recharts/React-Query in their own chunks so route-level splitting stays effective.
    chunkSizeWarningLimit: 900,
  },
});
