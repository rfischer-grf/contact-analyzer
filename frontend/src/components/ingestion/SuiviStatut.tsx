import { tokens } from "../../theme";
import type { EtatIngestion } from "../../api/types";

/**
 * Suivi visuel de la saga d'ingestion (#77, spec §4).
 *
 * Affiche la progression `RECU → CONTROLE → PARSING → EXTRACTION → RAPPROCHEMENT
 * → A_VALIDER → VALIDE → COMMITE`, avec branche terminale d'échec
 * (`REJETE_TECHNIQUE` / `REJETE_METIER`). Présentation pure : l'état courant est
 * fourni par le parent qui polle `api.statut.get(workflowId)`.
 *
 * Contrat de thème supposé (fourni par la fondation, cf. CarteKpi) :
 *   tokens.couleurs.{surface, bordure, texte, texteAttenue, accent, succes, danger, attention}
 *   tokens.espacements.{xs, sm, md, lg}  ·  tokens.rayons.{md, rond}  ·  tokens.typo.taille.{xs, sm, md}
 */

/** Étapes nominales dans l'ordre, hors états de rejet (branche d'échec). */
const ETAPES_NOMINALES: { etat: EtatIngestion; libelle: string }[] = [
  { etat: "RECU", libelle: "Reçu" },
  { etat: "CONTROLE", libelle: "Contrôle + AV" },
  { etat: "PARSING", libelle: "Parsing (Docling)" },
  { etat: "EXTRACTION", libelle: "Extraction LLM" },
  { etat: "RAPPROCHEMENT", libelle: "Rapprochement avenant" },
  { etat: "A_VALIDER", libelle: "À valider (HITL)" },
  { etat: "VALIDE", libelle: "Validé" },
  { etat: "COMMITE", libelle: "Committé" },
];

const ETATS_REJET: ReadonlySet<string> = new Set(["REJETE_TECHNIQUE", "REJETE_METIER"]);

interface SuiviStatutProps {
  /** État courant renvoyé par l'API, ou `null` tant qu'aucun polling n'a abouti. */
  statut: EtatIngestion | null;
}

/** Position (index) d'un état dans la chaîne nominale, -1 si hors chaîne. */
function indexEtape(statut: EtatIngestion | null): number {
  if (statut === null) return -1;
  return ETAPES_NOMINALES.findIndex((e) => e.etat === statut);
}

export function SuiviStatut({ statut }: SuiviStatutProps): JSX.Element {
  const rejet = statut !== null && ETATS_REJET.has(statut);
  const courant = indexEtape(statut);

  return (
    <div
      style={{
        background: tokens.couleurs.surface,
        border: `1px solid ${tokens.couleurs.bordure}`,
        borderRadius: tokens.rayons.md,
        padding: tokens.espacements.lg,
      }}
    >
      <div
        style={{
          fontSize: tokens.typo.taille.sm,
          color: tokens.couleurs.texteAttenue,
          marginBottom: tokens.espacements.md,
        }}
      >
        Avancement de l'ingestion
      </div>

      <ol
        style={{
          listStyle: "none",
          margin: 0,
          padding: 0,
          display: "flex",
          flexDirection: "column",
          gap: tokens.espacements.sm,
        }}
      >
        {ETAPES_NOMINALES.map((etape, i) => {
          const atteinte = courant >= 0 && i <= courant;
          const active = i === courant;
          const couleurPastille = atteinte ? tokens.couleurs.accent : tokens.couleurs.bordure;
          return (
            <li
              key={etape.etat}
              style={{ display: "flex", alignItems: "center", gap: tokens.espacements.sm }}
            >
              <span
                aria-hidden
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: tokens.rayons.rond,
                  background: couleurPastille,
                  flex: "0 0 auto",
                  boxShadow: active ? `0 0 0 3px ${tokens.couleurs.accentDoux}` : "none",
                }}
              />
              <span
                style={{
                  fontSize: tokens.typo.taille.md,
                  color: atteinte ? tokens.couleurs.texte : tokens.couleurs.texteAttenue,
                  fontWeight: active ? 600 : 400,
                }}
              >
                {etape.libelle}
              </span>
            </li>
          );
        })}
      </ol>

      {rejet && (
        <div
          role="alert"
          style={{
            marginTop: tokens.espacements.md,
            padding: tokens.espacements.sm,
            borderRadius: tokens.rayons.md,
            background: tokens.couleurs.dangerDoux,
            color: tokens.couleurs.danger,
            fontSize: tokens.typo.taille.sm,
          }}
        >
          {statut === "REJETE_TECHNIQUE"
            ? "Rejeté techniquement (contrôle/antivirus) — terminal."
            : "Rejeté métier au gate HITL — non propagé en aval."}
        </div>
      )}

      <div
        style={{
          marginTop: tokens.espacements.md,
          fontSize: tokens.typo.taille.xs,
          color: tokens.couleurs.texteAttenue,
        }}
      >
        État courant : <strong>{statut ?? "—"}</strong>
      </div>
    </div>
  );
}
