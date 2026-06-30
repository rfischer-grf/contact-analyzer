/**
 * Types du contrat API du cockpit Clausio — tickets #72/#74.
 *
 * Alignés sur le modèle de données de la spec (§3, §3.1). Les noms de champs
 * suivent le snake_case du backend FastAPI (sérialisation JSON), conservé tel
 * quel côté front pour éviter toute couche de transformation.
 */

/** Indices d'indexation reconnus (spec §2.5 / ClauseIndexation §3). */
export type Indice =
  | "syntec"
  | "ilat"
  | "ilc"
  | "icc"
  | "insee_autre"
  | "aucun";

/** Devises usuelles (le backend reste libre d'en renvoyer d'autres). */
export type Devise = "EUR" | "USD" | "GBP" | string;

/* --------------------------------------------------------------------------
 * Contrats
 * ----------------------------------------------------------------------- */

/** Vue résumée d'un contrat (listes, recherche, échéances). */
export interface ContratResume {
  id: string;
  reference?: string;
  objet?: string;
  fournisseur_siren?: string;
  indice?: Indice;
  montant?: number;
  devise?: Devise;
  date_echeance?: string; // ISO yyyy-mm-dd
  /** Date actionnable = échéance − préavis (calculée, jamais extraite — §3). */
  date_limite_denonciation?: string;
}

/** Pièce physique rattachée à un contrat (contrat d'origine ou avenant — §3.1). */
export interface DocumentContrat {
  sha256: string;
  numero_avenant?: number;
  reference?: string;
  date_signature: string; // ISO yyyy-mm-dd
}

/** Vue détaillée d'un contrat (état effectif + chaîne de documents — §3.1). */
export interface ContratDetail extends ContratResume {
  duree_initiale_mois?: number;
  tacite_reconduction?: boolean;
  preavis_delai?: number;
  preavis_unite?: "jour" | "mois" | "annee" | string;
  indice_base_valeur?: number; // S0
  indice_base_periode?: string;
  /** Signature du dernier acte tarifaire (re-ancrage des avenants de prix — §3.1). */
  date_acte_reference?: string;
  /** Clause d'indexation bidirectionnelle (unidirectionnelle = réputée non écrite — §2.5). */
  bidirectionnelle: boolean;
  documents: DocumentContrat[];
}

/* --------------------------------------------------------------------------
 * Uploads (presign → confirm — spec §2.1)
 * ----------------------------------------------------------------------- */

export interface PresignRequete {
  sha256: string;
  content_type: string;
}

export interface PresignReponse {
  url: string;
  methode: string; // p.ex. "PUT"
  cle: string;
  bucket: string;
  expire_dans: number; // secondes
}

export interface ConfirmRequete {
  sha256: string;
}

export interface ConfirmReponse {
  cle: string;
  etat: string;
}

/* --------------------------------------------------------------------------
 * Statut de la saga Temporal (spec §4)
 * ----------------------------------------------------------------------- */

/** États de la saga d'ingestion (spec §4). */
export type StatutSaga =
  | "RECU"
  | "CONTROLE"
  | "REJETE_TECHNIQUE"
  | "PARSING"
  | "EXTRACTION"
  | "RAPPROCHEMENT"
  | "A_VALIDER"
  | "VALIDE"
  | "COMMITE"
  | "REJETE_METIER"
  | string;

export interface StatutReponse {
  workflow_id: string;
  statut: StatutSaga;
}

/** Alias lisible côté ingestion (état de la saga affiché pendant le suivi). */
export type EtatIngestion = StatutSaga;

/* --------------------------------------------------------------------------
 * Tableau de bord
 * ----------------------------------------------------------------------- */

export interface ProchaineEcheance {
  id: string;
  reference: string;
  date_limite_denonciation: string;
  jours_restants: number;
}

export interface TableauDeBord {
  nb_contrats: number;
  par_indice: Record<string, number>;
  montant_total: number;
  alertes: Record<string, number>; // p.ex. { "7": 2, "30": 5, ... }
  prochaines_echeances: ProchaineEcheance[];
}

/* --------------------------------------------------------------------------
 * Projection tarifaire (révision indexée — spec §2.5)
 * ----------------------------------------------------------------------- */

export interface ProjectionRequete {
  date_revision: string; // ISO yyyy-mm-dd
  /** Part fixe `b` de la formule P1 = P0 × (a + b·S1/S0) ; absente = pas de part fixe. */
  part_fixe?: number;
}

export interface ProjectionReponse {
  p0: number;
  s0: number;
  s1: number;
  /** Coefficient de raccord Syntec (0,97975 si acte de référence < août 2022 — §2.5). */
  coefficient_raccord: number;
  p1: number;
  periode_s0: string;
  periode_s1: string;
}

/* --------------------------------------------------------------------------
 * Recherche
 * ----------------------------------------------------------------------- */

/** Paramètres de recherche par facette (SQL côté Postgres — spec §6). */
export interface FacetteParams {
  indice?: Indice;
  fournisseur_siren?: string;
  type_clause?: string;
  echeance_avant?: string;
  limite?: number;
  decalage?: number;
}

/** Résultat de recherche sémantique (vectoriel Weaviate — spec §6). */
export interface ResultatSemantique {
  contrat_id: string;
  type_clause: string;
  texte: string;
  metadata: Record<string, unknown>;
}

/* --------------------------------------------------------------------------
 * HITL (gate de validation — spec §2.4)
 * ----------------------------------------------------------------------- */

export interface ChampsARevoir {
  champs: string[];
}

export interface Correction {
  champ: string;
  /** Valeur extraite d'origine (`null` si le champ était vide). */
  ancienne_valeur: string | null;
  /** Valeur corrigée par le validateur (`null` si le champ est effacé). */
  nouvelle_valeur: string | null;
}

export interface CorrectionsRequete {
  corrections: Correction[];
}

export interface CorrectionsReponse {
  enregistrees: number;
}

export interface DecisionHitlReponse {
  statut: StatutSaga;
  decision: "validee" | "rejetee" | string;
}

/* --------------------------------------------------------------------------
 * Listing
 * ----------------------------------------------------------------------- */

export interface ListerContratsParams {
  indice?: Indice;
  fournisseur_siren?: string;
  echeance_avant?: string;
  limite?: number;
  decalage?: number;
}

/**
 * Valeurs des filtres de la liste de contrats (formulaire `FiltresContrats`).
 * Sous-ensemble actionnable des `ListerContratsParams` exposé à l'utilisateur ;
 * la pagination (`limite`/`decalage`) est gérée séparément par la page.
 */
export interface FiltresContratsValeurs {
  indice?: Indice;
  fournisseur_siren?: string;
  echeance_avant?: string;
}

/* --------------------------------------------------------------------------
 * Feed ICS (abonnement calendrier — spec §2.6)
 * ----------------------------------------------------------------------- */

export interface AbonnementIcs {
  id: string;
  url: string;
}
