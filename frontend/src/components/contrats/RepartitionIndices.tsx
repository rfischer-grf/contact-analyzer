/**
 * Répartition des contrats par indice d'indexation (#74).
 *
 * Affiche `par_indice` (Record<indice, nombre>) du tableau de bord sous forme de
 * barres proportionnelles. Purement structurel (compté en SQL côté API §6) —
 * aucun calcul vectoriel ni métier ici.
 */
import { Carte } from "../analyse/primitives";
import { couleurs, espacements, rayons, typo } from "../../theme/tokens";
import { libelleIndice } from "./format";

interface RepartitionIndicesProps {
  parIndice: Record<string, number>;
}

export function RepartitionIndices({ parIndice }: RepartitionIndicesProps): JSX.Element {
  const entrees = Object.entries(parIndice).sort((a, b) => b[1] - a[1]);
  const total = entrees.reduce((somme, [, n]) => somme + n, 0);

  return (
    <Carte>
      <div
        style={{
          fontSize: typo.taille.sm,
          fontWeight: typo.graisse.semi,
          color: couleurs.texteAttenue,
          marginBottom: espacements.md,
        }}
      >
        Répartition par indice
      </div>

      {entrees.length === 0 ? (
        <p style={{ fontSize: typo.taille.sm, color: couleurs.texteFaible, margin: 0 }}>
          Aucun contrat indexé.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: espacements.sm }}>
          {entrees.map(([indice, n]) => {
            const part = total > 0 ? Math.round((n / total) * 100) : 0;
            return (
              <div key={indice}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: typo.taille.sm,
                    marginBottom: espacements.xxs,
                  }}
                >
                  <span style={{ color: couleurs.texte }}>{libelleIndice(indice)}</span>
                  <span style={{ color: couleurs.texteFaible }}>
                    {n} · {part}%
                  </span>
                </div>
                <div
                  style={{
                    height: 8,
                    background: couleurs.surfaceAlt,
                    borderRadius: rayons.rond,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{ width: `${part}%`, height: "100%", background: couleurs.accent }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Carte>
  );
}
