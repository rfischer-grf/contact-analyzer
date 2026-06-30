"""Workflows Temporal (spec §4).

`IngestionWorkflow` matérialise la machine à états et enchaîne les activities du
pipeline réel. Le **gate HITL** est une vraie attente de signal de durée
indéterminée, avec relance si silence > 7 jours (en boucle) : c'est ce qui
justifie Temporal (et non l'alerting, qui est un job quotidien — §2.6).

Enchaînement (§2, §4) :

    CONTROLE → PARSING → EXTRACTION → RAPPROCHEMENT → persister → A_VALIDER
        → [signal valider] → committer_contrat → COMMITE → projeter_weaviate
        → [signal rejeter]  → rejeter_metier_contrat → REJETE_METIER

Garde-fous (§4) : erreur d'infra = *retryable* (RetryPolicy) ; AV négatif /
contrôle KO = décision métier *terminale* → l'activity lève une `ApplicationError`
non-retryable, qui remonte ici en `ActivityError` → `REJETE_TECHNIQUE`. Les
activities sont appelées par nom (découplage des signatures réelles).

Le `tenant` et la clé S3 sont dérivés de l'identité de la saga : le workflow_id
suit la convention `tenant:sha256` (cf. `api/routers/uploads.py::_workflow_id`),
et la clé S3 `tenant/sha256` (cf. `_objet_cle`). Les bytes ne transitent jamais
par l'API ni par le workflow — seules des références circulent (§7).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

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

    def _identite(self, sha256: str) -> tuple[str, str]:
        """Dérive `(tenant, cle_s3)` de l'identité de la saga (workflow_id).

        Convention `tenant:sha256` (uploads.py) → clé S3 `tenant/sha256`. Si le
        workflow_id ne porte pas de tenant (ex. test), on retombe sur ``"default"``.
        """
        wf_id = workflow.info().workflow_id
        tenant = wf_id.split(":", 1)[0] if ":" in wf_id else "default"
        return tenant, f"{tenant}/{sha256}"

    async def _activite(self, nom: str, *args: Any) -> Any:
        return await workflow.execute_activity(
            nom,
            args=list(args),
            start_to_close_timeout=_TIMEOUT_ACTIVITE,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, sha256: str) -> str:
        tenant, cle_s3 = self._identite(sha256)

        # Contrôle + antivirus. Un échec terminal (ControleRejete/MalwareDetecte)
        # remonte en erreur non-retryable → REJETE_TECHNIQUE.
        self._etat = EtatIngestion.CONTROLE
        try:
            await self._activite("controle_et_av", tenant, sha256, cle_s3)
        except ActivityError as exc:
            if _est_terminal(exc):
                self._etat = EtatIngestion.REJETE_TECHNIQUE
                return self._etat.value
            raise

        # Parsing → extraction.
        self._etat = EtatIngestion.PARSING
        parse = await self._activite("parser_document", tenant, sha256, cle_s3)
        markdown = parse.get("markdown", "") if isinstance(parse, dict) else ""

        self._etat = EtatIngestion.EXTRACTION
        extraction = await self._activite("extraire_champs", markdown)

        # Rapprochement avenant→parent : proposition seulement (jamais d'auto-lien).
        self._etat = EtatIngestion.RAPPROCHEMENT
        await self._activite("rapprocher_avenant", tenant, extraction)

        # Persistance (Document + Contrat A_VALIDER) → contrat_id propagé en aval.
        contrat_id = await self._activite("persister", tenant, sha256, cle_s3, extraction)

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
            await self._activite("rejeter_metier_contrat", contrat_id)
            self._etat = EtatIngestion.REJETE_METIER
            return self._etat.value

        # Validé : commit de l'état effectif puis projection Weaviate (APRÈS COMMITE).
        self._etat = EtatIngestion.VALIDE
        await self._activite("committer_contrat", contrat_id)
        self._etat = EtatIngestion.COMMITE
        await self._activite("projeter_weaviate", tenant, contrat_id, markdown)
        return self._etat.value


def _est_terminal(exc: ActivityError) -> bool:
    """Vrai si l'échec d'activity est une décision métier terminale (non-retryable).

    `controle_et_av` lève une `ApplicationError(non_retryable=True)` pour
    `ControleRejete`/`MalwareDetecte` ; Temporal l'enveloppe dans une
    `ActivityError` dont la cause est une `ApplicationError` marquée non-retryable.
    """
    cause = exc.cause
    return isinstance(cause, ApplicationError) and bool(cause.non_retryable)
