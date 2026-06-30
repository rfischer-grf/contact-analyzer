/**
 * Table des contrats (#75).
 *
 * Colonnes : référence, objet, fournisseur (SIREN), indice, échéance, date limite
 * de dénonciation, montant. Ligne entière cliquable → `/contrats/:id` (navigation
 * react-router). La date limite de dénonciation (date actionnable §2.6) est mise en
 * avant. Données = état effectif validé uniquement (garde-fou).
 */
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import type { ContratResume } from "../../api/types";
import { enteteTableau, celluleTableau } from "../../theme";
import { couleurs, typo } from "../../theme/tokens";
import { formaterDateIso, formaterMontant } from "../analyse/format";
import { libelleIndice } from "./format";

interface TableContratsProps {
  contrats: ContratResume[];
}

const enteteDroite: CSSProperties = { ...enteteTableau, textAlign: "right" };
const celluleDroite: CSSProperties = { ...celluleTableau, textAlign: "right" };

export function TableContrats({ contrats }: TableContratsProps): JSX.Element {
  const naviguer = useNavigate();

  if (contrats.length === 0) {
    return (
      <p style={{ fontSize: typo.taille.sm, color: couleurs.texteFaible }}>
        Aucun contrat ne correspond à ces filtres.
      </p>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", color: couleurs.texte }}>
        <thead>
          <tr>
            <th style={enteteTableau}>Référence</th>
            <th style={enteteTableau}>Objet</th>
            <th style={enteteTableau}>Fournisseur (SIREN)</th>
            <th style={enteteTableau}>Indice</th>
            <th style={enteteTableau}>Échéance</th>
            <th style={enteteTableau}>Date limite dénonciation</th>
            <th style={enteteDroite}>Montant</th>
          </tr>
        </thead>
        <tbody>
          {contrats.map((c) => (
            <tr
              key={c.id}
              onClick={() => naviguer(`/contrats/${c.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  naviguer(`/contrats/${c.id}`);
                }
              }}
              tabIndex={0}
              role="link"
              aria-label={`Ouvrir le contrat ${c.reference ?? c.id}`}
              style={{ cursor: "pointer" }}
            >
              <td style={{ ...celluleTableau, fontWeight: typo.graisse.semi, color: couleurs.accent }}>
                {c.reference || "—"}
              </td>
              <td style={celluleTableau}>{c.objet || "—"}</td>
              <td style={celluleTableau}>{c.fournisseur_siren || "—"}</td>
              <td style={celluleTableau}>{libelleIndice(c.indice)}</td>
              <td style={celluleTableau}>{formaterDateIso(c.date_echeance)}</td>
              <td style={{ ...celluleTableau, fontWeight: typo.graisse.semi }}>
                {formaterDateIso(c.date_limite_denonciation)}
              </td>
              <td style={celluleDroite}>
                {c.montant !== undefined && c.montant !== null
                  ? formaterMontant(c.montant, c.devise ?? "EUR")
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
