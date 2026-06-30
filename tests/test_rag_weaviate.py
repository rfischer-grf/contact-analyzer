"""Tests du vector store Weaviate réel + embeddeur HTTP + fabriques (#48, #49, #51).

Garde-fous vérifiés :
- `WeaviateVectorStore` / `EmbeddeurHTTP` sont **importables sans** `weaviate` ni
  `httpx` (import différé : le client n'est touché que dans le corps des méthodes).
- les deux **conforment aux Protocols** `VectorStore` / `Embeddeur` (mêmes méthodes
  et signatures — les Protocols ne sont pas `runtime_checkable`, on vérifie
  structurellement).
- `store_par_defaut` / `embeddeur_par_defaut` : **sans config → Fakes** (testable,
  sans réseau) ; **avec config → impl. réelle** (sans déclencher de connexion).
- la conformité du `FakeVectorStore` / `FakeEmbeddeur` reste couverte.

Aucun test ici n'ouvre de connexion réseau : la logique HTTP réelle est exercée
en injectant un faux module `httpx` dans `sys.modules`.
"""

from __future__ import annotations

import inspect
import sys
import types
from typing import Any

import pytest

from contract_intelligence.config import Settings
from contract_intelligence.rag import (
    Chunk,
    Embeddeur,
    EmbeddeurHTTP,
    FakeEmbeddeur,
    FakeVectorStore,
    VectorStore,
    WeaviateVectorStore,
    embeddeur_par_defaut,
    store_par_defaut,
)

# --- Conformité structurelle aux Protocols (non runtime_checkable) -------------


def _signatures_compatibles(impl: type, protocole: type, methode: str) -> bool:
    """Vrai si `impl.methode` existe et a les mêmes noms de paramètres que le Protocol."""
    if not hasattr(impl, methode):
        return False
    params_impl = list(inspect.signature(getattr(impl, methode)).parameters)
    params_proto = list(inspect.signature(getattr(protocole, methode)).parameters)
    return params_impl == params_proto


def test_weaviate_store_conforme_au_protocol() -> None:
    for methode in ("upsert", "supprimer", "rechercher"):
        assert _signatures_compatibles(WeaviateVectorStore, VectorStore, methode), methode


def test_embeddeur_http_conforme_au_protocol() -> None:
    assert _signatures_compatibles(EmbeddeurHTTP, Embeddeur, "vectoriser")


def test_construire_impls_reelles_ne_touche_pas_le_reseau() -> None:
    # Construire ne doit ni importer le client, ni se connecter.
    store = WeaviateVectorStore(url="http://weaviate:8080", api_key="k")
    embeddeur = EmbeddeurHTTP(base_url="http://emb/v1", modele="bge-m3")
    assert isinstance(store, WeaviateVectorStore)
    assert isinstance(embeddeur, EmbeddeurHTTP)


# --- Import différé : modules importables sans les dépendances réseau ----------


def test_weaviate_importable_sans_weaviate(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simule l'absence du client : tout import de `weaviate` doit échouer...
    monkeypatch.setitem(sys.modules, "weaviate", None)
    # ...sans empêcher d'importer le module ni de construire le store.
    import importlib

    module = importlib.import_module("contract_intelligence.rag.weaviate_store")
    store = module.WeaviateVectorStore(url="http://weaviate:8080")
    # La connexion (qui importerait `weaviate`) n'a lieu qu'à l'usage.
    with pytest.raises(ImportError):
        store._connecter()


def test_embeddeur_http_importable_sans_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "httpx", None)
    import importlib

    module = importlib.import_module("contract_intelligence.rag.embeddeur_http")
    embeddeur = module.EmbeddeurHTTP(base_url="http://emb/v1", modele="bge-m3")
    # vectoriser([]) court-circuite avant l'import de httpx (aucun appel réseau).
    assert embeddeur.vectoriser([]) == []
    # Dès qu'il y a des textes, l'import de httpx (absent) échoue.
    with pytest.raises(ImportError):
        embeddeur.vectoriser(["x"])


# --- Logique HTTP réelle exercée via un faux module httpx ----------------------


class _FausseReponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.appels_raise = 0

    def raise_for_status(self) -> None:
        self.appels_raise += 1

    def json(self) -> dict[str, Any]:
        return self._payload


def _injecter_httpx(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> dict[str, Any]:
    """Installe un faux `httpx.post` qui capture l'appel et renvoie `payload`."""
    capture: dict[str, Any] = {}

    def fausse_post(url: str, **kwargs: Any) -> _FausseReponse:
        capture["url"] = url
        capture["json"] = kwargs.get("json")
        capture["headers"] = kwargs.get("headers")
        capture["timeout"] = kwargs.get("timeout")
        return _FausseReponse(payload)

    faux_httpx = types.ModuleType("httpx")
    faux_httpx.post = fausse_post  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", faux_httpx)
    return capture


def test_embeddeur_http_appelle_endpoint_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]
    }
    capture = _injecter_httpx(monkeypatch, payload)
    embeddeur = EmbeddeurHTTP(base_url="http://emb/v1/", modele="bge-m3", api_key="secret")

    vecteurs = embeddeur.vectoriser(["a", "b"])

    assert vecteurs == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    # URL composée proprement (racine normalisée, suffixe /embeddings).
    assert capture["url"] == "http://emb/v1/embeddings"
    # Contrat OpenAI : {model, input}.
    assert capture["json"] == {"model": "bge-m3", "input": ["a", "b"]}
    # Clé API → Authorization Bearer.
    assert capture["headers"]["Authorization"] == "Bearer secret"


def test_embeddeur_http_reordonne_par_index(monkeypatch: pytest.MonkeyPatch) -> None:
    # L'API peut renvoyer les éléments dans le désordre → on réordonne par `index`.
    payload = {
        "data": [
            {"index": 1, "embedding": [9.0]},
            {"index": 0, "embedding": [1.0]},
        ]
    }
    _injecter_httpx(monkeypatch, payload)
    embeddeur = EmbeddeurHTTP(base_url="http://emb/v1", modele="m")
    assert embeddeur.vectoriser(["x", "y"]) == [[1.0], [9.0]]


def test_embeddeur_http_sans_cle_pas_d_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = _injecter_httpx(monkeypatch, {"data": [{"index": 0, "embedding": [1.0]}]})
    EmbeddeurHTTP(base_url="http://emb/v1", modele="m").vectoriser(["x"])
    assert "Authorization" not in capture["headers"]


def test_embeddeur_http_rejette_nb_vecteurs_incoherent(monkeypatch: pytest.MonkeyPatch) -> None:
    _injecter_httpx(monkeypatch, {"data": [{"index": 0, "embedding": [1.0]}]})
    embeddeur = EmbeddeurHTTP(base_url="http://emb/v1", modele="m")
    with pytest.raises(ValueError, match="vecteurs renvoyés"):
        embeddeur.vectoriser(["x", "y"])  # 1 vecteur pour 2 textes


def test_embeddeur_http_rejette_mauvaise_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    _injecter_httpx(monkeypatch, {"data": [{"index": 0, "embedding": [1.0, 2.0]}]})
    embeddeur = EmbeddeurHTTP(base_url="http://emb/v1", modele="m", dimension=3)
    with pytest.raises(ValueError, match="dimension"):
        embeddeur.vectoriser(["x"])


# --- Fabriques par défaut ------------------------------------------------------


def test_store_par_defaut_sans_config_renvoie_fake() -> None:
    settings = Settings(weaviate_url=None)
    store = store_par_defaut(settings)
    assert isinstance(store, FakeVectorStore)


def test_store_par_defaut_avec_config_renvoie_weaviate() -> None:
    settings = Settings(weaviate_url="http://weaviate:8080", weaviate_api_key="k")
    store = store_par_defaut(settings)
    # Impl. réelle, mais aucune connexion déclenchée par la construction.
    assert isinstance(store, WeaviateVectorStore)


def test_embeddeur_par_defaut_sans_config_renvoie_fake() -> None:
    settings = Settings(embeddings_base_url=None, embeddings_dimension=64)
    embeddeur = embeddeur_par_defaut(settings)
    assert isinstance(embeddeur, FakeEmbeddeur)
    # La dimension du Fake suit la configuration.
    assert len(embeddeur.vectoriser(["x"])[0]) == 64


def test_embeddeur_par_defaut_avec_config_renvoie_http() -> None:
    settings = Settings(embeddings_base_url="http://emb/v1", embeddings_modele="bge-m3")
    embeddeur = embeddeur_par_defaut(settings)
    assert isinstance(embeddeur, EmbeddeurHTTP)


# --- Couverture conservée des Fakes -------------------------------------------


def _chunk_minimal(contrat_id: str, tenant: str) -> Chunk:
    """Construit un `Chunk` minimal vectorisé pour les tests de Fake."""
    return Chunk(
        contrat_id=contrat_id,
        tenant=tenant,
        type_clause="Article 1",
        texte="texte",
        metadata={"contrat_id": contrat_id, "tenant": tenant},
        vecteur=[1.0, 0.0, 0.0, 0.0],
    )


def test_fake_store_upsert_delete_then_insert_idempotent() -> None:
    store = FakeVectorStore()
    chunk = _chunk_minimal("c1", "acme")
    store.upsert("acme", "c1", [chunk, chunk])
    store.upsert("acme", "c1", [chunk])  # réécriture → pas de doublon
    assert store.contrat_ids("acme") == {"c1"}
    assert len(store.rechercher("acme", [1.0] * 4, k=10)) == 1


def test_fake_store_isole_tenants() -> None:
    store = FakeVectorStore()
    store.upsert("acme", "c1", [_chunk_minimal("c1", "acme")])
    store.upsert("globex", "c2", [_chunk_minimal("c2", "globex")])
    assert store.contrat_ids("acme") == {"c1"}
    assert store.contrat_ids("globex") == {"c2"}
    # acme ne voit jamais un chunk de globex.
    assert all(c.tenant == "acme" for c in store.rechercher("acme", [1.0] * 4, k=10))


def test_fake_embeddeur_deterministe_et_dimensionne() -> None:
    embeddeur = FakeEmbeddeur(dimension=8)
    v1 = embeddeur.vectoriser(["bonjour"])[0]
    v2 = embeddeur.vectoriser(["bonjour"])[0]
    assert v1 == v2  # déterministe
    assert len(v1) == 8
    assert all(0.0 <= x < 1.0 for x in v1)  # composantes bornées
