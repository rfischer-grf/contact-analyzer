/**
 * Mise en page racine du cockpit Clausio — ticket #72.
 *
 * Structure : barre latérale (navigation) + colonne (en-tête tenant + zone de
 * contenu défilante). Les pages métier sont rendues via `<Outlet />`.
 *
 * Le titre de l'en-tête est dérivé de la route courante. Style intégralement
 * piloté par les jetons (`tokens`) → skin Clausio exact réglé dans `src/theme/`.
 */
import type { CSSProperties } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { tokens } from "../../theme";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

const { couleurs, espacements, dimensions } = tokens;

const styleRacine: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  background: couleurs.fond,
};

const styleColonne: CSSProperties = {
  flex: "1 1 auto",
  display: "flex",
  flexDirection: "column",
  minWidth: 0, // évite que des tableaux larges débordent la colonne
};

const styleContenu: CSSProperties = {
  flex: "1 1 auto",
  padding: espacements.xl,
};

const styleConteneur: CSSProperties = {
  maxWidth: dimensions.largeurContenuMax,
  margin: "0 auto",
};

/**
 * Détermine le titre de page à partir du chemin. Table simple ; les pages
 * peuvent par ailleurs afficher leur propre en-tête de contenu.
 */
function titrePour(chemin: string): string {
  if (chemin === "/") return "Tableau de bord";
  if (chemin.startsWith("/contrats")) return "Contrats";
  if (chemin.startsWith("/upload")) return "Déposer un contrat";
  if (chemin.startsWith("/validation")) return "Validation (HITL)";
  if (chemin.startsWith("/projection")) return "Projection tarifaire";
  if (chemin.startsWith("/recherche")) return "Recherche";
  if (chemin.startsWith("/echeances")) return "Échéances";
  return "Cockpit";
}

export function AppLayout(): JSX.Element {
  const { pathname } = useLocation();

  return (
    <div style={styleRacine}>
      <Sidebar />
      <div style={styleColonne}>
        <Header titre={titrePour(pathname)} />
        <main style={styleContenu}>
          <div style={styleConteneur}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
