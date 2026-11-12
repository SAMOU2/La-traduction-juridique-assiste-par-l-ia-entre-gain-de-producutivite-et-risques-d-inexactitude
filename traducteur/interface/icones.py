"""Icônes de l'interface, dessinées en SVG (mêmes tracés que la maquette)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

#: Tracés au trait, sur une grille de 24 × 24.
TRACES = {
    "balance": '<path d="M12 4v15.5M8 19.5h8M5.5 7h13"/>'
               '<path d="M5.5 7L3 13a2.5 2.5 0 0 0 5 0zM18.5 7L16 13a2.5 2.5 0 0 0 5 0z"/>',
    "loupe": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/>',
    "echange": '<path d="M4 8h15M15.5 4.5L19 8l-3.5 3.5"/><path d="M20 16H5M8.5 12.5L5 16l3.5 3.5"/>',
    "copier": '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/>'
              '<path d="M15.5 8.5V6A1.5 1.5 0 0 0 14 4.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
    "livre": '<path d="M12 6.5C10 5 7 4.5 4 5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5V5c-3-.5-6 0-8 1.5z"/>'
             '<path d="M12 6.5v13"/>',
    "fichier": '<path d="M7 3.5h6.5l5 5V19a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5z"/>'
               '<path d="M13.5 3.5v5h5M9 13h6M9 16.5h6"/>',
    "institution": '<path d="M3.5 9.5L12 4l8.5 5.5z"/>'
                   '<path d="M6 9.5V17M10 9.5V17M14 9.5V17M18 9.5V17M5 17h14M4 20h16"/>',
    "tableau": '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M4 10h16M4 14.5h16M10 5v14"/>',
    "texte": '<path d="M5 6.5h14M5 10.5h14M5 14.5h14M5 18.5h8"/>',
    "coche": '<path d="M5.5 12.5l4.5 4.5 8.5-9.5"/>',
}

_GABARIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<g fill="none" stroke="{couleur}" stroke-width="{epaisseur}" stroke-linecap="round" '
    'stroke-linejoin="round">{trace}</g></svg>'
)
_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<defs><linearGradient id="or" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#F7CE62"/><stop offset="1" stop-color="#DFA126"/></linearGradient></defs>'
    '<rect x="1" y="1" width="30" height="30" rx="8" fill="url(#or)"/>'
    '<g transform="translate(4 4)" fill="none" stroke="#0B1B3A" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">{trace}</g></svg>'
)


def _rapport_ecran() -> float:
    ecran = QGuiApplication.primaryScreen()
    return ecran.devicePixelRatio() if ecran else 1.0


def _rendre(svg: str, taille: int, rapport: float) -> QPixmap:
    cote = max(1, round(taille * rapport))
    image = QPixmap(cote, cote)
    image.fill(Qt.GlobalColor.transparent)
    peintre = QPainter(image)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(peintre)
    peintre.end()
    image.setDevicePixelRatio(rapport)
    return image


def image(nom: str, couleur: str, taille: int = 18, epaisseur: float = 2.0) -> QPixmap:
    """Dessine une icône à la résolution de l'écran (pour un QLabel)."""
    svg = _GABARIT.format(couleur=couleur, epaisseur=epaisseur, trace=TRACES[nom])
    return _rendre(svg, taille, _rapport_ecran())


def icone(nom: str, couleur: str, taille: int = 18, epaisseur: float = 2.0) -> QIcon:
    """Icône pour un bouton, préparée pour les écrans de densité 1×, 2× et 3×."""
    svg = _GABARIT.format(couleur=couleur, epaisseur=epaisseur, trace=TRACES[nom])
    resultat = QIcon()
    for rapport in (1.0, 2.0, 3.0):
        resultat.addPixmap(_rendre(svg, taille, rapport))
    return resultat


def icone_application() -> QIcon:
    """Icône de la fenêtre : une balance sur fond doré."""
    svg = _LOGO.format(trace=TRACES["balance"])
    resultat = QIcon()
    for taille in (16, 24, 32, 48, 64, 128, 256):
        resultat.addPixmap(_rendre(svg, taille, 1.0))
    return resultat
