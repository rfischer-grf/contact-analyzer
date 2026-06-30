import { tokens } from "../../theme";
import type { FiltresContratsValeurs } from "../../api/types";
import { LIBELLE_INDICE } from "./format";

/**
 * Barre de filtres de la liste des contrats (#75).
 *
 * Filtres = facettes structurées (SQL `WHERE` côté API §6, jamais du vectoriel) :
 * indice, SIREN fournisseur, échéance avant une date. État contrôlé remonté au
 * parent qui appelle `api.contrats.lister({...})`.
 */

interface FiltresContratsProps {
  valeurs: FiltresContratsValeurs;
  onChange: (valeurs: FiltresContratsValeurs) => void;
  onReinitialiser: () => void;
}

const styleChamp: React.CSSProperties = {
  padding: tokens.espace.sm,
  border: `1px solid ${tokens.couleur.bordure}`,
  borderRadius: tokens.rayon.md,
  background: tokens.couleur.fondCarte,
  color: tokens.couleur.texte,
  fontSize: tokens.police.sm,
};

const styleLabel: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  fontSize: tokens.police.sm,
  color: tokens.couleur.texteAttenue,
};

export function FiltresContrats({
  valeurs,
  onChange,
  onReinitialiser,
}: FiltresContratsProps): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        gap: tokens.espace.md,
        flexWrap: "wrap",
        alignItems: "flex-end",
        marginBottom: tokens.espace.lg,
      }}
    >
      <label style={styleLabel}>
        Indice
        <select
          value={valeurs.indice ?? ""}
          onChange={(e) => onChange({ ...valeurs, indice: e.target.value || undefined })}
          style={styleChamp}
        >
          <option value="">Tous</option>
          {Object.entries(LIBELLE_INDICE).map(([cle, libelle]) => (
            <option key={cle} value={cle}>
              {libelle}
            </option>
          ))}
        </select>
      </label>

      <label style={styleLabel}>
        SIREN fournisseur
        <input
          type="text"
          inputMode="numeric"
          placeholder="9 chiffres"
          value={valeurs.fournisseur_siren ?? ""}
          onChange={(e) =>
            onChange({ ...valeurs, fournisseur_siren: e.target.value.trim() || undefined })
          }
          style={styleChamp}
        />
      </label>

      <label style={styleLabel}>
        Échéance avant
        <input
          type="date"
          value={valeurs.echeance_avant ?? ""}
          onChange={(e) => onChange({ ...valeurs, echeance_avant: e.target.value || undefined })}
          style={styleChamp}
        />
      </label>

      <button
        type="button"
        onClick={onReinitialiser}
        style={{
          ...styleChamp,
          cursor: "pointer",
          color: tokens.couleur.texteAttenue,
        }}
      >
        Réinitialiser
      </button>
    </div>
  );
}
