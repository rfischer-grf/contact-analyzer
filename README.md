# Contract Intelligence (CLM souverain)

Plateforme souveraine (EU) de gestion intelligente des contrats fournisseurs.

Upload d'un contrat → extraction structurée par LLM (avec provenance page/bbox) →
**validation humaine (gate HITL)** → alertes d'échéance et de date limite de
dénonciation + projection tarifaire pour les contrats indexés (Syntec, ILAT, ILC,
ICC, INSEE). Pattern transverse : **qualification → résolution → traçabilité**.

## Architecture

La conception est documentée dans **[`docs/architecture.md`](docs/architecture.md)** —
source de vérité des décisions d'architecture. Le pipeline nominal :

```
upload (presigned)  →  contrôle + AV  →  Docling (parse/OCR)  →  extraction LLM
   →  rapprochement (avenant?)  →  [GATE HITL]  →  commit (état effectif)
   →  projection Weaviate  →  alertes (job quotidien) + feed ICS
```

## Stack (dev)

| Domaine            | Choix                                                        |
| ------------------ | ------------------------------------------------------------ |
| Source de vérité   | PostgreSQL (RLS multi-tenant)                                |
| Stockage S3        | Garage                                                       |
| Auth               | Keycloak (OIDC)                                              |
| Orchestration      | Temporal (saga d'ingestion)                                  |
| Parsing            | Docling (CPU, RapidOCR)                                      |
| Antivirus          | ClamAV                                                       |
| Extraction LLM     | Mistral Small 3.x (Scaleway Generative APIs ou vLLM local)   |
| Vector store / RAG | Weaviate (index dérivé)                                      |
| API                | FastAPI                                                      |
| Front              | React (Vite)                                                 |
| Mail (dev)         | Mailpit                                                      |

Voir `docs/architecture.md` §5 pour le détail et §7 pour les garde-fous explicites.

## Statut

Bootstrap : la spécification d'architecture est posée comme source de vérité.
L'implémentation des services suit cette référence.
