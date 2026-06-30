import { useState } from "react";
import { apiClient } from "../api/client";
import { couleurs, espacements, rayons, typo } from "../theme/tokens";
import {
  Bandeau,
  Bouton,
  Carte,
  Champ,
  EntetePage,
  Note,
  styleControle,
} from "../components/analyse/primitives";

/**
 * Recherche sémantique (#80, spec §6).
 *
 * Champ texte en langage naturel → GET /recherche/semantique?q=&k= (vectoriel,
 * Weaviate ; tenant injecté côté API, jamais fourni par le client — §6/§7).
 * On affiche les chunks de clause retournés (type + texte + lien vers le contrat).
 *
 * Distinction explicite rappelée à l'utilisateur (garde-fou §6) :
 *  - recherche par FACETTE (filtres structurés : « clause Syntec », « échéances Q3 »)
 *    = SQL `WHERE` sur Postgres → vit dans la page Contrats ;
 *  - recherche SÉMANTIQUE (sens du corps des clauses, RAG) = vectoriel → ici.
 */

interface ChunkResultat {
  contrat_id: string;
  type_clause: string;
  texte: string;
  metadata: Record<string, unknown>;
}

const LIBELLES_CLAUSE: Record<string, string> = {
  indexation: "Indexation",
  resiliation: "Résiliation",
  duree: "Durée",
  parties: "Parties",
  preavis: "Préavis",
  reconduction: "Reconduction",
  montant: "Montant",
};

function libelleClause(type: string): string {
  return LIBELLES_CLAUSE[type] ?? type;
}

/** Métadonnées « lisibles » d'un chunk (on masque les clés vides/internes). */
function metadataAffichables(metadata: Record<string, unknown>): [string, string][] {
  return Object.entries(metadata)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => [k, String(v)]);
}

const NB_RESULTATS = 8;

export function Recherche(): JSX.Element {
  const [requete, setRequete] = useState("");
  const [resultats, setResultats] = useState<ChunkResultat[] | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function rechercher(): Promise<void> {
    const q = requete.trim();
    if (q.length === 0) return;
    setEnCours(true);
    setErreur(null);
    try {
      const chunks = await apiClient.get<ChunkResultat[]>(
        `/recherche/semantique?q=${encodeURIComponent(q)}&k=${NB_RESULTATS}`,
      );
      setResultats(chunks);
    } catch (e) {
      setErreur(`Échec de la recherche : ${e instanceof Error ? e.message : String(e)}`);
      setResultats(null);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section>
      <EntetePage titre="Recherche sémantique">
        Interrogez le corps des clauses en langage naturel. La recherche s'appuie sur le moteur
        vectoriel (sens des clauses), et ne renvoie que des contrats <strong>validés</strong>{" "}
        (seuls indexés après le gate HITL).
      </EntetePage>

      <Carte style={{ marginBottom: espacements.xl }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void rechercher();
          }}
        >
          <Champ libelle="Votre question">
            <div style={{ display: "flex", gap: espacements.sm }}>
              <input
                type="search"
                value={requete}
                onChange={(e) => setRequete(e.target.value)}
                placeholder="Ex. : clauses de résiliation anticipée pour faute, indexation Syntec…"
                style={styleControle}
                autoFocus
              />
              <Bouton type="submit" disabled={enCours || requete.trim().length === 0}>
                {enCours ? "Recherche…" : "Rechercher"}
              </Bouton>
            </div>
          </Champ>
        </form>

        <div style={{ marginTop: espacements.lg }}>
          <Note>
            Cette page fait du <strong>sémantique</strong> (vectoriel, sur le corps des clauses).
            La recherche par <strong>facette</strong> (filtres structurés : indice, fournisseur,
            échéance) est du SQL et vit dans la page <em>Contrats</em>.
          </Note>
        </div>
      </Carte>

      {erreur && <Bandeau ton="danger">{erreur}</Bandeau>}

      {resultats !== null && !erreur && (
        <>
          <p
            style={{
              fontSize: typo.taille.sm,
              color: couleurs.texteAttenue,
              margin: `0 0 ${espacements.md}`,
            }}
          >
            {resultats.length === 0
              ? "Aucun extrait ne correspond à cette requête."
              : `${resultats.length} extrait(s) de clause`}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: espacements.md }}>
            {resultats.map((chunk, i) => (
              <ResultatChunk key={`${chunk.contrat_id}-${i}`} chunk={chunk} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function ResultatChunk({ chunk }: { chunk: ChunkResultat }): JSX.Element {
  const meta = metadataAffichables(chunk.metadata);
  return (
    <Carte>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: espacements.md,
          marginBottom: espacements.sm,
        }}
      >
        <span
          style={{
            background: couleurs.accentDoux,
            color: couleurs.accentFort,
            border: `1px solid ${couleurs.accent}`,
            borderRadius: rayons.rond,
            padding: `${espacements.xxs} ${espacements.md}`,
            fontSize: typo.taille.xs,
            fontWeight: typo.graisse.semi,
          }}
        >
          {libelleClause(chunk.type_clause)}
        </span>
        {/* Navigation par onglets dans le shell (#69) : pas de routeur. Le lien
            reste utile/partageable et dégrade proprement vers une URL future. */}
        <a
          href={`/contrats/${encodeURIComponent(chunk.contrat_id)}`}
          style={{
            fontSize: typo.taille.sm,
            color: couleurs.accent,
            textDecoration: "none",
            fontWeight: typo.graisse.moyenne,
            whiteSpace: "nowrap",
          }}
        >
          Voir le contrat →
        </a>
      </div>

      <p
        style={{
          fontSize: typo.taille.base,
          color: couleurs.texte,
          lineHeight: typo.hauteurLigne.aeree,
          margin: 0,
        }}
      >
        « {chunk.texte} »
      </p>

      {meta.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: espacements.sm,
            marginTop: espacements.md,
          }}
        >
          {meta.map(([k, v]) => (
            <span
              key={k}
              style={{
                fontSize: typo.taille.xs,
                color: couleurs.texteAttenue,
                background: couleurs.surfaceAlt,
                borderRadius: rayons.sm,
                padding: `${espacements.xxs} ${espacements.sm}`,
              }}
            >
              {k} : <strong>{v}</strong>
            </span>
          ))}
        </div>
      )}
    </Carte>
  );
}
