import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Le client API appelle VITE_API_URL en absolu (cf. src/api/client.ts), donc pas
// de proxy dev : on évite ainsi la collision entre les routes SPA (/recherche,
// /contrats…) et les chemins de l'API. Le cross-origin dev est couvert par le
// CORS de l'API FastAPI (origines configurables, défaut http://localhost:5173).
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: { port: 5173 },
  define: { __APP_MODE__: JSON.stringify(mode) },
}));
