import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SCAFFOLD (#69). En dev, le proxy renvoie les appels /uploads, /statut, /hitl,
// /ics... vers l'API FastAPI (VITE_API_URL), ce qui évite tout souci CORS local.
export default defineConfig(({ mode }) => {
  const apiUrl = process.env.VITE_API_URL ?? "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/uploads": { target: apiUrl, changeOrigin: true },
        "/statut": { target: apiUrl, changeOrigin: true },
        "/hitl": { target: apiUrl, changeOrigin: true },
        "/ics": { target: apiUrl, changeOrigin: true },
        "/recherche": { target: apiUrl, changeOrigin: true },
      },
    },
    // `mode` est conservé pour usage futur (build par environnement).
    define: { __APP_MODE__: JSON.stringify(mode) },
  };
});
