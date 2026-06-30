import { tokens } from "../../theme";
import type { ContratDetail } from "../../api/types";
import { formatDate, libelleIndice } from "./format";

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

interface BlocIndexationProps {
  contrat: ContratDetail;
}

const styleLigne: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: tokens.espace.md,
  padding: `${tokens.espace.sm} 0`,
  fontSize: tokens.police.sm,
};

function Ligne({ label, valeur }: { label: string; valeur: string }): JSX.Element {
  return (
    <div style={styleLigne}>
      <span style={{ color: tokens.couleur.texteAttenue }}>{label}</span>
      <span style={{ color: tokens.couleur.texte, fontWeight: 600, textAlign: "right" }}>
        {valeur}
      </span>
    </div>
  );
}

export function BlocIndexation({ contrat }: BlocIndexationProps): JSX.Element {
  const indexe = !!contrat.indice && contrat.indice !== "aucun";

  return (
    <div
      style={{
        background: tokens.couleur.fondCarte,
        border: `1px solid ${tokens.couleur.bordure}`,
        borderRadius: tokens.rayon.md,
        padding: tokens.espace.lg,
      }}
    >
      <h3 style={{ fontSize: tokens.police.lg, margin: `0 0 ${tokens.espace.sm}` }}>Indexation</h3>

      {!indexe ? (
        <p style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue, margin: 0 }}>
          Contrat non indexé (aucune clause d'indexation).
        </p>
      ) : (
        <>
          <Ligne label="Indice" valeur={libelleIndice(contrat.indice)} />
          <Ligne
            label="Base S0"
            valeur={
              contrat.indice_base_valeur !== null && contrat.indice_base_valeur !== undefined
                ? `${contrat.indice_base_valeur}${
                    contrat.indice_base_periode ? ` (${contrat.indice_base_periode})` : ""
                  }`
                : "—"
            }
          />
          <Ligne label="Acte de référence tarifaire" valeur={formatDate(contrat.date_acte_reference)} />
          <Ligne
            label="Sens de révision"
            valeur={contrat.bidirectionnelle ? "Bidirectionnel" : "Unidirectionnel"}
          />

          {contrat.bidirectionnelle && (
            <p
              style={{
                fontSize: tokens.police.sm,
                color: tokens.couleur.statut.info,
                background: tokens.couleur.fond,
                borderRadius: tokens.rayon.md,
                padding: tokens.espace.md,
                margin: `${tokens.espace.md} 0 0`,
              }}
            >
              Révision <strong>bidirectionnelle forcée</strong> : une clause de hausse seule est
              réputée non écrite (§2.5), la baisse est donc appliquée même si l'acte ne la prévoyait
              pas.
            </p>
          )}
        </>
      )}
    </div>
  );
}
