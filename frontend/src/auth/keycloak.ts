/**
 * Authentification OIDC via Keycloak (ticket #54).
 *
 * Garde-fou (spec §2.1, §7) : le `tenant` est DÉRIVÉ DU TOKEN, jamais saisi ni
 * fourni par le client. Côté front on le lit uniquement pour l'affichage ;
 * l'API le relit elle-même dans le claim et ne fait jamais confiance au client.
 *
 * PKCE (S256) obligatoire pour un client public SPA.
 */
import Keycloak from "keycloak-js";

const url = import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080";
const realm = import.meta.env.VITE_KEYCLOAK_REALM ?? "clm";
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "clm-spa";

export const keycloak = new Keycloak({ url, realm, clientId });

/** Nom du claim portant le tenant (aligné sur `tenant_claim` côté API). */
const TENANT_CLAIM = "tenant";

let initialise = false;

/**
 * Initialise Keycloak en flux code+PKCE. Redirige vers la page de login si
 * l'utilisateur n'est pas authentifié (`login-required`).
 */
export async function initAuth(): Promise<boolean> {
  if (initialise) {
    return keycloak.authenticated ?? false;
  }
  const authentifie = await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });
  initialise = true;

  // Rafraîchit l'access token de façon proactive (toutes les ~30 s) afin
  // qu'il reste valide ≥ 60 s lors des appels API.
  setInterval(() => {
    void keycloak.updateToken(60).catch(() => keycloak.login());
  }, 30_000);

  return authentifie;
}

/**
 * Renvoie un access token valide (rafraîchi si nécessaire) pour le bearer
 * des appels API. Lève si l'utilisateur n'est pas authentifié.
 */
export async function getToken(): Promise<string> {
  await keycloak.updateToken(30).catch(() => {
    keycloak.login();
  });
  if (!keycloak.token) {
    throw new Error("Non authentifié : aucun access token disponible.");
  }
  return keycloak.token;
}

/**
 * Lit le tenant depuis les claims du token (affichage uniquement).
 * NE PAS l'envoyer à l'API : celle-ci le dérive elle-même du token.
 */
export function getTenant(): string | null {
  const claims = keycloak.tokenParsed as Record<string, unknown> | undefined;
  const tenant = claims?.[TENANT_CLAIM];
  return typeof tenant === "string" ? tenant : null;
}

/** Nom d'utilisateur affichable (preferred_username / sub). */
export function getUtilisateur(): string {
  const claims = keycloak.tokenParsed as Record<string, unknown> | undefined;
  return (
    (claims?.["preferred_username"] as string | undefined) ??
    (claims?.["sub"] as string | undefined) ??
    "inconnu"
  );
}

export function logout(): void {
  void keycloak.logout({ redirectUri: window.location.origin });
}
