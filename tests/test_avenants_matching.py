"""Tests du rapprochement fuzzy avenant→parent (spec §3.1, tickets #32/#33).

Couvre le scoring (SIREN exacts + similarité référence/objet) et la proposition
classée. Le garde-fou §7 (jamais d'auto-lien) est structurel : aucune API ici ne
crée de lien — `proposer_candidats` ne renvoie que des propositions.
"""

from __future__ import annotations

from contract_intelligence.avenants import (
    Candidat,
    PartiesRef,
    proposer_candidats,
    score_similarite,
)

# Avenant de référence pour les tests : SIREN renseignés, référence + objet.
AVENANT = PartiesRef(
    siren_fournisseur="123 456 789",
    siren_client="987 654 321",
    reference="CTR-2024-0042",
    objet="Maintenance applicative et hébergement",
)


def test_siren_identiques_reference_objet_proches_score_eleve() -> None:
    # Même fournisseur + même client (espaces différents) + textes très proches.
    parent = PartiesRef(
        siren_fournisseur="123456789",
        siren_client="987654321",
        reference="CTR-2024-0042",
        objet="Maintenance applicative et hebergement",
    )
    score = score_similarite(AVENANT, parent)
    assert score > 0.9

    proposes = proposer_candidats(AVENANT, {"parent-1": parent})
    assert len(proposes) == 1
    assert proposes[0].contrat_id == "parent-1"
    assert proposes[0].score == score


def test_siren_differents_sous_seuil_non_propose() -> None:
    # Parties totalement différentes, mais objet vaguement similaire : le signal
    # fort (SIREN) manque → score sous le seuil → non proposé.
    autre = PartiesRef(
        siren_fournisseur="111 111 111",
        siren_client="222 222 222",
        reference="DIVERS-9",
        objet="Maintenance applicative",
    )
    score = score_similarite(AVENANT, autre)
    assert score < 0.5
    assert proposer_candidats(AVENANT, {"autre": autre}) == []


def test_tri_par_score_decroissant() -> None:
    # Trois candidats de qualité décroissante, tous au-dessus du seuil.
    fort = PartiesRef(
        siren_fournisseur="123456789",
        siren_client="987654321",
        reference="CTR-2024-0042",
        objet="Maintenance applicative et hébergement",
    )
    moyen = PartiesRef(
        siren_fournisseur="123456789",
        siren_client="987654321",
        reference="CTR-2024-0099",
        objet="Prestation différente",
    )
    faible = PartiesRef(
        siren_fournisseur="123456789",
        siren_client="000 000 000",
        reference="CTR-2024-0042",
        objet="Maintenance applicative et hébergement",
    )
    proposes = proposer_candidats(
        AVENANT,
        {"moyen": moyen, "fort": fort, "faible": faible},
    )
    assert [c.contrat_id for c in proposes] == ["fort", "moyen", "faible"]
    scores = [c.score for c in proposes]
    assert scores == sorted(scores, reverse=True)


def test_aucun_candidat_au_dessus_du_seuil_liste_vide() -> None:
    candidats = {
        "x": PartiesRef(siren_fournisseur="000000000", siren_client="000000001"),
        "y": PartiesRef(reference="SANS-RAPPORT", objet="Autre chose"),
    }
    assert proposer_candidats(AVENANT, candidats) == []


def test_details_ventilation_et_type() -> None:
    parent = PartiesRef(
        siren_fournisseur="123456789",
        siren_client="987654321",
        reference="CTR-2024-0042",
        objet="Maintenance applicative et hébergement",
    )
    [candidat] = proposer_candidats(AVENANT, {"p": parent})
    assert isinstance(candidat, Candidat)
    # SIREN exacts → poids pleins ; somme des composantes == score.
    assert candidat.details["siren_fournisseur"] == 0.25
    assert candidat.details["siren_client"] == 0.25
    assert abs(sum(candidat.details.values()) - candidat.score) < 1e-9


def test_siren_absents_ne_matchent_pas() -> None:
    # Deux SIREN à None ne doivent jamais compter comme identiques.
    avenant = PartiesRef(reference="CTR-2024-0042", objet="Maintenance applicative")
    candidat = PartiesRef(reference="CTR-2024-0042", objet="Maintenance applicative")
    details_score = score_similarite(avenant, candidat)
    # Seuls référence + objet contribuent (max 0,5) → strictement sous 0,5+ε.
    assert details_score <= 0.5
