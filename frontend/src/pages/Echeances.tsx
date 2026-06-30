import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

/**
 * Tableau de bord des échéances + abonnement ICS (ticket #57, spec §2.6).
 *
 * - Liste les échéances et surtout la DATE LIMITE DE DÉNONCIATION = échéance −
 *   préavis (date actionnable, critique en tacite reconduction ; calculée en aval,
 *   jamais extraite — spec §3).
 * - « S'abonner au calendrier » → POST /ics/abonnement → renvoie une URL capability
 *   (token bearer long, révocable) à coller dans Outlook. Le feed ne contient que
 *   dates + intitulé, jamais le contenu des clauses (garde-fou §2.6).
 */

interface LigneEcheance {
  contrat_id: string;
  fournisseur: string;
  date_echeance: string;
  date_limite_denonciation: string;
  tacite_reconduction: boolean;
  jours_restants: number;
}

interface AbonnementResponse {
  id: string;
  url: string;
}

// Données d'exemple tant que l'endpoint de liste (recherche par facette #52) n'expose
// pas les échéances ; remplacées dès que l'API renvoie l'état effectif filtré.
const EXEMPLE: LigneEcheance[] = [
  {
    contrat_id: "demo-1",
    fournisseur: "ACME Cloud SAS",
    date_echeance: "2026-09-30",
    date_limite_denonciation: "2026-06-30",
    tacite_reconduction: true,
    jours_restants: 0,
  },
  {
    contrat_id: "demo-2",
    fournisseur: "Réseaux & Liens SARL",
    date_echeance: "2026-12-31",
    date_limite_denonciation: "2026-10-02",
    tacite_reconduction: true,
    jours_restants: 94,
  },
];

const PALIERS_ALERTE = [90, 60, 30, 7];

/** Couleur indicative selon proximité des paliers d'alerte (spec §2.6). */
function couleurPalier(jours: number): string {
  if (jours <= 7) return "#b00";
  if (jours <= 30) return "#d97706";
  if (jours <= 90) return "#ca8a04";
  return "#2a7";
}

export function Echeances(): JSX.Element {
  const [lignes, setLignes] = useState<LigneEcheance[]>([]);
  const [urlIcs, setUrlIcs] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    void (async () => {
      try {
        const reponse = await apiClient.get<LigneEcheance[]>("/recherche/facette?type=echeances");
        if (actif && reponse.length > 0) {
          setLignes(reponse);
          return;
        }
      } catch (e) {
        console.warn("Liste d'échéances indisponible (#52 non implémenté) ; exemple.", e);
      }
      if (actif) {
        setLignes(EXEMPLE);
      }
    })();
    return () => {
      actif = false;
    };
  }, []);

  async function abonner(): Promise<void> {
    try {
      const reponse = await apiClient.post<AbonnementResponse>("/ics/abonnement");
      // L'URL renvoyée est relative à l'API ; on l'affiche en absolu pour Outlook.
      const base = import.meta.env.VITE_API_URL ?? window.location.origin;
      setUrlIcs(`${base}${reponse.url}`);
      setInfo("Abonnement créé. Copier l'URL ci-dessous dans Outlook (calendrier par internet).");
    } catch (e) {
      setInfo(`Échec de l'abonnement : ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <section>
      <h2>Échéances & dates limites de dénonciation</h2>
      <p style={{ color: "#555", fontSize: 14 }}>
        La date actionnable est la <strong>date limite de dénonciation</strong> (échéance −
        préavis), pas l'échéance. Alertes envoyées à J−{PALIERS_ALERTE.join(", J−")}.
      </p>

      <div style={{ margin: "12px 0" }}>
        <button onClick={() => void abonner()}>S'abonner au calendrier (.ics)</button>
        {info && <p style={{ fontSize: 13 }}>{info}</p>}
        {urlIcs && (
          <p style={{ fontSize: 13 }}>
            URL d'abonnement :{" "}
            <code style={{ wordBreak: "break-all" }}>{urlIcs}</code>
          </p>
        )}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #ddd" }}>
            <th style={{ padding: 6 }}>Fournisseur</th>
            <th style={{ padding: 6 }}>Échéance</th>
            <th style={{ padding: 6 }}>Date limite de dénonciation</th>
            <th style={{ padding: 6 }}>Tacite recond.</th>
            <th style={{ padding: 6 }}>Jours restants</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={l.contrat_id} style={{ borderBottom: "1px solid #eee" }}>
              <td style={{ padding: 6 }}>{l.fournisseur}</td>
              <td style={{ padding: 6 }}>{l.date_echeance}</td>
              <td style={{ padding: 6, fontWeight: 600 }}>{l.date_limite_denonciation}</td>
              <td style={{ padding: 6 }}>{l.tacite_reconduction ? "oui" : "non"}</td>
              <td style={{ padding: 6, color: couleurPalier(l.jours_restants) }}>
                {l.jours_restants}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
