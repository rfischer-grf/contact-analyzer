/**
 * Bloc indexation du détail contrat (#76).
 *
 * Affiche la clause d'indexation effective : indice, base S0 (valeur + période),
 * date de l'acte de référence tarifaire (signature du dernier acte tarifaire, pas
 * la signature initiale — §3.1), et le sens de révision.
 *
 * Garde-fou §2.5 : une clause unidirectionnelle (hausse seule) est réputée non écrite →
 * le moteur force le bidirectionnel. Quand `bidirectionnelle` est vrai, on signale
 * explicitement que la révision à la baisse est garantie même si la clause d'origine
 * ne la prévoyait pas.
 */
import type { ReactNode } from "react";
import type { ContratDetail } from "../../api/types";
import { Note } from "../analyse/primitives";
import { stylePastille } from "../../theme";
import { formaterDateIso, formaterNombre } from "../analyse/format";
import { couleurs, espacements, typo } from "../../theme/tokens";
import { estIndexe, libelleIndice } from "./format";

interface BlocIndexationProps {
  contrat: ContratDetail;
}

function Ligne({ label, valeur }: { label: string; valeur: ReactNode }): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: espacements.md,
        padding: `${espacements.sm} 0`,
        borderBottom: `1px solid ${couleurs.bordure}`,
        fontSize: typo.taille.base,
      }}
    >
      <span style={{ color: couleurs.texteAttenue }}>{label}</span>
      <span style={{ color: couleurs.texte, fontWeight: typo.graisse.semi, textAlign: "right" }}>
        {valeur}
      </span>
    </div>
  );
}

export function BlocIndexation({ contrat }: BlocIndexationProps): JSX.Element {
  return (
    <div>
      <h3
        style={{
          fontSize: typo.taille.lg,
          fontWeight: typo.graisse.semi,
          margin: `0 0 ${espacements.sm}`,
        }}
      >
        Indexation
      </h3>

      {!estIndexe(contrat.indice) ? (
        <p style={{ fontSize: typo.taille.sm, color: couleurs.texteFaible, margin: 0 }}>
          Contrat non indexé (aucune clause d'indexation).
        </p>
      ) : (
        <>
          <Ligne label="Indice" valeur={libelleIndice(contrat.indice)} />
          <Ligne
            label="Base S0"
            valeur={
              contrat.indice_base_valeur !== null && contrat.indice_base_valeur !== undefined
                ? `${formaterNombre(contrat.indice_base_valeur)}${
                    contrat.indice_base_periode ? ` (${contrat.indice_base_periode})` : ""
                  }`
                : "—"
            }
          />
          <Ligne
            label="Acte de référence tarifaire"
            valeur={formaterDateIso(contrat.date_acte_reference)}
          />
          <Ligne
            label="Sens de révision"
            valeur={
              <span style={stylePastille(contrat.bidirectionnelle ? "accent" : "attention")}>
                {contrat.bidirectionnelle ? "Bidirectionnel" : "Unidirectionnel"}
              </span>
            }
          />

          {contrat.bidirectionnelle && (
            <div style={{ marginTop: espacements.md }}>
              <Note>
                Révision <strong>bidirectionnelle forcée</strong> : une clause de hausse seule est
                réputée non écrite (§2.5), la baisse de l'indice est donc appliquée même si l'acte
                ne la prévoyait pas.
              </Note>
            </div>
          )}
        </>
      )}
    </div>
  );
}
