"""Extracteur LLM réel — Pydantic AI + sortie structurée (#28, #29, #30, spec §2.3).

Phase de **qualification** du pattern transverse : à partir du markdown Docling,
on reconstruit un `Contrat` (§3) dont chaque champ porte
**valeur + confiance + provenance** (wrapper `Champ`). La sortie du modèle est
**validée par Pydantic** contre `domain.Contrat` (#28).

Connecteur (#29) : modèle OpenAI-compatible pointant `llm_base_url` / `llm_modele`
/ `llm_api_key` — **Scaleway Generative APIs** (Mistral Small 3.x, souverain EU)
ou self-host **vLLM**. Aucune dépendance n'est imposée au core : `pydantic_ai`
(et tout client réseau) est importé **paresseusement** dans le corps des méthodes,
jamais au chargement du module. Le core et les tests fonctionnent donc sans la
dépendance `extraction`.

Stratégie d'entrée (#30) : un contrat de 5–30 pages tient dans la fenêtre → on
donne le **markdown Docling complet** ; au-delà de `llm_seuil_retrieve_caracteres`
on `retrieve` d'abord les **clauses utiles** (parties, durée, résiliation,
préavis, indexation, montant) via une heuristique pure et testable.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from contract_intelligence.config import Settings, get_settings
from contract_intelligence.domain import Contrat

if TYPE_CHECKING:  # Aides de type uniquement : aucun import réseau à l'exécution.
    from pydantic_ai import Agent


# --- Prompt système (français, consignes d'extraction du §3) ------------------

# Consigne unique et stable : le modèle remplit la structure `Contrat` (§3), où
# CHAQUE champ porte valeur + confiance + provenance. La structure est ensuite
# re-validée par Pydantic (#28) — le prompt cadre, Pydantic garantit.
PROMPT_SYSTEME = """\
Tu es un extracteur de contrats fournisseurs pour une plateforme souveraine de \
gestion contractuelle (CLM). À partir du texte Markdown d'un contrat (issu d'un \
parsing Docling, pagination et structure conservées), tu extrais des informations \
structurées et tu renvoies UNIQUEMENT un objet conforme au schéma demandé.

Règles d'extraction :
- Pour CHAQUE champ extrait, tu fournis trois éléments : la valeur (`valeur`), un \
score de confiance `confiance` dans l'intervalle [0, 1], et la provenance `source` \
(numéro de page `page`, et `extrait` = le passage source brut qui justifie la valeur).
- `confiance` reflète ta certitude réelle : élevée si le passage est explicite et \
sans ambiguïté, basse si la valeur est déduite, partiellement lisible ou incertaine. \
Ne gonfle jamais la confiance.
- Si une information est absente du texte, laisse le champ optionnel à null \
(ne l'invente pas). N'invente jamais une valeur pour atteindre la complétude.
- `fournisseur` et `client` sont les deux parties : identifie raison sociale, SIREN \
(9 chiffres), forme juridique et adresse quand ils figurent au contrat.
- Dates (`date_effet`, `date_echeance`) au format ISO (AAAA-MM-JJ). Ne calcule PAS \
la date limite de dénonciation : elle est dérivée en aval (échéance − préavis).
- `duree_initiale_mois` et `duree_reconduction_mois` en mois. `tacite_reconduction` \
= booléen (le contrat se renouvelle-t-il par tacite reconduction ?).
- `preavis` : délai (entier) + unité (`jours` ou `mois`) + modalités éventuelles.
- `indexation` : indice parmi {syntec, ilat, ilc, icc, insee_autre, aucun} ; valeur \
de base S0 et période de base si données ; formule de révision ; part fixe ; \
périodicité ; `bidirectionnelle` (révision à la hausse ET à la baisse ?).
- `montant` (nombre) et `devise` (code, ex. EUR) quand le contrat les précise.
- Cite dans `extrait` un passage court mais littéral du texte ; n'y mets jamais \
de contenu reformulé.
"""


# --- Stratégie d'entrée : retrieve des clauses utiles (#30) -------------------

# Sections jugées utiles à l'extraction (§2.3) : on cible parties, durée,
# résiliation/dénonciation, préavis, indexation/révision et montant/prix. Les
# motifs sont volontairement larges (variantes de libellés fréquentes en contrats
# fournisseurs FR) et insensibles à la casse/aux accents usuels.
_MOTS_CLES_SECTIONS_UTILES: tuple[str, ...] = (
    # Parties / identité
    "partie",
    "entre les soussign",
    "identification",
    "raison sociale",
    "siren",
    "siret",
    # Objet
    "objet",
    # Durée / effet / échéance / reconduction
    "duree",
    "durée",
    "date d'effet",
    "prise d'effet",
    "entree en vigueur",
    "entrée en vigueur",
    "echeance",
    "échéance",
    "terme",
    "reconduction",
    "renouvellement",
    "tacite",
    # Résiliation / dénonciation / préavis
    "resiliation",
    "résiliation",
    "denonciation",
    "dénonciation",
    "preavis",
    "préavis",
    # Indexation / révision de prix
    "indexation",
    "indice",
    "revision",
    "révision",
    "syntec",
    "ilat",
    "ilc",
    "icc",
    "insee",
    # Montant / prix / rémunération
    "montant",
    "prix",
    "tarif",
    "remuneration",
    "rémunération",
    "redevance",
)

# Frontière de section : titre markdown (`#`…`######`) ou en-tête « Article N … ».
_RE_TITRE_SECTION = re.compile(r"^\s{0,3}(?:#{1,6}\s+|article\s+\d+\b)", re.IGNORECASE)


def _normaliser(texte: str) -> str:
    """Minuscule + neutralisation des accents usuels FR pour un match robuste."""
    texte = texte.casefold()
    for accentue, base in (
        ("à", "a"),
        ("â", "a"),
        ("ä", "a"),
        ("é", "e"),
        ("è", "e"),
        ("ê", "e"),
        ("ë", "e"),
        ("î", "i"),
        ("ï", "i"),
        ("ô", "o"),
        ("ö", "o"),
        ("û", "u"),
        ("ù", "u"),
        ("ü", "u"),
        ("ç", "c"),
    ):
        texte = texte.replace(accentue, base)
    return texte


# Mots-clés normalisés une fois (les accents y sont déjà neutralisés).
_MOTS_CLES_NORMALISES: tuple[str, ...] = tuple(
    dict.fromkeys(_normaliser(mot) for mot in _MOTS_CLES_SECTIONS_UTILES)
)


def _titre_est_utile(titre: str) -> bool:
    """Vrai si un libellé de titre/section contient un mot-clé utile."""
    titre_norm = _normaliser(titre)
    return any(mot in titre_norm for mot in _MOTS_CLES_NORMALISES)


def _decouper_en_sections(markdown: str) -> list[tuple[str | None, list[str]]]:
    """Découpe le markdown en sections `(titre, lignes)` sur titres/articles.

    Le préambule éventuel (texte avant tout titre) porte `titre=None` et le titre
    de section est conservé dans ses lignes pour ne rien perdre lors d'une sélection.
    """
    sections: list[tuple[str | None, list[str]]] = []
    titre_courant: str | None = None
    lignes_courantes: list[str] = []

    def _clore() -> None:
        if titre_courant is not None or lignes_courantes:
            sections.append((titre_courant, lignes_courantes))

    for ligne in markdown.splitlines():
        if _RE_TITRE_SECTION.match(ligne):
            _clore()
            titre_courant = ligne.strip()
            lignes_courantes = [ligne]
        else:
            lignes_courantes.append(ligne)

    _clore()
    return sections


def retrieve_clauses_utiles(markdown: str) -> str:
    """Retient les sections utiles d'un markdown volumineux (#30, helper pur).

    Heuristique : on découpe le document sur ses frontières structurelles (titres
    markdown / « Article N ») puis on conserve les sections dont le **titre** porte
    un mot-clé utile (parties, durée, résiliation/dénonciation, préavis, indexation,
    montant). À défaut de titre exploitable, une section est gardée si son **corps**
    mentionne un mot-clé, afin de ne pas perdre une clause dans un document peu titré.

    Fonction **pure et déterministe** (aucun réseau) : préserve l'ordre d'origine et
    réassemble les sections retenues, séparées par une ligne vide. Si rien ne
    ressort (document atypique), on renvoie le markdown complet en repli — mieux
    vaut un prompt plus long qu'une extraction privée de sa source.
    """
    sections = _decouper_en_sections(markdown)
    retenues: list[str] = []
    for _titre, lignes in sections:
        corps = "\n".join(lignes).strip()
        if not corps:
            continue
        # Le titre (s'il existe) figure déjà dans `corps` : tester le corps couvre
        # à la fois un titre porteur de mot-clé et, à défaut, une clause repérée
        # dans le texte d'une section au titre neutre (document peu titré).
        if _titre_est_utile(corps):
            retenues.append(corps)

    if not retenues:
        return markdown.strip()
    return "\n\n".join(retenues)


def _preparer_entree(markdown: str, seuil_caracteres: int) -> str:
    """Choisit l'entrée du modèle selon la stratégie #30.

    `markdown` court (≤ seuil) → markdown complet ; volumineux → clauses utiles.
    """
    if len(markdown) <= seuil_caracteres:
        return markdown
    return retrieve_clauses_utiles(markdown)


# --- Extracteur LLM réel (#28, #29) -------------------------------------------


class ExtracteurLLM:
    """`Extracteur` réel : Pydantic AI + modèle OpenAI-compatible (souverain EU).

    Conforme au `Protocol` `Extracteur` (`extraire(markdown) -> Contrat`). La
    dépendance `pydantic_ai` n'est PAS importée au chargement du module : elle
    l'est dans le corps de `extraire` / `_construire_agent` (import différé), si
    bien que l'on peut importer et instancier `ExtracteurLLM` sans la dépendance
    `extraction` installée (vérifié en test). Seul l'appel réseau l'exige.

    Paramètres résolus depuis `get_settings()` par défaut : `llm_base_url`,
    `llm_modele`, `llm_api_key`, `llm_seuil_retrieve_caracteres` (#29, #30). On
    peut les surcharger explicitement (tests, multi-fournisseurs).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        reglages = settings or get_settings()
        self._base_url = reglages.llm_base_url
        self._modele = reglages.llm_modele
        self._api_key = reglages.llm_api_key
        self._seuil_retrieve = reglages.llm_seuil_retrieve_caracteres
        self._prompt_systeme = PROMPT_SYSTEME

    def _construire_agent(self) -> Agent[None, Contrat]:
        """Construit l'`Agent` Pydantic AI (import différé, sortie structurée #28).

        Cible la base OpenAI-compatible `llm_base_url` (Scaleway Generative APIs /
        vLLM). `output_type=Contrat` impose la **re-validation Pydantic** de la
        sortie du modèle contre le schéma du §3.
        """
        from pydantic_ai import Agent
        from pydantic_ai.providers.openai import OpenAIProvider

        try:
            # Nom de classe courant (pydantic_ai récent).
            from pydantic_ai.models.openai import OpenAIChatModel as _ModeleOpenAI
        except ImportError:  # Repli pour les versions plus anciennes.
            from pydantic_ai.models.openai import OpenAIModel as _ModeleOpenAI

        if not self._base_url:
            raise RuntimeError(
                "llm_base_url non configurée : renseigner CI_LLM_BASE_URL "
                "(Scaleway Generative APIs ou endpoint vLLM OpenAI-compatible)."
            )

        provider = OpenAIProvider(base_url=self._base_url, api_key=self._api_key)
        modele = _ModeleOpenAI(self._modele, provider=provider)
        return Agent(
            modele,
            output_type=Contrat,
            instructions=self._prompt_systeme,
        )

    def extraire(self, markdown: str) -> Contrat:
        """Extrait un `Contrat` structuré (§3) depuis le markdown Docling.

        Applique la stratégie #30 (markdown complet vs clauses utiles selon
        `llm_seuil_retrieve_caracteres`), interroge le modèle et renvoie la sortie
        structurée **déjà validée** contre `Contrat` par Pydantic AI (#28).
        """
        entree = _preparer_entree(markdown, self._seuil_retrieve)
        agent = self._construire_agent()
        resultat = agent.run_sync(entree)
        contrat: Contrat = resultat.output
        return contrat
