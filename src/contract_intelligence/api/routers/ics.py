"""Feed ICS de visibilité (#46/#47).

Garde-fous (§2.6) : capability bearer (token long aléatoire, révocable/rotatable) ;
le feed ne contient que dates + intitulé (jamais le contenu des clauses) ; pas de
`VALARM` comme mécanisme d'alerte. L'accès est porté par le token de capability,
pas par la session Keycloak → cet endpoint n'utilise pas `get_principal`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/ics", tags=["ics"])


@router.get("/{token}.ics")
def feed_ics(token: str) -> str:
    """Renvoie le calendrier .ics (1 VEVENT par échéance / date limite / révision) (#46)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#46/#47)")
