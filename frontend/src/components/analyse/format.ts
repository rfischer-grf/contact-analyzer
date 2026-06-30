/**
 * Helpers de formatage français partagés par les pages d'analyse (#79/#80/#81).
 * Aucune dépendance ; s'appuie sur l'API `Intl` du navigateur (locale fr-FR).
 */

/** Montant en euros (ou devise donnée), format français : « 12 345,67 € ». */
export function formaterMontant(valeur: number, devise = "EUR"): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: devise,
    maximumFractionDigits: 2,
  }).format(valeur);
}

/** Nombre brut (indice) avec jusqu'à 2 décimales, séparateurs français. */
export function formaterNombre(valeur: number, decimales = 2): string {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: decimales,
  }).format(valeur);
}

/** Variation relative signée en pourcentage : « +3,2 % », « −1,8 % ». */
export function formaterVariation(p0: number, p1: number): string {
  if (p0 === 0) return "—";
  const pct = ((p1 - p0) / p0) * 100;
  const signe = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${signe}${new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  }).format(Math.abs(pct))} %`;
}

/** Signe de la variation, pour la coloration sémantique (hausse/baisse/nul). */
export function sensVariation(p0: number, p1: number): "hausse" | "baisse" | "nul" {
  if (p1 > p0) return "hausse";
  if (p1 < p0) return "baisse";
  return "nul";
}

/** Date ISO (`2026-09-30`) → format français long (« 30 septembre 2026 »). */
export function formaterDateIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(d);
}
