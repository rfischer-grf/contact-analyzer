/**
 * Barre de filtres de la liste des contrats (#75).
 *
 * Filtres = facettes structurées (SQL `WHERE` côté API §6, jamais du vectoriel) :
 * indice, SIREN fournisseur, échéance avant une date. État contrôlé remonté au
 * parent qui appelle `api.contrats.lister({...})`.
 */
import type { Indice, ListerContratsParams } from "../../api/types";
import { Bouton, Champ, styleControle } from "../analyse/primitives";
import { espacements } from "../../theme/tokens";
import { LIBELLE_INDICE } from "./format";

/** Sous-ensemble des params piloté par l'UI (la pagination est gérée par la page). */
export type FiltresContratsValeurs = Pick<
  ListerContratsParams,
  "indice" | "fournisseur_siren" | "echeance_avant"
>;

interface FiltresContratsProps {
  valeurs: FiltresContratsValeurs;
  onChange: (valeurs: FiltresContratsValeurs) => void;
  onReinitialiser: () => void;
}

export function FiltresContrats({
  valeurs,
  onChange,
  onReinitialiser,
}: FiltresContratsProps): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        gap: espacements.lg,
        flexWrap: "wrap",
        alignItems: "flex-end",
      }}
    >
      <div style={{ flex: "0 0 180px" }}>
        <Champ libelle="Indice">
          <select
            value={valeurs.indice ?? ""}
            onChange={(e) =>
              onChange({ ...valeurs, indice: (e.target.value || undefined) as Indice | undefined })
            }
            style={styleControle}
          >
            <option value="">Tous</option>
            {Object.entries(LIBELLE_INDICE).map(([cle, libelle]) => (
              <option key={cle} value={cle}>
                {libelle}
              </option>
            ))}
          </select>
        </Champ>
      </div>

      <div style={{ flex: "0 0 200px" }}>
        <Champ libelle="SIREN fournisseur">
          <input
            type="text"
            inputMode="numeric"
            placeholder="9 chiffres"
            value={valeurs.fournisseur_siren ?? ""}
            onChange={(e) =>
              onChange({ ...valeurs, fournisseur_siren: e.target.value.trim() || undefined })
            }
            style={styleControle}
          />
        </Champ>
      </div>

      <div style={{ flex: "0 0 180px" }}>
        <Champ libelle="Échéance avant">
          <input
            type="date"
            value={valeurs.echeance_avant ?? ""}
            onChange={(e) => onChange({ ...valeurs, echeance_avant: e.target.value || undefined })}
            style={styleControle}
          />
        </Champ>
      </div>

      <Bouton variante="secondaire" onClick={onReinitialiser}>
        Réinitialiser
      </Bouton>
    </div>
  );
}
