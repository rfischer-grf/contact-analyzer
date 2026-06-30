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
 *   tokens.couleur.{fond, fondCarte, bordure, accent, accentDoux, texte, texteAttenue}
 *   tokens.espace.{sm, md, lg, xl}  ·  tokens.rayon.{md, lg}  ·  tokens.police.{sm, md, lg}
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
          border: `2px dashed ${survol ? tokens.couleur.accent : tokens.couleur.bordure}`,
          background: survol ? tokens.couleur.accentDoux : tokens.couleur.fondCarte,
          borderRadius: tokens.rayon.lg,
          padding: tokens.espace.xl,
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
            <div style={{ fontSize: tokens.police.md, color: tokens.couleur.texte, fontWeight: 600 }}>
              {fichier.name}
            </div>
            <div style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue }}>
              {tailleLisible(fichier.size)} · {fichier.type || "type inconnu"}
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: tokens.police.lg, color: tokens.couleur.texte }}>
              Glisser un PDF ici, ou cliquer pour choisir
            </div>
            <div style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue }}>
              Contrat fournisseur (PDF). Les octets partent directement vers le stockage
              souverain, jamais via l'API.
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: tokens.espace.sm, marginTop: tokens.espace.md }}>
        <button
          type="button"
          onClick={onDeposer}
          disabled={!fichier || enCours}
          style={{
            background: tokens.couleur.accent,
            color: tokens.couleur.texteInverse,
            border: "none",
            borderRadius: tokens.rayon.md,
            padding: `${tokens.espace.sm} ${tokens.espace.lg}`,
            fontSize: tokens.police.md,
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
              color: tokens.couleur.texteAttenue,
              border: `1px solid ${tokens.couleur.bordure}`,
              borderRadius: tokens.rayon.md,
              padding: `${tokens.espace.sm} ${tokens.espace.lg}`,
              fontSize: tokens.police.md,
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
