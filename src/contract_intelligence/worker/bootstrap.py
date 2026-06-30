"""Démarrage du worker Temporal (#5).

Usage : ``python -m contract_intelligence.worker.bootstrap`` (extra `worker` requis).
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import get_settings
from . import activities
from .workflows import HelloWorkflow, IngestionWorkflow


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal_target, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow, IngestionWorkflow],
        activities=[
            activities.controle_et_av,
            activities.parser_document,
            activities.extraire_champs,
            activities.rapprocher_avenant,
            activities.persister,
            activities.rattacher_avenant,
            activities.committer_contrat,
            activities.rejeter_metier_contrat,
            activities.projeter_weaviate,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
