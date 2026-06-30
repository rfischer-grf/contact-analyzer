import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { EtatIngestion } from "../api/types";
import { tokens } from "../theme";
import { DepotFichier } from "../components/ingestion/DepotFichier";
import { SuiviStatut } from "../components/ingestion/SuiviStatut";

/**
 * Dépôt d'un contrat fournisseur + suivi de la saga d'ingestion (#77, spec §2.1 / §4).
 *
 * Flux :
 *   1. SHA256 du fichier côté navigateur (clé canonique, idempotence) — WebCrypto.
 *   2. api.uploads.presign({sha256, content_type}) → URL présignée S3.
 *      (bucket/préfixe dérivés du token côté API ; jamais fournis par le client.)
 *   3. PUT direct navigateur → S3 (Garage), sans bearer, Content-Type = content_type.
 *      Les octets NE transitent JAMAIS par l'API (garde-fou §2.1).
 *   4. api.uploads.confirm({sha256}) → l'API fait un HEAD puis démarre le workflow Temporal.
 *   5. Polling api.statut.get(workflowId) → progression jusqu'à un état terminal.
 *
 * Tout le style passe par les tokens du thème (`../theme`).
 */

/** États terminaux de la saga (spec §4) : on arrête le polling. */
const ETATS_TERMINAUX: ReadonlySet<string> = new Set([
  "COMMITE",
  "REJETE_TECHNIQUE",
  "REJETE_METIER",
]);

const INTERVALLE_POLLING_MS = 3000;

/** SHA256 hex du fichier via WebCrypto (aucune dépendance externe). */
async function sha256Hex(fichier: File): Promise<string> {
  const buffer = await fichier.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((octet) => octet.toString(16).padStart(2, "0"))
    .join("");
}

export function Upload(): JSX.Element {
  const [fichier, setFichier] = useState<File | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [statut, setStatut] = useState<EtatIngestion | null>(null);

  // Référence de l'intervalle de polling, nettoyée au démontage / au redémarrage.
  const pollRef = useRef<number | null>(null);

  function arreterPolling(): void {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => arreterPolling, []);

  function demarrerPolling(id: string): void {
    arreterPolling();
    pollRef.current = window.setInterval(() => {
      void (async () => {
        try {
          const reponse = await api.statut.get(id);
          setStatut(reponse.statut);
          if (ETATS_TERMINAUX.has(reponse.statut)) {
            arreterPolling();
          }
        } catch (e) {
          // Le workflow peut ne pas être interrogeable immédiatement (404) ; on
          // log et on réessaie au prochain tick plutôt que d'arrêter le suivi.
          console.warn("Statut indisponible, nouvelle tentative…", e);
        }
      })();
    }, INTERVALLE_POLLING_MS);
  }

  async function deposer(): Promise<void> {
    if (!fichier) return;
    setEnCours(true);
    setErreur(null);
    setMessage(null);
    setStatut(null);
    setWorkflowId(null);
    arreterPolling();

    try {
      const contentType = fichier.type || "application/pdf";

      setMessage("Calcul de l'empreinte SHA256…");
      const sha256 = await sha256Hex(fichier);

      setMessage("Demande d'URL présignée…");
      const presign = await api.uploads.presign({ sha256, content_type: contentType });

      setMessage("Envoi direct vers le stockage souverain (S3/Garage)…");
      // PUT brut, sans bearer : l'URL signée porte déjà l'autorisation (§2.1).
      const reponseS3 = await fetch(presign.url, {
        method: presign.methode,
        headers: { "Content-Type": contentType },
        body: fichier,
      });
      if (!reponseS3.ok) {
        throw new Error(`Échec de l'envoi S3 (HTTP ${reponseS3.status}).`);
      }

      setMessage("Confirmation de l'upload…");
      const confirm = await api.uploads.confirm({ sha256 });

      // L'API démarre la saga Temporal et renvoie son workflow_id (scopé tenant).
      const id = confirm.workflow_id;
      setWorkflowId(id);
      setStatut(confirm.etat);
      setMessage(`Upload confirmé (clé ${confirm.cle}). Suivi de l'ingestion en cours…`);
      demarrerPolling(id);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section>
      <h2 style={{ fontSize: tokens.typo.taille.xl, color: tokens.couleurs.texte, marginTop: 0 }}>
        Déposer un contrat fournisseur
      </h2>
      <p style={{ color: tokens.couleurs.texteAttenue, fontSize: tokens.typo.taille.sm }}>
        Le fichier part directement vers le stockage souverain (S3/Garage) via une URL
        présignée. Les octets ne transitent jamais par l'API. La clé canonique est le
        SHA256 du fichier (dédoublonnage et idempotence).
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: tokens.espacements.xl, alignItems: "start" }}>
        <div>
          <DepotFichier
            fichier={fichier}
            onSelection={setFichier}
            onDeposer={() => void deposer()}
            enCours={enCours}
          />

          {message && (
            <p style={{ fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue, marginTop: tokens.espacements.md }}>
              {message}
            </p>
          )}
          {erreur && (
            <p
              role="alert"
              style={{
                fontSize: tokens.typo.taille.sm,
                color: tokens.couleurs.danger,
                background: tokens.couleurs.dangerDoux,
                padding: tokens.espacements.sm,
                borderRadius: tokens.rayons.md,
                marginTop: tokens.espacements.md,
              }}
            >
              Erreur : {erreur}
            </p>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: tokens.espacements.md }}>
          {workflowId ? (
            <>
              <div
                style={{
                  fontSize: tokens.typo.taille.xs,
                  color: tokens.couleurs.texteAttenue,
                  wordBreak: "break-all",
                }}
              >
                Workflow : <code>{workflowId}</code>
              </div>
              <SuiviStatut statut={statut} />
              {statut === "A_VALIDER" && (
                <p
                  style={{
                    fontSize: tokens.typo.taille.sm,
                    color: tokens.couleurs.accentFort,
                    background: tokens.couleurs.accentDoux,
                    padding: tokens.espacements.sm,
                    borderRadius: tokens.rayons.md,
                  }}
                >
                  Prêt pour la validation humaine : voir l'onglet « Validation (HITL) ».
                </p>
              )}
            </>
          ) : (
            <SuiviChamp
              onSuivre={(id) => {
                setWorkflowId(id);
                setStatut(null);
                demarrerPolling(id);
              }}
            />
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Saisie manuelle d'un workflow_id à suivre (filet de sécurité tant que
 * l'API ne renvoie pas explicitement le workflow_id — TODO #16/#22).
 */
function SuiviChamp({ onSuivre }: { onSuivre: (id: string) => void }): JSX.Element {
  const [valeur, setValeur] = useState("");
  return (
    <div
      style={{
        border: `1px solid ${tokens.couleurs.bordure}`,
        borderRadius: tokens.rayons.md,
        padding: tokens.espacements.md,
        background: tokens.couleurs.surface,
      }}
    >
      <div style={{ fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue, marginBottom: tokens.espacements.sm }}>
        Suivre une ingestion existante (workflow_id) :
      </div>
      <div style={{ display: "flex", gap: tokens.espacements.sm }}>
        <input
          value={valeur}
          onChange={(e) => setValeur(e.target.value)}
          placeholder="SHA256 / workflow_id"
          style={{
            flex: 1,
            minWidth: 0,
            border: `1px solid ${tokens.couleurs.bordure}`,
            borderRadius: tokens.rayons.md,
            padding: tokens.espacements.sm,
            fontSize: tokens.typo.taille.sm,
          }}
        />
        <button
          type="button"
          onClick={() => valeur.trim() && onSuivre(valeur.trim())}
          disabled={!valeur.trim()}
          style={{
            background: tokens.couleurs.accent,
            color: tokens.couleurs.texteInverse,
            border: "none",
            borderRadius: tokens.rayons.md,
            padding: `${tokens.espacements.sm} ${tokens.espacements.md}`,
            fontSize: tokens.typo.taille.sm,
            cursor: valeur.trim() ? "pointer" : "not-allowed",
            opacity: valeur.trim() ? 1 : 0.6,
          }}
        >
          Suivre
        </button>
      </div>
    </div>
  );
}
