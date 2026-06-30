"""Extracteur factice déterministe (epic #63) — sans LLM ni réseau.

Implémente `Extracteur` en renvoyant un `Contrat` plausible et **déterministe**,
chaque `Champ` portant valeur + confiance + `source=Provenance(...)`. Quelques
champs sont volontairement sous le seuil (cf. `seuils`) pour exercer la file de
revue HITL en test / démo offline.

Le vrai extracteur LLM est livré plus tard (cf. `base.Extracteur`, TODO #28/#29/#30).
"""

from __future__ import annotations

from datetime import date

from contract_intelligence.domain import (
    Champ,
    ClauseIndexation,
    Contrat,
    Indice,
    Partie,
    Preavis,
    Provenance,
    Signataire,
    UnitePreavis,
)


def _prov(page: int, extrait: str) -> Provenance:
    """Provenance synthétique (bbox plausible) pour un extrait de la pièce."""
    return Provenance(page=page, bbox=(0.1, 0.1, 0.9, 0.2), extrait=extrait)


class FakeExtracteur:
    """`Extracteur` factice : renvoie toujours le même `Contrat` plausible.

    Le contrat mêle des champs très confiants (≥ seuil) et quelques champs peu
    fiables (< seuil, dont des champs actionnables stricts à 0.9) pour que
    `champs_sous_seuil` produise une file de revue non vide.
    """

    def extraire(self, markdown: str) -> Contrat:  # noqa: ARG002 — fake déterministe
        fournisseur = Partie(
            raison_sociale=Champ[str](
                valeur="ACME Services SAS",
                confiance=0.97,
                source=_prov(1, "ACME Services SAS"),
            ),
            siren=Champ[str](
                valeur="552100554",
                confiance=0.95,
                source=_prov(1, "SIREN 552 100 554"),
            ),
            forme_juridique=Champ[str](
                valeur="SAS",
                confiance=0.93,
                source=_prov(1, "Société par actions simplifiée"),
            ),
        )
        client = Partie(
            raison_sociale=Champ[str](
                valeur="Groupe RF SA",
                confiance=0.96,
                source=_prov(1, "Groupe RF SA"),
            ),
            # Confiance basse : SIREN du client mal lu → doit partir en revue.
            siren=Champ[str](
                valeur="402360567",
                confiance=0.55,
                source=_prov(1, "SIREN 402 360 ???"),
            ),
        )
        signataires = [
            Signataire(
                nom=Champ[str](
                    valeur="Jean Dupont",
                    confiance=0.94,
                    source=_prov(8, "Jean Dupont, Directeur des achats"),
                ),
                qualite=Champ[str](
                    valeur="Directeur des achats",
                    confiance=0.91,
                    source=_prov(8, "Directeur des achats"),
                ),
            ),
        ]
        preavis = Preavis(
            delai=Champ[int](
                valeur=3,
                confiance=0.92,
                source=_prov(5, "préavis de trois (3) mois"),
            ),
            # Confiance basse sur l'unité (champ actionnable strict à 0.9) :
            # ambiguïté mois/jours → revue.
            unite=Champ[UnitePreavis](
                valeur=UnitePreavis.mois,
                confiance=0.7,
                source=_prov(5, "trois mois"),
            ),
        )
        indexation = ClauseIndexation(
            indice=Champ[Indice](
                valeur=Indice.syntec,
                confiance=0.9,
                source=_prov(6, "indice Syntec"),
            ),
            indice_base_valeur=Champ[float](
                valeur=128.4,
                confiance=0.88,
                source=_prov(6, "valeur de base 128,4"),
            ),
            bidirectionnelle=Champ[bool](
                valeur=True,
                confiance=0.85,
                source=_prov(6, "révision à la hausse comme à la baisse"),
            ),
        )
        return Contrat(
            fournisseur=fournisseur,
            client=client,
            signataires=signataires,
            objet=Champ[str](
                valeur="Prestations de maintenance applicative",
                confiance=0.9,
                source=_prov(1, "Objet : maintenance applicative"),
            ),
            date_effet=Champ[date](
                valeur=date(2024, 1, 1),
                confiance=0.95,
                source=_prov(2, "à compter du 1er janvier 2024"),
            ),
            # Confiance basse sur l'échéance (champ actionnable strict à 0.9) :
            # date partiellement illisible → revue.
            date_echeance=Champ[date](
                valeur=date(2026, 12, 31),
                confiance=0.6,
                source=_prov(2, "jusqu'au 31 décembre 20??"),
            ),
            duree_initiale_mois=Champ[int](
                valeur=36,
                confiance=0.93,
                source=_prov(2, "durée de trente-six (36) mois"),
            ),
            tacite_reconduction=Champ[bool](
                valeur=True,
                confiance=0.92,
                source=_prov(4, "renouvelé par tacite reconduction"),
            ),
            duree_reconduction_mois=Champ[int](
                valeur=12,
                confiance=0.9,
                source=_prov(4, "par périodes de douze (12) mois"),
            ),
            preavis=preavis,
            indexation=indexation,
            montant=Champ[float](
                valeur=120000.0,
                confiance=0.9,
                source=_prov(7, "montant annuel de 120 000 €"),
            ),
            devise=Champ[str](
                valeur="EUR",
                confiance=0.99,
                source=_prov(7, "€"),
            ),
        )
