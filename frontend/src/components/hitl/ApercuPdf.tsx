import { useCallback, useEffect, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";
// Worker pdf.js packagé par le bundler (URL résolue à la compilation).
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { tokens } from "../../theme";
import type { Provenance } from "../../api/types";

/**
 * Aperçu PDF + surlignage de la provenance (#78, spec §2.4).
 *
 * Rend la page source via pdf.js et superpose la bbox du champ sélectionné
 * (overlay de validation). Si aucune source n'est disponible (URL absente, ou
 * l'API ne fournit pas encore la provenance — voir TODO ci-dessous), un
 * placeholder explicite est affiché à la place du canevas.
 *
 * Les bbox sont en coordonnées PDF (points, origine bas-gauche) → converties
 * vers le canevas (origine haut-gauche) via le viewport pdf.js.
 *
 * Contrat de thème supposé (fourni par la fondation) :
 *   tokens.couleur.{fondCarte, bordure, texteAttenue, attention, attentionDoux}
 *   tokens.espace.{md, lg}  ·  tokens.rayon.md  ·  tokens.police.sm
 */

pdfjsLib.GlobalWorkerOptions.workerSrc = PdfWorker;

const ECHELLE = 1.5;

interface ApercuPdfProps {
  /** URL (présignée) du PDF source, ou `null` si indisponible. */
  documentUrl: string | null;
  /** Provenance du champ sélectionné (page + bbox), ou `null`. */
  provenance: Provenance | null;
}

export function ApercuPdf({ documentUrl, provenance }: ApercuPdfProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);

  const rendre = useCallback(async () => {
    const canvas = canvasRef.current;
    const overlay = overlayRef.current;
    if (!documentUrl || !provenance || !canvas || !overlay) return;

    const doc = await pdfjsLib.getDocument(documentUrl).promise;
    try {
      const pdfPage = await doc.getPage(provenance.page);
      const viewport = pdfPage.getViewport({ scale: ECHELLE });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      await pdfPage.render({ canvasContext: ctx, viewport }).promise;

      overlay.innerHTML = "";
      const bbox = provenance.bbox;
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
        boite.style.outline = `2px solid ${tokens.couleur.attention}`;
        boite.style.background = tokens.couleur.attentionDoux;
        boite.style.opacity = "0.45";
        overlay.appendChild(boite);
      }
    } finally {
      void doc.destroy();
    }
  }, [documentUrl, provenance]);

  useEffect(() => {
    void rendre();
  }, [rendre]);

  if (!documentUrl) {
    return (
      <div
        style={{
          border: `1px solid ${tokens.couleur.bordure}`,
          borderRadius: tokens.rayon.md,
          background: tokens.couleur.fondCarte,
          padding: tokens.espace.lg,
          color: tokens.couleur.texteAttenue,
          fontSize: tokens.police.sm,
          minHeight: 240,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
        }}
      >
        Aperçu PDF indisponible (placeholder).
        <br />
        L'URL du document source et la provenance (page + bbox) seront fournies par l'API
        (TODO : la file de revue HITL ne renvoie aujourd'hui que les noms de champs). La
        logique de rendu pdf.js + surlignage bbox est en place.
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        border: `1px solid ${tokens.couleur.bordure}`,
        borderRadius: tokens.rayon.md,
        overflow: "auto",
        maxHeight: "75vh",
      }}
    >
      <canvas ref={canvasRef} style={{ display: "block" }} />
      <div ref={overlayRef} style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />
    </div>
  );
}
