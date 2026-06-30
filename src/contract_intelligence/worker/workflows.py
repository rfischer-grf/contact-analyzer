"""Workflows Temporal (spec §4).

`IngestionWorkflow` matérialise la machine à états. Le **gate HITL** est une vraie
attente de signal de durée indéterminée, avec relance si silence > 7 jours (en boucle) :
c'est ce qui justifie Temporal (et non l'alerting, qui est un job quotidien — §2.6).
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .states import EtatIngestion

RELANCE_HITL = timedelta(days=7)


@workflow.defn
class HelloWorkflow:
    """Workflow de fumée (bootstrap worker, #5)."""

    @workflow.run
    async def run(self, nom: str) -> str:
        return f"bonjour {nom}"


@workflow.defn
class IngestionWorkflow:
    """Saga d'ingestion (squelette des états ; activities câblées via tickets dédiés)."""

    def __init__(self) -> None:
        self._etat: EtatIngestion = EtatIngestion.RECU
        self._decision: str | None = None

    @workflow.query
    def statut(self) -> str:
        """Lecture de l'avancement par le front (#22)."""
        return self._etat.value

    @workflow.signal
    def valider(self) -> None:
        self._decision = "valider"

    @workflow.signal
    def rejeter(self) -> None:
        self._decision = "rejeter"

    @workflow.run
    async def run(self, sha256: str) -> str:
        # Enchaînement nominal (les activities seront branchées : #20).
        self._etat = EtatIngestion.CONTROLE
        # ... PARSING → EXTRACTION → RAPPROCHEMENT (#20)
        self._etat = EtatIngestion.A_VALIDER

        # Gate HITL (#21) : attente de signal, relance toutes les 7 j tant que silence.
        while self._decision is None:
            try:
                await workflow.wait_condition(
                    lambda: self._decision is not None, timeout=RELANCE_HITL
                )
            except TimeoutError:
                workflow.logger.info("Relance HITL : silence > 7 jours")

        if self._decision == "valider":
            self._etat = EtatIngestion.VALIDE
            # committer() puis projection Weaviate (idempotente, après COMMITE) : #38/#48
            self._etat = EtatIngestion.COMMITE
        else:
            self._etat = EtatIngestion.REJETE_METIER
        return self._etat.value
