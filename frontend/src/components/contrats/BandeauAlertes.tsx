/**
 * Bandeau d'alertes par palier de date limite de dénonciation (#74).
 *
 * Reçoit `alertes` (Record clé palier → nombre de contrats), clés "90"/"60"/"30"/"7"
 * (spec §2.6). Chaque palier compte les contrats dont la **date limite de
 * dénonciation** (échéance − préavis, date actionnable) tombe exactement à J−n.
 * Couleur = jetons `palier*` du thème via `couleurPalier` (cohérent avec
 * l'échéancier #81). Rappel : la vraie alerte est le job quotidien loggé côté
 * serveur (garde-fou §2.6), pas cet affichage.
 */
import { couleurs, espacements, rayons, typo } from "../../theme/tokens";
import { couleurPalier } from "../analyse/BadgeUrgence";
import { PALIERS_ALERTE } from "./format";

interface BandeauAlertesProps {
  alertes: Record<string, number>;
}

export function BandeauAlertes({ alertes }: BandeauAlertesProps): JSX.Element {
  return (
    <div>
      <div
        style={{
          fontSize: typo.taille.sm,
          fontWeight: typo.graisse.semi,
          color: couleurs.texteAttenue,
          marginBottom: espacements.sm,
        }}
      >
        Échéances de dénonciation imminentes (par palier J−n)
      </div>
      <div style={{ display: "flex", gap: espacements.md, flexWrap: "wrap" }}>
        {PALIERS_ALERTE.map((palier) => {
          const nombre = alertes[String(palier)] ?? 0;
          const couleur = couleurPalier(palier);
          return (
            <div
              key={palier}
              style={{
                flex: "1 1 130px",
                minWidth: 130,
                background: `${couleur}1a`, // teinte douce (alpha hex) du palier
                border: `1px solid ${couleur}`,
                borderRadius: rayons.md,
                padding: espacements.md,
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: typo.taille.xl, fontWeight: typo.graisse.forte, color: couleur }}>
                {nombre}
              </div>
              <div style={{ fontSize: typo.taille.sm, color: couleurs.texteAttenue }}>
                à J−{palier}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
