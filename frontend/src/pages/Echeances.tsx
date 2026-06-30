import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TableauDeBord } from "../api/types";
import { couleurs, espacements, rayons, typo } from "../theme/tokens";
import {
  Bandeau,
  Bouton,
  Carte,
  EntetePage,
  Note,
} from "../components/analyse/primitives";
import { BadgeUrgence, couleurPalier } from "../components/analyse/BadgeUrgence";
import { formaterDateIso, formaterMontant, formaterNombre } from "../components/analyse/format";

/**
 * Échéancier + abonnement ICS (#81, réécriture du stub ; spec §2.6).
 *
 * Source = api.tableauDeBord.get() (état effectif, tenant via RLS). La date
 * actionnable est la DATE LIMITE DE DÉNONCIATION = échéance − préavis (calculée
 * en aval, jamais extraite — §3), critique en tacite reconduction. Tableau trié
 * par urgence (jours restants croissants — déjà ordonné côté API).
 *
 * « S'abonner au calendrier » → api.ics.abonnement() → URL capability (token
 * bearer long, aléatoire, révocable/rotatable). Le feed ne contient que dates +
 * intitulés, JAMAIS le contenu des clauses (garde-fou §2.6). L'alerte fiable
 * reste le job quotidien loggé côté serveur — l'ICS n'est que de la visibilité
 * (pas de VALARM).
 */

// Ordre d'affichage des paliers d'alerte (spec §2.6 : J−90 / J−60 / J−30 / J−7).
const PALIERS = [90, 60, 30, 7] as const;

export function Echeances(): JSX.Element {
  const [tdb, setTdb] = useState<TableauDeBord | null>(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState<string | null>(null);

  const [urlIcs, setUrlIcs] = useState<string | null>(null);
  const [abonnementEnCours, setAbonnementEnCours] = useState(false);
  const [infoIcs, setInfoIcs] = useState<string | null>(null);
  const [copie, setCopie] = useState(false);

  useEffect(() => {
    let actif = true;
    void (async () => {
      try {
        const reponse = await api.tableauDeBord.get();
        if (actif) setTdb(reponse);
      } catch (e) {
        if (actif) {
          setErreur(
            `Tableau de bord indisponible : ${e instanceof Error ? e.message : String(e)}`,
          );
        }
      } finally {
        if (actif) setChargement(false);
      }
    })();
    return () => {
      actif = false;
    };
  }, []);

  async function abonner(): Promise<void> {
    setAbonnementEnCours(true);
    setInfoIcs(null);
    setCopie(false);
    try {
      const reponse = await api.ics.abonnement();
      // L'API renvoie une URL relative (/ics/{token}.ics) ; on l'affiche en
      // absolu pour l'abonnement « calendrier par internet » dans Outlook.
      const base = import.meta.env.VITE_API_URL ?? window.location.origin;
      setUrlIcs(`${base}${reponse.url}`);
      setInfoIcs(
        "Abonnement créé. Collez l'URL ci-dessous dans Outlook (« Ajouter un calendrier » → « À partir d'Internet »).",
      );
    } catch (e) {
      setInfoIcs(`Échec de l'abonnement : ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setAbonnementEnCours(false);
    }
  }

  async function copier(): Promise<void> {
    if (!urlIcs) return;
    try {
      await navigator.clipboard.writeText(urlIcs);
      setCopie(true);
      window.setTimeout(() => setCopie(false), 2000);
    } catch {
      // Presse-papiers indisponible (contexte non sécurisé) : l'utilisateur copie à la main.
      setCopie(false);
    }
  }

  const echeances = tdb?.prochaines_echeances ?? [];

  return (
    <section>
      <EntetePage titre="Échéances & dates limites de dénonciation">
        La date actionnable est la <strong>date limite de dénonciation</strong> (échéance −
        préavis), pas l'échéance elle-même — critique en tacite reconduction. Les alertes mail +
        in-app partent à J−{PALIERS.join(", J−")} via un job quotidien loggé.
      </EntetePage>

      {erreur && <Bandeau ton="danger">{erreur}</Bandeau>}

      {tdb && <BandeauAlertes alertes={tdb.alertes} />}

      <Carte style={{ margin: `${espacements.xl} 0` }}>
        <h3
          style={{
            fontSize: typo.taille.md,
            fontWeight: typo.graisse.semi,
            color: couleurs.texte,
            margin: `0 0 ${espacements.xs}`,
          }}
        >
          Abonnement calendrier (.ics)
        </h3>
        <p
          style={{
            fontSize: typo.taille.sm,
            color: couleurs.texteAttenue,
            margin: `0 0 ${espacements.md}`,
          }}
        >
          Un VEVENT par échéance / date limite de dénonciation / date de révision, en lecture seule
          dans votre agenda. Visibilité uniquement : l'alerte fiable reste le job quotidien.
        </p>

        <Bouton onClick={() => void abonner()} disabled={abonnementEnCours}>
          {abonnementEnCours ? "Création…" : "S'abonner au calendrier"}
        </Bouton>

        {infoIcs && (
          <div style={{ marginTop: espacements.md }}>
            <Bandeau ton={urlIcs ? "succes" : "danger"}>{infoIcs}</Bandeau>
          </div>
        )}

        {urlIcs && (
          <div style={{ marginTop: espacements.md }}>
            <div style={{ display: "flex", gap: espacements.sm, alignItems: "center" }}>
              <code
                style={{
                  flex: 1,
                  fontFamily: typo.familleMono,
                  fontSize: typo.taille.xs,
                  background: couleurs.surfaceAlt,
                  border: `1px solid ${couleurs.bordure}`,
                  borderRadius: rayons.sm,
                  padding: espacements.sm,
                  wordBreak: "break-all",
                }}
              >
                {urlIcs}
              </code>
              <Bouton variante="secondaire" onClick={() => void copier()}>
                {copie ? "Copié ✓" : "Copier"}
              </Bouton>
            </div>
            <div style={{ marginTop: espacements.md }}>
              <Note>
                Cette URL est une <strong>capability</strong> (jeton bearer aléatoire, long) :
                quiconque la détient lit le feed. Elle est <strong>révocable et rotatable</strong>{" "}
                à tout moment, et ne contient que des <strong>dates + intitulés</strong>, jamais le
                contenu des clauses.
              </Note>
            </div>
          </div>
        )}
      </Carte>

      <h3
        style={{
          fontSize: typo.taille.md,
          fontWeight: typo.graisse.semi,
          color: couleurs.texte,
          margin: `0 0 ${espacements.md}`,
        }}
      >
        Prochaines échéances{tdb ? ` (${tdb.nb_contrats} contrat(s) au total)` : ""}
      </h3>

      {chargement && (
        <p style={{ fontSize: typo.taille.base, color: couleurs.texteAttenue }}>Chargement…</p>
      )}

      {!chargement && echeances.length === 0 && !erreur && (
        <Bandeau ton="info">Aucune échéance dans les 120 prochains jours.</Bandeau>
      )}

      {echeances.length > 0 && (
        <Carte style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: typo.taille.base }}>
            <thead>
              <tr style={{ background: couleurs.surfaceAlt, textAlign: "left" }}>
                <th style={enteteCellule}>Contrat</th>
                <th style={enteteCellule}>Date limite de dénonciation</th>
                <th style={enteteCellule}>Urgence</th>
              </tr>
            </thead>
            <tbody>
              {echeances.map((e) => (
                <tr key={e.id} style={{ borderTop: `1px solid ${couleurs.bordure}` }}>
                  <td style={cellule}>
                    {/* Pas de routeur (shell par onglets #69) ; lien partageable et dégradable. */}
                    <a
                      href={`/contrats/${encodeURIComponent(e.id)}`}
                      style={{
                        color: couleurs.accent,
                        textDecoration: "none",
                        fontWeight: typo.graisse.moyenne,
                      }}
                    >
                      {e.reference || e.id.slice(0, 8)}
                    </a>
                  </td>
                  <td style={{ ...cellule, fontWeight: typo.graisse.semi }}>
                    {formaterDateIso(e.date_limite_denonciation)}
                  </td>
                  <td style={cellule}>
                    <BadgeUrgence jours={e.jours_restants} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Carte>
      )}

      {tdb && tdb.montant_total > 0 && (
        <p
          style={{
            fontSize: typo.taille.sm,
            color: couleurs.texteAttenue,
            marginTop: espacements.lg,
          }}
        >
          Engagement total sous gestion : {formaterMontant(tdb.montant_total)}.
        </p>
      )}
    </section>
  );
}

/** Récapitulatif des paliers d'alerte (compte de contrats par échéance proche). */
function BandeauAlertes({ alertes }: { alertes: Record<string, number> }): JSX.Element {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
        gap: espacements.md,
      }}
    >
      {PALIERS.map((palier) => {
        const compte = alertes[String(palier)] ?? 0;
        const couleur = couleurPalier(palier);
        return (
          <Carte key={palier} style={{ padding: espacements.lg, textAlign: "center" }}>
            <div
              style={{ fontSize: typo.taille.xs, color: couleurs.texteAttenue, marginBottom: espacements.xs }}
            >
              À J−{palier}
            </div>
            <div style={{ fontSize: typo.taille.xxl, fontWeight: typo.graisse.forte, color: couleur }}>
              {formaterNombre(compte, 0)}
            </div>
            <div style={{ fontSize: typo.taille.xs, color: couleurs.texteFaible }}>
              contrat(s)
            </div>
          </Carte>
        );
      })}
    </div>
  );
}

const enteteCellule = {
  padding: `${espacements.md} ${espacements.lg}`,
  fontSize: typo.taille.sm,
  fontWeight: typo.graisse.semi,
  color: couleurs.texteAttenue,
} as const;

const cellule = {
  padding: `${espacements.md} ${espacements.lg}`,
  color: couleurs.texte,
} as const;
