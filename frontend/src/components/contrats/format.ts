/**
 * Helpers de présentation spécifiques aux contrats (#74/#75/#76).
 *
 * Le formatage générique (montant, date, nombre) vit dans `../analyse/format`
 * (réutilisé tel quel) ; on n'ajoute ici que ce qui est propre au domaine contrat :
 * libellés d'indices et paliers d'alerte. Aucune logique métier (les valeurs
 * viennent de l'état effectif validé, source de vérité Postgres).
 */
import type { Indice } from "../../api/types";

/** Libellés lisibles des indices (cf. enum `Indice` du domaine, §2.5 / §3). */
export const LIBELLE_INDICE: Record<string, string> = {
  syntec: "Syntec",
  ilat: "ILAT",
  ilc: "ILC",
  icc: "ICC",
  insee_autre: "INSEE (autre)",
  aucun: "Aucun",
};

/** Paliers d'alerte (jours avant la date limite de dénonciation), §2.6. */
export const PALIERS_ALERTE = [90, 60, 30, 7] as const;

export function libelleIndice(indice: Indice | string | null | undefined): string {
  if (!indice) return "—";
  return LIBELLE_INDICE[indice] ?? indice;
}

/** Vrai si le contrat est effectivement indexé (clause présente, ≠ « aucun »). */
export function estIndexe(indice: Indice | string | null | undefined): boolean {
  return !!indice && indice !== "aucun";
}
