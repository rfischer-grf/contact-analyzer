import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { ContratResume, FiltresContratsValeurs } from "../api/types";
import { tokens } from "../theme";
import { FiltresContrats } from "../components/contrats/FiltresContrats";
import { TableContrats } from "../components/contrats/TableContrats";

/**
 * Liste des contrats (#75, spec §6).
 *
 * Table filtrable par **facettes structurées** (indice, SIREN fournisseur, échéance
 * avant) → `api.contrats.lister({...})` (SQL `WHERE` côté API, jamais du vectoriel).
 * Ligne cliquable → `/contrats/:id`. N'affiche que l'état effectif validé (garde-fou).
 *
 * La navigation passe par `window.location` (chemins absolus) : la coquille/fondation
 * fournit le routeur ; on reste découplé de son implémentation.
 */

const LIMITE = 50;

export function Contrats(): JSX.Element {
  const [filtres, setFiltres] = useState<FiltresContratsValeurs>({});
  const [contrats, setContrats] = useState<ContratResume[]>([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [decalage, setDecalage] = useState(0);
  const [pageComplete, setPageComplete] = useState(false);

  const charger = useCallback(
    async (valeurs: FiltresContratsValeurs, dec: number) => {
      setChargement(true);
      setErreur(null);
      try {
        const reponse = await api.contrats.lister({
          indice: valeurs.indice,
          fournisseur_siren: valeurs.fournisseur_siren,
          echeance_avant: valeurs.echeance_avant,
          limite: LIMITE,
          decalage: dec,
        });
        setContrats(reponse);
        setPageComplete(reponse.length === LIMITE);
      } catch (e) {
        setErreur(e instanceof Error ? e.message : String(e));
        setContrats([]);
      } finally {
        setChargement(false);
      }
    },
    [],
  );

  // Recharge à chaque changement de filtres (léger debounce pour le SIREN saisi).
  useEffect(() => {
    const minuteur = window.setTimeout(() => {
      setDecalage(0);
      void charger(filtres, 0);
    }, 250);
    return () => window.clearTimeout(minuteur);
  }, [filtres, charger]);

  function ouvrir(id: string): void {
    window.location.assign(`/contrats/${id}`);
  }

  function changerPage(nouveauDecalage: number): void {
    const dec = Math.max(0, nouveauDecalage);
    setDecalage(dec);
    void charger(filtres, dec);
  }

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: tokens.espace.md }}>
      <h2 style={{ color: tokens.couleur.texte, margin: 0 }}>Contrats</h2>
      <p style={{ color: tokens.couleur.texteAttenue, fontSize: tokens.police.sm, margin: 0 }}>
        Recherche par facette structurée (état effectif validé). La <strong>date limite de
        dénonciation</strong> (échéance − préavis) est la date actionnable.
      </p>

      <FiltresContrats
        valeurs={filtres}
        onChange={setFiltres}
        onReinitialiser={() => setFiltres({})}
      />

      {erreur ? (
        <p style={{ color: tokens.couleur.statut.danger, fontSize: tokens.police.sm }}>
          Erreur de chargement : {erreur}
        </p>
      ) : chargement ? (
        <p style={{ color: tokens.couleur.texteAttenue, fontSize: tokens.police.sm }}>Chargement…</p>
      ) : (
        <>
          <TableContrats contrats={contrats} onOuvrir={ouvrir} />

          {(decalage > 0 || pageComplete) && (
            <div
              style={{
                display: "flex",
                gap: tokens.espace.md,
                justifyContent: "flex-end",
                alignItems: "center",
                fontSize: tokens.police.sm,
              }}
            >
              <button
                type="button"
                disabled={decalage === 0}
                onClick={() => changerPage(decalage - LIMITE)}
              >
                Précédent
              </button>
              <span style={{ color: tokens.couleur.texteAttenue }}>
                {decalage + 1}–{decalage + contrats.length}
              </span>
              <button
                type="button"
                disabled={!pageComplete}
                onClick={() => changerPage(decalage + LIMITE)}
              >
                Suivant
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
