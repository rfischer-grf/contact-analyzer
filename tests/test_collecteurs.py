"""Tests des collecteurs d'indices (#39 INSEE BDM, #40 Syntec).

httpx est MOCKÉ (monkeypatch `httpx.get`) : faux XML SDMX / faux HTML Syntec, aucun
réseau réel. On vérifie l'upsert dans `serie_indice` (SQLite) et le nb de points.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy import create_engine, select

from contract_intelligence.db import Base, SerieIndice, make_sessionmaker
from contract_intelligence.db.series import dernier_indice_a_date
from contract_intelligence.indexation import collecteurs

# --- Faux corps de réponse (SDMX GenericData ILAT + page Syntec) ---

# Message SDMX 2.1 GenericData minimal : 2 trimestres ILAT (2024-Q1, 2024-Q2).
XML_SDMX = """<?xml version="1.0" encoding="UTF-8"?>
<message:GenericData
    xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
    xmlns:generic="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic">
  <message:DataSet>
    <generic:Series>
      <generic:Obs>
        <generic:ObsDimension value="2024-Q1"/>
        <generic:ObsValue value="130.5"/>
      </generic:Obs>
      <generic:Obs>
        <generic:ObsDimension value="2024-Q2"/>
        <generic:ObsValue value="131.2"/>
      </generic:Obs>
    </generic:Series>
  </message:DataSet>
</message:GenericData>
"""

# Page Syntec simplifiée : un tableau mois → valeur, décimale FR (virgule).
HTML_SYNTEC = """<!doctype html><html><body>
<h1>Indice Syntec</h1>
<table>
  <tr><th>Mois</th><th>Indice</th></tr>
  <tr><td>mars 2024</td><td>304,2</td></tr>
  <tr><td>avril 2024</td><td>305,1</td></tr>
  <tr><td>mai 2024</td><td>306,7</td></tr>
</table>
</body></html>
"""


class _FausseReponse:
    """Double minimal de `httpx.Response` (texte + raise_for_status sans réseau)."""

    def __init__(self, texte: str, code: int = 200) -> None:
        self.text = texte
        self.status_code = code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "erreur",
                request=httpx.Request("GET", "http://test"),
                response=None,  # type: ignore[arg-type]
            )


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return make_sessionmaker(engine)


def test_collecter_insee_upsert(factory, monkeypatch) -> None:
    appels: list[tuple[str, object]] = []

    def faux_get(url: str, **kwargs: object) -> _FausseReponse:
        appels.append((url, kwargs.get("timeout")))
        return _FausseReponse(XML_SDMX)

    monkeypatch.setattr(collecteurs.httpx, "get", faux_get)

    with factory() as s:
        n = collecteurs.collecter_insee(s, idbank="001515333", indice="ilat")
        s.commit()

    assert n == 2
    # URL souveraine INSEE BDM, dataflow + idbank dans le chemin ; timeout transmis.
    assert appels[0] == ("https://bdm.insee.fr/series/sdmx/data/ILC-ILAT-ICC/001515333", 30.0)

    with factory() as s:
        lignes = (
            s.execute(
                select(SerieIndice)
                .where(SerieIndice.indice == "ilat")
                .order_by(SerieIndice.periode)
            )
            .scalars()
            .all()
        )
        # Trimestriel normalisé en fin de trimestre (YYYY-MM) + source 'insee'.
        assert [(ligne.periode, float(ligne.valeur), ligne.source) for ligne in lignes] == [
            ("2024-03", 130.5, "insee"),
            ("2024-06", 131.2, "insee"),
        ]


def test_collecter_insee_aucune_obs(factory, monkeypatch) -> None:
    vide = (
        '<?xml version="1.0"?>'
        "<message:GenericData "
        'xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">'
        "<message:DataSet/></message:GenericData>"
    )
    monkeypatch.setattr(collecteurs.httpx, "get", lambda url, **kw: _FausseReponse(vide))

    with factory() as s:
        assert collecteurs.collecter_insee(s, idbank="x", indice="ilc") == 0


def test_collecter_syntec_derniere_valeur(factory, monkeypatch) -> None:
    appels: list[str] = []

    def faux_get(url: str, **kwargs: object) -> _FausseReponse:
        appels.append(url)
        return _FausseReponse(HTML_SYNTEC)

    monkeypatch.setattr(collecteurs.httpx, "get", faux_get)

    with factory() as s:
        n = collecteurs.collecter_syntec(s)
        s.commit()

    assert n == 1
    assert appels == [collecteurs.SYNTEC_URL]

    with factory() as s:
        # On retient la période la plus récente publiée (mai 2024 → 306,7), source 'syntec'.
        ligne = s.execute(select(SerieIndice).where(SerieIndice.indice == "syntec")).scalar_one()
        assert (ligne.periode, float(ligne.valeur), ligne.source) == ("2024-05", 306.7, "syntec")
        assert dernier_indice_a_date(s, "syntec", date(2024, 6, 1)) == ("2024-05", 306.7)


def test_collecter_syntec_rien_dexploitable(factory, monkeypatch) -> None:
    monkeypatch.setattr(
        collecteurs.httpx,
        "get",
        lambda url, **kw: _FausseReponse("<html><body>aucune donnée</body></html>"),
    )
    with factory() as s:
        assert collecteurs.collecter_syntec(s) == 0


def test_collecteurs_propagent_erreur_http(factory, monkeypatch) -> None:
    monkeypatch.setattr(
        collecteurs.httpx, "get", lambda url, **kw: _FausseReponse("erreur", code=500)
    )
    with factory() as s:
        with pytest.raises(httpx.HTTPStatusError):
            collecteurs.collecter_insee(s, idbank="x", indice="ilat")
        with pytest.raises(httpx.HTTPStatusError):
            collecteurs.collecter_syntec(s)
