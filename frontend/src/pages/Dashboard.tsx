import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TableauDeBord } from "../api/types";
import { EntetePage, Bandeau } from "../components/analyse/primitives";
import { formaterMontant } from "../components/analyse/format";
import { espacements } from "../theme/tokens";
import { CarteKpi } from "../components/contrats/CarteKpi";
import { BandeauAlertes } from "../components/contrats/BandeauAlertes";
import { RepartitionIndices } from "../components/contrats/RepartitionIndices";
import { ListeProchainesEcheances } from "../components/contrats/ListeProchainesEcheances";

/**
 * Tableau de bord Clausio (#74, spec §2.6).
 *
 * Agrège l'état effectif **validé** (garde-fou : aucune donnée `à_valider` n'est
 * comptée — l'API n'expose que l'état post-COMMITE) :
 *   - cartes KPI : nb de contrats, montant total, répartition par indice ;
 *   - bandeau d'alertes par palier 90/60/30/7 (date limite de dénonciation) ;
 *   - liste des prochaines dates limites de dénonciation (date actionnable).
 *
 * Source unique : `api.tableauDeBord.get()`.
 */
export function Dashboard(): JSX.Element {
  const [donnees, setDonnees] = useState<TableauDeBord | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    void (async () => {
      try {
        const reponse = await api.tableauDeBord.get();
        if (actif) setDonnees(reponse);
      } catch (e) {
        if (actif) setErreur(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      actif = false;
    };
  }, []);

  return (
    <section>
      <EntetePage titre="Tableau de bord">
        Vue d'ensemble du parc de contrats validés. La <strong>date limite de dénonciation</strong>{" "}
        (échéance − préavis) est la date actionnable en tacite reconduction.
      </EntetePage>

      {erreur ? (
        <Bandeau ton="danger">Impossible de charger le tableau de bord : {erreur}</Bandeau>
      ) : !donnees ? (
        <Bandeau ton="info">Chargement…</Bandeau>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: espacements.xl }}>
          {/* Cartes KPI */}
          <div style={{ display: "flex", gap: espacements.lg, flexWrap: "wrap" }}>
            <CarteKpi intitule="Contrats suivis" valeur={donnees.nb_contrats} />
            <CarteKpi intitule="Montant total" valeur={formaterMontant(donnees.montant_total, "EUR")} />
            <CarteKpi
              intitule="Indices utilisés"
              valeur={Object.keys(donnees.par_indice).length}
              detail="voir la répartition ci-dessous"
            />
          </div>

          {/* Bandeau d'alertes par palier */}
          <BandeauAlertes alertes={donnees.alertes} />

          {/* Répartition par indice + prochaines échéances */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: espacements.xl,
              alignItems: "start",
            }}
          >
            <RepartitionIndices parIndice={donnees.par_indice} />
            <ListeProchainesEcheances echeances={donnees.prochaines_echeances} />
          </div>
        </div>
      )}
    </section>
  );
}
