# CLAUDE.md — Contract Intelligence (CLM souverain)

Guidance pour Claude Code travaillant sur ce dépôt.

## Source de vérité

L'architecture du projet est spécifiée dans `docs/architecture.md`. **C'est la source de
vérité des décisions de conception** — la lire avant toute implémentation, et la mettre à
jour dans le même commit quand une décision change.

@docs/architecture.md

## Le projet en une phrase

Plateforme **souveraine** (EU) de gestion intelligente des contrats fournisseurs : upload →
extraction structurée (LLM + provenance) → validation humaine (gate HITL) → alertes
d'échéance/dénonciation + projection tarifaire indexée. Pattern transverse :
**qualification → résolution → traçabilité**.

## Invariants à ne jamais enfreindre

Ces garde-fous (détaillés en §7 de la spec) priment sur toute autre considération :

- **Stockage S3 = Garage**, jamais MinIO.
- **Vector store = Weaviate**, jamais pgvector. Postgres = source de vérité, Weaviate = index dérivé.
- **OCR = RapidOCR** (ONNX/CPU), jamais EasyOCR.
- **Pas de Neo4j** : la chaîne avenant→parent et fournisseur→contrats est relationnelle (Postgres).
- **Pas de Redis** sans besoin concret documenté.
- **Upload** : URL présignée navigateur→S3 ; les octets ne transitent jamais par l'API.
- **Tenant/bucket** dérivés du token Keycloak, jamais fournis par le client.
- **Gate HITL non négociable** : aucune donnée `à_valider` n'entre dans alertes / ICS / Weaviate.
- **Écriture Weaviate uniquement après `COMMITE`** (activity de projection idempotente).
- **Alerte = job quotidien loggé**, jamais un timer Temporal ni un `VALARM` iCal.
- **`date_limite_denonciation`** = échéance − préavis : calculée, jamais extraite. C'est la date actionnable.
- **Lien avenant→parent** : proposé au RAPPROCHEMENT, confirmé en HITL. Jamais d'auto-lien.
- **Clause d'indexation unidirectionnelle** (hausse seule) = réputée non écrite → forcer le bidirectionnel.
- **Pas de GPU always-on** pour Docling ; ne jamais colocaliser Docling sur le nœud vLLM.

## Notes de travail

- Les champs extraits portent toujours `valeur + confiance + provenance` (wrapper `Champ`, cf. §3).
- `document` (pièce physique) ≠ `contrat` (entité logique = état effectif foldé sur la chaîne de documents).
- Code/commentaires métier : français (cohérent avec la spec et le domaine).
