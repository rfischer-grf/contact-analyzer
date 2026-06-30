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
 *   tokens.couleur.{fondCarte, bordure, texte, texteAttenue, accent, succes, danger, attention}
 *   tokens.espace.{xs, sm, md, lg}  ·  tokens.rayon.{md, rond}  ·  tokens.police.{xs, sm, md}
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
        background: tokens.couleur.fondCarte,
        border: `1px solid ${tokens.couleur.bordure}`,
        borderRadius: tokens.rayon.md,
        padding: tokens.espace.lg,
      }}
    >
      <div
        style={{
          fontSize: tokens.police.sm,
          color: tokens.couleur.texteAttenue,
          marginBottom: tokens.espace.md,
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
          gap: tokens.espace.sm,
        }}
      >
        {ETAPES_NOMINALES.map((etape, i) => {
          const atteinte = courant >= 0 && i <= courant;
          const active = i === courant;
          const couleurPastille = atteinte ? tokens.couleur.accent : tokens.couleur.bordure;
          return (
            <li
              key={etape.etat}
              style={{ display: "flex", alignItems: "center", gap: tokens.espace.sm }}
            >
              <span
                aria-hidden
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: tokens.rayon.rond,
                  background: couleurPastille,
                  flex: "0 0 auto",
                  boxShadow: active ? `0 0 0 3px ${tokens.couleur.accentDoux}` : "none",
                }}
              />
              <span
                style={{
                  fontSize: tokens.police.md,
                  color: atteinte ? tokens.couleur.texte : tokens.couleur.texteAttenue,
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
            marginTop: tokens.espace.md,
            padding: tokens.espace.sm,
            borderRadius: tokens.rayon.md,
            background: tokens.couleur.dangerDoux,
            color: tokens.couleur.danger,
            fontSize: tokens.police.sm,
          }}
        >
          {statut === "REJETE_TECHNIQUE"
            ? "Rejeté techniquement (contrôle/antivirus) — terminal."
            : "Rejeté métier au gate HITL — non propagé en aval."}
        </div>
      )}

      <div
        style={{
          marginTop: tokens.espace.md,
          fontSize: tokens.police.xs,
          color: tokens.couleur.texteAttenue,
        }}
      >
        État courant : <strong>{statut ?? "—"}</strong>
      </div>
    </div>
  );
}
