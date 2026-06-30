import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ContratDetail as ContratDetailType } from "../api/types";
import { Carte, Bandeau } from "../components/analyse/primitives";
import { formaterDateIso, formaterMontant } from "../components/analyse/format";
import { couleurs, espacements, rayons, typo } from "../theme/tokens";
import { FriseDocuments } from "../components/contrats/FriseDocuments";
import { BlocIndexation } from "../components/contrats/BlocIndexation";
import { libelleIndice } from "../components/contrats/format";

/**
 * Détail d'un contrat (#76, spec §3.1).
 *
 * Affiche l'**état effectif** validé (fold sur la chaîne de documents) :
 *   - synthèse (fournisseur, échéance, durée, tacite reconduction, préavis, montant) ;
 *   - bloc indexation (indice, base S0, sens de révision — bidirectionnel forcé) ;
 *   - frise ordonnée des documents/avenants ;
 *   - actions : projection tarifaire (`/projection/:id`) et validation (`/validation/:id`).
 *
 * Garde-fou : seul l'état effectif validé est exposé par l'API ; aucune donnée
 * `à_valider` n'est affichée comme effective ici. La `date_limite_denonciation`
 * (date actionnable, §2.6) est calculée en aval, jamais éditée ici.
 */

function Ligne({ label, valeur }: { label: string; valeur: string }): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: espacements.md,
        padding: `${espacements.sm} 0`,
        borderBottom: `1px solid ${couleurs.bordure}`,
        fontSize: typo.taille.base,
      }}
    >
      <span style={{ color: couleurs.texteAttenue }}>{label}</span>
      <span style={{ color: couleurs.texte, fontWeight: typo.graisse.semi, textAlign: "right" }}>
        {valeur}
      </span>
    </div>
  );
}

/** Bouton-lien d'action (react-router) stylé via les jetons du thème. */
function LienAction({
  to,
  primaire,
  children,
}: {
  to: string;
  primaire?: boolean;
  children: string;
}): JSX.Element {
  return (
    <Link
      to={to}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: `${espacements.sm} ${espacements.lg}`,
        borderRadius: rayons.md,
        border: `1px solid ${primaire ? couleurs.accent : couleurs.bordureForte}`,
        background: primaire ? couleurs.accent : couleurs.surface,
        color: primaire ? couleurs.texteInverse : couleurs.texte,
        textDecoration: "none",
        fontSize: typo.taille.base,
        fontWeight: typo.graisse.moyenne,
      }}
    >
      {children}
    </Link>
  );
}

export function ContratDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [contrat, setContrat] = useState<ContratDetailType | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setErreur("Identifiant de contrat manquant.");
      return;
    }
    let actif = true;
    setContrat(null);
    setErreur(null);
    void (async () => {
      try {
        const reponse = await api.contrats.detail(id);
        if (actif) setContrat(reponse);
      } catch (e) {
        if (actif) setErreur(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      actif = false;
    };
  }, [id]);

  if (erreur) {
    return (
      <section>
        <Link to="/contrats" style={{ color: couleurs.accent, fontSize: typo.taille.sm }}>
          ← Contrats
        </Link>
        <div style={{ marginTop: espacements.md }}>
          <Bandeau ton="danger">{erreur}</Bandeau>
        </div>
      </section>
    );
  }

  if (!contrat) {
    return (
      <section>
        <Bandeau ton="info">Chargement…</Bandeau>
      </section>
    );
  }

  const preavis =
    contrat.preavis_delai !== null && contrat.preavis_delai !== undefined
      ? `${contrat.preavis_delai} ${contrat.preavis_unite ?? ""}`.trim()
      : "—";
  const dureeInitiale =
    contrat.duree_initiale_mois !== null && contrat.duree_initiale_mois !== undefined
      ? `${contrat.duree_initiale_mois} mois`
      : "—";
  const montant =
    contrat.montant !== undefined && contrat.montant !== null
      ? formaterMontant(contrat.montant, contrat.devise ?? "EUR")
      : "—";

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: espacements.xl }}>
      {/* En-tête + actions */}
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: espacements.lg,
          flexWrap: "wrap",
        }}
      >
        <div>
          <Link to="/contrats" style={{ color: couleurs.accent, fontSize: typo.taille.sm, textDecoration: "none" }}>
            ← Contrats
          </Link>
          <h2
            style={{
              fontSize: typo.taille.xl,
              fontWeight: typo.graisse.semi,
              color: couleurs.texte,
              margin: `${espacements.sm} 0 0`,
            }}
          >
            {contrat.reference || `Contrat ${contrat.id.slice(0, 8)}`}
          </h2>
          {contrat.objet && (
            <p style={{ fontSize: typo.taille.base, color: couleurs.texteAttenue, margin: `${espacements.xs} 0 0` }}>
              {contrat.objet}
            </p>
          )}
        </div>

        <div style={{ display: "flex", gap: espacements.sm }}>
          <LienAction to={`/projection/${contrat.id}`} primaire>
            Projection tarifaire
          </LienAction>
          <LienAction to={`/validation/${contrat.id}`}>Validation (HITL)</LienAction>
        </div>
      </header>

      {/* Synthèse de l'état effectif + indexation */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: espacements.xl,
          alignItems: "start",
        }}
      >
        <Carte>
          <h3 style={{ fontSize: typo.taille.lg, fontWeight: typo.graisse.semi, margin: `0 0 ${espacements.sm}` }}>
            État effectif
          </h3>
          <Ligne label="Fournisseur (SIREN)" valeur={contrat.fournisseur_siren || "—"} />
          <Ligne label="Échéance" valeur={formaterDateIso(contrat.date_echeance)} />
          <Ligne label="Date limite de dénonciation" valeur={formaterDateIso(contrat.date_limite_denonciation)} />
          <Ligne label="Durée initiale" valeur={dureeInitiale} />
          <Ligne label="Tacite reconduction" valeur={contrat.tacite_reconduction ? "oui" : "non"} />
          <Ligne label="Préavis" valeur={preavis} />
          <Ligne label="Montant" valeur={montant} />
          <Ligne label="Indice" valeur={libelleIndice(contrat.indice)} />
        </Carte>

        <Carte>
          <BlocIndexation contrat={contrat} />
        </Carte>
      </div>

      {/* Frise des documents / avenants */}
      <Carte>
        <FriseDocuments documents={contrat.documents} />
      </Carte>
    </section>
  );
}
