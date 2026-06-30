"""Tests de la saga d'ingestion via le serveur de test Temporal (time-skipping).

Doubles d'activities (mêmes noms que la prod) couvrant les trois issues de la
machine à états (§4) :

- valider → COMMITE (commit de l'état effectif puis projection Weaviate) ;
- rejeter → REJETE_METIER ;
- contrôle/AV terminal → REJETE_TECHNIQUE (l'activity lève une `ApplicationError`
  non-retryable, comme `controle_et_av` pour `ControleRejete`/`MalwareDetecte`).

Auto-skippés si le serveur de test Temporal n'est pas démarrable (ex. binaire non
téléchargeable hors-ligne). Exécutés en CI.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("temporalio")

from temporalio import activity  # noqa: E402
from temporalio.exceptions import ApplicationError  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from contract_intelligence.worker.workflows import IngestionWorkflow  # noqa: E402

TASK_QUEUE = "test-ingestion"

# Extraction sérialisée minimale renvoyée par le double d'extraction.
_EXTRACTION = {
    "fournisseur": {"raison_sociale": {"valeur": "ACME", "confiance": 0.99}},
    "client": {"raison_sociale": {"valeur": "RF", "confiance": 0.99}},
}


@activity.defn(name="controle_et_av")
async def _av_ok(tenant: str, sha256: str, cle_s3: str) -> bool:
    return True


@activity.defn(name="controle_et_av")
async def _av_terminal(tenant: str, sha256: str, cle_s3: str) -> bool:
    # Décision métier terminale (malware/contrôle) → non-retryable → REJETE_TECHNIQUE.
    raise ApplicationError("malware détecté", type="MalwareDetecte", non_retryable=True)


@activity.defn(name="parser_document")
async def _parser(tenant: str, sha256: str, cle_s3: str) -> dict:
    return {"markdown": "# contrat", "blocs": []}


@activity.defn(name="extraire_champs")
async def _extraire(markdown: str) -> dict:
    return dict(_EXTRACTION)


@activity.defn(name="rapprocher_avenant")
async def _rapprocher(tenant: str, extraction: dict) -> dict | None:
    return None


@activity.defn(name="persister")
async def _persister(tenant: str, sha256: str, cle_s3: str, extraction: dict) -> str:
    return "11111111-1111-1111-1111-111111111111"


#: Cibles successives de `committer_contrat` (le test du chemin avenant l'inspecte).
COMMITS: list[str] = []


@activity.defn(name="committer_contrat")
async def _committer(contrat_id: str) -> None:
    COMMITS.append(contrat_id)


@activity.defn(name="rattacher_avenant")
async def _rattacher_avenant(contrat_id: str, parent_contrat_id: str) -> str:
    # Rattachement réel : renvoie le parent, qui devient la cible du commit (#33).
    return parent_contrat_id


@activity.defn(name="rejeter_metier_contrat")
async def _rejeter(contrat_id: str) -> None:
    return None


@activity.defn(name="projeter_weaviate")
async def _projeter(tenant: str, contrat_id: str, markdown: str) -> None:
    return None


# Pipeline aval commun (le double de contrôle/AV est injecté par scénario).
_PIPELINE = [
    _parser,
    _extraire,
    _rapprocher,
    _persister,
    _rattacher_avenant,
    _committer,
    _rejeter,
    _projeter,
]


async def _demarrer_env():
    try:
        return await WorkflowEnvironment.start_time_skipping()
    except Exception as exc:  # pragma: no cover - dépend du réseau
        pytest.skip(f"serveur de test Temporal indisponible : {exc}")


async def _scenario(av, signal: str | None, parent: str | None = None) -> str:
    env = await _demarrer_env()
    async with env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IngestionWorkflow],
            activities=[av, *_PIPELINE],
        ):
            handle = await env.client.start_workflow(
                IngestionWorkflow.run, "sha-test", id="acme:sha-test", task_queue=TASK_QUEUE
            )
            if signal == "valider":
                await handle.signal(IngestionWorkflow.valider, parent)
            elif signal == "rejeter":
                await handle.signal(IngestionWorkflow.rejeter)
            return await handle.result()


def test_valider_mene_a_commite() -> None:
    assert asyncio.run(_scenario(_av_ok, "valider")) == "COMMITE"


def test_rejeter_mene_a_rejete_metier() -> None:
    assert asyncio.run(_scenario(_av_ok, "rejeter")) == "REJETE_METIER"


def test_controle_terminal_mene_a_rejete_technique() -> None:
    assert asyncio.run(_scenario(_av_terminal, None)) == "REJETE_TECHNIQUE"


def test_valider_avec_parent_commit_le_parent() -> None:
    """#33 : un parent confirmé → rattachement → c'est le PARENT qui est committé."""
    COMMITS.clear()
    assert asyncio.run(_scenario(_av_ok, "valider", parent="parent-xyz")) == "COMMITE"
    # La cible du commit est le parent (pas le contrat standalone `persister`).
    assert COMMITS == ["parent-xyz"]
