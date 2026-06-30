"""Activities du pipeline d'ingestion (spec §2, §4).

Pipeline réel câblé de bout en bout : contrôle + AV → parsing Docling → extraction
LLM → rapprochement avenant (proposition) → persistance → commit de l'état effectif
→ projection Weaviate. Chaque activity est `async` et décorée `@activity.defn`.

**Imports différés** : les modules métier (ingestion, parsing, extraction, rag,
avenants, db, boto3) sont importés **dans le corps des activities**, jamais au
niveau module. Le worker importe donc `activities` sans tirer les extras lourds
(docling, weaviate, pydantic-ai…), qui ne sont requis qu'à l'exécution réelle.

Garde-fous §4 — infra (retryable) vs métier (terminal) :

- `ControleRejete` / `MalwareDetecte` → **décision métier terminale** :
  `ApplicationError(..., non_retryable=True)` → la saga bascule en `REJETE_TECHNIQUE`,
  sans retry (le fichier ne deviendra jamais conforme).
- `AntivirusIndisponible` et toute erreur d'infra (S3, DB, réseau) → on les laisse
  **remonter** : la RetryPolicy du workflow les retentera (clamd peut redémarrer…).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

if TYPE_CHECKING:  # imports purement typage — non exécutés à l'exécution
    from sqlalchemy.orm import Session, sessionmaker

    from ..config import Settings


# --------------------------------------------------------------------------- S3


def _s3_client(settings: Settings):  # type: ignore[no-untyped-def]
    """Client S3 (Garage) côté serveur — même style que `api/routers/uploads.py`.

    Path-style forcé (URLs `…/contrats/<clé>` déterministes) et endpoint INTERNE :
    l'activity lit les octets déjà déposés sur S3 (les bytes ne transitent jamais
    par l'API — §7). Import différé de boto3 (extra `api`).
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _session_factory(settings: Settings) -> sessionmaker[Session]:
    """Fabrique de sessions DB liée à la base configurée (import différé)."""
    from ..db import make_engine, make_sessionmaker

    return make_sessionmaker(make_engine(settings.database_url))


# ----------------------------------------------------------------- aides locales


def _date_signature(extraction: dict[str, Any]) -> date:
    """Déduit la date de signature de la pièce depuis l'extraction.

    Priorité : 1er `signataire.date_signature` renseigné, sinon `date_effet`,
    sinon `date.today()`. La chaîne de documents est ordonnée par cette date
    (§3.1) ; un avenant porte sa propre date de signature.
    """
    for signataire in extraction.get("signataires") or []:
        valeur = _valeur_champ(signataire.get("date_signature"))
        if valeur:
            return date.fromisoformat(str(valeur))
    valeur = _valeur_champ(extraction.get("date_effet"))
    if valeur:
        return date.fromisoformat(str(valeur))
    return date.today()


def _valeur_champ(champ: Any) -> Any:
    """Valeur d'un wrapper `Champ` sérialisé (`{"valeur": ..., ...}`), ou None."""
    if isinstance(champ, dict):
        return champ.get("valeur")
    return None


def _parties_ref(extraction: dict[str, Any]):  # type: ignore[no-untyped-def]
    """Construit la signature de rapprochement d'une pièce (SIREN + référence + objet)."""
    from ..avenants.matching import PartiesRef

    fournisseur = extraction.get("fournisseur") or {}
    client = extraction.get("client") or {}
    return PartiesRef(
        siren_fournisseur=_valeur_champ(fournisseur.get("siren")),
        siren_client=_valeur_champ(client.get("siren")),
        reference=extraction.get("reference"),
        objet=_valeur_champ(extraction.get("objet")),
    )


# ------------------------------------------------------------------- activities


@activity.defn
async def controle_et_av(tenant: str, sha256: str, cle_s3: str) -> bool:
    """Contrôles MIME/taille (#17) + scan antivirus ClamAV (#18) sur l'objet S3.

    HEAD pour le type/taille (les bytes ne transitent pas par l'API — §7), puis
    GET du contenu pour le scan AV. `ControleRejete`/`MalwareDetecte` → terminal
    (non-retryable) ; `AntivirusIndisponible`/erreur infra → remonte (retryable).
    """
    from ..config import get_settings
    from ..ingestion.antivirus import MalwareDetecte, analyser
    from ..ingestion.controles import ControleRejete, valider_mime, valider_taille

    settings = get_settings()
    s3 = _s3_client(settings)

    tete = s3.head_object(Bucket=settings.s3_bucket, Key=cle_s3)
    content_type = tete.get("ContentType") or "application/octet-stream"
    content_length = int(tete.get("ContentLength") or 0)

    try:
        valider_mime(content_type)
        valider_taille(content_length)
    except ControleRejete as exc:
        # Décision métier terminale → REJETE_TECHNIQUE (pas de retry).
        raise ApplicationError(str(exc), type="ControleRejete", non_retryable=True) from exc

    objet = s3.get_object(Bucket=settings.s3_bucket, Key=cle_s3)
    octets = objet["Body"].read()

    try:
        analyser(octets)  # None si sain ; lève sinon
    except MalwareDetecte as exc:
        # Malware détecté = décision métier terminale → REJETE_TECHNIQUE.
        raise ApplicationError(str(exc), type="MalwareDetecte", non_retryable=True) from exc
    # AntivirusIndisponible (et toute erreur infra) : on laisse remonter (retryable).

    return True


@activity.defn
async def parser_document(tenant: str, sha256: str, cle_s3: str) -> dict:
    """Parsing Docling CPU + OCR conditionnel RapidOCR + provenance (#24–#27).

    GET de l'objet S3 puis `DoclingParser().parser(...)`. Renvoie un dict
    sérialisable `{"markdown": str, "blocs": [{page, bbox, texte, type}, ...]}`.
    Si l'extra `parsing` (docling) n'est pas installé, repli sur le `FakeParser`
    (mêmes octets → blocs + markdown) pour garder le pipeline fonctionnel offline.
    """
    from ..config import get_settings

    settings = get_settings()
    s3 = _s3_client(settings)
    objet = s3.get_object(Bucket=settings.s3_bucket, Key=cle_s3)
    octets = objet["Body"].read()

    parser = _construire_parser()
    parse = parser.parser(octets, ocr_si_scanne=settings.docling_ocr_si_scanne)

    return {
        "markdown": parse.markdown,
        "blocs": [
            {
                "page": b.page,
                "bbox": list(b.bbox) if b.bbox else None,
                "texte": b.texte,
                "type": b.type,
            }
            for b in parse.blocs
        ],
    }


def _construire_parser():  # type: ignore[no-untyped-def]
    """Parser réel Docling si l'extra est disponible, sinon `FakeParser` (offline)."""
    try:
        from ..parsing.docling_parser import DoclingParser

        return DoclingParser()
    except Exception:  # noqa: BLE001 - extra `parsing` (docling) absent → repli
        from ..parsing import FakeParser

        return FakeParser()


@activity.defn
async def extraire_champs(markdown: str) -> dict:
    """Extraction LLM structurée (Pydantic AI) → `Contrat` (§3) sérialisé (#28–#31).

    `ExtracteurLLM().extraire(markdown)` rend un `domain.Contrat` (chaque champ
    porte valeur + confiance + provenance) ; on le sérialise en JSON. Repli sur le
    `FakeExtracteur` si l'extra `extraction` (pydantic-ai) n'est pas installé.
    """
    extracteur = _construire_extracteur()
    contrat = extracteur.extraire(markdown)
    return contrat.model_dump(mode="json")


def _construire_extracteur():  # type: ignore[no-untyped-def]
    """Extracteur LLM réel si disponible, sinon `FakeExtracteur` (offline)."""
    try:
        from ..extraction import ExtracteurLLM  # type: ignore[attr-defined]

        return ExtracteurLLM()
    except Exception:  # noqa: BLE001 - extra `extraction` (pydantic-ai) absent → repli
        from ..extraction import FakeExtracteur

        return FakeExtracteur()


@activity.defn
async def rapprocher_avenant(tenant: str, extraction: dict) -> dict | None:
    """Propose un parent pour l'avenant (SIREN + référence + objet) (#32, #33).

    Garde-fou §7 — **jamais d'auto-lien** : on ne fait que *proposer* le meilleur
    candidat (confirmation en gate HITL). La proposition est consignée en audit.
    Renvoie ``{"contrat_id", "score", "details"}`` du meilleur candidat, ou None
    si aucun contrat du tenant n'atteint le seuil. Les erreurs DB remontent
    (retryable) : une proposition manquée ne doit pas perdre le document.
    """
    from ..avenants.matching import proposer_candidats
    from ..config import get_settings
    from ..db import tenant_session
    from ..db.models import EvenementAudit

    settings = get_settings()
    factory = _session_factory(settings)
    avenant_ref = _parties_ref(extraction)

    with tenant_session(factory, tenant) as session:
        candidats = _candidats_du_tenant(session, tenant)
        proposes = proposer_candidats(avenant_ref, candidats)
        meilleur = proposes[0] if proposes else None

        # Traçabilité (§2) : on consigne la proposition, jamais le lien lui-même.
        session.add(
            EvenementAudit(
                tenant=tenant,
                acteur="systeme",
                type_evenement="RAPPROCHEMENT_PROPOSE",
                objet_type="document",
                objet_id=None,
                payload={
                    "candidats": [
                        {"contrat_id": c.contrat_id, "score": c.score, "details": c.details}
                        for c in proposes
                    ]
                },
            )
        )

        if meilleur is None:
            return None
        return {
            "contrat_id": meilleur.contrat_id,
            "score": meilleur.score,
            "details": meilleur.details,
        }


def _candidats_du_tenant(session: Session, tenant: str):  # type: ignore[no-untyped-def]
    """Signatures de rapprochement des contrats déjà committés du tenant.

    On ne propose comme parent qu'un contrat à l'état effectif établi (`COMMITE`),
    via sa première pièce (le contrat d'origine porte la référence/objet de tête).
    """
    from ..avenants.matching import PartiesRef
    from ..db.models import Contrat, Document

    candidats: dict[str, PartiesRef] = {}
    contrats = session.query(Contrat).filter(Contrat.tenant == tenant).all()
    for contrat in contrats:
        if contrat.etat != "COMMITE":
            continue
        origine = (
            session.query(Document)
            .filter(Document.contrat_id == contrat.id)
            .order_by(Document.date_signature)
            .first()
        )
        objet = None
        if origine is not None and origine.extraction:
            objet = _valeur_champ(origine.extraction.get("objet"))
        candidats[str(contrat.id)] = PartiesRef(
            siren_fournisseur=contrat.fournisseur_siren,
            siren_client=contrat.client_siren,
            reference=contrat.reference,
            objet=objet,
        )
    return candidats


@activity.defn
async def persister(tenant: str, sha256: str, cle_s3: str, extraction: dict) -> str:
    """Persiste l'extraction (Document + Contrat A_VALIDER) → renvoie `contrat_id`.

    Idempotent sur `(tenant, sha256)` (cf. `persister_extraction`). Renvoie l'id
    du contrat logique sous forme de chaîne (transport Temporal).
    """
    from ..config import get_settings
    from ..db import tenant_session
    from ..db.ingestion_repo import persister_extraction

    settings = get_settings()
    factory = _session_factory(settings)
    with tenant_session(factory, tenant) as session:
        contrat_id = persister_extraction(
            session,
            tenant=tenant,
            sha256=sha256,
            cle_s3=cle_s3,
            extraction=extraction,
            date_signature=_date_signature(extraction),
            reference=extraction.get("reference"),
        )
    return str(contrat_id)


@activity.defn
async def committer_contrat(contrat_id: str) -> None:
    """Rejoue la chaîne de documents, réécrit l'état effectif puis marque `COMMITE`.

    `committer()` folde les pièces (durée→échéance, préavis→date limite, indice/base,
    montant) et recalcule `date_limite_denonciation` ; le job d'alerte se corrige
    seul (§3.1). On positionne ensuite `etat="COMMITE"` (porte d'entrée projection).
    """
    from ..config import get_settings
    from ..db import committer, tenant_session
    from ..db.ingestion_repo import marquer_etat

    cid = uuid.UUID(contrat_id)
    settings = get_settings()
    factory = _session_factory(settings)

    # Le tenant est requis par la session RLS : on le lit hors-RLS (clé primaire).
    tenant = _tenant_du_contrat(factory, cid)
    with tenant_session(factory, tenant) as session:
        committer(session, cid, acteur="hitl")
        marquer_etat(session, cid, "COMMITE")


@activity.defn
async def rejeter_metier_contrat(contrat_id: str) -> None:
    """Marque le contrat `REJETE_METIER` (gate HITL négatif) — terminal côté saga."""
    from ..config import get_settings
    from ..db import tenant_session
    from ..db.ingestion_repo import rejeter_metier

    cid = uuid.UUID(contrat_id)
    settings = get_settings()
    factory = _session_factory(settings)
    tenant = _tenant_du_contrat(factory, cid)
    with tenant_session(factory, tenant) as session:
        rejeter_metier(session, cid)


@activity.defn
async def projeter_weaviate(tenant: str, contrat_id: str, markdown: str) -> None:
    """Projection Weaviate idempotente — UNIQUEMENT après COMMITE (#48, #50).

    `projeter_contrat(store, embeddeur, session, tenant, contrat_id, markdown)` fait
    un delete-then-insert des chunks (gère les avenants qui réécrivent l'état). Le
    store/embeddeur réels (Weaviate, embeddings BYO) sont choisis selon la config ;
    repli sur les implémentations Fake en mémoire en dev/offline.
    """
    from ..config import get_settings
    from ..db import tenant_session
    from ..rag import projeter_contrat

    settings = get_settings()
    factory = _session_factory(settings)
    store = _store_par_defaut(settings)
    embeddeur = _embeddeur_par_defaut(settings)

    with tenant_session(factory, tenant) as session:
        projeter_contrat(store, embeddeur, session, tenant, contrat_id, markdown)


def _store_par_defaut(settings: Settings):  # type: ignore[no-untyped-def]
    """Vector store : `store_par_defaut(settings)` si fourni, sinon Weaviate réel
    quand `weaviate_url` est configurée, sinon `FakeVectorStore` (dev/offline)."""
    try:
        from ..rag import store_par_defaut  # type: ignore[attr-defined]

        return store_par_defaut(settings)
    except Exception:  # noqa: BLE001 - factory non fournie → choix explicite ci-dessous
        pass
    if settings.weaviate_url:
        from ..rag.weaviate_store import WeaviateVectorStore

        return WeaviateVectorStore(settings.weaviate_url, settings.weaviate_api_key)
    from ..rag import FakeVectorStore

    return FakeVectorStore()


def _embeddeur_par_defaut(settings: Settings):  # type: ignore[no-untyped-def]
    """Embeddeur BYO : `embeddeur_par_defaut(settings)` si fourni, sinon `FakeEmbeddeur`."""
    try:
        from ..rag import embeddeur_par_defaut  # type: ignore[attr-defined]

        return embeddeur_par_defaut(settings)
    except Exception:  # noqa: BLE001 - factory non fournie → repli déterministe offline
        from ..rag import FakeEmbeddeur

        return FakeEmbeddeur(settings.embeddings_dimension)


def _tenant_du_contrat(factory: sessionmaker[Session], contrat_id: uuid.UUID) -> str:
    """Lit le tenant d'un contrat par clé primaire (hors-RLS) pour ouvrir ensuite
    une session bornée à ce tenant. Lève `ValueError` si le contrat est introuvable.
    """
    from ..db.models import Contrat

    with factory() as session:
        contrat = session.get(Contrat, contrat_id)
        if contrat is None:
            raise ValueError(f"Contrat introuvable : {contrat_id}")
        return contrat.tenant
