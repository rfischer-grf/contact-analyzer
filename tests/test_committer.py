"""Test du committer() persistant sur SQLite (fold → état effectif + audit)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, select

from contract_intelligence.db import (
    Base,
    Contrat,
    Document,
    EvenementAudit,
    committer,
    make_sessionmaker,
)
from contract_intelligence.domain import (
    Champ,
    ClauseIndexation,
    Indice,
    Partie,
    Preavis,
    UnitePreavis,
)
from contract_intelligence.domain import Contrat as ContratExtrait


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def _origine() -> dict:
    return ContratExtrait(
        fournisseur=Partie(
            raison_sociale=Champ[str](valeur="F", confiance=1.0),
            siren=Champ[str](valeur="111222333", confiance=1.0),
        ),
        client=Partie(raison_sociale=Champ[str](valeur="C", confiance=1.0)),
        date_echeance=Champ[date](valeur=date(2025, 12, 31), confiance=0.9),
        preavis=Preavis(
            delai=Champ[int](valeur=3, confiance=0.9),
            unite=Champ[UnitePreavis](valeur=UnitePreavis.mois, confiance=0.9),
        ),
        montant=Champ[float](valeur=1000.0, confiance=0.9),
        indexation=ClauseIndexation(
            indice=Champ[Indice](valeur=Indice.syntec, confiance=0.9),
            bidirectionnelle=Champ[bool](valeur=False, confiance=0.9),
        ),
    ).model_dump(mode="json")


def _avenant() -> dict:
    return ContratExtrait(
        fournisseur=Partie(raison_sociale=Champ[str](valeur="F", confiance=1.0)),
        client=Partie(raison_sociale=Champ[str](valeur="C", confiance=1.0)),
        date_echeance=Champ[date](valeur=date(2027, 6, 30), confiance=0.9),
        preavis=Preavis(
            delai=Champ[int](valeur=60, confiance=0.9),
            unite=Champ[UnitePreavis](valeur=UnitePreavis.jours, confiance=0.9),
        ),
    ).model_dump(mode="json")


def test_committer_recalcule_etat_effectif(factory) -> None:
    cid = uuid.uuid4()
    with factory() as s:  # type: Session
        s.add(Contrat(id=cid, tenant="acme"))
        s.add(
            Document(
                tenant="acme",
                sha256="a" * 64,
                cle_s3=f"acme/{'a' * 64}",
                date_signature=date(2023, 1, 1),
                contrat_id=cid,
                extraction=_origine(),
            )
        )
        s.add(
            Document(
                tenant="acme",
                sha256="b" * 64,
                cle_s3=f"acme/{'b' * 64}",
                numero_avenant=1,
                date_signature=date(2024, 6, 1),
                contrat_id=cid,
                extraction=_avenant(),
            )
        )
        s.commit()

    with factory() as s:
        contrat = committer(s, cid, acteur="alice")
        s.commit()

        assert contrat.date_echeance == date(2027, 6, 30)
        assert contrat.preavis_delai == 60
        assert contrat.preavis_unite == "jours"
        assert contrat.date_limite_denonciation == date(2027, 5, 1)
        assert contrat.indice == "syntec"
        assert contrat.montant == 1000.0
        # §7 : bidirectionnel forcé malgré l'extraction (hausse seule).
        assert contrat.bidirectionnelle is True

        evenements = (
            s.execute(select(EvenementAudit).where(EvenementAudit.objet_id == str(cid)))
            .scalars()
            .all()
        )
        assert len(evenements) == 1
        assert evenements[0].type_evenement == "COMMITE"
