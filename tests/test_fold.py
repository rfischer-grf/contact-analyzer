"""Tests du fold d'état effectif (§3.1) — pur, sans base de données."""

from __future__ import annotations

from datetime import date

from contract_intelligence.domain import (
    Champ,
    ClauseIndexation,
    Contrat,
    Indice,
    Partie,
    PieceVersee,
    Preavis,
    UnitePreavis,
    fold_etat_effectif,
)


def _partie(raison: str, siren: str | None = None) -> Partie:
    return Partie(
        raison_sociale=Champ[str](valeur=raison, confiance=1.0),
        siren=Champ[str](valeur=siren, confiance=1.0) if siren else None,
    )


def _origine() -> Contrat:
    return Contrat(
        fournisseur=_partie("Fournisseur", "111222333"),
        client=_partie("Client"),
        date_echeance=Champ[date](valeur=date(2025, 12, 31), confiance=0.9),
        preavis=Preavis(
            delai=Champ[int](valeur=3, confiance=0.9),
            unite=Champ[UnitePreavis](valeur=UnitePreavis.mois, confiance=0.9),
        ),
        montant=Champ[float](valeur=1000.0, confiance=0.9),
        # Clause déclarée unidirectionnelle (hausse seule) à l'extraction.
        indexation=ClauseIndexation(
            indice=Champ[Indice](valeur=Indice.syntec, confiance=0.9),
            bidirectionnelle=Champ[bool](valeur=False, confiance=0.9),
        ),
    )


def test_fold_contrat_seul() -> None:
    etat = fold_etat_effectif([PieceVersee(date(2023, 1, 1), _origine())])
    assert etat.date_echeance == date(2025, 12, 31)
    assert etat.date_limite_denonciation == date(2025, 9, 30)  # − 3 mois
    assert etat.indice == Indice.syntec
    # §7 : la clause unidirectionnelle est réputée non écrite → bidirectionnel forcé.
    assert etat.bidirectionnelle is True
    assert etat.date_acte_reference == date(2023, 1, 1)


def test_fold_avenant_repousse_echeance_et_preavis() -> None:
    avenant = Contrat(
        fournisseur=_partie("Fournisseur"),
        client=_partie("Client"),
        date_echeance=Champ[date](valeur=date(2027, 6, 30), confiance=0.9),
        preavis=Preavis(
            delai=Champ[int](valeur=60, confiance=0.9),
            unite=Champ[UnitePreavis](valeur=UnitePreavis.jours, confiance=0.9),
        ),
    )
    etat = fold_etat_effectif(
        [
            PieceVersee(date(2024, 6, 1), avenant, numero_avenant=1),
            PieceVersee(date(2023, 1, 1), _origine()),  # ordre volontairement inversé
        ]
    )
    # L'avenant (signé après) prime ; le fold trie par date de signature.
    assert etat.date_echeance == date(2027, 6, 30)
    assert etat.preavis_delai == 60
    assert etat.preavis_unite == UnitePreavis.jours
    assert etat.date_limite_denonciation == date(2027, 5, 1)  # 30/06 − 60 j
    # Montant non modifié par l'avenant → conservé depuis l'origine.
    assert etat.montant == 1000.0


def test_fold_avenant_tarifaire_reancre_la_reference() -> None:
    avenant_prix = Contrat(
        fournisseur=_partie("Fournisseur"),
        client=_partie("Client"),
        montant=Champ[float](valeur=1200.0, confiance=0.9),
    )
    etat = fold_etat_effectif(
        [
            PieceVersee(date(2023, 1, 1), _origine()),
            PieceVersee(date(2024, 9, 15), avenant_prix, numero_avenant=2),
        ]
    )
    assert etat.montant == 1200.0
    # Re-ancrage tarifaire : date de l'acte = signature du dernier avenant de prix.
    assert etat.date_acte_reference == date(2024, 9, 15)
