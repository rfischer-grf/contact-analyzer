import { useCallback, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ChampRevue, CorrectionEntree } from "../api/types";
import { tokens } from "../theme";
import { ListeChamps } from "../components/hitl/ListeChamps";
import { ApercuPdf } from "../components/hitl/ApercuPdf";
import { BarreDecision } from "../components/hitl/BarreDecision";

/**
 * Validation humaine (HITL) — GATE non négociable (#78, spec §2.4).
 *
 * Flux :
 *   1. api.hitl.champsARevoir(contratId, seuil?) → { champs: string[] } : les
 *      champs de l'extraction sous le seuil de confiance (file de revue).
 *   2. Édition des valeurs → corrections (ancienne → nouvelle valeur).
 *   3. À la validation : on persiste d'abord les corrections (gold set) via
 *      api.hitl.corrections(...), puis on émet le signal api.hitl.valider(...).
 *      Le rejet émet api.hitl.rejeter(...).
 *
 * Garde-fou : aucune donnée « à valider » n'entre dans alertes / ICS / Weaviate
 * avant la validation. Chaque champ porte valeur + confiance + provenance (§3).
 *
 * L'API (#35) renvoie désormais, par champ sous le seuil, sa valeur, sa confiance
 * et sa provenance (page + bbox), plus `document_url` (PDF source présigné) : la
 * liste est donc pré-remplie et l'aperçu PDF surligne la source réelle. Un champ
 * facultatif permet de confirmer le rattachement d'un avenant à son contrat
 * parent (#33) — jamais d'auto-lien : le lien n'est posé qu'à cette confirmation.
 */

/** Rend une valeur extraite (scalaire ou objet) en texte éditable. */
function valeurEnTexte(valeur: unknown): string {
  if (valeur === null || valeur === undefined) return "";
  if (typeof valeur === "object") return JSON.stringify(valeur);
  return String(valeur);
}

/** Libellé lisible à partir du chemin pointé d'un champ (ex. `preavis.delai`). */
function libelleChamp(cle: string): string {
  const LIBELLES: Record<string, string> = {
    date_echeance: "Date d'échéance",
    date_effet: "Date d'effet",
    "preavis.delai": "Préavis (délai)",
    "preavis.unite": "Préavis (unité)",
    montant: "Montant",
    devise: "Devise",
    "indexation.indice": "Indice d'indexation",
    "indexation.indice_base_valeur": "Indice base (S0)",
    tacite_reconduction: "Tacite reconduction",
    duree_initiale_mois: "Durée initiale (mois)",
  };
  return LIBELLES[cle] ?? cle;
}

const SEUIL_DEFAUT = 0.7;

export function Validation(): JSX.Element {
  const [contratId, setContratId] = useState("");
  const [seuil, setSeuil] = useState(SEUIL_DEFAUT);
  const [contratCharge, setContratCharge] = useState<string | null>(null);
  const [champs, setChamps] = useState<ChampRevue[]>([]);
  const [selection, setSelection] = useState<string | null>(null);
  const [chargement, setChargement] = useState(false);
  const [decisionEnCours, setDecisionEnCours] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  // URL présignée du PDF source (aperçu + overlay bbox), fournie par l'API (#35).
  const [documentUrl, setDocumentUrl] = useState<string | null>(null);
  // Parent confirmé pour un avenant (#33) — vide = la pièce reste autonome.
  const [parentContratId, setParentContratId] = useState("");

  const provenanceSelection = useMemo(() => {
    const champ = champs.find((c) => c.cle === selection) ?? champs[0];
    return champ?.source ?? null;
  }, [champs, selection]);

  const charger = useCallback(async () => {
    const id = contratId.trim();
    if (!id) return;
    setChargement(true);
    setErreur(null);
    setInfo(null);
    try {
      const reponse = await api.hitl.champsARevoir(id, seuil);
      const construits: ChampRevue[] = reponse.champs.map((c) => {
        const texte = valeurEnTexte(c.valeur);
        return {
          cle: c.cle,
          libelle: libelleChamp(c.cle),
          valeur: texte,
          valeurOriginale: texte,
          confiance: c.confiance,
          source: c.source,
        };
      });
      setChamps(construits);
      setDocumentUrl(reponse.document_url);
      setSelection(construits[0]?.cle ?? null);
      setContratCharge(id);
      if (construits.length === 0) {
        setInfo("Aucun champ sous le seuil : extraction jugée fiable, validation rapide possible.");
      }
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
      setChamps([]);
      setDocumentUrl(null);
      setContratCharge(null);
    } finally {
      setChargement(false);
    }
  }, [contratId, seuil]);

  function modifier(cle: string, valeur: string): void {
    setChamps((prec) => prec.map((c) => (c.cle === cle ? { ...c, valeur } : c)));
  }

  /** Corrections effectives (valeur modifiée par rapport à l'originale). */
  function correctionsAEnvoyer(): CorrectionEntree[] {
    return champs
      .filter((c) => c.valeur !== c.valeurOriginale)
      .map((c) => ({
        champ: c.cle,
        ancienne_valeur: c.valeurOriginale || null,
        nouvelle_valeur: c.valeur || null,
      }));
  }

  async function valider(): Promise<void> {
    if (!contratCharge) return;
    setDecisionEnCours(true);
    setErreur(null);
    setInfo(null);
    try {
      // 1. Persistance des corrections (gold set, §2.4) avant le signal de validation.
      const corrections = correctionsAEnvoyer();
      if (corrections.length > 0) {
        await api.hitl.corrections(contratCharge, { corrections });
      }
      // 2. Signal de validation → VALIDE → COMMITE côté saga. Si un parent est
      //    renseigné, l'avenant lui est rattaché avant commit (#33).
      const parent = parentContratId.trim() || null;
      await api.hitl.valider(contratCharge, parent);
      setInfo(
        `Contrat validé (${corrections.length} correction(s) enregistrée(s))` +
          (parent ? `, rattaché au parent ${parent}` : "") +
          ". Il entre désormais dans les alertes, le feed ICS et l'index.",
      );
    } catch (e) {
      setErreur(`Échec de la validation : ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setDecisionEnCours(false);
    }
  }

  async function rejeter(): Promise<void> {
    if (!contratCharge) return;
    setDecisionEnCours(true);
    setErreur(null);
    setInfo(null);
    try {
      await api.hitl.rejeter(contratCharge);
      setInfo("Contrat rejeté (REJETE_METIER) : non propagé en aval.");
    } catch (e) {
      setErreur(`Échec du rejet : ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setDecisionEnCours(false);
    }
  }

  return (
    <section>
      <h2 style={{ fontSize: tokens.typo.taille.xl, color: tokens.couleurs.texte, marginTop: 0 }}>
        Validation humaine (HITL)
      </h2>
      <p style={{ color: tokens.couleurs.texteAttenue, fontSize: tokens.typo.taille.sm }}>
        Vérifier chaque champ sous le seuil de confiance contre la source surlignée, corriger
        si besoin, puis décider. Un préavis ou une date mal extraits = engagement raté.
      </p>

      {/* Sélection du contrat à revoir (pas d'endpoint de file globale dans ce périmètre). */}
      <div
        style={{
          display: "flex",
          gap: tokens.espacements.sm,
          alignItems: "flex-end",
          flexWrap: "wrap",
          marginBottom: tokens.espacements.lg,
        }}
      >
        <label style={{ display: "flex", flexDirection: "column", fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue }}>
          Contrat (id)
          <input
            value={contratId}
            onChange={(e) => setContratId(e.target.value)}
            placeholder="UUID du contrat"
            style={{
              marginTop: tokens.espacements.xs,
              border: `1px solid ${tokens.couleurs.bordure}`,
              borderRadius: tokens.rayons.md,
              padding: tokens.espacements.sm,
              fontSize: tokens.typo.taille.sm,
              minWidth: 280,
            }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", fontSize: tokens.typo.taille.sm, color: tokens.couleurs.texteAttenue }}>
          Seuil de confiance
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={seuil}
            onChange={(e) => setSeuil(Number(e.target.value))}
            style={{
              marginTop: tokens.espacements.xs,
              border: `1px solid ${tokens.couleurs.bordure}`,
              borderRadius: tokens.rayons.md,
              padding: tokens.espacements.sm,
              fontSize: tokens.typo.taille.sm,
              width: 100,
            }}
          />
        </label>
        <button
          type="button"
          onClick={() => void charger()}
          disabled={!contratId.trim() || chargement}
          style={{
            background: tokens.couleurs.accent,
            color: tokens.couleurs.texteInverse,
            border: "none",
            borderRadius: tokens.rayons.md,
            padding: `${tokens.espacements.sm} ${tokens.espacements.lg}`,
            fontSize: tokens.typo.taille.md,
            fontWeight: 600,
            cursor: !contratId.trim() || chargement ? "not-allowed" : "pointer",
            opacity: !contratId.trim() || chargement ? 0.6 : 1,
          }}
        >
          {chargement ? "Chargement…" : "Charger les champs à revoir"}
        </button>
      </div>

      {erreur && (
        <p
          role="alert"
          style={{
            fontSize: tokens.typo.taille.sm,
            color: tokens.couleurs.danger,
            background: tokens.couleurs.dangerDoux,
            padding: tokens.espacements.sm,
            borderRadius: tokens.rayons.md,
          }}
        >
          {erreur}
        </p>
      )}

      {contratCharge && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "360px minmax(0, 1fr)",
            gap: tokens.espacements.xl,
            alignItems: "start",
          }}
        >
          {/* Colonne champs éditables + décision */}
          <div style={{ display: "flex", flexDirection: "column", gap: tokens.espacements.lg }}>
            <ListeChamps
              champs={champs}
              selection={selection}
              onSelection={setSelection}
              onModifier={modifier}
            />
            <label
              style={{
                display: "flex",
                flexDirection: "column",
                fontSize: tokens.typo.taille.sm,
                color: tokens.couleurs.texteAttenue,
              }}
            >
              Rattacher à un contrat parent (avenant) — optionnel
              <input
                value={parentContratId}
                onChange={(e) => setParentContratId(e.target.value)}
                placeholder="UUID du contrat parent (laisser vide si contrat autonome)"
                style={{
                  marginTop: tokens.espacements.xs,
                  border: `1px solid ${tokens.couleurs.bordure}`,
                  borderRadius: tokens.rayons.md,
                  padding: tokens.espacements.sm,
                  fontSize: tokens.typo.taille.sm,
                }}
              />
            </label>
            <BarreDecision
              onValider={() => void valider()}
              onRejeter={() => void rejeter()}
              enCours={decisionEnCours}
            />
            {info && (
              <p
                style={{
                  fontSize: tokens.typo.taille.sm,
                  color: tokens.couleurs.accentFort,
                  background: tokens.couleurs.accentDoux,
                  padding: tokens.espacements.sm,
                  borderRadius: tokens.rayons.md,
                  margin: 0,
                }}
              >
                {info}
              </p>
            )}
          </div>

          {/* Colonne aperçu PDF + overlay bbox */}
          <ApercuPdf documentUrl={documentUrl} provenance={provenanceSelection} />
        </div>
      )}
    </section>
  );
}
