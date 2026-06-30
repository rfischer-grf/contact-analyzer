/**
 * Point d'entrée du thème Clausio — ticket #72.
 *
 * Rôle :
 *  1. `applyTheme()` projette les jetons de `tokens.ts` en variables CSS
 *     (`--clausio-*`) consommées par `global.css` et les primitives ci-dessous.
 *  2. Expose des PRIMITIVES de style (objets `CSSProperties` réutilisables et
 *     fabriques de styles) pour que les composants ne codent JAMAIS une couleur,
 *     un espacement ou un rayon en dur.
 *
 * Conséquence visée (#83) : remplacer le skin Clausio exact = modifier UNIQUEMENT
 * `src/theme/` (tokens + éventuellement ces primitives), sans toucher aux pages.
 */
import type { CSSProperties } from "react";
import "./global.css";
import { tokens } from "./tokens";

export { tokens } from "./tokens";
export type { Tokens } from "./tokens";

/**
 * Injecte les jetons sous forme de variables CSS sur `:root`. À appeler une fois
 * au démarrage (cf. main.tsx) avant le rendu.
 */
export function applyTheme(): void {
  if (typeof document === "undefined") {
    return;
  }
  const r = document.documentElement.style;
  const { couleurs, typo, espacements, rayons, transitions } = tokens;

  // Couleurs
  r.setProperty("--clausio-fond", couleurs.fond);
  r.setProperty("--clausio-surface", couleurs.surface);
  r.setProperty("--clausio-surface-alt", couleurs.surfaceAlt);
  r.setProperty("--clausio-texte", couleurs.texte);
  r.setProperty("--clausio-texte-attenue", couleurs.texteAttenue);
  r.setProperty("--clausio-texte-faible", couleurs.texteFaible);
  r.setProperty("--clausio-accent", couleurs.accent);
  r.setProperty("--clausio-accent-fort", couleurs.accentFort);
  r.setProperty("--clausio-accent-doux", couleurs.accentDoux);
  r.setProperty("--clausio-bordure", couleurs.bordure);
  r.setProperty("--clausio-bordure-forte", couleurs.bordureForte);

  // Typographie
  r.setProperty("--clausio-police-base", typo.familleBase);
  r.setProperty("--clausio-police-mono", typo.familleMono);
  r.setProperty("--clausio-taille-xs", typo.taille.xs);
  r.setProperty("--clausio-taille-sm", typo.taille.sm);
  r.setProperty("--clausio-taille-base", typo.taille.base);
  r.setProperty("--clausio-taille-md", typo.taille.md);
  r.setProperty("--clausio-taille-lg", typo.taille.lg);
  r.setProperty("--clausio-taille-xl", typo.taille.xl);
  r.setProperty("--clausio-graisse-semi", String(typo.graisse.semi));
  r.setProperty("--clausio-hauteur-ligne-base", String(typo.hauteurLigne.base));
  r.setProperty(
    "--clausio-hauteur-ligne-serree",
    String(typo.hauteurLigne.serree),
  );

  // Espacements
  r.setProperty("--clausio-espace-sm", espacements.sm);
  r.setProperty("--clausio-espace-md", espacements.md);
  r.setProperty("--clausio-espace-lg", espacements.lg);

  // Rayons
  r.setProperty("--clausio-rayon-md", rayons.md);
  r.setProperty("--clausio-rayon-rond", rayons.rond);

  // Transitions
  r.setProperty("--clausio-transition-base", transitions.base);
}

/* --------------------------------------------------------------------------
 * PRIMITIVES DE STYLE
 * Objets `CSSProperties` partagés : les composants importent ces primitives au
 * lieu d'écrire des valeurs en dur.
 * ----------------------------------------------------------------------- */

const { couleurs, typo, espacements, rayons, ombres, transitions } = tokens;

/** Carte/panneau de contenu. */
export const carte: CSSProperties = {
  background: couleurs.surface,
  border: `1px solid ${couleurs.bordure}`,
  borderRadius: rayons.lg,
  boxShadow: ombres.sm,
  padding: espacements.xl,
};

/** Section avec un peu de respiration verticale. */
export const section: CSSProperties = {
  marginBottom: espacements.xl,
};

/** Texte secondaire (descriptions, légendes). */
export const texteAttenue: CSSProperties = {
  color: couleurs.texteAttenue,
  fontSize: typo.taille.sm,
};

/** Variantes de bouton. */
export type VarianteBouton = "primaire" | "secondaire" | "discret" | "danger";

export function styleBouton(variante: VarianteBouton = "primaire"): CSSProperties {
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: espacements.sm,
    padding: `${espacements.sm} ${espacements.lg}`,
    borderRadius: rayons.md,
    border: "1px solid transparent",
    fontSize: typo.taille.base,
    fontWeight: typo.graisse.moyenne,
    lineHeight: 1,
    transition: `background ${transitions.base}, border-color ${transitions.base}, color ${transitions.base}`,
  };
  switch (variante) {
    case "primaire":
      return { ...base, background: couleurs.accent, color: couleurs.texteInverse };
    case "secondaire":
      return {
        ...base,
        background: couleurs.surface,
        color: couleurs.texte,
        borderColor: couleurs.bordureForte,
      };
    case "discret":
      return { ...base, background: "transparent", color: couleurs.texteAttenue };
    case "danger":
      return { ...base, background: couleurs.danger, color: couleurs.texteInverse };
  }
}

/** Style d'une cellule d'en-tête de tableau. */
export const enteteTableau: CSSProperties = {
  textAlign: "left",
  padding: espacements.md,
  fontSize: typo.taille.xs,
  fontWeight: typo.graisse.semi,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: couleurs.texteFaible,
  borderBottom: `2px solid ${couleurs.bordure}`,
};

/** Style d'une cellule de corps de tableau. */
export const celluleTableau: CSSProperties = {
  padding: espacements.md,
  borderBottom: `1px solid ${couleurs.bordure}`,
  fontSize: typo.taille.base,
};

/** Variantes de pastille (badge). */
export type TonPastille = "neutre" | "accent" | "succes" | "attention" | "danger";

export function stylePastille(ton: TonPastille = "neutre"): CSSProperties {
  const map: Record<TonPastille, { fond: string; texte: string }> = {
    neutre: { fond: couleurs.surfaceAlt, texte: couleurs.texteAttenue },
    accent: { fond: couleurs.accentDoux, texte: couleurs.accentFort },
    succes: { fond: couleurs.succesDoux, texte: couleurs.succes },
    attention: { fond: couleurs.attentionDoux, texte: couleurs.attention },
    danger: { fond: couleurs.dangerDoux, texte: couleurs.danger },
  };
  const { fond, texte } = map[ton];
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: espacements.xs,
    padding: `${espacements.xxs} ${espacements.sm}`,
    borderRadius: rayons.rond,
    background: fond,
    color: texte,
    fontSize: typo.taille.xs,
    fontWeight: typo.graisse.moyenne,
    whiteSpace: "nowrap",
  };
}

/**
 * Couleur d'un palier d'échéance selon le nombre de jours restants avant la
 * date limite de dénonciation (spec §2.6 : J−90 / J−60 / J−30 / J−7). Centralisé
 * ici pour rester cohérent entre Tableau de bord et Échéances.
 */
export function couleurPalierEcheance(joursRestants: number): string {
  if (joursRestants <= 7) return couleurs.palier7;
  if (joursRestants <= 30) return couleurs.palier30;
  if (joursRestants <= 90) return couleurs.palier90;
  return couleurs.palierLoin;
}
