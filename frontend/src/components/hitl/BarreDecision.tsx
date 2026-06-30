import { tokens } from "../../theme";

/**
 * Barre de décision du gate HITL (#78, spec §2.4).
 *
 * Rappelle le garde-fou — seule une donnée VALIDÉE entre dans les alertes, le
 * feed ICS et l'index Weaviate — puis émet la décision (valider / rejeter).
 * Les corrections sont d'abord persistées par le parent (gold set), puis le
 * signal correspondant est émis au workflow Temporal en attente.
 *
 * Contrat de thème supposé (fourni par la fondation) :
 *   tokens.couleurs.{accent, accentDoux, accentFort, danger, dangerDoux, texteInverse, texteAttenue, bordure, info, infoDoux}
 *   tokens.espacements.{sm, md, lg}  ·  tokens.rayons.md  ·  tokens.typo.taille.{sm, md}
 */

interface BarreDecisionProps {
  onValider: () => void;
  onRejeter: () => void;
  /** Désactive les boutons pendant l'émission d'une décision. */
  enCours: boolean;
}

export function BarreDecision({ onValider, onRejeter, enCours }: BarreDecisionProps): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: tokens.espacements.md }}>
      <p
        style={{
          fontSize: tokens.typo.taille.sm,
          color: tokens.couleurs.info,
          background: tokens.couleurs.infoDoux,
          padding: tokens.espacements.sm,
          borderRadius: tokens.rayons.md,
          margin: 0,
        }}
      >
        Gate non négociable : seule une donnée validée entre dans les alertes, le feed ICS
        et la recherche (Weaviate). Aucune donnée « à valider » n'est propagée en aval.
      </p>

      <div style={{ display: "flex", gap: tokens.espacements.sm }}>
        <button
          type="button"
          onClick={onValider}
          disabled={enCours}
          style={{
            flex: 1,
            background: tokens.couleurs.accent,
            color: tokens.couleurs.texteInverse,
            border: "none",
            borderRadius: tokens.rayons.md,
            padding: `${tokens.espacements.sm} ${tokens.espacements.lg}`,
            fontSize: tokens.typo.taille.md,
            fontWeight: 600,
            cursor: enCours ? "not-allowed" : "pointer",
            opacity: enCours ? 0.6 : 1,
          }}
        >
          Valider
        </button>
        <button
          type="button"
          onClick={onRejeter}
          disabled={enCours}
          style={{
            flex: 1,
            background: tokens.couleurs.dangerDoux,
            color: tokens.couleurs.danger,
            border: `1px solid ${tokens.couleurs.danger}`,
            borderRadius: tokens.rayons.md,
            padding: `${tokens.espacements.sm} ${tokens.espacements.lg}`,
            fontSize: tokens.typo.taille.md,
            fontWeight: 600,
            cursor: enCours ? "not-allowed" : "pointer",
            opacity: enCours ? 0.6 : 1,
          }}
        >
          Rejeter
        </button>
      </div>
    </div>
  );
}
