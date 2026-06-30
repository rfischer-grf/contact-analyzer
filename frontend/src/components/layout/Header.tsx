/**
 * En-tête du cockpit Clausio — ticket #72.
 *
 * Affiche le tenant courant et l'utilisateur (lecture seule, depuis les claims du
 * token — le tenant n'est jamais transmis à l'API, garde-fou §7) + déconnexion.
 * Style 100 % piloté par les jetons (`tokens`) pour le skin #83.
 */
import type { CSSProperties } from "react";
import { useAuth } from "../../auth/AuthContext";
import { styleBouton, stylePastille, tokens } from "../../theme";

const { couleurs, espacements, typo, dimensions, zIndex } = tokens;

const styleHeader: CSSProperties = {
  height: dimensions.hauteurHeader,
  flex: "0 0 auto",
  position: "sticky",
  top: 0,
  zIndex: zIndex.header,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: espacements.lg,
  padding: `0 ${espacements.xl}`,
  background: couleurs.surface,
  borderBottom: `1px solid ${couleurs.bordure}`,
};

const styleTitre: CSSProperties = {
  fontSize: typo.taille.md,
  fontWeight: typo.graisse.semi,
  color: couleurs.texte,
};

const styleZoneDroite: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: espacements.lg,
};

const styleUtilisateur: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-end",
  lineHeight: 1.2,
};

const styleNomUtilisateur: CSSProperties = {
  fontSize: typo.taille.sm,
  fontWeight: typo.graisse.moyenne,
  color: couleurs.texte,
};

const styleLibelleTenant: CSSProperties = {
  fontSize: typo.taille.xs,
  color: couleurs.texteFaible,
};

/** Titre contextuel affiché à gauche (ex. nom de la page courante). */
export function Header({ titre }: { titre?: string }): JSX.Element {
  const { utilisateur, tenant, seDeconnecter } = useAuth();

  return (
    <header style={styleHeader}>
      <div style={styleTitre}>{titre ?? "Cockpit"}</div>

      <div style={styleZoneDroite}>
        <span style={stylePastille("accent")} title="Tenant actif (dérivé du token)">
          Tenant&nbsp;: {tenant ?? "—"}
        </span>

        <div style={styleUtilisateur}>
          <span style={styleNomUtilisateur}>
            {utilisateur.nom ?? utilisateur.identifiant}
          </span>
          {utilisateur.email && (
            <span style={styleLibelleTenant}>{utilisateur.email}</span>
          )}
        </div>

        <button
          type="button"
          onClick={seDeconnecter}
          style={styleBouton("secondaire")}
        >
          Se déconnecter
        </button>
      </div>
    </header>
  );
}
