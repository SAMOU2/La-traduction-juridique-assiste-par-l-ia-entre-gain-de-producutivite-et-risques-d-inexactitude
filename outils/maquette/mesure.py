"""Mesure de la largeur des textes, pour placer les éléments de la maquette.

Les fichiers du dépôt ont été produits avec Selawik (mêmes dimensions que Segoe UI) et
Noto Sans Arabic. Sur une autre machine, les polices installées sont utilisées : Segoe UI
sous Windows. La variable d'environnement ``POLICES_MAQUETTE`` peut désigner un dossier de
fichiers ``.ttf`` à charger en plus.
"""
from __future__ import annotations

import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import regex
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QGuiApplication

_application = QGuiApplication.instance() or QGuiApplication([])
if os.environ.get("POLICES_MAQUETTE"):
    for _fichier in sorted(pathlib.Path(os.environ["POLICES_MAQUETTE"]).glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(_fichier))


def _premiere_installee(*familles: str) -> str:
    installees = set(QFontDatabase.families())
    return next((famille for famille in familles if famille in installees), familles[-1])


LATIN = _premiere_installee("Selawik", "Segoe UI", "Arial", "Helvetica")
ARABE = _premiere_installee("Noto Sans Arabic", "Segoe UI", "Arial")

_ARABE = regex.compile(r"[\p{Arabic}\u200f\u202b\u202c]")
_SEGMENTS = regex.compile(r"\p{Arabic}[\p{Arabic}\p{Mn}\s،؛؟.]*[\p{Arabic}\p{Mn}،؛؟.]|\p{Arabic}|[^\p{Arabic}]+")
_metriques: dict[tuple[str, int], QFontMetricsF] = {}


def _metrique(famille: str, poids: int) -> QFontMetricsF:
    if (famille, poids) not in _metriques:
        police = QFont(famille)
        police.setPixelSize(1000)  # mesure à grande taille, puis mise à l'échelle : pas d'arrondi au pixel
        police.setWeight(QFont.Weight(poids))
        police.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        _metriques[famille, poids] = QFontMetricsF(police)
    return _metriques[famille, poids]


def est_arabe(texte: str) -> bool:
    return bool(_ARABE.search(texte))


def largeur(texte: str, taille: float, poids: int = 400) -> float:
    """Largeur du texte en pixels. Un texte demi-gras (600) est mesuré en gras : la mesure est un maximum."""
    total = 0.0
    for segment in _SEGMENTS.findall(texte):
        if est_arabe(segment):
            metrique = _metrique(ARABE, 600 if poids >= 600 else 400)
        else:
            metrique = _metrique(LATIN, 700 if poids >= 600 else 400)
        total += metrique.horizontalAdvance(segment) * taille / 1000
    return total
