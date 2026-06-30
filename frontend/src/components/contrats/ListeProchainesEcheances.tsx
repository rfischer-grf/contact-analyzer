/**
 * Liste « prochaines dates limites de dénonciation » du tableau de bord (#74).
 *
 * Met en avant la **date limite de dénonciation** (échéance − préavis), seule date
 * actionnable en tacite reconduction (§2.6). Chaque ligne pointe vers le détail du
 * contrat (`/contrats/:id`). Données = état effectif validé (garde-fou : aucune
 * donnée `à_valider`).
 */
import { Link } from "react-router-dom";
import type { ProchaineEcheance } from "../../api/types";
import { Carte } from "../analyse/primitives";
import { BadgeUrgence } from "../analyse/BadgeUrgence";
import { formaterDateIso } from "../analyse/format";
import { couleurs, espacements, typo } from "../../theme/tokens";
import { PALIERS_ALERTE } from "./format";

interface ListeProchainesEcheancesProps {
  echeances: ProchaineEcheance[];
}

export function ListeProchainesEcheances({
  echeances,
}: ListeProchainesEcheancesProps): JSX.Element {
  return (
    <Carte>
      <div style={{ fontSize: typo.taille.lg, fontWeight: typo.graisse.semi, color: couleurs.texte }}>
        Prochaines dates limites de dénonciation
      </div>
      <p
        style={{
          fontSize: typo.taille.sm,
          color: couleurs.texteAttenue,
          lineHeight: typo.hauteurLigne.base,
          margin: `${espacements.sm} 0 ${espacements.md}`,
        }}
      >
        Date <strong>actionnable</strong> = date limite de dénonciation (échéance − préavis), pas
        l'échéance. Alertes envoyées à J−{PALIERS_ALERTE.join(", J−")}.
      </p>

      {echeances.length === 0 ? (
        <p style={{ fontSize: typo.taille.sm, color: couleurs.texteFaible, margin: 0 }}>
          Aucune échéance dans les 120 prochains jours.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {echeances.map((e) => (
            <li
              key={e.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: espacements.md,
                padding: `${espacements.sm} 0`,
                borderTop: `1px solid ${couleurs.bordure}`,
              }}
            >
              <Link
                to={`/contrats/${e.id}`}
                style={{
                  color: couleurs.accent,
                  textDecoration: "none",
                  fontWeight: typo.graisse.semi,
                  fontSize: typo.taille.base,
                }}
              >
                {e.reference || `Contrat ${e.id.slice(0, 8)}`}
              </Link>
              <span style={{ fontSize: typo.taille.sm, color: couleurs.texte, marginLeft: "auto", marginRight: espacements.md }}>
                {formaterDateIso(e.date_limite_denonciation)}
              </span>
              <BadgeUrgence jours={e.jours_restants} />
            </li>
          ))}
        </ul>
      )}
    </Carte>
  );
}
