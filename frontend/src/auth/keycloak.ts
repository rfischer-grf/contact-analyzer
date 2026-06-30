/**
 * Authentification OIDC via Keycloak — tickets #72/#73.
 *
 * Client public SPA, flux code + PKCE (S256) obligatoire.
 *   realm  = `clm`
 *   client = `clm-spa`
 *
 * Garde-fou (spec §2.1, §7) : le `tenant` est DÉRIVÉ DU TOKEN, jamais saisi ni
 * fourni par le client. Côté front on le lit uniquement pour l'affichage ;
 * l'API le relit elle-même dans le claim et ne fait jamais confiance au client.
 */
import Keycloak from "keycloak-js";

const url = import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080";
const realm = import.meta.env.VITE_KEYCLOAK_REALM ?? "clm";
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "clm-spa";

export const keycloak = new Keycloak({ url, realm, clientId });

/** Nom du claim portant le tenant (aligné sur `tenant_claim` côté API). */
const TENANT_CLAIM = "tenant";

/** Profil utilisateur dérivé des claims du token (lecture seule, affichage). */
export interface Utilisateur {
  /** Identifiant affichable (preferred_username, à défaut sub). */
  identifiant: string;
  /** Nom complet si présent dans les claims. */
  nom: string | null;
  /** Adresse e-mail si présente. */
  email: string | null;
  /** Tenant dérivé du claim `tenant` (jamais renvoyé à l'API). */
  tenant: string | null;
  /** Rôles applicatifs (realm + client) pour d'éventuelles gardes fines. */
  roles: string[];
}

let initialise = false;

/**
 * Initialise Keycloak en flux code + PKCE. Redirige vers la page de login si
 * l'utilisateur n'est pas authentifié (`login-required`). Idempotent.
 */
export async function initAuth(): Promise<boolean> {
  if (initialise) {
    return keycloak.authenticated ?? false;
  }
  const authentifie = await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
    enableLogging: import.meta.env.DEV,
  });
  initialise = true;

  // Rafraîchit l'access token de façon proactive (toutes les ~30 s) afin
  // qu'il reste valide ≥ 60 s lors des appels API. Si le refresh échoue
  // (session expirée), on relance le login.
  window.setInterval(() => {
    void keycloak.updateToken(60).catch(() => keycloak.login());
  }, 30_000);

  return authentifie;
}

/**
 * Renvoie un access token valide (rafraîchi si nécessaire) pour le bearer des
 * appels API. Lève si l'utilisateur n'est pas authentifié.
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
 * Force le rafraîchissement de l'access token (utilisé par le client API en
 * réponse à un 401). Renvoie `true` si un token frais est disponible.
 */
export async function rafraichirToken(): Promise<boolean> {
  try {
    await keycloak.updateToken(-1); // -1 → rafraîchit quel que soit le TTL restant
    return Boolean(keycloak.token);
  } catch {
    return false;
  }
}

function claims(): Record<string, unknown> {
  return (keycloak.tokenParsed as Record<string, unknown> | undefined) ?? {};
}

/** Tenant depuis les claims (affichage uniquement — NE PAS l'envoyer à l'API). */
export function getTenant(): string | null {
  const tenant = claims()[TENANT_CLAIM];
  return typeof tenant === "string" ? tenant : null;
}

/** Identifiant utilisateur affichable (preferred_username / sub). */
export function getUtilisateur(): string {
  const c = claims();
  return (
    (c["preferred_username"] as string | undefined) ??
    (c["sub"] as string | undefined) ??
    "inconnu"
  );
}

/** Construit le profil complet à partir des claims du token. */
export function lireUtilisateur(): Utilisateur {
  const c = claims();
  const realmRoles = ((c["realm_access"] as { roles?: string[] } | undefined)?.roles) ?? [];
  const resourceAccess = (c["resource_access"] as
    | Record<string, { roles?: string[] }>
    | undefined) ?? {};
  const clientRoles = resourceAccess[clientId]?.roles ?? [];

  return {
    identifiant: getUtilisateur(),
    nom: (c["name"] as string | undefined) ?? null,
    email: (c["email"] as string | undefined) ?? null,
    tenant: getTenant(),
    roles: [...new Set([...realmRoles, ...clientRoles])],
  };
}

export function logout(): void {
  void keycloak.logout({ redirectUri: window.location.origin });
}
