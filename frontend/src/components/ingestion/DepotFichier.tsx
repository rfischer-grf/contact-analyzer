import { useCallback, useRef, useState } from "react";
import { tokens } from "../../theme";

/**
 * Zone de dépôt d'un contrat (#77).
 *
 * Présentation + sélection du fichier uniquement (glisser-déposer + sélecteur).
 * Le calcul du SHA256 et le flux presign → PUT S3 → confirm sont portés par le
 * parent (`Upload`), pour garder ici un composant de présentation testable.
 *
 * Garde-fou (§2.1) : aucun octet ne part d'ici vers l'API ; le PUT direct vers
 * S3 (Garage) est déclenché par le parent une fois le fichier choisi.
 *
 * Contrat de thème supposé (fourni par la fondation, cf. CarteKpi) :
 *   tokens.couleurs.{fond, surface, bordure, accent, accentDoux, texte, texteAttenue}
 *   tokens.espacements.{sm, md, lg, xl}  ·  tokens.rayons.{md, lg}  ·  tokens.typo.taille.{sm, md, lg}
 */

interface DepotFichierProps {
  /** Fichier actuellement sélectionné (remonté par le parent). */
  fichier: File | null;
  /** Sélection (sélecteur ou glisser-déposer). */
  onSelection: (fichier: File | null) => void;
  /** Déclenche le dépôt (calcul SHA256 + presign + PUT + confirm). */
  onDeposer: () => void;
  /** Désactive l'interaction pendant un dépôt en cours. */
  enCours: boolean;
}

/** Taille lisible (Ko/Mo) d'un fichier. */
function tailleLisible(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

export function DepotFichier({
  fichier,
  onSelection,
  onDeposer,
  enCours,
}: DepotFichierProps): JSX.Element {
  const [survol, setSurvol] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const surDepot = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setSurvol(false);
      if (enCours) return;
      const f = e.dataTransfer.files?.[0] ?? null;
      onSelection(f);
    },
    [enCours, onSelection],
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!enCours) setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={surDepot}
        onClick={() => !enCours && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !enCours) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        style={{
          border: `2px dashed ${survol ? tokens.couleurs.accent : tokens.couleurs.bordure}`,
          background: survol ? tokens.couleurs.accentDoux : tokens.couleurs.surface,
          borderRadius: tokens.rayons.lg,
          padding: tokens.espacements.xl,
          textAlign: "center",
          cursor: enCours ? "default" : "pointer",
          opacity: enCours ? 0.6 : 1,
          transition: "border-color 120ms ease, background 120ms ease",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          onChange={(e) => onSelection(e.target.files?.[0] ?? null)}
          disabled={enCours}
          style={{ display: "none" }}
        />
        {fichier ? (
          <div>
            <div style={{ fontSize: tokens.typo.taille.md, color: tokens.couleurs.texte, fontWeight: 600 }}>
              {fichier.name}
            </div>
            <div style={{ fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue }}>
              {tailleLisible(fichier.size)} · {fichier.type || "type inconnu"}
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: tokens.typo.taille.lg, color: tokens.couleurs.texte }}>
              Glisser un PDF ici, ou cliquer pour choisir
            </div>
            <div style={{ fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue }}>
              Contrat fournisseur (PDF). Les octets partent directement vers le stockage
              souverain, jamais via l'API.
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: tokens.espacements.sm, marginTop: tokens.espacements.md }}>
        <button
          type="button"
          onClick={onDeposer}
          disabled={!fichier || enCours}
          style={{
            background: tokens.couleurs.accent,
            color: tokens.couleurs.texteInverse,
            border: "none",
            borderRadius: tokens.rayons.md,
            padding: `${tokens.espacements.sm} ${tokens.espacements.lg}`,
            fontSize: tokens.typo.taille.md,
            fontWeight: 600,
            cursor: !fichier || enCours ? "not-allowed" : "pointer",
            opacity: !fichier || enCours ? 0.6 : 1,
          }}
        >
          {enCours ? "Dépôt en cours…" : "Déposer le contrat"}
        </button>
        {fichier && !enCours && (
          <button
            type="button"
            onClick={() => onSelection(null)}
            style={{
              background: "transparent",
              color: tokens.couleurs.texteAttenue,
              border: `1px solid ${tokens.couleurs.bordure}`,
              borderRadius: tokens.rayons.md,
              padding: `${tokens.espacements.sm} ${tokens.espacements.lg}`,
              fontSize: tokens.typo.taille.md,
              cursor: "pointer",
            }}
          >
            Retirer
          </button>
        )}
      </div>
    </div>
  );
}
