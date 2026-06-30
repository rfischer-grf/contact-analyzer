/**
 * Barre latérale de navigation du cockpit Clausio — ticket #72.
 *
 * Toutes les valeurs visuelles proviennent des jetons (`tokens`) — aucun style en
 * dur, pour que le skin Clausio exact (#83) se règle dans `src/theme/`.
 */
import type { CSSProperties } from "react";
import { NavLink } from "react-router-dom";
import { tokens } from "../../theme";

/** Entrée de navigation. `fin` = correspondance exacte (utile pour `/`). */
interface EntreeNav {
  chemin: string;
  libelle: string;
  icone: string; // glyphe sobre ; remplacé par les icônes Clausio en #83
  fin?: boolean;
}

/** Entrées du cockpit (libellés en français — cf. consignes de routage). */
const ENTREES: EntreeNav[] = [
  { chemin: "/", libelle: "Tableau de bord", icone: "▦", fin: true },
  { chemin: "/contrats", libelle: "Contrats", icone: "▤" },
  { chemin: "/upload", libelle: "Déposer", icone: "↑" },
  { chemin: "/validation", libelle: "Validation", icone: "✓" },
  { chemin: "/recherche", libelle: "Recherche", icone: "⌕" },
  { chemin: "/echeances", libelle: "Échéances", icone: "◷" },
];

const { couleurs, espacements, typo, rayons, dimensions, transitions } = tokens;

const styleAside: CSSProperties = {
  width: dimensions.largeurSidebar,
  flex: `0 0 ${dimensions.largeurSidebar}`,
  background: couleurs.sidebarFond,
  color: couleurs.sidebarTexte,
  display: "flex",
  flexDirection: "column",
  height: "100vh",
  position: "sticky",
  top: 0,
};

const styleMarque: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: espacements.sm,
  height: dimensions.hauteurHeader,
  padding: `0 ${espacements.lg}`,
  fontSize: typo.taille.lg,
  fontWeight: typo.graisse.forte,
  color: couleurs.texteInverse,
  borderBottom: `1px solid ${couleurs.sidebarSurface}`,
  flex: "0 0 auto",
};

const styleNav: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: espacements.xxs,
  padding: espacements.md,
  overflowY: "auto",
};

function styleLien(actif: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: espacements.md,
    padding: `${espacements.sm} ${espacements.md}`,
    borderRadius: rayons.md,
    color: actif ? couleurs.sidebarActifTexte : couleurs.sidebarTexte,
    background: actif ? couleurs.sidebarActifFond : "transparent",
    fontSize: typo.taille.base,
    fontWeight: actif ? typo.graisse.semi : typo.graisse.normale,
    textDecoration: "none",
    transition: `background ${transitions.base}, color ${transitions.base}`,
  };
}

const styleIcone: CSSProperties = {
  width: 20,
  textAlign: "center",
  fontSize: typo.taille.md,
  flex: "0 0 auto",
};

const stylePied: CSSProperties = {
  marginTop: "auto",
  padding: espacements.lg,
  fontSize: typo.taille.xs,
  color: couleurs.sidebarTexteAttenue,
  borderTop: `1px solid ${couleurs.sidebarSurface}`,
};

export function Sidebar(): JSX.Element {
  return (
    <aside style={styleAside}>
      <div style={styleMarque}>
        <span aria-hidden>◆</span>
        <span>Clausio</span>
      </div>

      <nav style={styleNav} aria-label="Navigation principale">
        {ENTREES.map((e) => (
          <NavLink
            key={e.chemin}
            to={e.chemin}
            end={e.fin}
            style={({ isActive }) => styleLien(isActive)}
          >
            <span aria-hidden style={styleIcone}>
              {e.icone}
            </span>
            <span>{e.libelle}</span>
          </NavLink>
        ))}
      </nav>

      <div style={stylePied}>CLM souverain · UE</div>
    </aside>
  );
}
