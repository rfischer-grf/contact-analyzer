import { tokens } from "../../theme";
import type { ProchaineEcheance } from "../../api/types";
import { formatDate, libelleJoursRestants, PALIERS_ALERTE } from "./format";

/**
 * Liste « prochaines dates limites de dénonciation » du tableau de bord (#74).
 *
 * Met en avant la **date limite de dénonciation** (échéance − préavis), seule date
 * actionnable en tacite reconduction (§2.6). Chaque ligne pointe vers le détail du
 * contrat (`/contrats/:id`). Données = état effectif validé (garde-fou : aucune
 * donnée `à_valider`).
 *
 * Contrat de thème supposé : tokens.couleur.statut.{info, attention, avertissement, danger}.
 */

interface ListeProchainesEcheancesProps {
  echeances: ProchaineEcheance[];
}

/** Couleur du texte « jours restants » selon le palier atteint (§2.6). */
function couleurJours(jours: number): string {
  if (jours <= 7) return tokens.couleur.statut.danger;
  if (jours <= 30) return tokens.couleur.statut.avertissement;
  if (jours <= 60) return tokens.couleur.statut.attention;
  return tokens.couleur.statut.info;
}

export function ListeProchainesEcheances({
  echeances,
}: ListeProchainesEcheancesProps): JSX.Element {
  return (
    <div
      style={{
        background: tokens.couleur.fondCarte,
        border: `1px solid ${tokens.couleur.bordure}`,
        borderRadius: tokens.rayon.md,
        padding: tokens.espace.lg,
      }}
    >
      <div
        style={{
          fontSize: tokens.police.lg,
          fontWeight: 600,
          color: tokens.couleur.texte,
        }}
      >
        Prochaines dates limites de dénonciation
      </div>
      <p
        style={{
          fontSize: tokens.police.sm,
          color: tokens.couleur.texteAttenue,
          margin: `${tokens.espace.sm} 0 ${tokens.espace.md}`,
        }}
      >
        Date <strong>actionnable</strong> = date limite de dénonciation (échéance − préavis), pas
        l'échéance. Alertes envoyées à J−{PALIERS_ALERTE.join(", J−")}.
      </p>

      {echeances.length === 0 ? (
        <p style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue, margin: 0 }}>
          Aucune échéance dans les 120 prochains jours.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {echeances.map((e) => (
            <li
              key={e.id}
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: tokens.espace.md,
                padding: `${tokens.espace.sm} 0`,
                borderTop: `1px solid ${tokens.couleur.bordure}`,
              }}
            >
              <a
                href={`/contrats/${e.id}`}
                style={{ color: tokens.couleur.accent, textDecoration: "none", fontWeight: 600 }}
              >
                {e.reference || `Contrat ${e.id.slice(0, 8)}`}
              </a>
              <span style={{ fontSize: tokens.police.sm, color: tokens.couleur.texte }}>
                {formatDate(e.date_limite_denonciation)}
              </span>
              <span
                style={{
                  fontSize: tokens.police.sm,
                  fontWeight: 600,
                  color: couleurJours(e.jours_restants),
                  whiteSpace: "nowrap",
                }}
              >
                {libelleJoursRestants(e.jours_restants)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
