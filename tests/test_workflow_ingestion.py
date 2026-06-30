"""Tests de la saga d'ingestion via le serveur de test Temporal (time-skipping).

Auto-skippés si le serveur de test Temporal n'est pas démarrable (ex. binaire non
téléchargeable hors-ligne). Exécutés en CI.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("temporalio")

from temporalio import activity  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from contract_intelligence.worker.workflows import IngestionWorkflow  # noqa: E402

TASK_QUEUE = "test-ingestion"


@activity.defn(name="controle_et_av")
async def _av_ok(arg: str) -> bool:
    return True


@activity.defn(name="controle_et_av")
async def _av_ko(arg: str) -> bool:
    return False


@activity.defn(name="parser_document")
async def _parser(arg: str) -> dict:
    return {}


@activity.defn(name="extraire_champs")
async def _extraire(arg: str) -> dict:
    return {}


@activity.defn(name="rapprocher_avenant")
async def _rapprocher(arg: str) -> dict:
    return {}


@activity.defn(name="committer")
async def _committer(arg: str) -> str:
    return "ok"


@activity.defn(name="projeter_weaviate")
async def _projeter(arg: str) -> None:
    return None


_PIPELINE = [_parser, _extraire, _rapprocher, _committer, _projeter]


async def _demarrer_env():
    try:
        return await WorkflowEnvironment.start_time_skipping()
    except Exception as exc:  # pragma: no cover - dépend du réseau
        pytest.skip(f"serveur de test Temporal indisponible : {exc}")


async def _scenario(av, signal: str | None) -> str:
    env = await _demarrer_env()
    async with env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IngestionWorkflow],
            activities=[av, *_PIPELINE],
        ):
            handle = await env.client.start_workflow(
                IngestionWorkflow.run, "sha-test", id="wf-test", task_queue=TASK_QUEUE
            )
            if signal == "valider":
                await handle.signal(IngestionWorkflow.valider)
            elif signal == "rejeter":
                await handle.signal(IngestionWorkflow.rejeter)
            return await handle.result()


def test_valider_mene_a_commite() -> None:
    assert asyncio.run(_scenario(_av_ok, "valider")) == "COMMITE"


def test_rejeter_mene_a_rejete_metier() -> None:
    assert asyncio.run(_scenario(_av_ok, "rejeter")) == "REJETE_METIER"


def test_av_negatif_mene_a_rejete_technique() -> None:
    assert asyncio.run(_scenario(_av_ko, None)) == "REJETE_TECHNIQUE"
