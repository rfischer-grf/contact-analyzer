import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { ContratResume } from "../api/types";
import { EntetePage, Bandeau, Bouton } from "../components/analyse/primitives";
import { couleurs, espacements, typo } from "../theme/tokens";
import {
  FiltresContrats,
  type FiltresContratsValeurs,
} from "../components/contrats/FiltresContrats";
import { TableContrats } from "../components/contrats/TableContrats";

/**
 * Liste des contrats (#75, spec §6).
 *
 * Table filtrable par **facettes structurées** (indice, SIREN fournisseur, échéance
 * avant) → `api.contrats.lister({...})` (SQL `WHERE` côté API, jamais du vectoriel).
 * Ligne cliquable → `/contrats/:id`. N'affiche que l'état effectif validé (garde-fou).
 */
const LIMITE = 50;

export function Contrats(): JSX.Element {
  const [filtres, setFiltres] = useState<FiltresContratsValeurs>({});
  const [contrats, setContrats] = useState<ContratResume[]>([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);
  const [decalage, setDecalage] = useState(0);
  const [pageComplete, setPageComplete] = useState(false);

  const charger = useCallback(async (valeurs: FiltresContratsValeurs, dec: number) => {
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
  }, []);

  // Recharge à chaque changement de filtres (léger debounce pour le SIREN saisi).
  // Tout changement de filtre revient à la première page.
  useEffect(() => {
    const minuteur = window.setTimeout(() => {
      setDecalage(0);
      void charger(filtres, 0);
    }, 250);
    return () => window.clearTimeout(minuteur);
  }, [filtres, charger]);

  function changerPage(nouveauDecalage: number): void {
    const dec = Math.max(0, nouveauDecalage);
    setDecalage(dec);
    void charger(filtres, dec);
  }

  return (
    <section>
      <EntetePage titre="Contrats">
        Recherche par facette structurée sur l'état effectif validé. La <strong>date limite de
        dénonciation</strong> (échéance − préavis) est la date actionnable.
      </EntetePage>

      <div style={{ marginBottom: espacements.xl }}>
        <FiltresContrats valeurs={filtres} onChange={setFiltres} onReinitialiser={() => setFiltres({})} />
      </div>

      {erreur ? (
        <Bandeau ton="danger">Erreur de chargement : {erreur}</Bandeau>
      ) : chargement ? (
        <Bandeau ton="info">Chargement…</Bandeau>
      ) : (
        <>
          <TableContrats contrats={contrats} />

          {(decalage > 0 || pageComplete) && (
            <div
              style={{
                display: "flex",
                gap: espacements.md,
                justifyContent: "flex-end",
                alignItems: "center",
                marginTop: espacements.lg,
                fontSize: typo.taille.sm,
                color: couleurs.texteAttenue,
              }}
            >
              <Bouton variante="secondaire" disabled={decalage === 0} onClick={() => changerPage(decalage - LIMITE)}>
                Précédent
              </Bouton>
              <span>
                {contrats.length > 0 ? `${decalage + 1}–${decalage + contrats.length}` : "—"}
              </span>
              <Bouton variante="secondaire" disabled={!pageComplete} onClick={() => changerPage(decalage + LIMITE)}>
                Suivant
              </Bouton>
            </div>
          )}
        </>
      )}
    </section>
  );
}
