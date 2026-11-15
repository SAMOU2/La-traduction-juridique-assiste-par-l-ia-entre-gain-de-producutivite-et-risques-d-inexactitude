"""Lecture de ce qu'un modèle a écrit.

Certains modèles écrivent une « réflexion » avant leur réponse, entre deux marques. Cette réflexion
n'est pas la réponse : elle est retirée avant tout affichage et avant tout contrôle.
"""

from __future__ import annotations

import re

#: Blocs de réflexion connus, quand ils ouvrent la réponse.
#: - Gemma 4 : « <|channel>thought … <channel|> » (le bloc est parfois vide) ;
#: - d'autres modèles : « <think> … </think> ».
_REFLEXIONS = (
    re.compile(r"\A\s*<\|channel>\s*thought\b.*?<channel\|>", re.DOTALL),
    re.compile(r"\A\s*<think>.*?</think>", re.DOTALL | re.IGNORECASE),
)


def sans_reflexion(texte: str) -> str:
    """La réponse du modèle, sans le bloc de réflexion qui la précède et sans espaces autour.

    Un bloc qui n'est pas refermé est laissé tel quel : rien ne dit où la réponse commence.
    """
    for motif in _REFLEXIONS:
        texte = motif.sub("", texte, count=1)
    return texte.strip()
