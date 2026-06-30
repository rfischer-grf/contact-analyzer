# Contract Intelligence (CLM souverain) — Spécification d'architecture

> Référence de conception destinée à Claude Code. **Source de vérité des décisions d'architecture.**
> Importée par le `CLAUDE.md` racine. À tenir à jour quand une décision change.

## 1. Objet

Plateforme souveraine de gestion intelligente des contrats fournisseurs :

1. Upload d'un contrat fournisseur.
2. Extraction structurée sur l'ensemble du corpus : informations fournisseur, signataires, dates (effet / échéance), préavis, tacite reconduction, clause d'indexation, montant.
3. Alertes (échéance, date limite de dénonciation) et projection tarifaire si le contrat est indexé sur un indice (Syntec, ILAT, ILC, ICC, INSEE).

**Pattern transverse : qualification → résolution → traçabilité.** Extraction = qualification ; validation HITL + alerte = résolution ; piste d'audit = traçabilité.

## 2. Pipeline (flux nominal)

```
upload (presigned)  →  contrôle + AV  →  Docling (parse/OCR)  →  extraction LLM
   →  rapprochement (avenant?)  →  [GATE HITL]  →  commit (état effectif)
   →  projection Weaviate  →  alertes (job quotidien) + feed ICS
```

### 2.1 Ingestion

- Upload direct navigateur → S3 via URL présignée (PUT, courte durée). Les octets ne transitent jamais par l'API.
- Le bucket/préfixe est dérivé du claim tenant du token Keycloak, jamais fourni par le client.
- Clé canonique = SHA256 du fichier (join key, dédoublonnage, idempotence).
- L'app confirme la fin d'upload → l'API fait un `HEAD` sur l'objet → démarre le workflow Temporal. Idempotent sur le SHA256.
- Contrôles première étape : type MIME, taille, scan antivirus (ClamAV).

### 2.2 Parsing — Docling

- CPU par défaut. La latence n'a aucune importance (pipeline async + gate HITL de plusieurs jours), donc seuls comptent coût et throughput en pic.
- OCR : RapidOCR (ONNX, efficace CPU). **Jamais EasyOCR** (torch, réclame GPU). OCR conditionnel : uniquement si pas de couche texte (PDF scanné).
- Conserver la provenance (page + bbox) de chaque bloc → indispensable pour le surlignage de validation et l'audit.
- GPU : seulement en pool L4 éphémère scale-to-zero sur Kapsule, et seulement si l'OCR sur des bursts de scans devient pénible. Ne pas le construire en avance. **Ne jamais colocaliser Docling sur le nœud GPU qui sert vLLM.**

### 2.3 Extraction LLM

- Pydantic AI + sortie structurée validée contre le schéma (voir §3).
- Modèle : Mistral Small 3.x via Scaleway Generative APIs (souverain EU) ou self-host vLLM. Le 7B local seulement pour pré-filtrage/classification.
- Stratégie : un contrat fait en général 5–30 pages → donner le markdown Docling complet. Si volumineux, retrieve les clauses utiles (parties, durée, résiliation, indexation) avant extraction.
- Chaque champ porte valeur + confiance + provenance (cf. wrapper `Champ`).

### 2.4 Validation humaine (HITL) — GATE

- **Non négociable.** Un préavis ou une date mal extraits = engagement raté.
- La validation est un gate : seul un contrat **VALIDÉ** entre dans l'ICS, le périmètre d'alerte et l'index Weaviate. Aucune donnée `à_valider` ne doit polluer recherche/RAG ni générer d'alerte.
- Champs sous le seuil de confiance → file de revue. UI : champ + surlignage de la source (pdf.js + overlay bbox). Les corrections alimentent un gold set.

### 2.5 Indexation / projection

- ILAT, ILC, ICC et indices INSEE → API BDM INSEE (SDMX 2.1 REST, gratuite), interrogation par `idbank` (dataflow `ILC-ILAT-ICC`). Déterministe, souverain.
- Syntec → **PAS d'API.** Publié par la Fédération Syntec (et non l'INSEE) ; seule la valeur mensuelle est diffusée sur syntec.fr. → collecteur dédié : scrape mensuel de syntec.fr (ou service payant type Le Moniteur).
  - Appliquer le coefficient de raccord **0,97975** pour tout acte de référence antérieur à août 2022 (passage à l'indice révisé).
- Séries stockées en PostgreSQL (`indice, periode, valeur`).
- Formule de révision par contrat : `P1 = P0 × (S1/S0)`, ou avec part fixe `P1 = P0 × (a + b·S1/S0)`. `S0` = dernier indice à la date de l'acte de référence tarifaire ; `S1` = dernier indice à la date de révision.
- Clause unidirectionnelle (hausse seule) = réputée non écrite → **forcer le bidirectionnel** dans le moteur.

### 2.6 Alerting + visibilité

- Date actionnable = date limite de dénonciation = échéance − préavis (**pas l'échéance**), critique en tacite reconduction.
- Alerte fiable = job quotidien qui scanne l'état effectif : `WHERE date_limite_denonciation - today IN (90, 60, 30, 7)` → mail (Mailjet) + in-app, et logge l'envoi (preuve, traçabilité). **Pas de timer Temporal pour l'alerte.**
- iCal = visibilité seulement. Feed `.ics` (1 VEVENT par échéance / date limite de dénonciation / date de révision) auquel l'utilisateur s'abonne dans Outlook. **Ne pas s'appuyer sur `VALARM`** pour alerter (honoré de façon inconstante, pas de preuve d'envoi). URL d'abonnement = capability bearer → token long aléatoire, révocable/rotatable par utilisateur ; le feed ne contient que dates + intitulé, jamais le contenu des clauses.

## 3. Modèle de données

Wrapper générique pour tout champ extrait :

```python
class Provenance(BaseModel):
    page: int
    bbox: tuple[float, float, float, float] | None = None
    extrait: str                       # texte source brut

class Champ(BaseModel, Generic[T]):
    valeur: Optional[T]
    confiance: float = Field(ge=0, le=1)
    source: Provenance | None = None
```

Entités extraites :

- `Partie` (raison_sociale, siren, forme_juridique, adresse)
- `Signataire` (nom, qualite, pour_le_compte_de, date_signature)
- `ClauseIndexation` (indice ∈ {syntec, ilat, ilc, icc, insee_autre, aucun}, indice_base_valeur S0, indice_base_periode, formule, part_fixe, periodicite, bidirectionnelle)
- `Preavis` (delai, unite, modalites)
- `Contrat` (fournisseur, client, signataires, objet, date_effet, date_echeance, duree_initiale_mois, tacite_reconduction, duree_reconduction_mois, preavis, indexation, montant, devise)

`date_limite_denonciation` est **CALCULÉE** en aval (échéance − préavis), jamais extraite.

### 3.1 document vs contrat (clé pour les avenants)

- `document` = chaque pièce physique (contrat d'origine OU avenant) : SHA256, clé S3, n° d'avenant, sa propre date de signature, extraction de la pièce.
- `contrat` = entité logique. Ne stocke pas des champs bruts mais **l'état effectif calculé**.
- Relation 1—N ordonnée par date de signature. État effectif = fold sur la chaîne de documents dans l'ordre de signature.
- Un avenant peut modifier durée (→ nouvelle échéance), préavis (→ nouvelle date limite), indice/base, montant. `committer()` rejoue la chaîne et réécrit l'état effectif → le job quotidien se corrige seul (aucun timer à reprogrammer).
- Re-ancrage tarifaire : un avenant de prix re-fixe `P0` et `S0` à sa date. `date_acte_reference` pour l'indexation = signature du dernier acte tarifaire, pas la signature initiale.
- Lien avenant→parent = fuzzy (SIREN des parties + référence + objet) : proposé à l'étape RAPPROCHEMENT, confirmé dans le même gate HITL. **Jamais d'auto-lien** (rattacher au mauvais parent corromprait silencieusement les échéances).

## 4. Saga Temporal (ingestion)

États : `RECU → CONTROLE → (REJETE_TECHNIQUE) → PARSING → EXTRACTION → RAPPROCHEMENT → A_VALIDER →` [attente signal `valider`/`rejeter`] `→ VALIDE → COMMITE` / `REJETE_METIER`.

- `Query statut` = comment le front lit l'avancement (polling léger ou SSE).
- AV positif ≠ retry : infra AV qui tombe → retry ; malware détecté → décision métier `REJETE_TECHNIQUE`, terminal.
- Le gate HITL est une vraie attente de signal (durée indéterminée) avec relance si silence > 7 j, en boucle. C'est ce qui justifie Temporal ici (pas l'alerting).
- Après `COMMITE` : activity de projection Weaviate (cf. §6), idempotente.

## 5. Stack (dev)

**Cœur de données :**

- **PostgreSQL** — source de vérité unique : documents, contrats, état effectif, champs + provenance, séries d'indices, piste d'audit. RLS multi-tenant dès le dev.
- **Garage** (+ garage-webui) — stockage S3 des originaux. **Jamais MinIO.**
- **Keycloak** — OIDC SPA + API ; en dev `start-dev`, mono-realm.

**Workflow & traitement :**

- **Temporal** — saga d'ingestion ; en dev le dev server (binaire unique, UI).
- **Worker Docling** (CPU, RapidOCR).
- **ClamAV** (clamd) — gate AV.
- **LLM extraction** — Scaleway Generative APIs, ou Ollama/vLLM local en offline.
- **Service d'embeddings** (BYO vectors) — bge-m3 / e5 local ou Mistral embed.

**App :**

- **API FastAPI** — presign, trigger workflow, endpoints HITL, recherche, feed ICS, job d'alerte.
- **Front React** (Vite) branché Keycloak.

**Substitutions dev :**

- Mailpit au lieu de Mailjet.
- Collecteur d'indices : script + fixtures (valeurs INSEE/Syntec figées).
- Job d'alerte quotidien : tâche planifiée simple (ou Temporal Schedule).

Optionnel : Langfuse (traces/qualité d'extraction, léger). SigNoz = prod seulement. Redis = non par défaut (ajouter sur besoin concret).

## 6. Recherche & RAG (Weaviate)

- **Weaviate** est le vector store (réutilisation de l'instance RF Cortex pour homogénéité du retrieval / feeder RAG). **pgvector retiré** — pas deux vector stores.
- Postgres = source de vérité, Weaviate = index dérivé, **jamais l'inverse**.
- Écriture Weaviate **uniquement après `COMMITE`**. Activity de projection en fin de saga, idempotente sur `contrat_id` : delete-then-insert des chunks (gère les avenants qui réécrivent l'état).
- Isolation multi-tenant : RLS Postgres ne protège pas Weaviate → utiliser le multi-tenancy natif Weaviate (isolation physique + purge tenant propre, RGPD/réversibilité), ou a minima propriété `tenant` + filtre injecté côté API (jamais fourni par le client).
- Réconciliation périodique : diff `contrat_id` Postgres vs Weaviate pour rattraper une écriture Weaviate échouée après commit Postgres.
- Chunking par clause/article (via la structure Docling), pas en fenêtre fixe. Métadonnée par chunk : `contrat_id, tenant, type_clause, date_echeance, fournisseur_siren` → filtrage RAG sans repasser par Postgres.
- Embeddings BYO, découplés du store.
- Recherche purement par facette extraite (« contrats à clause Syntec », « échéances Q3 ») = SQL `WHERE` sur Postgres, **pas du vectoriel**. Le vectoriel sert uniquement au sémantique sur le corps des clauses et au RAG.

## 7. Garde-fous explicites (NE PAS faire)

- Pas de MinIO → **Garage**.
- Pas de pgvector → **Weaviate** est le vector store.
- Pas de Neo4j → la chaîne avenant→parent / fournisseur→contrats est **relationnelle**.
- Pas de Redis sans besoin concret (rate-limit, cache d'index).
- Pas d'EasyOCR → **RapidOCR**.
- Pas de GPU always-on pour Docling ; pas de Docling sur le nœud vLLM.
- Pas de bytes d'upload via l'API → **URL présignée**.
- Pas de bucket/tenant fourni par le client → **dérivé du token**.
- Pas de confiance au `VALARM` iCal pour alerter → **job quotidien loggé**.
- Pas d'auto-lien avenant→parent → **confirmation HITL**.
- Pas d'écriture Weaviate avant `COMMITE`.
