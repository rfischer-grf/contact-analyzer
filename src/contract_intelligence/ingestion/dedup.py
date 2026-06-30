"""Dédoublonnage / idempotence du déclenchement (#15, spec §2.1).

Clé canonique = SHA256 du fichier (§2.1) : un re-upload du même contenu pour le
même tenant ne doit PAS relancer un workflow ni créer un doublon. Le déclenchement
consulte `document_existe()` au moment du confirm d'upload → re-upload = no-op.

La contrainte d'unicité `(tenant, sha256)` (cf. `Document` en §5) reste la garantie
forte en base ; cette vérification évite simplement de démarrer une saga pour rien.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Document


def document_existe(session: Session, tenant: str, sha256: str) -> bool:
    """Indique si un document de même `(tenant, sha256)` est déjà connu.

    Le tenant provient du token, jamais du client (§7). Retourne `True` si une
    pièce identique existe déjà pour ce tenant (déclenchement = no-op idempotent).
    """
    requete = select(Document.id).where(
        Document.tenant == tenant,
        Document.sha256 == sha256,
    )
    return session.execute(requete).first() is not None
