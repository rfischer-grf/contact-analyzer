/**
 * Jetons de design (design tokens) du cockpit Clausio — ticket #72 (fondation /
 * design-system) + #83 (skin fidèle au design « Clausio - Pilotage des contrats »).
 *
 * SOURCE DE VÉRITÉ DU STYLE. Tout le style de l'application passe par ces jetons
 * (ou les primitives de `index.ts` qui les consomment) ; aucun composant ne code
 * une couleur / un espacement en dur. Les VALEURS ci-dessous sont alignées sur le
 * design Clausio (espace colorimétrique OKLCH, accent indigo, IBM Plex) ; les CLÉS
 * sont stables (re-skin = modifier ces valeurs uniquement).
 *
 * Thème Clausio : clair, sobre, orienté cockpit ; sidebar claire, accent indigo,
 * couleurs sémantiques ok/warn/danger.
 */

/** Palette de couleurs (OKLCH, repris du design Clausio). Sémantique d'abord. */
export const couleurs = {
  // Surfaces
  fond: "oklch(0.984 0.003 255)", // --bg : zone de contenu
  surface: "#ffffff", // --surface : cartes, panneaux, en-tête
  surfaceAlt: "oklch(0.964 0.005 255)", // --surface-3 : survol léger, zébrures

  // Barre latérale (cockpit clair)
  sidebarFond: "oklch(0.978 0.004 255)", // --surface-2
  sidebarSurface: "oklch(0.964 0.005 255)", // --surface-3
  sidebarTexte: "oklch(0.40 0.016 264)", // --ink-2
  sidebarTexteAttenue: "oklch(0.54 0.012 264)", // --muted
  sidebarActifFond: "oklch(0.955 0.025 264)", // --accent-soft
  sidebarActifTexte: "oklch(0.52 0.13 264)", // --accent

  // Texte
  texte: "oklch(0.27 0.018 264)", // --ink
  texteAttenue: "oklch(0.54 0.012 264)", // --muted
  texteFaible: "oklch(0.66 0.012 264)", // --faint
  texteInverse: "#ffffff",

  // Accent / marque (indigo Clausio ≈ #4b53c9)
  accent: "oklch(0.52 0.13 264)", // --accent
  accentFort: "oklch(0.45 0.14 264)", // --accent-2
  accentDoux: "oklch(0.955 0.025 264)", // --accent-soft

  // Bordures
  bordure: "oklch(0.922 0.005 255)", // --border
  bordureForte: "oklch(0.885 0.007 255)", // --border-2

  // États sémantiques
  succes: "oklch(0.52 0.10 158)", // --ok
  succesDoux: "oklch(0.962 0.03 160)", // --ok-soft
  attention: "oklch(0.56 0.12 70)", // --warn
  attentionDoux: "oklch(0.965 0.05 80)", // --warn-soft
  danger: "oklch(0.55 0.17 25)", // --danger
  dangerDoux: "oklch(0.962 0.03 25)", // --danger-soft
  info: "oklch(0.52 0.13 264)", // = accent
  infoDoux: "oklch(0.955 0.025 264)", // = accent-soft

  // Paliers d'alerte d'échéance (spec §2.6 : J−90 / J−60 / J−30 / J−7)
  palier7: "oklch(0.55 0.17 25)", // danger
  palier30: "oklch(0.56 0.12 70)", // warn
  palier90: "oklch(0.62 0.10 95)", // warn atténué
  palierLoin: "oklch(0.52 0.10 158)", // ok
} as const;

/** Typographie — IBM Plex (design Clausio). */
export const typo = {
  familleBase: "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  familleMono: "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
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

/** Rayons de bordure (Clausio : coins doux 8–14px). */
export const rayons = {
  sm: "6px",
  md: "10px",
  lg: "14px",
  rond: "999px",
} as const;

/** Ombres portées (teintées indigo, reprises du design). */
export const ombres = {
  none: "none",
  sm: "0 1px 2px oklch(0.45 0.02 264 / 0.06)",
  md: "0 1px 2px oklch(0.45 0.02 264 / 0.05), 0 10px 30px oklch(0.45 0.02 264 / 0.06)",
  lg: "0 4px 12px oklch(0.45 0.02 264 / 0.10), 0 18px 40px oklch(0.45 0.02 264 / 0.10)",
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
