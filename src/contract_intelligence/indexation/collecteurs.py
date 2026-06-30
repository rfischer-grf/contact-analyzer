"""Collecte des séries d'indices (spec §2.5).

- **INSEE BDM** (ILAT/ILC/ICC + INSEE) : API SDMX 2.1 REST, par `idbank` (#39).
- **Syntec** : pas d'API → scrape mensuel de syntec.fr (#40).
- **Dev** : `charger_fixtures` injecte des valeurs figées (substitution §5).

Réseau via `httpx` (déjà installé). Les appels réseau ne partent jamais pendant
les tests (httpx mocké). Le coefficient de raccord Syntec s'applique au calcul de
révision, pas à la collecte.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import httpx
from sqlalchemy.orm import Session

from ..db.series import upsert_serie

# Points d'accès des collecteurs réels.
INSEE_BDM_BASE_URL = "https://bdm.insee.fr/series/sdmx"
INSEE_BDM_DATAFLOW = "ILC-ILAT-ICC"
SYNTEC_URL = "https://syntec.fr/indice-syntec/"

# Délai réseau par défaut (s) : collecte asynchrone, la latence est sans enjeu (§2.2).
_TIMEOUT_S = 30.0

# Espaces de noms SDMX 2.1 (message GenericData de l'INSEE BDM).
_NS_SDMX = {
    "message": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
    "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
}

# Dernier mois de chaque trimestre (les séries ILAT/ILC/ICC sont trimestrielles).
_FIN_DE_TRIMESTRE = {"1": "03", "2": "06", "3": "09", "4": "12"}


def charger_fixtures(session: Session, chemin: str | Path) -> int:
    """Charge des séries figées `{indice: {periode: valeur}}`. Renvoie le nb de points."""
    data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    n = 0
    for indice, serie in data.items():
        if indice.startswith("_") or not isinstance(serie, dict):
            continue  # clés de métadonnées (ex. "_comment")
        for periode, valeur in serie.items():
            upsert_serie(
                session, indice=indice, periode=periode, valeur=float(valeur), source="fixture"
            )
            n += 1
    return n


def _normaliser_periode(brut: str) -> str | None:
    """Normalise une période SDMX en `YYYY-MM` (convention `serie_indice`).

    - `YYYY-MM` : conservé tel quel.
    - `YYYY-Qn` (trimestriel ILAT/ILC/ICC) : ramené au dernier mois du trimestre,
      cohérent avec la comparaison lexicographique de `dernier_indice_a_date`.
    - Tout autre format : ignoré (None) plutôt que stocké de travers.
    """
    brut = brut.strip()
    if re.fullmatch(r"\d{4}-\d{2}", brut):
        return brut
    trimestre = re.fullmatch(r"(\d{4})-?Q([1-4])", brut)
    if trimestre is not None:
        annee, num = trimestre.group(1), trimestre.group(2)
        return f"{annee}-{_FIN_DE_TRIMESTRE[num]}"
    return None


def collecter_insee(session: Session, idbank: str, indice: str) -> int:
    """Collecte INSEE BDM (SDMX 2.1) par `idbank` → `serie_indice` (#39).

    Interroge le dataflow `ILC-ILAT-ICC` par `idbank` (clé déterministe), parse le
    message `GenericData` (stdlib `xml.etree.ElementTree`) et upsert chaque
    observation `(periode, valeur)`. Renvoie le nombre de points enregistrés.
    Déterministe et souverain (API publique INSEE, gratuite).
    """
    url = f"{INSEE_BDM_BASE_URL}/data/{INSEE_BDM_DATAFLOW}/{idbank}"
    reponse = httpx.get(url, timeout=_TIMEOUT_S)
    reponse.raise_for_status()

    racine = ElementTree.fromstring(reponse.text)
    n = 0
    for obs in racine.iter(f"{{{_NS_SDMX['generic']}}}Obs"):
        dimension = obs.find(f"{{{_NS_SDMX['generic']}}}ObsDimension")
        valeur = obs.find(f"{{{_NS_SDMX['generic']}}}ObsValue")
        if dimension is None or valeur is None:
            continue
        periode = _normaliser_periode(dimension.get("value", ""))
        valeur_brute = valeur.get("value")
        if periode is None or valeur_brute is None:
            continue
        try:
            valeur_num = float(valeur_brute)
        except ValueError:
            continue
        upsert_serie(session, indice=indice, periode=periode, valeur=valeur_num, source="insee")
        n += 1
    return n


class _ExtracteurSyntec(HTMLParser):
    """Extrait les couples (période, valeur) du tableau mensuel de syntec.fr.

    La page publie l'indice mois par mois ; on accumule le texte des cellules et on
    reconstitue les couples « <mois année> → <valeur> » par une expression régulière
    sur le texte aplati (robuste aux variations de balisage du tableau).
    """

    def __init__(self) -> None:
        super().__init__()
        self._morceaux: list[str] = []

    def handle_data(self, data: str) -> None:
        texte = data.strip()
        if texte:
            self._morceaux.append(texte)

    @property
    def texte(self) -> str:
        return " ".join(self._morceaux)


_MOIS_FR = {
    "janvier": "01",
    "février": "02",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
    "decembre": "12",
}

# « mai 2024 ... 145,3 » → (mois, année, valeur). Décimale FR (virgule) ou point.
_MOTIF_SYNTEC = re.compile(
    r"(?P<mois>"
    + "|".join(_MOIS_FR)
    + r")\s+(?P<annee>\d{4})\D{0,40}?(?P<valeur>\d{2,4}(?:[.,]\d+)?)",
    re.IGNORECASE,
)


def collecter_syntec(session: Session) -> int:
    """Scrape la valeur mensuelle Syntec depuis syntec.fr → `serie_indice` (#40).

    Pas d'API INSEE pour Syntec (publié par la Fédération Syntec) : on récupère la
    page, on aplatit le tableau via `html.parser` (stdlib) et on retient la période
    publiée la plus récente. Le coefficient de raccord 0,97975 (actes < août 2022)
    est appliqué côté moteur de révision, jamais ici. Renvoie le nombre de points
    enregistrés (0 si rien d'exploitable, 1 sinon).
    """
    reponse = httpx.get(SYNTEC_URL, timeout=_TIMEOUT_S)
    reponse.raise_for_status()

    extracteur = _ExtracteurSyntec()
    extracteur.feed(reponse.text)

    dernier: tuple[str, float] | None = None
    for correspondance in _MOTIF_SYNTEC.finditer(extracteur.texte):
        mois = _MOIS_FR[correspondance.group("mois").lower()]
        periode = f"{correspondance.group('annee')}-{mois}"
        valeur = float(correspondance.group("valeur").replace(",", "."))
        # On garde la période la plus récente (ordre lexicographique = chronologique).
        if dernier is None or periode > dernier[0]:
            dernier = (periode, valeur)

    if dernier is None:
        return 0
    upsert_serie(session, indice="syntec", periode=dernier[0], valeur=dernier[1], source="syntec")
    return 1
