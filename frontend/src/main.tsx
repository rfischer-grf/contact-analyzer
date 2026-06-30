import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { initAuth } from "./auth/keycloak";
import { applyTheme, tokens } from "./theme";

// Garde-fou (§2.1/§7) : on n'affiche l'app qu'une fois l'authentification OIDC
// établie (init `login-required` + PKCE). Le thème Clausio est appliqué avant le
// rendu pour éviter tout flash de style.
async function demarrer(): Promise<void> {
  const racine = document.getElementById("root");
  if (!racine) {
    throw new Error("Élément #root introuvable.");
  }
  const root = createRoot(racine);

  applyTheme();

  try {
    await initAuth();
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  } catch (erreur) {
    root.render(
      <p style={{ padding: tokens.espacements.xl, color: tokens.couleurs.danger }}>
        Échec de l'authentification : {String(erreur)}
      </p>,
    );
  }
}

void demarrer();
