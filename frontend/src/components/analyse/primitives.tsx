/**
 * Primitives d'UI partagées par les pages d'analyse (Projection #79, Recherche
 * #80, Échéances #81) du cockpit Clausio (epic #88).
 *
 * Tout le style passe par les jetons de `../../theme` (source de vérité du style,
 * #72/#83) : AUCUNE couleur / espacement codé en dur ici. Ces primitives sont
 * volontairement légères (pas de dépendance UI tierce) et neutres, pour que le
 * skin Clausio exact (#83) s'applique en ne touchant que `src/theme/`.
 */
import type { CSSProperties, ReactNode } from "react";
import { couleurs, espacements, rayons, typo, ombres } from "../../theme/tokens";

/** En-tête de page : titre + sous-titre explicatif (rappel de garde-fou métier). */
export function EntetePage({
  titre,
  children,
}: {
  titre: string;
  children?: ReactNode;
}): JSX.Element {
  return (
    <header style={{ marginBottom: espacements.xl }}>
      <h2
        style={{
          fontSize: typo.taille.xl,
          fontWeight: typo.graisse.semi,
          color: couleurs.texte,
          margin: 0,
        }}
      >
        {titre}
      </h2>
      {children !== undefined && (
        <p
          style={{
            fontSize: typo.taille.base,
            color: couleurs.texteAttenue,
            lineHeight: typo.hauteurLigne.base,
            margin: `${espacements.sm} 0 0`,
          }}
        >
          {children}
        </p>
      )}
    </header>
  );
}

/** Carte (panneau) : surface blanche, bordure douce, rayon et ombre du thème. */
export function Carte({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}): JSX.Element {
  return (
    <div
      style={{
        background: couleurs.surface,
        border: `1px solid ${couleurs.bordure}`,
        borderRadius: rayons.lg,
        boxShadow: ombres.sm,
        padding: espacements.xl,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Bouton primaire (accent) / secondaire (contour). */
export function Bouton({
  children,
  onClick,
  disabled,
  variante = "primaire",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variante?: "primaire" | "secondaire";
  type?: "button" | "submit";
}): JSX.Element {
  const primaire = variante === "primaire";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        font: "inherit",
        fontSize: typo.taille.base,
        fontWeight: typo.graisse.moyenne,
        color: primaire ? couleurs.texteInverse : couleurs.accent,
        background: primaire ? couleurs.accent : couleurs.surface,
        border: `1px solid ${primaire ? couleurs.accent : couleurs.bordureForte}`,
        borderRadius: rayons.md,
        padding: `${espacements.sm} ${espacements.lg}`,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
      }}
    >
      {children}
    </button>
  );
}

/** Champ de formulaire étiqueté (label + contrôle empilés). */
export function Champ({
  libelle,
  children,
  aide,
}: {
  libelle: string;
  children: ReactNode;
  aide?: string;
}): JSX.Element {
  return (
    <label style={{ display: "block" }}>
      <span
        style={{
          display: "block",
          fontSize: typo.taille.sm,
          fontWeight: typo.graisse.moyenne,
          color: couleurs.texteAttenue,
          marginBottom: espacements.xs,
        }}
      >
        {libelle}
      </span>
      {children}
      {aide !== undefined && (
        <span
          style={{
            display: "block",
            fontSize: typo.taille.xs,
            color: couleurs.texteFaible,
            marginTop: espacements.xs,
          }}
        >
          {aide}
        </span>
      )}
    </label>
  );
}

/** Style commun des contrôles de saisie (input / select). */
export const styleControle: CSSProperties = {
  font: "inherit",
  fontSize: typo.taille.base,
  color: couleurs.texte,
  background: couleurs.surface,
  border: `1px solid ${couleurs.bordureForte}`,
  borderRadius: rayons.md,
  padding: `${espacements.sm} ${espacements.md}`,
  width: "100%",
  boxSizing: "border-box",
};

/** Bandeau d'information / d'erreur (ton sémantique du thème). */
export function Bandeau({
  ton = "info",
  children,
}: {
  ton?: "info" | "succes" | "attention" | "danger";
  children: ReactNode;
}): JSX.Element {
  const map = {
    info: { fond: couleurs.infoDoux, texte: couleurs.info },
    succes: { fond: couleurs.succesDoux, texte: couleurs.succes },
    attention: { fond: couleurs.attentionDoux, texte: couleurs.attention },
    danger: { fond: couleurs.dangerDoux, texte: couleurs.danger },
  } as const;
  const t = map[ton];
  return (
    <div
      role={ton === "danger" ? "alert" : "status"}
      style={{
        background: t.fond,
        color: t.texte,
        border: `1px solid ${t.texte}`,
        borderRadius: rayons.md,
        padding: `${espacements.sm} ${espacements.md}`,
        fontSize: typo.taille.sm,
        lineHeight: typo.hauteurLigne.base,
      }}
    >
      {children}
    </div>
  );
}

/** Note explicative discrète (encadré « pourquoi » / garde-fou). */
export function Note({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p
      style={{
        fontSize: typo.taille.sm,
        color: couleurs.texteAttenue,
        background: couleurs.surfaceAlt,
        borderLeft: `3px solid ${couleurs.bordureForte}`,
        borderRadius: rayons.sm,
        padding: `${espacements.sm} ${espacements.md}`,
        margin: 0,
        lineHeight: typo.hauteurLigne.base,
      }}
    >
      {children}
    </p>
  );
}
