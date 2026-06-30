/**
 * Contexte d'authentification React — ticket #73.
 *
 * Expose l'utilisateur courant (dérivé des claims Keycloak) et son tenant, ainsi
 * qu'une garde de routes. Le contexte est alimenté APRÈS l'init Keycloak fait
 * dans `main.tsx` ; au moment où l'App est rendue, l'utilisateur est authentifié.
 *
 * Garde-fou (spec §2.1, §7) : le tenant n'est lu que pour l'affichage et n'est
 * jamais transmis à l'API (l'API le dérive elle-même du token).
 */
import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { keycloak, lireUtilisateur, logout, type Utilisateur } from "./keycloak";

export interface AuthContexte {
  utilisateur: Utilisateur;
  tenant: string | null;
  estAuthentifie: boolean;
  /** Vrai si l'utilisateur possède le rôle demandé. */
  aRole: (role: string) => boolean;
  seDeconnecter: () => void;
}

const Contexte = createContext<AuthContexte | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const valeur = useMemo<AuthContexte>(() => {
    const utilisateur = lireUtilisateur();
    return {
      utilisateur,
      tenant: utilisateur.tenant,
      estAuthentifie: keycloak.authenticated ?? false,
      aRole: (role) => utilisateur.roles.includes(role),
      seDeconnecter: logout,
    };
  }, []);

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

/** Hook d'accès au contexte d'authentification. Lève hors d'un AuthProvider. */
export function useAuth(): AuthContexte {
  const ctx = useContext(Contexte);
  if (!ctx) {
    throw new Error("useAuth doit être utilisé à l'intérieur d'un AuthProvider.");
  }
  return ctx;
}

/**
 * Garde de routes : n'affiche les enfants que si l'utilisateur est authentifié
 * (et, optionnellement, possède l'un des rôles requis). L'init `login-required`
 * garantit déjà l'authentification ; cette garde couvre l'autorisation fine et
 * sert de point d'extension pour des routes réservées.
 */
export function RouteProtegee({
  children,
  rolesRequis,
}: {
  children: ReactNode;
  rolesRequis?: string[];
}): JSX.Element {
  const { estAuthentifie, aRole } = useAuth();

  if (!estAuthentifie) {
    return (
      <p style={{ padding: 24 }}>
        Authentification requise. Redirection vers la connexion…
      </p>
    );
  }

  if (rolesRequis && rolesRequis.length > 0 && !rolesRequis.some(aRole)) {
    return (
      <p style={{ padding: 24 }}>
        Accès refusé : votre compte ne dispose pas des droits requis pour cette page.
      </p>
    );
  }

  return <>{children}</>;
}
