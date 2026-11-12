"""Repérage d'un terme du glossaire dans une phrase d'exemple.

Sert à mettre le terme en évidence dans le champ « Contextualisation ». Le
repérage est volontairement large, car la phrase appartient déjà à l'entrée :

* en français, on accepte le terme, son pluriel et un « s » final ;
* en arabe, on accepte les particules collées au mot (و، ف، ب، ل، ك), l'article
  (ال، لل), les terminaisons courantes (duel, pluriel, pronoms) et les
  variantes d'écriture de la hamza : « عقد » est repéré dans « العقد » et
  « طرف » dans « الطرفان ».
"""

from __future__ import annotations

import regex

from .glossaire import Entree
from .langues import AR, cle_stricte

_DIACRITIQUES = r"[\u064B-\u065F\u0670\u0640]*"
_PARTICULES = r"[وفبلك]{0,2}"
_ARTICLE = r"(?:ال|لل)?"
_TERMINAISONS = r"(?:ا|ان|ين|ون|ات|ي|ه|ها|هم|هما|هن|نا|كم)?"
_LIMITE_GAUCHE = r"(?<![\p{L}\p{M}\p{N}])"
_LIMITE_DROITE = r"(?![\p{L}\p{M}\p{N}])"
_CLASSES_ARABES = {
    **dict.fromkeys("أإؤئء", "[أإؤئءا]"),
    **dict.fromkeys("اآٱ", "[اأإآٱ]"),
    **dict.fromkeys("يى", "[يى]"),
    **dict.fromkeys("ةه", "[ةهت]"),
}


def _lettres_arabes(mot: str) -> str:
    return _DIACRITIQUES.join(_CLASSES_ARABES.get(lettre, regex.escape(lettre)) for lettre in mot)


def _motif_arabe(forme: str) -> str:
    mots = []
    for mot in cle_stricte(forme).split():
        variantes = [_lettres_arabes(mot)]
        if mot.startswith("ال") and len(mot) >= 4:
            # « ال » est le plus souvent l'article (القانون), mais il peut aussi
            # appartenir au mot (التزام) : on accepte les deux lectures.
            variantes.append(_lettres_arabes(mot[2:]))
        mots.append(_ARTICLE + "(?:" + "|".join(variantes) + ")")
    if not mots:
        return ""
    return _PARTICULES + r"\s+".join(mots) + _DIACRITIQUES + _TERMINAISONS + _DIACRITIQUES


def _motif_francais(forme: str) -> str:
    morceaux = []
    for caractere in " ".join(forme.split()):
        if caractere in "'’":
            morceaux.append("['’]")
        elif caractere in "-‑":
            morceaux.append("[-‑]")
        elif caractere == " ":
            morceaux.append(r"\s+")
        else:
            morceaux.append(regex.escape(caractere))
    return "".join(morceaux) + "s?" if morceaux else ""


def positions_du_terme(phrase: str, entree: Entree, langue: str) -> list[tuple[int, int]]:
    """Positions (début, fin) des occurrences du terme de ``entree`` dans ``phrase``."""
    construire = _motif_arabe if langue == AR else _motif_francais
    formes = sorted(entree.formes(langue), key=len, reverse=True)
    motifs = [motif for motif in map(construire, formes) if motif]
    if not motifs:
        return []
    expression = regex.compile(_LIMITE_GAUCHE + "(?:" + "|".join(motifs) + ")" + _LIMITE_DROITE,
                               regex.IGNORECASE)
    return [(trouve.start(), trouve.end()) for trouve in expression.finditer(phrase)]
