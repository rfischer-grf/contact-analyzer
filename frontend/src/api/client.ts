/**
 * Client HTTP typé de l'API CLM (Clausio) — tickets #72/#74.
 *
 * - Base = `import.meta.env.VITE_API_URL`.
 * - Bearer Keycloak ajouté systématiquement (sauf PUT S3 et feed ICS public).
 * - Le tenant n'est JAMAIS transmis : l'API le dérive du token (garde-fou §7).
 * - Sur 401, on tente UN rafraîchissement de token puis on rejoue la requête.
 *
 * Le client expose des méthodes namespacées (`api.uploads`, `api.contrats`, …)
 * conformes au contrat. Un client bas niveau (`apiClient.get/post/del`) et le
 * helper `putVersS3` restent exposés pour les usages existants.
 */
import { getToken, rafraichirToken } from "../auth/keycloak";
import type {
  AbonnementIcs,
  ChampsARevoirReponse,
  ConfirmReponse,
  ConfirmRequete,
  ContratDetail,
  ContratResume,
  CorrectionsReponse,
  CorrectionsRequete,
  DecisionHitlReponse,
  FacetteParams,
  ListerContratsParams,
  PresignReponse,
  PresignRequete,
  ProjectionReponse,
  ProjectionRequete,
  ResultatSemantique,
  StatutReponse,
  TableauDeBord,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public readonly statut: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** N'ajoute pas le bearer (ex. ressources publiques). */
  sansAuth?: boolean;
};

async function requete<T>(chemin: string, options: Options = {}): Promise<T> {
  const reponse = await envoyer(chemin, options, false);
  return await lireCorps<T>(reponse);
}

/**
 * Exécute la requête en ajoutant le bearer. Sur 401, rafraîchit le token UNE
 * fois et rejoue (`dejaRejoue` empêche la boucle infinie).
 */
async function envoyer(
  chemin: string,
  options: Options,
  dejaRejoue: boolean,
): Promise<Response> {
  const headers = new Headers(options.headers);

  if (!options.sansAuth) {
    const token = await getToken();
    headers.set("Authorization", `Bearer ${token}`);
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const reponse = await fetch(`${BASE_URL}${chemin}`, { ...options, headers, body });

  if (reponse.status === 401 && !options.sansAuth && !dejaRejoue) {
    const rafraichi = await rafraichirToken();
    if (rafraichi) {
      return envoyer(chemin, options, true);
    }
  }

  if (!reponse.ok) {
    const detail = await reponse.text().catch(() => reponse.statusText);
    throw new ApiError(reponse.status, detail || reponse.statusText);
  }
  return reponse;
}

async function lireCorps<T>(reponse: Response): Promise<T> {
  // 204 No Content (révocation d'abonnement, …) → pas de corps.
  if (reponse.status === 204) {
    return undefined as T;
  }
  return (await reponse.json()) as T;
}

/** Construit une query string à partir d'un objet (ignore les valeurs nulles). */
function qs(params?: object): string {
  if (!params) {
    return "";
  }
  const usp = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(params)) {
    if (valeur !== undefined && valeur !== null && valeur !== "") {
      usp.set(cle, String(valeur));
    }
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

/** Client bas niveau (verbes HTTP bruts). */
export const apiClient = {
  get: <T>(chemin: string) => requete<T>(chemin, { method: "GET" }),
  post: <T>(chemin: string, body?: unknown) =>
    requete<T>(chemin, { method: "POST", body }),
  put: <T>(chemin: string, body?: unknown) =>
    requete<T>(chemin, { method: "PUT", body }),
  del: <T>(chemin: string) => requete<T>(chemin, { method: "DELETE" }),
};

/**
 * PUT brut d'un fichier vers une URL présignée S3 (Garage).
 * Hors API : les octets vont directement navigateur→S3 (garde-fou §2.1), donc
 * PAS de bearer Keycloak ici — l'URL signée porte déjà l'autorisation.
 */
export async function putVersS3(
  url: string,
  fichier: File,
  contentType: string,
): Promise<void> {
  const reponse = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: fichier,
  });
  if (!reponse.ok) {
    throw new ApiError(reponse.status, `Échec de l'upload S3 (${reponse.status}).`);
  }
}

const id = (v: string) => encodeURIComponent(v);

/**
 * Client API typé namespacé — surface de référence pour les pages métier (#74→).
 */
export const api = {
  uploads: {
    /** Demande une URL présignée (tenant/bucket dérivés du token — §2.1). */
    presign: (req: PresignRequete) =>
      apiClient.post<PresignReponse>("/uploads/presign", req),
    /** Confirme la fin d'upload → l'API fait un HEAD puis démarre le workflow. */
    confirm: (req: ConfirmRequete) =>
      apiClient.post<ConfirmReponse>("/uploads/confirm", req),
  },

  statut: {
    /** Lit l'avancement de la saga d'ingestion (polling léger — §4). */
    get: (workflowId: string) =>
      apiClient.get<StatutReponse>(`/statut/${id(workflowId)}`),
  },

  contrats: {
    lister: (params?: ListerContratsParams) =>
      apiClient.get<ContratResume[]>(`/contrats${qs(params)}`),
    detail: (contratId: string) =>
      apiClient.get<ContratDetail>(`/contrats/${id(contratId)}`),
    /** Projection tarifaire indexée (P1 = P0 × (a + b·S1/S0) — §2.5). */
    projection: (contratId: string, req: ProjectionRequete) =>
      apiClient.post<ProjectionReponse>(`/contrats/${id(contratId)}/projection`, req),
  },

  tableauDeBord: {
    get: (params?: { aujourd_hui?: string }) =>
      apiClient.get<TableauDeBord>(`/tableau-de-bord${qs(params)}`),
  },

  recherche: {
    /** Recherche par facette extraite (SQL Postgres, pas du vectoriel — §6). */
    facette: (params?: FacetteParams) =>
      apiClient.get<ContratResume[]>(`/recherche/facette${qs(params)}`),
    /** Recherche sémantique sur le corps des clauses (vectoriel Weaviate — §6). */
    semantique: (q: string, k?: number) =>
      apiClient.get<ResultatSemantique[]>(
        `/recherche/semantique${qs({ q, k })}`,
      ),
  },

  hitl: {
    /** Champs sous le seuil + provenance + URL du PDF source (file de revue — §2.4). */
    champsARevoir: (contratId: string, seuil?: number) =>
      apiClient.get<ChampsARevoirReponse>(
        `/hitl/contrats/${id(contratId)}/champs-a-revoir${qs({ seuil })}`,
      ),
    /** Enregistre les corrections (alimentent le gold set — §2.4). */
    corrections: (contratId: string, req: CorrectionsRequete) =>
      apiClient.post<CorrectionsReponse>(
        `/hitl/contrats/${id(contratId)}/corrections`,
        req,
      ),
    /**
     * Signal `valider` du gate HITL (§4). `parentContratId` (optionnel) confirme
     * le rattachement d'un avenant au contrat parent proposé (#33) — jamais
     * d'auto-lien : le lien n'est posé qu'à cette confirmation explicite.
     */
    valider: (contratId: string, parentContratId?: string | null) =>
      apiClient.post<DecisionHitlReponse>(
        `/hitl/contrats/${id(contratId)}/valider`,
        parentContratId ? { parent_contrat_id: parentContratId } : undefined,
      ),
    /** Signal `rejeter` du gate HITL (§4). */
    rejeter: (contratId: string) =>
      apiClient.post<DecisionHitlReponse>(`/hitl/contrats/${id(contratId)}/rejeter`),
  },

  ics: {
    /** Crée/renvoie l'URL capability d'abonnement au feed ICS (§2.6). */
    abonnement: () => apiClient.post<AbonnementIcs>("/ics/abonnement"),
  },
};

export type ApiClient = typeof api;
