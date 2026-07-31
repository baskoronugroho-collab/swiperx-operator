import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev: proxy /api to the FastAPI backend so cookies stay same-origin (the session
// cookie is httpOnly + SameSite, so cross-origin dev would drop it).
// Prod: nginx serves the build and the ingress routes /api to the backend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      // PORT is set by the launcher when 5173 is taken (autoPort); nothing here depends
      // on a fixed port — /api is proxied same-origin regardless.
      port: Number(env.PORT) || 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_TARGET || "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
      // Substrait's platform SSO gateway allowlists exactly two prefixes — `/c/*` and
      // `/api/c/*` — and redirects everything else to Google. Couriers have no Google
      // account, so if the bundle sat at the default `/assets/*` the wizard would load
      // index.html and then get an SSO redirect for its own JS: a blank page at the
      // pharmacy door. Emitting under `c/assets` puts the bundle inside the exempt
      // prefix. Verified against the live host, 26 Jul 2026.
      //
      // Cleaner long-term fix: have the portal allowlist `/assets/` too, then drop this.
      assetsDir: "c/assets",
    },
  };
});
