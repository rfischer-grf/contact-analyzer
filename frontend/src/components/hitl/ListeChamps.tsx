import { tokens } from "../../theme";
import type { ChampRevue } from "../../api/types";

/**
 * Liste des champs à revoir, éditables (#78, spec §2.4).
 *
 * Chaque champ porte valeur + confiance + provenance (wrapper `Champ`, §3). Les
 * champs sous le seuil de confiance sont signalés (danger). La sélection d'un
 * champ pilote le surlignage de sa source dans l'aperçu PDF. Les corrections
 * alimentent le gold set (envoyées par le parent à la validation).
 *
 * Contrat de thème supposé (fourni par la fondation) :
 *   tokens.couleur.{fondCarte, bordure, accent, accentDoux, texte, texteAttenue, danger, succes}
 *   tokens.espace.{xs, sm, md}  ·  tokens.rayon.md  ·  tokens.police.{xs, sm, md}
 */

/** Seuil d'affichage « confiance faible » (cohérent avec le seuil API par défaut). */
const SEUIL_AFFICHAGE = 0.7;

interface ListeChampsProps {
  champs: ChampRevue[];
  /** Clé du champ sélectionné (surlignage source), ou `null`. */
  selection: string | null;
  onSelection: (cle: string) => void;
  /** Édition de la valeur d'un champ. */
  onModifier: (cle: string, valeur: string) => void;
}

export function ListeChamps({
  champs,
  selection,
  onSelection,
  onModifier,
}: ListeChampsProps): JSX.Element {
  if (champs.length === 0) {
    return (
      <p style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue }}>
        Aucun champ sous le seuil de confiance : rien à revoir manuellement.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: tokens.espace.sm }}>
      {champs.map((champ) => {
        const faible = champ.confiance < SEUIL_AFFICHAGE;
        const actif = selection === champ.cle;
        const modifie = champ.valeur !== champ.valeurOriginale;
        return (
          <div
            key={champ.cle}
            onClick={() => onSelection(champ.cle)}
            style={{
              border: `${actif ? 2 : 1}px solid ${actif ? tokens.couleur.accent : tokens.couleur.bordure}`,
              background: actif ? tokens.couleur.accentDoux : tokens.couleur.fondCarte,
              borderRadius: tokens.rayon.md,
              padding: tokens.espace.md,
              cursor: "pointer",
            }}
          >
            <label
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                fontSize: tokens.police.sm,
                color: tokens.couleur.texteAttenue,
                gap: tokens.espace.sm,
              }}
            >
              <span style={{ color: tokens.couleur.texte }}>{champ.libelle}</span>
              <span
                style={{
                  fontSize: tokens.police.xs,
                  color: faible ? tokens.couleur.danger : tokens.couleur.succes,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                confiance {Math.round(champ.confiance * 100)}%
              </span>
            </label>

            <input
              value={champ.valeur}
              onChange={(e) => onModifier(champ.cle, e.target.value)}
              onClick={(e) => e.stopPropagation()}
              style={{
                width: "100%",
                boxSizing: "border-box",
                marginTop: tokens.espace.xs,
                border: `1px solid ${modifie ? tokens.couleur.accent : tokens.couleur.bordure}`,
                borderRadius: tokens.rayon.md,
                padding: tokens.espace.sm,
                fontSize: tokens.police.md,
                color: tokens.couleur.texte,
              }}
            />

            {modifie && (
              <div style={{ fontSize: tokens.police.xs, color: tokens.couleur.texteAttenue, marginTop: tokens.espace.xs }}>
                Valeur initiale : « {champ.valeurOriginale || "—"} » → corrigée
              </div>
            )}

            {champ.source && (
              <p style={{ fontSize: tokens.police.xs, color: tokens.couleur.texteAttenue, margin: `${tokens.espace.xs} 0 0` }}>
                Source p.{champ.source.page} : « {champ.source.extrait} »
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
