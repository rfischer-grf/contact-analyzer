"""Workflows Temporal (spec §4).

`IngestionWorkflow` matérialise la machine à états et enchaîne les activities du
pipeline. Le **gate HITL** est une vraie attente de signal de durée indéterminée,
avec relance si silence > 7 jours (en boucle) : c'est ce qui justifie Temporal
(et non l'alerting, qui est un job quotidien — §2.6).

Garde-fous (§4) : une erreur d'infra est *retryable* (RetryPolicy) ; un AV négatif
est une décision métier *terminale* → `REJETE_TECHNIQUE`. Les activities sont
appelées par nom (découplage des signatures réelles, branchées via tickets dédiés).
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .states import EtatIngestion

RELANCE_HITL = timedelta(days=7)
_TIMEOUT_ACTIVITE = timedelta(minutes=10)
_RETRY = RetryPolicy(maximum_attempts=5)


@workflow.defn
class HelloWorkflow:
    """Workflow de fumée (bootstrap worker, #5)."""

    @workflow.run
    async def run(self, nom: str) -> str:
        return f"bonjour {nom}"


@workflow.defn
class IngestionWorkflow:
    """Saga d'ingestion : RECU → … → A_VALIDER → [signal] → COMMITE / REJETE_*."""

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

    async def _activite(self, nom: str, arg: str) -> object:
        return await workflow.execute_activity(
            nom,
            args=[arg],
            start_to_close_timeout=_TIMEOUT_ACTIVITE,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, sha256: str) -> str:
        # Contrôle + antivirus.
        self._etat = EtatIngestion.CONTROLE
        sain = await self._activite("controle_et_av", sha256)
        if not sain:
            # Décision métier terminale (malware) — pas de retry.
            self._etat = EtatIngestion.REJETE_TECHNIQUE
            return self._etat.value

        # Parsing → extraction → rapprochement.
        self._etat = EtatIngestion.PARSING
        await self._activite("parser_document", sha256)
        self._etat = EtatIngestion.EXTRACTION
        await self._activite("extraire_champs", sha256)
        self._etat = EtatIngestion.RAPPROCHEMENT
        await self._activite("rapprocher_avenant", sha256)

        # Gate HITL (#21) : attente de signal, relance toutes les 7 j tant que silence.
        self._etat = EtatIngestion.A_VALIDER
        while self._decision is None:
            try:
                await workflow.wait_condition(
                    lambda: self._decision is not None, timeout=RELANCE_HITL
                )
            except TimeoutError:
                workflow.logger.info("Relance HITL : silence > 7 jours")

        if self._decision == "rejeter":
            self._etat = EtatIngestion.REJETE_METIER
            return self._etat.value

        # Validé : commit de l'état effectif puis projection Weaviate (après COMMITE).
        self._etat = EtatIngestion.VALIDE
        await self._activite("committer", sha256)
        self._etat = EtatIngestion.COMMITE
        await self._activite("projeter_weaviate", sha256)
        return self._etat.value
