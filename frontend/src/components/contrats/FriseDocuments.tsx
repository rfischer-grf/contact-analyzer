import { tokens } from "../../theme";
import type { DocumentContrat } from "../../api/types";
import { formatDate } from "./format";

/**
 * Frise ordonnée des documents d'un contrat (#76).
 *
 * `document` (pièce physique) ≠ `contrat` (entité logique = état effectif foldé sur
 * la chaîne, §3.1). La chaîne est ordonnée par date de signature ; l'état effectif
 * affiché ailleurs est le résultat du fold sur cette chaîne (le contrat d'origine
 * puis ses avenants). Aucun lien avenant→parent n'est inféré ici : il est confirmé
 * en HITL (garde-fou, jamais d'auto-lien).
 *
 * On suppose `documents` déjà ordonnés par l'API (date de signature croissante).
 */

interface FriseDocumentsProps {
  documents: DocumentContrat[];
}

function libelleDocument(d: DocumentContrat): string {
  if (d.numero_avenant === null || d.numero_avenant === undefined) {
    return "Contrat d'origine";
  }
  return `Avenant n°${d.numero_avenant}`;
}

export function FriseDocuments({ documents }: FriseDocumentsProps): JSX.Element {
  return (
    <div>
      <h3 style={{ fontSize: tokens.police.lg, margin: `0 0 ${tokens.espace.md}` }}>
        Chaîne des documents
      </h3>

      {documents.length === 0 ? (
        <p style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue, margin: 0 }}>
          Aucun document rattaché.
        </p>
      ) : (
        <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {documents.map((d, i) => {
            const estOrigine = d.numero_avenant === null || d.numero_avenant === undefined;
            return (
              <li
                key={d.sha256}
                style={{
                  position: "relative",
                  paddingLeft: tokens.espace.lg,
                  paddingBottom: i < documents.length - 1 ? tokens.espace.md : 0,
                  borderLeft: `2px solid ${tokens.couleur.bordure}`,
                  marginLeft: 6,
                }}
              >
                {/* Pastille de la frise */}
                <span
                  style={{
                    position: "absolute",
                    left: -7,
                    top: 2,
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    background: estOrigine ? tokens.couleur.accent : tokens.couleur.statut.info,
                    border: `2px solid ${tokens.couleur.fond}`,
                  }}
                />
                <div style={{ fontWeight: 600, color: tokens.couleur.texte }}>
                  {libelleDocument(d)}
                </div>
                <div style={{ fontSize: tokens.police.sm, color: tokens.couleur.texteAttenue }}>
                  Signé le {formatDate(d.date_signature)}
                  {d.reference ? ` · réf. ${d.reference}` : ""}
                </div>
                <div
                  style={{
                    fontSize: tokens.police.sm,
                    color: tokens.couleur.texteAttenue,
                    fontFamily: "monospace",
                    wordBreak: "break-all",
                  }}
                  title="SHA256 (clé canonique du document, §2.1)"
                >
                  {d.sha256.slice(0, 16)}…
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
