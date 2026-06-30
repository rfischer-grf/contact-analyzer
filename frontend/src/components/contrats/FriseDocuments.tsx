/**
 * Frise ordonnée des documents d'un contrat (#76).
 *
 * `document` (pièce physique) ≠ `contrat` (entité logique = état effectif foldé sur
 * la chaîne, §3.1). La chaîne est ordonnée par date de signature ; l'état effectif
 * affiché ailleurs est le résultat du fold sur cette chaîne (contrat d'origine puis
 * avenants). Aucun lien avenant→parent n'est inféré ici : il est confirmé en HITL
 * (garde-fou, jamais d'auto-lien).
 *
 * On suppose `documents` déjà ordonnés par l'API (date de signature croissante).
 */
import type { DocumentContrat } from "../../api/types";
import { formaterDateIso } from "../analyse/format";
import { couleurs, espacements, typo } from "../../theme/tokens";

interface FriseDocumentsProps {
  documents: DocumentContrat[];
}

function estOrigine(d: DocumentContrat): boolean {
  return d.numero_avenant === null || d.numero_avenant === undefined;
}

function libelleDocument(d: DocumentContrat): string {
  return estOrigine(d) ? "Contrat d'origine" : `Avenant n°${d.numero_avenant}`;
}

export function FriseDocuments({ documents }: FriseDocumentsProps): JSX.Element {
  return (
    <div>
      <h3 style={{ fontSize: typo.taille.lg, fontWeight: typo.graisse.semi, margin: `0 0 ${espacements.md}` }}>
        Chaîne des documents
      </h3>

      {documents.length === 0 ? (
        <p style={{ fontSize: typo.taille.sm, color: couleurs.texteFaible, margin: 0 }}>
          Aucun document rattaché.
        </p>
      ) : (
        <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {documents.map((d, i) => (
            <li
              key={d.sha256}
              style={{
                position: "relative",
                paddingLeft: espacements.lg,
                paddingBottom: i < documents.length - 1 ? espacements.lg : 0,
                borderLeft: `2px solid ${couleurs.bordure}`,
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
                  background: estOrigine(d) ? couleurs.accent : couleurs.info,
                  border: `2px solid ${couleurs.surface}`,
                }}
              />
              <div style={{ fontWeight: typo.graisse.semi, color: couleurs.texte }}>
                {libelleDocument(d)}
              </div>
              <div style={{ fontSize: typo.taille.sm, color: couleurs.texteAttenue }}>
                Signé le {formaterDateIso(d.date_signature)}
                {d.reference ? ` · réf. ${d.reference}` : ""}
              </div>
              <div
                style={{
                  fontSize: typo.taille.xs,
                  color: couleurs.texteFaible,
                  fontFamily: typo.familleMono,
                  wordBreak: "break-all",
                }}
                title="SHA256 (clé canonique du document, §2.1)"
              >
                {d.sha256.slice(0, 16)}…
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
