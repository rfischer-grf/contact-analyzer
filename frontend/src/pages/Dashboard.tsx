import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TableauDeBord } from "../api/types";
import { tokens } from "../theme";
import { CarteKpi } from "../components/contrats/CarteKpi";
import { BandeauAlertes } from "../components/contrats/BandeauAlertes";
import { RepartitionIndices } from "../components/contrats/RepartitionIndices";
import { ListeProchainesEcheances } from "../components/contrats/ListeProchainesEcheances";
import { formatMontant } from "../components/contrats/format";

/**
 * Tableau de bord Clausio (#74, spec §2.6).
 *
 * Agrège l'état effectif **validé** (garde-fou : aucune donnée `à_valider` n'est
 * comptée, l'API n'expose que l'état post-COMMITE) :
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

  if (erreur) {
    return (
      <section>
        <h2 style={{ color: tokens.couleur.texte }}>Tableau de bord</h2>
        <p style={{ color: tokens.couleur.statut.danger, fontSize: tokens.police.sm }}>
          Impossible de charger le tableau de bord : {erreur}
        </p>
      </section>
    );
  }

  if (!donnees) {
    return (
      <section>
        <h2 style={{ color: tokens.couleur.texte }}>Tableau de bord</h2>
        <p style={{ color: tokens.couleur.texteAttenue, fontSize: tokens.police.sm }}>Chargement…</p>
      </section>
    );
  }

  const nbIndices = Object.keys(donnees.par_indice).length;

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: tokens.espace.lg }}>
      <h2 style={{ color: tokens.couleur.texte, margin: 0 }}>Tableau de bord</h2>

      {/* Cartes KPI */}
      <div style={{ display: "flex", gap: tokens.espace.md, flexWrap: "wrap" }}>
        <CarteKpi intitule="Contrats suivis" valeur={donnees.nb_contrats} />
        <CarteKpi
          intitule="Montant total"
          valeur={formatMontant(donnees.montant_total, "EUR")}
        />
        <CarteKpi
          intitule="Indices utilisés"
          valeur={nbIndices}
          detail={nbIndices > 0 ? "voir la répartition ci-dessous" : "aucun contrat indexé"}
        />
      </div>

      {/* Bandeau d'alertes par palier */}
      <BandeauAlertes alertes={donnees.alertes} />

      {/* Répartition par indice + prochaines échéances */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(240px, 1fr) minmax(280px, 2fr)",
          gap: tokens.espace.lg,
        }}
      >
        <RepartitionIndices parIndice={donnees.par_indice} />
        <ListeProchainesEcheances echeances={donnees.prochaines_echeances} />
      </div>
    </section>
  );
}
