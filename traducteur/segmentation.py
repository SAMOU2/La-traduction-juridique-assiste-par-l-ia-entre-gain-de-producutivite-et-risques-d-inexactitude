"""Découpage d'un texte en phrases, puis en mots.

Ce sont les deux premières étapes de la traduction d'un texte :

1. ``segmenter_en_phrases`` repère les phrases. Une phrase se termine par un
   point, un point d'interrogation, un point d'exclamation, des points de
   suspension ou un retour à la ligne. Le point d'une abréviation (« art. »,
   « cf. », « M. »), d'une initiale ou d'un numéro de liste ne termine pas la
   phrase ;
2. ``decouper_en_mots`` découpe une phrase en « jetons » : mots, nombres et
   signes de ponctuation. L'article ou la préposition élidés sont séparés du
   mot qui suit : « l'usage » donne « l' » et « usage ». Dans le décompte des
   mots, « l'usage » compte pour un seul mot, comme dans un traitement de texte.

Chaque phrase et chaque jeton gardent leur position dans le texte d'origine.
"""

from __future__ import annotations

from dataclasses import dataclass

import regex

MOT = "mot"
NOMBRE = "nombre"
PONCTUATION = "ponctuation"


@dataclass(frozen=True)
class Phrase:
    """Une phrase du texte : ``texte[debut:fin]``."""

    texte: str
    debut: int
    fin: int


@dataclass(frozen=True)
class Jeton:
    """Un mot, un nombre ou un signe de ponctuation : ``texte[debut:fin]``."""

    texte: str
    debut: int
    fin: int
    nature: str
    #: Vrai pour un mot élidé, collé au mot suivant par une apostrophe : « l' », « d' », « qu' ».
    elide: bool = False

    @property
    def est_mot(self) -> bool:
        return self.nature == MOT

    @property
    def compte(self) -> bool:
        """Vrai si le jeton compte pour un mot (un mot élidé est compté avec le mot qui le suit)."""
        return self.nature == MOT and not self.elide


# ------------------------------------------------------------------ phrases
#: Abréviations françaises courantes dans les textes juridiques, écrites sans leur point final.
ABREVIATIONS = frozenset({
    "al", "art", "arts", "av", "bull", "cass", "cf", "ch", "chap", "cit", "civ", "coll", "com", "crim", "déc",
    "dr", "éd", "ed", "env", "etc", "ex", "fig", "ibid", "id", "infra", "jo", "j.o", "j.o.r.a", "j.o.r.a.d.p",
    "m", "me", "mes", "mlle", "mm", "mme", "mmes", "n", "no", "nos", "obs", "op", "ord", "p", "pp", "pr", "préc",
    "r", "réf", "ref", "req", "rev", "s", "sect", "soc", "sq", "ss", "st", "ste", "supra", "t", "tél", "trib", "v",
    "vol", "c.-à-d", "c.à.d", "p.ex",
})

_LIGNE = regex.compile(r"[^\r\n]+")
# Fin de phrase possible : ponctuation finale, suivie d'éventuels guillemets ou parenthèses fermants.
_FIN = regex.compile(r"(?:[.!?…؟۔]+)(?:[»”\"'’)\]]|[\u00A0\u202F ]»)*")
# Mot placé juste avant le point (il peut contenir des points : « J.O »).
_MOT_AVANT = regex.compile(r"[\p{L}\p{N}][\p{L}\p{N}.\-°]*$")
_NUMERO = regex.compile(r"(?:\p{Nd}+|[ivxlcdm]+|\p{L})$", regex.IGNORECASE)
_CONTENU = regex.compile(r"[\p{L}\p{N}]")


def _termine_la_phrase(ligne: str, debut_phrase: int, trouve: regex.Match) -> bool:
    """Indique si la ponctuation trouvée termine vraiment la phrase commencée à ``debut_phrase``."""
    apres = trouve.end()
    if apres >= len(ligne):
        return True
    if not ligne[apres].isspace():
        return False  # « 3.5 », « www.joradp.dz », « J.O.R.A. »
    signes = trouve.group()
    if signes[0] in "!?؟۔":
        return True
    if ligne[apres:].lstrip()[:1].islower():
        return False  # « art. 5 du code », « ord. n° 75-58 », « … et autres »
    if not signes.startswith(".") or signes.startswith(".."):
        return True  # points de suspension suivis d'une majuscule
    avant = _MOT_AVANT.search(ligne, debut_phrase, trouve.start())
    if avant is None:
        return True
    mot = avant.group()
    if not ligne[debut_phrase:avant.start()].strip() and _NUMERO.fullmatch(mot):
        return False  # numéro de liste en début de phrase : « 1. », « a. », « II. »
    if mot.casefold() == "etc":
        return True  # « etc. » suivi d'une majuscule : la phrase est finie
    if mot.casefold() in ABREVIATIONS:
        return False
    # Une lettre isolée est une initiale ou une abréviation : « J. Dupont », « L. 110-1 », « ص. 12 ».
    return not (len(mot) == 1 and mot.isalpha())


def segmenter_en_phrases(texte: str) -> list[Phrase]:
    """Découpe un texte en phrases (étape 1).

    Les passages sans lettre ni chiffre (lignes vides, tirets de séparation)
    n'appartiennent à aucune phrase.
    """
    phrases: list[Phrase] = []

    def ajouter(debut: int, fin: int) -> None:
        morceau = texte[debut:fin]
        if not _CONTENU.search(morceau):
            return
        debut += len(morceau) - len(morceau.lstrip())
        fin -= len(morceau) - len(morceau.rstrip())
        phrases.append(Phrase(texte[debut:fin], debut, fin))

    for trouve_ligne in _LIGNE.finditer(texte):
        ligne, origine = trouve_ligne.group(), trouve_ligne.start()
        debut = 0
        for trouve in _FIN.finditer(ligne):
            if trouve.start() < debut or not _CONTENU.search(ligne, debut, trouve.start()):
                continue
            if _termine_la_phrase(ligne, debut, trouve):
                ajouter(origine + debut, origine + trouve.end())
                debut = trouve.end()
        ajouter(origine + debut, origine + len(ligne))
    return phrases


# ------------------------------------------------------------------ mots
_JETON = regex.compile(
    r"""
    (?P<elision>(?<![\p{L}\p{M}\p{N}])(?i:[cdjlmnst]|qu|jusqu|lorsqu|puisqu|quoiqu)['’](?=\p{L}))
  | (?P<nombre>\p{Nd}[\p{Nd}\p{L}]*(?:[.,/:\-\u066B\u066C]\p{Nd}+)*)
  | (?P<mot>[\p{L}\p{M}][\p{L}\p{M}\p{N}]*(?:[-‑'’][\p{L}\p{M}\p{N}]+)*)
  | (?P<ponctuation>\.{2,}|\S)
    """,
    regex.VERBOSE,
)


def decouper_en_mots(texte: str, decalage: int = 0) -> list[Jeton]:
    """Découpe une phrase en jetons : mots, nombres, signes de ponctuation (étape 2).

    ``decalage`` est la position de la phrase dans le texte complet ; il est
    ajouté aux positions des jetons.
    """
    jetons: list[Jeton] = []
    for trouve in _JETON.finditer(texte):
        if trouve.lastgroup == "nombre":
            nature = NOMBRE
        elif trouve.lastgroup == "ponctuation":
            nature = PONCTUATION
        else:
            nature = MOT
        jetons.append(Jeton(trouve.group(), decalage + trouve.start(), decalage + trouve.end(), nature,
                            elide=trouve.lastgroup == "elision"))
    return jetons


def compter(texte: str) -> tuple[int, int, int]:
    """Nombre de phrases, de mots et de caractères d'un texte."""
    phrases = segmenter_en_phrases(texte)
    mots = sum(1 for phrase in phrases for jeton in decouper_en_mots(phrase.texte) if jeton.compte)
    return len(phrases), mots, len(texte.strip())
