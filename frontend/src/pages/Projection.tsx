import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type {
  ContratResume,
  Indice,
  ProjectionReponse,
} from "../api/types";
import { couleurs, espacements, rayons, typo } from "../theme/tokens";
import {
  Bandeau,
  Bouton,
  Carte,
  Champ,
  EntetePage,
  Note,
  styleControle,
} from "../components/analyse/primitives";
import {
  formaterMontant,
  formaterNombre,
  formaterVariation,
  sensVariation,
} from "../components/analyse/format";

/**
 * Projection tarifaire (#79, spec §2.5).
 *
 * On choisit un contrat indexé puis une date de révision (et une part fixe
 * optionnelle) → api.contrats.projection() expose le moteur de révision.
 * Formule : `P1 = P0 × (S1/S0)`, ou `P1 = P0 × (a + b·S1/S0)` avec part fixe.
 *
 * Garde-fous rappelés à l'utilisateur :
 *  - la révision est BIDIRECTIONNELLE (le tarif peut BAISSER) — une clause de
 *    hausse seule est réputée non écrite et forcée au bidirectionnel (§2.5) ;
 *  - le coefficient de raccord Syntec 0,97975 s'applique aux actes de référence
 *    antérieurs à août 2022 ; il est appliqué à S0 par le moteur, on l'affiche.
 */

const LIBELLES_INDICE: Record<string, string> = {
  syntec: "Syntec",
  ilat: "ILAT",
  ilc: "ILC",
  icc: "ICC",
  insee_autre: "INSEE (autre)",
};

function libelleIndice(indice: Indice | undefined): string {
  if (!indice) return "—";
  return LIBELLES_INDICE[indice] ?? indice;
}

/** Date du jour au format `YYYY-MM-DD` pour valeur par défaut du sélecteur. */
function aujourdhuiIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function Projection(): JSX.Element {
  const [contrats, setContrats] = useState<ContratResume[]>([]);
  const [chargementListe, setChargementListe] = useState(true);
  const [erreurListe, setErreurListe] = useState<string | null>(null);

  const [contratId, setContratId] = useState<string>("");
  const [dateRevision, setDateRevision] = useState<string>(aujourdhuiIso());
  const [avecPartFixe, setAvecPartFixe] = useState(false);
  const [partFixe, setPartFixe] = useState<string>("0.15");

  const [resultat, setResultat] = useState<ProjectionReponse | null>(null);
  const [calcul, setCalcul] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // Charge les contrats indexés (un contrat sans clause d'indexation n'est pas
  // projetable : le moteur lève « Contrat sans clause d'indexation »).
  useEffect(() => {
    let actif = true;
    void (async () => {
      try {
        const liste = await api.contrats.lister({ limite: 200 });
        if (!actif) return;
        const indexes = liste.filter((c) => c.indice && c.indice !== "aucun");
        setContrats(indexes);
        if (indexes.length > 0) {
          setContratId(indexes[0].id);
        }
      } catch (e) {
        if (actif) {
          setErreurListe(
            `Impossible de charger les contrats : ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      } finally {
        if (actif) setChargementListe(false);
      }
    })();
    return () => {
      actif = false;
    };
  }, []);

  const contratSelectionne = contrats.find((c) => c.id === contratId) ?? null;

  async function projeter(): Promise<void> {
    if (!contratId) return;
    setCalcul(true);
    setErreur(null);
    setResultat(null);

    // part_fixe ∈ [0,1] : la part variable est (1 − a). Omise si non cochée.
    let pf: number | undefined;
    if (avecPartFixe) {
      const n = Number(partFixe.replace(",", "."));
      if (Number.isNaN(n) || n < 0 || n > 1) {
        setErreur("La part fixe doit être un nombre entre 0 et 1.");
        setCalcul(false);
        return;
      }
      pf = n;
    }

    try {
      const res = await api.contrats.projection(contratId, {
        date_revision: dateRevision,
        ...(pf !== undefined ? { part_fixe: pf } : {}),
      });
      setResultat(res);
    } catch (e) {
      // 422 = donnée métier manquante (pas d'indice à la date, S0 absent, etc.).
      const msg =
        e instanceof ApiError && e.statut === 422
          ? `Projection impossible : ${e.message}`
          : e instanceof Error
            ? e.message
            : String(e);
      setErreur(msg);
    } finally {
      setCalcul(false);
    }
  }

  return (
    <section>
      <EntetePage titre="Projection tarifaire">
        Simulez le tarif révisé d'un contrat indexé à une date donnée selon la formule
        d'indexation. La révision est <strong>bidirectionnelle</strong> : le tarif peut aussi
        bien baisser que monter.
      </EntetePage>

      {erreurListe && <Bandeau ton="danger">{erreurListe}</Bandeau>}

      <Carte style={{ marginBottom: espacements.xl }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: espacements.lg,
            alignItems: "start",
          }}
        >
          <Champ libelle="Contrat indexé">
            <select
              value={contratId}
              onChange={(e) => {
                setContratId(e.target.value);
                setResultat(null);
                setErreur(null);
              }}
              disabled={chargementListe || contrats.length === 0}
              style={styleControle}
            >
              {chargementListe && <option>Chargement…</option>}
              {!chargementListe && contrats.length === 0 && (
                <option value="">Aucun contrat indexé</option>
              )}
              {contrats.map((c) => (
                <option key={c.id} value={c.id}>
                  {(c.reference ?? c.objet ?? c.id).slice(0, 60)} — {libelleIndice(c.indice)}
                </option>
              ))}
            </select>
          </Champ>

          <Champ libelle="Date de révision">
            <input
              type="date"
              value={dateRevision}
              onChange={(e) => setDateRevision(e.target.value)}
              style={styleControle}
            />
          </Champ>

          <Champ
            libelle="Part fixe (optionnelle)"
            aide="Cochez pour P1 = P0 × (a + (1−a)·S1/S0). Sinon révision pleine."
          >
            <div style={{ display: "flex", alignItems: "center", gap: espacements.sm }}>
              <input
                type="checkbox"
                checked={avecPartFixe}
                onChange={(e) => setAvecPartFixe(e.target.checked)}
                aria-label="Activer la part fixe"
              />
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={partFixe}
                onChange={(e) => setPartFixe(e.target.value)}
                disabled={!avecPartFixe}
                style={{ ...styleControle, opacity: avecPartFixe ? 1 : 0.5 }}
              />
            </div>
          </Champ>
        </div>

        {contratSelectionne && (
          <p
            style={{
              fontSize: typo.taille.sm,
              color: couleurs.texteAttenue,
              margin: `${espacements.lg} 0 0`,
            }}
          >
            Indice : <strong>{libelleIndice(contratSelectionne.indice)}</strong>
            {contratSelectionne.montant !== undefined && (
              <>
                {" · "}P0 actuel :{" "}
                <strong>
                  {formaterMontant(
                    contratSelectionne.montant,
                    contratSelectionne.devise ?? "EUR",
                  )}
                </strong>
              </>
            )}
            {contratSelectionne.fournisseur_siren && (
              <> · SIREN {contratSelectionne.fournisseur_siren}</>
            )}
          </p>
        )}

        <div style={{ marginTop: espacements.lg }}>
          <Bouton onClick={() => void projeter()} disabled={calcul || !contratId}>
            {calcul ? "Calcul en cours…" : "Projeter le tarif"}
          </Bouton>
        </div>

        {erreur && (
          <div style={{ marginTop: espacements.lg }}>
            <Bandeau ton="danger">{erreur}</Bandeau>
          </div>
        )}
      </Carte>

      {resultat && (
        <ResultatProjectionVue
          resultat={resultat}
          devise={contratSelectionne?.devise ?? "EUR"}
        />
      )}
    </section>
  );
}

/** Affichage du résultat : P0→P1, S0/S1 + périodes, coefficient de raccord, variation. */
function ResultatProjectionVue({
  resultat,
  devise,
}: {
  resultat: ProjectionReponse;
  devise: string;
}): JSX.Element {
  const sens = sensVariation(resultat.p0, resultat.p1);
  const couleurSens =
    sens === "hausse" ? couleurs.danger : sens === "baisse" ? couleurs.succes : couleurs.texte;
  const raccordApplique = resultat.coefficient_raccord !== 1;

  return (
    <Carte>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: espacements.lg,
          marginBottom: espacements.xl,
        }}
      >
        <BlocPrix etiquette="Tarif de référence (P0)" valeur={formaterMontant(resultat.p0, devise)} />
        <span style={{ fontSize: typo.taille.xxl, color: couleurs.texteFaible }} aria-hidden>
          →
        </span>
        <BlocPrix
          etiquette="Tarif révisé (P1)"
          valeur={formaterMontant(resultat.p1, devise)}
          accent
        />
        <div
          style={{
            fontSize: typo.taille.lg,
            fontWeight: typo.graisse.forte,
            color: couleurSens,
            background: `${couleurSens}14`,
            borderRadius: rayons.md,
            padding: `${espacements.sm} ${espacements.md}`,
          }}
        >
          {formaterVariation(resultat.p0, resultat.p1)}
          {sens === "baisse" && (
            <span style={{ fontSize: typo.taille.xs, fontWeight: typo.graisse.normale }}>
              {" "}
              (baisse)
            </span>
          )}
        </div>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: typo.taille.base }}>
        <tbody>
          <LigneDetail
            cle="Indice de base S0"
            valeur={formaterNombre(resultat.s0)}
            note={
              resultat.periode_s0
                ? `Période ${resultat.periode_s0}${
                    raccordApplique ? " · après coefficient de raccord" : ""
                  }`
                : "Période non renseignée"
            }
          />
          <LigneDetail
            cle="Indice de révision S1"
            valeur={formaterNombre(resultat.s1)}
            note={`Période ${resultat.periode_s1}`}
          />
          <LigneDetail
            cle="Ratio S1/S0"
            valeur={resultat.s0 !== 0 ? formaterNombre(resultat.s1 / resultat.s0, 4) : "—"}
          />
          <LigneDetail
            cle="Coefficient de raccord Syntec"
            valeur={formaterNombre(resultat.coefficient_raccord, 5)}
            note={
              raccordApplique
                ? "Acte de référence antérieur à août 2022 → 0,97975 appliqué à S0."
                : "Non applicable (= 1)."
            }
          />
        </tbody>
      </table>

      <div style={{ marginTop: espacements.xl }}>
        <Note>
          Révision <strong>bidirectionnelle</strong> : une clause d'indexation à la hausse seule
          est réputée non écrite et forcée au bidirectionnel par le moteur (§2.5). Une baisse de
          l'indice fait donc baisser le tarif. Le coefficient de raccord 0,97975 est appliqué à S0
          pour tout acte de référence antérieur au passage à l'indice Syntec révisé (août 2022).
        </Note>
      </div>
    </Carte>
  );
}

function BlocPrix({
  etiquette,
  valeur,
  accent,
}: {
  etiquette: string;
  valeur: string;
  accent?: boolean;
}): JSX.Element {
  return (
    <div>
      <div style={{ fontSize: typo.taille.xs, color: couleurs.texteAttenue }}>{etiquette}</div>
      <div
        style={{
          fontSize: typo.taille.xxl,
          fontWeight: typo.graisse.forte,
          color: accent ? couleurs.accent : couleurs.texte,
        }}
      >
        {valeur}
      </div>
    </div>
  );
}

function LigneDetail({
  cle,
  valeur,
  note,
}: {
  cle: string;
  valeur: string;
  note?: string;
}): JSX.Element {
  return (
    <tr style={{ borderTop: `1px solid ${couleurs.bordure}` }}>
      <th
        scope="row"
        style={{
          textAlign: "left",
          padding: `${espacements.sm} 0`,
          fontWeight: typo.graisse.normale,
          color: couleurs.texteAttenue,
          verticalAlign: "top",
          width: "40%",
        }}
      >
        {cle}
      </th>
      <td style={{ padding: `${espacements.sm} 0`, fontWeight: typo.graisse.semi }}>
        {valeur}
        {note && (
          <div
            style={{
              fontSize: typo.taille.xs,
              fontWeight: typo.graisse.normale,
              color: couleurs.texteFaible,
            }}
          >
            {note}
          </div>
        )}
      </td>
    </tr>
  );
}
