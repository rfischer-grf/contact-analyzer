import { useCallback, useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
// Worker pdf.js packagé par le bundler (URL résolue à la compilation).
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { apiClient } from "../api/client";

/**
 * Validation humaine (HITL) — GATE (ticket #56, spec §2.4).
 *
 * PLACEHOLDER fonctionnel : rend la page PDF source via pdf.js et superpose la
 * bbox de provenance du champ sélectionné (surlignage de la source). Les champs
 * sont éditables ; les boutons émettent les signaux valider/rejeter au workflow.
 *
 * Rappels garde-fous (§2.4) : aucune donnée `à_valider` n'entre dans alertes /
 * ICS / Weaviate avant la validation. Chaque champ porte valeur + confiance +
 * provenance (page + bbox) — cf. wrapper `Champ` (spec §3). Les bbox sont en
 * coordonnées PDF (origine bas-gauche) → converties vers le canevas ci-dessous.
 */

pdfjsLib.GlobalWorkerOptions.workerSrc = PdfWorker;

interface Provenance {
  page: number;
  /** bbox PDF : [x0, y0, x1, y1] en points, origine bas-gauche. */
  bbox: [number, number, number, number] | null;
  extrait: string;
}

interface ChampEditable {
  cle: string;
  libelle: string;
  valeur: string;
  confiance: number;
  source: Provenance | null;
}

/** Élément de la file de revue renvoyé par GET /hitl/file (#35). */
interface ItemFileRevue {
  contrat_id: string;
  document_url: string; // URL (présignée) du PDF source à afficher
  champs: ChampEditable[];
}

// Jeu d'exemple tant que GET /hitl/file (#35) n'est pas implémenté côté API.
const EXEMPLE: ItemFileRevue = {
  contrat_id: "demo-contrat",
  document_url: "",
  champs: [
    {
      cle: "date_echeance",
      libelle: "Date d'échéance",
      valeur: "2027-03-31",
      confiance: 0.62,
      source: { page: 1, bbox: [120, 640, 320, 660], extrait: "échéance au 31 mars 2027" },
    },
    {
      cle: "preavis_delai",
      libelle: "Préavis (mois)",
      valeur: "3",
      confiance: 0.55,
      source: { page: 1, bbox: [120, 600, 300, 620], extrait: "préavis de trois mois" },
    },
  ],
};

export function Validation(): JSX.Element {
  const [item, setItem] = useState<ItemFileRevue | null>(null);
  const [champs, setChamps] = useState<ChampEditable[]>([]);
  const [selection, setSelection] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  // Chargement de la file de revue (#35). En attendant l'implémentation API,
  // on retombe sur le jeu d'exemple si l'endpoint renvoie 501.
  useEffect(() => {
    let actif = true;
    void (async () => {
      try {
        const reponse = await apiClient.get<ItemFileRevue[]>("/hitl/file");
        if (actif && reponse.length > 0) {
          setItem(reponse[0]);
          setChamps(reponse[0].champs);
          return;
        }
      } catch (e) {
        console.warn("File de revue indisponible (#35 non implémenté) ; jeu d'exemple.", e);
      }
      if (actif) {
        setItem(EXEMPLE);
        setChamps(EXEMPLE.champs);
      }
    })();
    return () => {
      actif = false;
    };
  }, []);

  // Rend la page PDF du champ sélectionné + dessine la bbox de provenance.
  const rendreApercu = useCallback(async () => {
    const champ = champs.find((c) => c.cle === selection) ?? champs[0];
    const canvas = canvasRef.current;
    const overlay = overlayRef.current;
    if (!champ?.source || !item?.document_url || !canvas || !overlay) {
      return;
    }
    const { page, bbox } = champ.source;

    const doc = await pdfjsLib.getDocument(item.document_url).promise;
    const pdfPage = await doc.getPage(page);
    const viewport = pdfPage.getViewport({ scale: 1.5 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }
    await pdfPage.render({ canvasContext: ctx, viewport }).promise;

    overlay.innerHTML = "";
    if (bbox) {
      // PDF (origine bas-gauche) → canevas (origine haut-gauche) via le viewport.
      const [x0, y0, x1, y1] = bbox;
      const [vx0, vy0] = viewport.convertToViewportPoint(x0, y1);
      const [vx1, vy1] = viewport.convertToViewportPoint(x1, y0);
      const boite = document.createElement("div");
      boite.style.position = "absolute";
      boite.style.left = `${Math.min(vx0, vx1)}px`;
      boite.style.top = `${Math.min(vy0, vy1)}px`;
      boite.style.width = `${Math.abs(vx1 - vx0)}px`;
      boite.style.height = `${Math.abs(vy1 - vy0)}px`;
      boite.style.outline = "2px solid #f5a623";
      boite.style.background = "rgba(245, 166, 35, 0.25)";
      overlay.appendChild(boite);
    }
  }, [champs, selection, item]);

  useEffect(() => {
    void rendreApercu();
  }, [rendreApercu]);

  function modifier(cle: string, valeur: string): void {
    setChamps((prec) => prec.map((c) => (c.cle === cle ? { ...c, valeur } : c)));
  }

  async function valider(): Promise<void> {
    if (!item) {
      return;
    }
    try {
      // Les corrections sont transmises pour alimenter le gold set (spec §2.4).
      await apiClient.post(`/hitl/contrats/${encodeURIComponent(item.contrat_id)}/valider`, {
        champs: champs.map(({ cle, valeur }) => ({ cle, valeur })),
      });
      setInfo("Contrat validé : il entre dans le périmètre d'alerte, l'ICS et l'index.");
    } catch (e) {
      setInfo(`Échec de la validation : ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function rejeter(): Promise<void> {
    if (!item) {
      return;
    }
    try {
      await apiClient.post(`/hitl/contrats/${encodeURIComponent(item.contrat_id)}/rejeter`, {});
      setInfo("Contrat rejeté (REJETE_METIER) : non propagé en aval.");
    } catch (e) {
      setInfo(`Échec du rejet : ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <section>
      <h2>Validation humaine (HITL)</h2>
      <p style={{ color: "#555", fontSize: 14 }}>
        Gate non négociable : seuls les contrats validés entrent dans les alertes, le feed ICS et
        l'index. Vérifier chaque champ contre la source surlignée.
      </p>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* Colonne champs éditables */}
        <div style={{ flex: "0 0 320px" }}>
          {champs.map((c) => (
            <div
              key={c.cle}
              onClick={() => setSelection(c.cle)}
              style={{
                border: selection === c.cle ? "2px solid #2557d6" : "1px solid #ddd",
                borderRadius: 6,
                padding: 10,
                marginBottom: 8,
                cursor: "pointer",
              }}
            >
              <label style={{ display: "block", fontSize: 13, color: "#555" }}>
                {c.libelle}{" "}
                <span style={{ color: c.confiance < 0.7 ? "#b00" : "#2a7" }}>
                  (confiance {Math.round(c.confiance * 100)}%)
                </span>
              </label>
              <input
                value={c.valeur}
                onChange={(e) => modifier(c.cle, e.target.value)}
                style={{ width: "100%", marginTop: 4 }}
              />
              {c.source && (
                <p style={{ fontSize: 12, color: "#777", margin: "4px 0 0" }}>
                  Source p.{c.source.page} : « {c.source.extrait} »
                </p>
              )}
            </div>
          ))}

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button onClick={() => void valider()}>Valider</button>
            <button onClick={() => void rejeter()}>Rejeter</button>
          </div>
          {info && <p style={{ fontSize: 13, marginTop: 8 }}>{info}</p>}
        </div>

        {/* Colonne aperçu PDF + overlay bbox */}
        <div style={{ position: "relative", border: "1px solid #ddd" }}>
          <canvas ref={canvasRef} />
          <div
            ref={overlayRef}
            style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
          />
          {!item?.document_url && (
            <p style={{ padding: 16, color: "#999", fontSize: 13 }}>
              Aperçu PDF indisponible (placeholder) : l'URL du document source sera fournie par
              GET /hitl/file (#35). La logique de rendu pdf.js + surlignage bbox est en place.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
