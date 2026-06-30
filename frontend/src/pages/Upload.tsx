import { useEffect, useRef, useState } from "react";
import { apiClient, putVersS3 } from "../api/client";

/**
 * Dépôt d'un contrat + suivi de statut (ticket #55).
 *
 * Flux (spec §2.1) :
 *   1. calcul du SHA256 du fichier côté navigateur (clé canonique, idempotence) ;
 *   2. POST /uploads/presign → URL présignée (le tenant/bucket sont dérivés du token) ;
 *   3. PUT direct navigateur → S3 (Garage) : les octets NE transitent PAS par l'API ;
 *   4. POST /uploads/confirm → l'API fait un HEAD puis démarre le workflow Temporal ;
 *   5. polling GET /statut/{workflow_id} pour suivre la saga d'ingestion.
 */

interface PresignResponse {
  url: string;
  methode: string;
  cle: string;
  bucket: string;
  expire_dans: number;
}

interface ConfirmResponse {
  cle: string;
  etat: string;
}

interface StatutResponse {
  workflow_id: string;
  statut: string;
}

// États de la saga (spec §4) jusqu'à un état terminal.
const ETATS_TERMINAUX = new Set(["COMMITE", "VALIDE", "REJETE_TECHNIQUE", "REJETE_METIER"]);

/** SHA256 hex du fichier via WebCrypto (aucune dépendance). */
async function sha256Hex(fichier: File): Promise<string> {
  const buffer = await fichier.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((o) => o.toString(16).padStart(2, "0"))
    .join("");
}

export function Upload(): JSX.Element {
  const [fichier, setFichier] = useState<File | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [statut, setStatut] = useState<string | null>(null);

  // Référence d'intervalle de polling, nettoyée au démontage.
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  function demarrerPolling(id: string): void {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
    }
    pollRef.current = window.setInterval(async () => {
      try {
        const reponse = await apiClient.get<StatutResponse>(`/statut/${encodeURIComponent(id)}`);
        setStatut(reponse.statut);
        if (ETATS_TERMINAUX.has(reponse.statut) && pollRef.current !== null) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (e) {
        // Le workflow peut ne pas être interrogeable immédiatement ; on log et on réessaie.
        console.warn("Statut indisponible, nouvelle tentative…", e);
      }
    }, 3000);
  }

  async function deposer(): Promise<void> {
    if (!fichier) {
      return;
    }
    setEnCours(true);
    setErreur(null);
    setMessage(null);
    setStatut(null);
    setWorkflowId(null);

    try {
      const contentType = fichier.type || "application/pdf";

      setMessage("Calcul de l'empreinte SHA256…");
      const sha256 = await sha256Hex(fichier);

      setMessage("Demande d'URL présignée…");
      const presign = await apiClient.post<PresignResponse>("/uploads/presign", {
        sha256,
        content_type: contentType,
      });

      setMessage("Envoi direct vers le stockage S3…");
      await putVersS3(presign.url, fichier, contentType);

      setMessage("Confirmation de l'upload…");
      const confirm = await apiClient.post<ConfirmResponse>("/uploads/confirm", { sha256 });

      // Le workflow Temporal est idempotent sur le SHA256 (spec §2.1) ;
      // on s'aligne sur cette convention pour le workflow_id de suivi.
      const id = sha256;
      setWorkflowId(id);
      setStatut(confirm.etat);
      setMessage(`Upload confirmé (clé ${confirm.cle}). Suivi de l'ingestion…`);
      demarrerPolling(id);
    } catch (e) {
      setErreur(String(e instanceof Error ? e.message : e));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section>
      <h2>Déposer un contrat fournisseur</h2>
      <p style={{ color: "#555", fontSize: 14 }}>
        Le fichier part directement vers le stockage souverain (S3/Garage) via une URL présignée.
        Les octets ne transitent jamais par l'API.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "12px 0" }}>
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
          disabled={enCours}
        />
        <button onClick={() => void deposer()} disabled={!fichier || enCours}>
          {enCours ? "En cours…" : "Déposer"}
        </button>
      </div>

      {message && <p style={{ fontSize: 14 }}>{message}</p>}
      {erreur && <p style={{ color: "#b00", fontSize: 14 }}>Erreur : {erreur}</p>}

      {workflowId && (
        <div style={{ marginTop: 16, padding: 12, border: "1px solid #ddd", borderRadius: 6 }}>
          <div style={{ fontSize: 13, color: "#555" }}>Workflow : {workflowId}</div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Statut : {statut ?? "—"}</div>
          {statut === "A_VALIDER" && (
            <p style={{ fontSize: 14 }}>
              Prêt pour la validation humaine : rendez-vous dans l'onglet « Validation (HITL) ».
            </p>
          )}
        </div>
      )}
    </section>
  );
}
