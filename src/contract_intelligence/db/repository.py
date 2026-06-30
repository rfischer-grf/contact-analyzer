"""Opérations de persistance — notamment `committer()` (spec §2, §3.1).

`committer()` rejoue la chaîne de documents d'un contrat, réécrit l'état effectif
et recalcule `date_limite_denonciation` → le job d'alerte quotidien se corrige seul
(aucun timer à reprogrammer). Idempotent : rejouer donne le même état.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..domain import Contrat as ContratExtrait
from ..domain import PieceVersee, fold_etat_effectif
from .models import Contrat, EvenementAudit


def committer(session: Session, contrat_id: uuid.UUID, acteur: str | None = None) -> Contrat:
    """Recalcule et persiste l'état effectif du contrat ; consigne un évènement d'audit."""
    contrat = session.get(Contrat, contrat_id)
    if contrat is None:
        raise ValueError(f"Contrat introuvable : {contrat_id}")

    pieces: list[PieceVersee] = []
    for doc in contrat.documents:  # déjà ordonnés par date_signature
        if not doc.extraction:
            continue
        pieces.append(
            PieceVersee(
                date_signature=doc.date_signature,
                contrat=ContratExtrait.model_validate(doc.extraction),
                numero_avenant=doc.numero_avenant,
            )
        )

    etat = fold_etat_effectif(pieces)

    contrat.fournisseur_siren = etat.fournisseur_siren
    contrat.client_siren = etat.client_siren
    contrat.objet = etat.objet
    contrat.date_effet = etat.date_effet
    contrat.date_echeance = etat.date_echeance
    contrat.date_limite_denonciation = etat.date_limite_denonciation
    contrat.duree_initiale_mois = etat.duree_initiale_mois
    contrat.tacite_reconduction = etat.tacite_reconduction
    contrat.preavis_delai = etat.preavis_delai
    contrat.preavis_unite = etat.preavis_unite.value if etat.preavis_unite else None
    contrat.indice = etat.indice.value if etat.indice else None
    contrat.indice_base_valeur = etat.indice_base_valeur
    contrat.indice_base_periode = etat.indice_base_periode
    contrat.date_acte_reference = etat.date_acte_reference
    contrat.montant = etat.montant
    contrat.devise = etat.devise
    contrat.bidirectionnelle = etat.bidirectionnelle

    session.add(
        EvenementAudit(
            tenant=contrat.tenant,
            acteur=acteur,
            type_evenement="COMMITE",
            objet_type="contrat",
            objet_id=str(contrat.id),
            payload={
                "date_limite_denonciation": (
                    etat.date_limite_denonciation.isoformat()
                    if etat.date_limite_denonciation
                    else None
                ),
                "nb_documents": len(pieces),
            },
        )
    )
    session.flush()
    return contrat
