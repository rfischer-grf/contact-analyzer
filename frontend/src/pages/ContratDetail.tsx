import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ContratDetail as ContratDetailType } from "../api/types";
import { tokens } from "../theme";
import { FriseDocuments } from "../components/contrats/FriseDocuments";
import { BlocIndexation } from "../components/contrats/BlocIndexation";
import { formatDate, formatMontant, libelleIndice } from "../components/contrats/format";

/**
 * Détail d'un contrat (#76, spec §3.1).
 *
 * Affiche l'**état effectif** validé (fold sur la chaîne de documents) :
 *   - synthèse (parties, objet, dates, durée, tacite reconduction, préavis, montant) ;
 *   - bloc indexation (indice, base S0, sens de révision — bidirectionnel forcé) ;
 *   - frise ordonnée des documents/avenants ;
 *   - actions : projection tarifaire (`/projection/:id`) et validation (`/validation/:id`).
 *
 * Garde-fou : seul l'état effectif validé est exposé par l'API ; aucune donnée
 * `à_valider` n'est affichée comme effective ici. La `date_limite_denonciation`
 * (date actionnable, §2.6) est calculée en aval, jamais éditée ici.
 *
 * L'`id` vient du routeur (prop) ou, à défaut, du chemin `/contrats/:id`.
 */

interface ContratDetailProps {
  id?: string;
}

function idDepuisUrl(): string | null {
  const segments = window.location.pathname.split("/").filter(Boolean);
  const i = segments.indexOf("contrats");
  return i >= 0 && segments[i + 1] ? decodeURIComponent(segments[i + 1]) : null;
}

const styleLigne: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: tokens.espace.md,
  padding: `${tokens.espace.sm} 0`,
  borderBottom: `1px solid ${tokens.couleur.bordure}`,
  fontSize: tokens.police.sm,
};

function Ligne({ label, valeur }: { label: string; valeur: string }): JSX.Element {
  return (
    <div style={styleLigne}>
      <span style={{ color: tokens.couleur.texteAttenue }}>{label}</span>
      <span style={{ color: tokens.couleur.texte, fontWeight: 600, textAlign: "right" }}>
        {valeur}
      </span>
    </div>
  );
}

export function ContratDetail({ id }: ContratDetailProps): JSX.Element {
  const contratId = id ?? idDepuisUrl();
  const [contrat, setContrat] = useState<ContratDetailType | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!contratId) {
      setErreur("Identifiant de contrat manquant.");
      return;
    }
    let actif = true;
    void (async () => {
      try {
        const reponse = await api.contrats.detail(contratId);
        if (actif) setContrat(reponse);
      } catch (e) {
        if (actif) setErreur(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      actif = false;
    };
  }, [contratId]);

  if (erreur) {
    return (
      <section>
        <h2 style={{ color: tokens.couleur.texte }}>Détail du contrat</h2>
        <p style={{ color: tokens.couleur.statut.danger, fontSize: tokens.police.sm }}>{erreur}</p>
        <a href="/contrats" style={{ color: tokens.couleur.accent }}>
          ← Retour à la liste
        </a>
      </section>
    );
  }

  if (!contrat) {
    return (
      <section>
        <h2 style={{ color: tokens.couleur.texte }}>Détail du contrat</h2>
        <p style={{ color: tokens.couleur.texteAttenue, fontSize: tokens.police.sm }}>Chargement…</p>
      </section>
    );
  }

  const preavis =
    contrat.preavis_delai !== null && contrat.preavis_delai !== undefined
      ? `${contrat.preavis_delai} ${contrat.preavis_unite ?? ""}`.trim()
      : "—";

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: tokens.espace.lg }}>
      {/* En-tête + actions */}
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: tokens.espace.md,
          flexWrap: "wrap",
        }}
      >
        <div>
          <a
            href="/contrats"
            style={{ color: tokens.couleur.accent, fontSize: tokens.police.sm, textDecoration: "none" }}
          >
            ← Contrats
          </a>
          <h2 style={{ color: tokens.couleur.texte, margin: `${tokens.espace.sm} 0 0` }}>
            {contrat.reference || `Contrat ${contrat.id.slice(0, 8)}`}
          </h2>
          {contrat.objet && (
            <p style={{ color: tokens.couleur.texteAttenue, fontSize: tokens.police.sm, margin: 0 }}>
              {contrat.objet}
            </p>
          )}
        </div>

        <div style={{ display: "flex", gap: tokens.espace.sm }}>
          <a
            href={`/projection/${contrat.id}`}
            style={{
              padding: `${tokens.espace.sm} ${tokens.espace.md}`,
              borderRadius: tokens.rayon.md,
              border: `1px solid ${tokens.couleur.accent}`,
              color: tokens.couleur.accent,
              textDecoration: "none",
              fontSize: tokens.police.sm,
            }}
          >
            Projection tarifaire
          </a>
          <a
            href={`/validation/${contrat.id}`}
            style={{
              padding: `${tokens.espace.sm} ${tokens.espace.md}`,
              borderRadius: tokens.rayon.md,
              border: `1px solid ${tokens.couleur.bordure}`,
              color: tokens.couleur.texte,
              textDecoration: "none",
              fontSize: tokens.police.sm,
            }}
          >
            Validation (HITL)
          </a>
        </div>
      </header>

      {/* Synthèse de l'état effectif */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(280px, 1fr) minmax(280px, 1fr)",
          gap: tokens.espace.lg,
        }}
      >
        <div
          style={{
            background: tokens.couleur.fondCarte,
            border: `1px solid ${tokens.couleur.bordure}`,
            borderRadius: tokens.rayon.md,
            padding: tokens.espace.lg,
          }}
        >
          <h3 style={{ fontSize: tokens.police.lg, margin: `0 0 ${tokens.espace.sm}` }}>
            État effectif
          </h3>
          <Ligne label="Fournisseur (SIREN)" valeur={contrat.fournisseur_siren || "—"} />
          <Ligne label="Date d'effet — échéance" valeur={`${formatDate(contrat.date_echeance)}`} />
          <Ligne
            label="Date limite de dénonciation"
            valeur={formatDate(contrat.date_limite_denonciation)}
          />
          <Ligne
            label="Durée initiale"
            valeur={
              contrat.duree_initiale_mois !== null && contrat.duree_initiale_mois !== undefined
                ? `${contrat.duree_initiale_mois} mois`
                : "—"
            }
          />
          <Ligne
            label="Tacite reconduction"
            valeur={contrat.tacite_reconduction ? "oui" : "non"}
          />
          <Ligne label="Préavis" valeur={preavis} />
          <Ligne label="Montant" valeur={formatMontant(contrat.montant, contrat.devise)} />
          <Ligne label="Indice" valeur={libelleIndice(contrat.indice)} />
        </div>

        <BlocIndexation contrat={contrat} />
      </div>

      {/* Frise des documents / avenants */}
      <div
        style={{
          background: tokens.couleur.fondCarte,
          border: `1px solid ${tokens.couleur.bordure}`,
          borderRadius: tokens.rayon.md,
          padding: tokens.espace.lg,
        }}
      >
        <FriseDocuments documents={contrat.documents} />
      </div>
    </section>
  );
}
