"""Vector store **Weaviate** réel (ticket #48 ; multi-tenancy natif #49, spec §6).

Implémentation du `Protocol VectorStore` adossée au client `weaviate-client` v4.

Garde-fous (§6, §7) appliqués ici :
- Weaviate est le **seul** vector store (jamais pgvector). Postgres = source de
  vérité, Weaviate = index dérivé.
- **Multi-tenancy natif** : la collection est créée avec le multi-tenancy activé,
  et toute opération est **bornée au tenant** (`collection.with_tenant(tenant)`).
  Isolation physique + purge tenant propre (RGPD / réversibilité, §6). Le tenant
  est **injecté côté serveur**, jamais fourni par le client.
- **delete-then-insert par `contrat_id`** dans `upsert` → idempotent (gère les
  avenants qui réécrivent l'état effectif). Appelée **uniquement après COMMITE**
  par l'activity de projection de la saga.

Import différé : `weaviate` (dépendance de l'extra `rag`) n'est importé QUE dans
le corps des méthodes — le module reste importable sans le client installé, et
les tests vérifient la conformité au Protocol sans dépendance réseau.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .store import Chunk

if TYPE_CHECKING:  # uniquement pour le typage : aucun import au chargement
    from weaviate import WeaviateClient
    from weaviate.collections import Collection

# Nom de la collection (classe Weaviate) hébergeant les chunks de clauses.
NOM_COLLECTION = "ChunkClause"


class WeaviateVectorStore:
    """`VectorStore` réel sur Weaviate v4, multi-tenant natif (#48, #49).

    Le client est connecté paresseusement à la première opération (puis mémoïsé),
    de sorte que construire le store ne déclenche aucune connexion réseau ni import
    de `weaviate`. La collection est créée si absente, avec le multi-tenancy activé.
    """

    def __init__(
        self,
        url: str,
        api_key: str = "",
        *,
        nom_collection: str = NOM_COLLECTION,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._nom_collection = nom_collection
        # Mémoïsation : le client v4 est lourd (ouvre gRPC + HTTP) → un seul.
        self._client: WeaviateClient | None = None

    # --- Connexion & schéma (import différé de `weaviate`) ---

    def _connecter(self) -> WeaviateClient:
        """Connecte (une fois) le client Weaviate v4. Import différé."""
        if self._client is not None:
            return self._client

        import weaviate
        from weaviate.classes.init import Auth

        auth = Auth.api_key(self._api_key) if self._api_key else None
        self._client = weaviate.connect_to_weaviate_cloud(
            cluster_url=self._url,
            auth_credentials=auth,
        )
        return self._client

    def _collection(self) -> Collection:
        """Renvoie la collection, en la créant (multi-tenancy activé) si absente."""
        from weaviate.classes.config import Configure, DataType, Property

        client = self._connecter()
        if not client.collections.exists(self._nom_collection):
            client.collections.create(
                self._nom_collection,
                # Multi-tenancy NATIF : isolation physique par tenant (#49, §6).
                multi_tenancy_config=Configure.multi_tenancy(
                    enabled=True,
                    auto_tenant_creation=True,
                ),
                # Vecteurs BYO (#51) : on fournit l'embedding, pas de vectorizer.
                vectorizer_config=Configure.Vectorizer.none(),
                properties=[
                    Property(name="contrat_id", data_type=DataType.TEXT),
                    Property(name="tenant", data_type=DataType.TEXT),
                    Property(name="type_clause", data_type=DataType.TEXT),
                    Property(name="texte", data_type=DataType.TEXT),
                    Property(name="date_echeance", data_type=DataType.TEXT),
                    Property(name="fournisseur_siren", data_type=DataType.TEXT),
                ],
            )
        return client.collections.get(self._nom_collection)

    def _tenant(self, tenant: str) -> Collection:
        """Collection **bornée au tenant** : garde-fou d'isolation natif (§6).

        S'assure que le tenant existe (idempotent) puis renvoie la vue bornée. Le
        tenant vient du serveur (token Keycloak), jamais du client.
        """
        from weaviate.classes.tenants import Tenant

        collection = self._collection()
        tenants = collection.tenants
        if tenant not in tenants.get():
            tenants.create(Tenant(name=tenant))
        return collection.with_tenant(tenant)

    # --- Opérations du Protocol VectorStore ---

    def upsert(self, tenant: str, contrat_id: str, chunks: list[Chunk]) -> None:
        """Réécrit l'ensemble des chunks d'un contrat (delete-then-insert).

        Idempotent sur `contrat_id` : on supprime d'abord tout chunk existant du
        contrat dans le tenant, puis on (ré)insère. Appelée après COMMITE.
        """
        self.supprimer(tenant, contrat_id)
        if not chunks:
            return

        from weaviate.classes.data import DataObject

        objets = [
            DataObject(
                properties={
                    "contrat_id": chunk.contrat_id,
                    "tenant": chunk.tenant,
                    "type_clause": chunk.type_clause,
                    "texte": chunk.texte,
                    "date_echeance": _texte_ou_vide(chunk.metadata.get("date_echeance")),
                    "fournisseur_siren": _texte_ou_vide(chunk.metadata.get("fournisseur_siren")),
                },
                vector=chunk.vecteur if chunk.vecteur is not None else None,
            )
            for chunk in chunks
        ]
        self._tenant(tenant).data.insert_many(objets)

    def supprimer(self, tenant: str, contrat_id: str) -> None:
        """Supprime tous les chunks d'un contrat dans le tenant donné."""
        from weaviate.classes.query import Filter

        self._tenant(tenant).data.delete_many(
            where=Filter.by_property("contrat_id").equal(contrat_id),
        )

    def rechercher(self, tenant: str, vecteur: list[float], k: int = 5) -> list[Chunk]:
        """Renvoie les `k` chunks les plus proches du vecteur, bornés au tenant."""
        resultat = self._tenant(tenant).query.near_vector(
            near_vector=vecteur,
            limit=k,
        )
        return [_objet_vers_chunk(objet.properties) for objet in resultat.objects]

    # --- Aides hors Protocol (réconciliation #53, fermeture) ---

    def contrat_ids(self, tenant: str) -> set[str]:
        """Ensemble des `contrat_id` projetés pour ce tenant (diff de réconciliation).

        Parcourt les objets du tenant (sans vecteur) et collecte les `contrat_id`.
        Aligné sur l'aide homonyme du `FakeVectorStore` (cf. `reconciliation`).
        """
        ids: set[str] = set()
        for objet in self._tenant(tenant).iterator():
            cid = objet.properties.get("contrat_id")
            if isinstance(cid, str):
                ids.add(cid)
        return ids

    def fermer(self) -> None:
        """Ferme la connexion Weaviate (libère gRPC/HTTP)."""
        if self._client is not None:
            self._client.close()
            self._client = None


def _texte_ou_vide(valeur: object) -> str:
    """Coerce une métadonnée optionnelle en TEXT Weaviate (jamais None)."""
    return valeur if isinstance(valeur, str) else ""


def _objet_vers_chunk(props: dict[str, Any]) -> Chunk:
    """Reconstruit un `Chunk` depuis les propriétés d'un objet Weaviate.

    Les métadonnées de filtrage RAG (§6) sont reconstituées depuis les propriétés
    plates de l'objet, sans repasser par Postgres.
    """
    contrat_id = _texte_ou_vide(props.get("contrat_id"))
    tenant = _texte_ou_vide(props.get("tenant"))
    type_clause = _texte_ou_vide(props.get("type_clause"))
    date_echeance = props.get("date_echeance") or None
    fournisseur_siren = props.get("fournisseur_siren") or None
    return Chunk(
        contrat_id=contrat_id,
        tenant=tenant,
        type_clause=type_clause,
        texte=_texte_ou_vide(props.get("texte")),
        metadata={
            "contrat_id": contrat_id,
            "tenant": tenant,
            "type_clause": type_clause,
            "date_echeance": date_echeance,
            "fournisseur_siren": fournisseur_siren,
        },
    )
