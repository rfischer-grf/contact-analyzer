/**
 * Wrapper fetch de l'API CLM (ticket #54/#55).
 *
 * - Ajoute systématiquement l'en-tête `Authorization: Bearer <token>`.
 * - Le tenant n'est JAMAIS transmis : l'API le dérive du token (garde-fou §7).
 * - En dev, `VITE_API_URL` est servi via le proxy Vite ; en prod c'est l'URL
 *   absolue de l'API.
 */
import { getToken } from "../auth/keycloak";

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

type Options = Omit<RequestInit, "body"> & { body?: unknown };

async function requete<T>(chemin: string, options: Options = {}): Promise<T> {
  const token = await getToken();
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  const reponse = await fetch(`${BASE_URL}${chemin}`, { ...options, headers, body });

  if (!reponse.ok) {
    const detail = await reponse.text().catch(() => reponse.statusText);
    throw new ApiError(reponse.status, detail || reponse.statusText);
  }

  // 204 No Content (révocation d'abonnement, ...) → pas de corps.
  if (reponse.status === 204) {
    return undefined as T;
  }
  return (await reponse.json()) as T;
}

export const apiClient = {
  get: <T>(chemin: string) => requete<T>(chemin, { method: "GET" }),
  post: <T>(chemin: string, body?: unknown) => requete<T>(chemin, { method: "POST", body }),
  del: <T>(chemin: string) => requete<T>(chemin, { method: "DELETE" }),
};

/**
 * PUT brut d'un fichier vers une URL présignée S3 (Garage).
 * Hors API : les octets vont directement navigateur→S3 (garde-fou §2.1),
 * donc PAS de bearer Keycloak ici, et l'URL signée porte déjà l'autorisation.
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
