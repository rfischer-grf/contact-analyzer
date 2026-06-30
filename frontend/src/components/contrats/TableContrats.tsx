import { tokens } from "../../theme";
import type { ContratResume } from "../../api/types";
import { formatDate, formatMontant, libelleIndice } from "./format";

/**
 * Table des contrats (#75).
 *
 * Colonnes : référence, objet, fournisseur (SIREN), indice, échéance, date limite
 * de dénonciation, montant. Ligne entière cliquable → `/contrats/:id`. La date limite
 * de dénonciation (date actionnable §2.6) est mise en avant. Données = état effectif
 * validé uniquement (garde-fou).
 */

interface TableContratsProps {
  contrats: ContratResume[];
  /** Navigation vers le détail (le routeur est fourni par la coquille/fondation). */
  onOuvrir: (id: string) => void;
}

const styleCellule: React.CSSProperties = {
  padding: tokens.espace.sm,
  textAlign: "left",
  verticalAlign: "top",
};

export function TableContrats({ contrats, onOuvrir }: TableContratsProps): JSX.Element {
  if (contrats.length === 0) {
    return (
      <p style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue }}>
        Aucun contrat ne correspond à ces filtres.
      </p>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: tokens.police.sm,
          color: tokens.couleur.texte,
        }}
      >
        <thead>
          <tr
            style={{
              textAlign: "left",
              borderBottom: `2px solid ${tokens.couleur.bordure}`,
              color: tokens.couleur.texteAttenue,
            }}
          >
            <th style={styleCellule}>Référence</th>
            <th style={styleCellule}>Objet</th>
            <th style={styleCellule}>Fournisseur (SIREN)</th>
            <th style={styleCellule}>Indice</th>
            <th style={styleCellule}>Échéance</th>
            <th style={styleCellule}>Date limite dénonciation</th>
            <th style={{ ...styleCellule, textAlign: "right" }}>Montant</th>
          </tr>
        </thead>
        <tbody>
          {contrats.map((c) => (
            <tr
              key={c.id}
              onClick={() => onOuvrir(c.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOuvrir(c.id);
                }
              }}
              tabIndex={0}
              role="link"
              aria-label={`Ouvrir le contrat ${c.reference ?? c.id}`}
              style={{
                borderBottom: `1px solid ${tokens.couleur.bordure}`,
                cursor: "pointer",
              }}
            >
              <td style={{ ...styleCellule, fontWeight: 600, color: tokens.couleur.accent }}>
                {c.reference || "—"}
              </td>
              <td style={styleCellule}>{c.objet || "—"}</td>
              <td style={styleCellule}>{c.fournisseur_siren || "—"}</td>
              <td style={styleCellule}>{libelleIndice(c.indice)}</td>
              <td style={styleCellule}>{formatDate(c.date_echeance)}</td>
              <td style={{ ...styleCellule, fontWeight: 600 }}>
                {formatDate(c.date_limite_denonciation)}
              </td>
              <td style={{ ...styleCellule, textAlign: "right" }}>
                {formatMontant(c.montant, c.devise)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
