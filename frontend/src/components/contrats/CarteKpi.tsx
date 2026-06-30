/**
 * Carte KPI du tableau de bord (#74).
 *
 * Présentation pure : un intitulé, une valeur mise en avant, un détail optionnel.
 * Tout le style passe par les jetons du thème (`../../theme/tokens`) — aucune
 * couleur / espacement en dur (cf. #72/#83).
 */
import { Carte } from "../analyse/primitives";
import { couleurs, espacements, typo } from "../../theme/tokens";

interface CarteKpiProps {
  intitule: string;
  valeur: string | number;
  detail?: string;
  /** Couleur d'accent de la valeur (sinon couleur de texte standard). */
  accent?: string;
}

export function CarteKpi({ intitule, valeur, detail, accent }: CarteKpiProps): JSX.Element {
  return (
    <Carte style={{ flex: "1 1 200px", minWidth: 200 }}>
      <div style={{ fontSize: typo.taille.sm, color: couleurs.texteAttenue }}>{intitule}</div>
      <div
        style={{
          fontSize: typo.taille.xxl,
          fontWeight: typo.graisse.forte,
          color: accent ?? couleurs.texte,
          marginTop: espacements.xs,
        }}
      >
        {valeur}
      </div>
      {detail && (
        <div
          style={{
            fontSize: typo.taille.sm,
            color: couleurs.texteFaible,
            marginTop: espacements.xs,
          }}
        >
          {detail}
        </div>
      )}
    </Carte>
  );
}
