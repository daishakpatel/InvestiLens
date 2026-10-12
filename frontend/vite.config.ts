import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import type { Plugin } from "vite";

// Dev proxy: the SPA calls same-origin `/api/...`, forwarded to the FastAPI backend, so no CORS
// config or secrets are needed in the browser (UI-005). Dev-only; prod uses VITE_API_BASE_URL.
// The target is configurable so the dev server works both locally (localhost:8000) and inside
// docker-compose, where it must reach the `api` service (VITE_DEV_PROXY_TARGET=http://api:8000).
const apiTarget = process.env.VITE_DEV_PROXY_TARGET ?? "http://localhost:8000";

/** Preload the one font file every page needs, so text is not drawn twice (fallback, then
 *  Inter). Its hashed name is only known once the bundle exists, hence a build step. */
function preloadLatinFont(): Plugin {
  return {
    name: "preload-latin-font",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, context) {
        const file = Object.keys(context.bundle ?? {}).find((name) =>
          /inter-latin-wght-normal.*\.woff2$/.test(name),
        );
        if (!file) return [];
        return [
          {
            tag: "link",
            attrs: { rel: "preload", as: "font", type: "font/woff2", href: `/${file}`, crossorigin: "" },
            injectTo: "head",
          },
        ];
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), preloadLatinFont()],
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
