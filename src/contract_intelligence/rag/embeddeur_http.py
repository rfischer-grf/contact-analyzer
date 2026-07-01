"""Embeddeur **HTTP** réel, OpenAI-compatible (ticket #51 ; BYO, spec §6).

Implémentation du `Protocol Embeddeur` qui appelle un endpoint d'embeddings
**OpenAI-compatible** (`POST {base_url}/embeddings`, payload `{model, input}`,
réponse `{"data": [{"embedding": [...]}, ...]}`). Cible : bge-m3 / e5 self-host
ou Mistral embed — tous exposables derrière ce contrat.

Garde-fou (§6) : embeddings **BYO et découplés du store** — cet embeddeur ne
connaît pas Weaviate ; il rend des vecteurs que la projection passe au store.

Import différé : `httpx` n'est importé QUE dans le corps de `vectoriser` — le
module reste importable sans `httpx`, et la conformité au Protocol se teste sans
réseau.
"""

from __future__ import annotations

# Timeout généreux : pipeline asynchrone, la latence n'a aucune importance (§2.2).
TIMEOUT_PAR_DEFAUT = 60.0


class EmbeddeurHTTP:
    """`Embeddeur` réel appelant un endpoint d'embeddings OpenAI-compatible (#51).

    `base_url` est la racine de l'API (ex. `https://api.scaleway.ai/v1`) ; on y
    appelle `POST /embeddings`. `dimension`, si fournie, sert au contrôle de
    cohérence des vecteurs renvoyés (et documente le modèle attendu).
    """

    def __init__(
        self,
        base_url: str,
        modele: str,
        api_key: str = "",
        *,
        dimension: int | None = None,
        timeout: float = TIMEOUT_PAR_DEFAUT,
    ) -> None:
        # On normalise la racine pour composer une URL propre côté requête.
        self._base_url = base_url.rstrip("/")
        self._modele = modele
        self._api_key = api_key
        self._dimension = dimension
        self._timeout = timeout

    def vectoriser(self, textes: list[str]) -> list[list[float]]:
        """Renvoie un vecteur par texte (ordre préservé). Import différé de `httpx`.

        Appelle l'endpoint en un seul aller-retour (batch `input`). Vérifie que le
        nombre de vecteurs correspond au nombre de textes (et la dimension si elle
        est connue) — un écart trahit une mauvaise configuration du modèle/endpoint.
        """
        if not textes:
            return []

        import httpx

        entetes = {"Content-Type": "application/json"}
        if self._api_key:
            entetes["Authorization"] = f"Bearer {self._api_key}"

        reponse = httpx.post(
            f"{self._base_url}/embeddings",
            json={"model": self._modele, "input": textes},
            headers=entetes,
            timeout=self._timeout,
        )
        reponse.raise_for_status()
        donnees = reponse.json().get("data", [])

        if len(donnees) != len(textes):
            raise ValueError(
                f"Embeddeur HTTP : {len(donnees)} vecteurs renvoyés pour {len(textes)} textes"
            )

        vecteurs: list[list[float]] = []
        # On réordonne par `index` si l'API le fournit (contrat OpenAI), sinon ordre brut.
        for rang, element in enumerate(sorted(donnees, key=lambda e: e.get("index", 0))):
            vecteur = [float(x) for x in element["embedding"]]
            if self._dimension is not None and len(vecteur) != self._dimension:
                raise ValueError(
                    f"Embeddeur HTTP : vecteur {rang} de dimension {len(vecteur)}, "
                    f"attendu {self._dimension}"
                )
            vecteurs.append(vecteur)
        return vecteurs
