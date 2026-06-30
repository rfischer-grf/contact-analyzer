/**
 * Jetons de design (design tokens) du cockpit Clausio — ticket #72 (fondation /
 * design-system), socle du skin Clausio exact (#83).
 *
 * SOURCE DE VÉRITÉ DU STYLE. Tout le style de l'application passe par ces jetons
 * (ou les primitives de `index.ts` qui les consomment). Objectif : appliquer plus
 * tard le skin Clausio exact (design `.dc.html`, #83) en ne touchant QUE
 * `src/theme/` — aucun composant ne doit coder une couleur / un espacement en dur.
 *
 * Thème par défaut : sobre, professionnel, orienté cockpit (sidebar sombre,
 * header tenant clair, zone de contenu claire).
 */

/** Palette de couleurs. Sémantique d'abord, valeurs ensuite (#83 réécrira les valeurs). */
export const couleurs = {
  // Surfaces
  fond: "#f4f6fa", // fond applicatif (zone de contenu)
  surface: "#ffffff", // cartes, panneaux, en-tête
  surfaceAlt: "#eef1f7", // survol léger, zébrures de tableau

  // Barre latérale (cockpit sombre)
  sidebarFond: "#0f1b2d",
  sidebarSurface: "#16263d",
  sidebarTexte: "#c2cddd",
  sidebarTexteAttenue: "#7e8da6",
  sidebarActifFond: "#1f64ff",
  sidebarActifTexte: "#ffffff",

  // Texte
  texte: "#1a2433",
  texteAttenue: "#5b6b80",
  texteFaible: "#8a99ad",
  texteInverse: "#ffffff",

  // Accent / marque
  accent: "#1f64ff",
  accentFort: "#1549cc",
  accentDoux: "#e7eeff",

  // Bordures
  bordure: "#d9e0ea",
  bordureForte: "#c2ccd9",

  // États sémantiques
  succes: "#1f9d62",
  succesDoux: "#e3f6ec",
  attention: "#c9820a",
  attentionDoux: "#fdf2dd",
  danger: "#d23b3b",
  dangerDoux: "#fbe7e7",
  info: "#1f64ff",
  infoDoux: "#e7eeff",

  // Paliers d'alerte d'échéance (spec §2.6 : J−90 / J−60 / J−30 / J−7)
  palier7: "#d23b3b",
  palier30: "#c9820a",
  palier90: "#b78a00",
  palierLoin: "#1f9d62",
} as const;

/** Typographie. */
export const typo = {
  familleBase:
    "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  familleMono:
    "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  taille: {
    xs: "12px",
    sm: "13px",
    base: "14px",
    md: "15px",
    lg: "18px",
    xl: "22px",
    xxl: "28px",
  },
  graisse: {
    normale: 400,
    moyenne: 500,
    semi: 600,
    forte: 700,
  },
  hauteurLigne: {
    serree: 1.25,
    base: 1.5,
    aeree: 1.7,
  },
} as const;

/** Échelle d'espacement (multiples de 4px). */
export const espacements = {
  none: "0",
  xxs: "2px",
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "24px",
  xxl: "32px",
  xxxl: "48px",
} as const;

/** Rayons de bordure. */
export const rayons = {
  sm: "4px",
  md: "8px",
  lg: "12px",
  rond: "999px",
} as const;

/** Ombres portées. */
export const ombres = {
  none: "none",
  sm: "0 1px 2px rgba(15, 27, 45, 0.06)",
  md: "0 2px 8px rgba(15, 27, 45, 0.08)",
  lg: "0 8px 24px rgba(15, 27, 45, 0.12)",
} as const;

/** Dimensions de structure du cockpit. */
export const dimensions = {
  largeurSidebar: "248px",
  largeurSidebarReduite: "72px",
  hauteurHeader: "60px",
  largeurContenuMax: "1280px",
} as const;

/** Profondeurs (z-index) pour empilement cohérent. */
export const zIndex = {
  base: 0,
  sidebar: 100,
  header: 200,
  overlay: 800,
  modal: 900,
  toast: 1000,
} as const;

/** Transitions standard. */
export const transitions = {
  rapide: "120ms ease",
  base: "180ms ease",
  lente: "260ms ease",
} as const;

/** Regroupement exporté comme un seul objet thème. */
export const tokens = {
  couleurs,
  typo,
  espacements,
  rayons,
  ombres,
  dimensions,
  zIndex,
  transitions,
} as const;

export type Tokens = typeof tokens;
