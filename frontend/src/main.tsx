import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { initAuth } from "./auth/keycloak";

// Garde-fou #54 : on n'affiche l'app qu'une fois l'authentification OIDC établie.
async function demarrer(): Promise<void> {
  const racine = document.getElementById("root");
  if (!racine) {
    throw new Error("Élément #root introuvable.");
  }
  const root = createRoot(racine);

  try {
    await initAuth();
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  } catch (erreur) {
    root.render(
      <p style={{ padding: 24, color: "#b00" }}>
        Échec de l'authentification : {String(erreur)}
      </p>,
    );
  }
}

void demarrer();
