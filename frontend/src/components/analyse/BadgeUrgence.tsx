/**
 * Pastille d'urgence selon la proximité de la `date_limite_denonciation`,
 * alignée sur les paliers d'alerte de la spec §2.6 (J−90 / J−60 / J−30 / J−7)
 * et les jetons de couleur `palier*` du thème (#72/#83).
 *
 * Utilisée par l'échéancier (#81). La couleur n'est qu'indicative : la vraie
 * alerte est le job quotidien loggé côté serveur (garde-fou §2.6), jamais l'UI.
 */
import { couleurs, rayons, typo, espacements } from "../../theme/tokens";

/** Palier de couleur en fonction des jours restants avant la date limite. */
export function couleurPalier(jours: number): string {
  if (jours <= 7) return couleurs.palier7;
  if (jours <= 30) return couleurs.palier30;
  if (jours <= 90) return couleurs.palier90;
  return couleurs.palierLoin;
}

/** Libellé court du niveau d'urgence (pour lecteurs d'écran + lisibilité). */
function libellePalier(jours: number): string {
  if (jours < 0) return "Échue";
  if (jours <= 7) return "Critique";
  if (jours <= 30) return "Urgent";
  if (jours <= 90) return "À surveiller";
  return "Lointain";
}

export function BadgeUrgence({ jours }: { jours: number }): JSX.Element {
  const couleur = couleurPalier(jours);
  return (
    <span
      title={`${jours} jour(s) avant la date limite de dénonciation`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: espacements.xs,
        background: `${couleur}1a`, // teinte douce (alpha hex) du palier
        color: couleur,
        border: `1px solid ${couleur}`,
        borderRadius: rayons.rond,
        padding: `${espacements.xxs} ${espacements.sm}`,
        fontSize: typo.taille.xs,
        fontWeight: typo.graisse.semi,
        whiteSpace: "nowrap",
      }}
    >
      <span aria-hidden style={{ width: 6, height: 6, borderRadius: "50%", background: couleur }} />
      {libellePalier(jours)} · J−{Math.max(0, jours)}
    </span>
  );
}
