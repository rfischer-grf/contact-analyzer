"""Contrôles de première étape (#17, spec §2.1).

Type MIME et taille du fichier uploadé. Un échec ici est une **décision métier
terminale** (`ControleRejete`) : le fichier ne sera jamais conforme, donc inutile
de retenter — au contraire d'une panne d'infra, retryable (cf. `antivirus`).

Ces contrôles s'exécutent côté serveur APRÈS l'upload présigné : les octets ne
transitent pas par l'API (§7), mais le `HEAD` sur l'objet S3 fournit type MIME et
taille, et le scan AV lit le contenu déposé.
"""

from __future__ import annotations

from ..config import get_settings


class ControleRejete(Exception):
    """Le document viole un contrôle d'ingestion (MIME/taille) — refus terminal.

    Décision métier : ne PAS retenter (le fichier ne deviendra pas conforme).
    Mappe sur l'état `REJETE_TECHNIQUE` de la saga (§4).
    """


def valider_mime(content_type: str, autorises: list[str] | None = None) -> None:
    """Vérifie que le type MIME déclaré figure dans la liste autorisée.

    `autorises` par défaut = `get_settings().upload_types_mime` (PDF, DOCX, DOC).
    La comparaison ignore les paramètres éventuels du Content-Type
    (ex. ``application/pdf; charset=binary``) et la casse du type.

    Lève `ControleRejete` si le type n'est pas autorisé.
    """
    if autorises is None:
        autorises = get_settings().upload_types_mime
    type_nu = content_type.split(";", 1)[0].strip().lower()
    permis = {t.strip().lower() for t in autorises}
    if type_nu not in permis:
        raise ControleRejete(f"Type MIME non autorisé : {type_nu!r} (autorisés : {sorted(permis)})")


def valider_taille(taille_octets: int, maximum: int | None = None) -> None:
    """Vérifie que la taille du fichier ne dépasse pas le plafond.

    `maximum` par défaut = `get_settings().upload_taille_max_octets`. Une taille
    négative ou nulle est elle aussi rejetée (objet vide ou métadonnée aberrante).

    Lève `ControleRejete` si la taille est invalide ou dépasse le plafond.
    """
    if maximum is None:
        maximum = get_settings().upload_taille_max_octets
    if taille_octets <= 0:
        raise ControleRejete(f"Taille de fichier invalide : {taille_octets} octet(s)")
    if taille_octets > maximum:
        raise ControleRejete(
            f"Fichier trop volumineux : {taille_octets} octet(s) > maximum {maximum}"
        )
