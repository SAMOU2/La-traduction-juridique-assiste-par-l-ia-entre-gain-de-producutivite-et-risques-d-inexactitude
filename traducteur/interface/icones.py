"""Icônes de l'interface, dessinées en SVG (mêmes tracés que la proposition d'interface)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

#: Tracés au trait, sur une grille de 16 × 16.
TRACES = {
    "balance": '<path d="M8 2.8v10.4M5.5 13.2h5M3.4 4.6h9.2M3.4 4.6 1.8 8.6h3.2zM12.6 4.6 11 8.6h3.2z'
               'M1.8 8.6a1.6 1.6 0 0 0 3.2 0M11 8.6a1.6 1.6 0 0 0 3.2 0"/>',
    "loupe": '<circle cx="7" cy="7" r="4.25"/><path d="M10.2 10.2 13.5 13.5"/>',
    "echange": '<path d="M2.5 5.5H13M10.5 3 13 5.5 10.5 8M13.5 10.5H3M5.5 8 3 10.5 5.5 13"/>',
    "fleche": '<path d="M3 8h10M9.5 4.5 13 8l-3.5 3.5"/>',
    "chevron-d": '<path d="M6 3.5 10.5 8 6 12.5"/>',
    "chevron-g": '<path d="M10 3.5 5.5 8 10 12.5"/>',
    "chevron-b": '<path d="M3.5 6 8 10.5 12.5 6"/>',
    "croix": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
    "copier": '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
              '<path d="M10.5 5.5V4A1.5 1.5 0 0 0 9 2.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"/>',
    "document": '<path d="M9.5 2.5h-5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-7z"/>'
                '<path d="M9.5 2.5v3h3M6 8.5h4M6 11h4"/>',
    "importer": '<path d="M8 2.5v8M4.8 7.4 8 10.6l3.2-3.2M3 13.5h10"/>',
    "exporter": '<path d="M8 10.5v-8M4.8 5.7 8 2.5l3.2 3.2M3 13.5h10"/>',
    "alerte": '<circle cx="8" cy="8" r="5.75"/><path d="M8 5v3.4M8 10.9v.1"/>',
    "information": '<circle cx="8" cy="8" r="5.75"/><path d="M8 7.6V11M8 5v.1"/>',
    "coche": '<circle cx="8" cy="8" r="5.75"/><path d="M5.6 8.2 7.3 9.9l3.2-3.6"/>',
    "lien": '<path d="M9.5 3H13v3.5M13 3 7.5 8.5M11 9.5V12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2.5"/>',
    "texte": '<path d="M3 4.5h10M3 8h10M3 11.5h6"/>',
    "fiche": '<rect x="3" y="2.5" width="10" height="11" rx="1.5"/><path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3"/>',
}

_GABARIT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<g fill="none" stroke="{couleur}" stroke-width="{epaisseur}" stroke-linecap="round" '
    'stroke-linejoin="round">{trace}</g></svg>'
)
_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect x="1" y="1" width="30" height="30" rx="8" fill="#0F1F3D"/>'
    '<g transform="translate(4 4) scale(1.5)" fill="none" stroke="#F4C95D" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round">{trace}</g></svg>'
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


def _svg(nom: str, couleur: str, epaisseur: float) -> str:
    return _GABARIT.format(couleur=couleur, epaisseur=epaisseur, trace=TRACES[nom])


def image(nom: str, couleur: str, taille: int = 16, epaisseur: float = 1.5) -> QPixmap:
    """Dessine une icône à la résolution de l'écran (pour un QLabel)."""
    return _rendre(_svg(nom, couleur, epaisseur), taille, _rapport_ecran())


def icone(nom: str, couleur: str, taille: int = 16, epaisseur: float = 1.5, *,
          couleur_inactive: str | None = None) -> QIcon:
    """Icône pour un bouton, préparée pour les écrans de densité 1×, 2× et 3×.

    ``couleur_inactive`` est la couleur de l'icône quand le bouton est désactivé.
    """
    resultat = QIcon()
    teintes = [(couleur, QIcon.Mode.Normal)]
    if couleur_inactive is not None:
        teintes.append((couleur_inactive, QIcon.Mode.Disabled))
    for teinte, mode in teintes:
        svg = _svg(nom, teinte, epaisseur)
        for rapport in (1.0, 2.0, 3.0):
            resultat.addPixmap(_rendre(svg, taille, rapport), mode)
    return resultat


def icone_a_deux_etats(nom: str, couleur: str, couleur_cochee: str, taille: int = 16,
                       epaisseur: float = 1.5) -> QIcon:
    """Icône d'un bouton à cocher : une couleur au repos, une autre quand le bouton est coché."""
    resultat = QIcon()
    for teinte, etat in ((couleur, QIcon.State.Off), (couleur_cochee, QIcon.State.On)):
        svg = _svg(nom, teinte, epaisseur)
        for rapport in (1.0, 2.0, 3.0):
            resultat.addPixmap(_rendre(svg, taille, rapport), QIcon.Mode.Normal, etat)
    return resultat


def icone_application() -> QIcon:
    """Icône de la fenêtre : une balance dorée sur fond bleu marine."""
    svg = _LOGO.format(trace=TRACES["balance"])
    resultat = QIcon()
    for taille in (16, 24, 32, 48, 64, 128, 256):
        resultat.addPixmap(_rendre(svg, taille, 1.0))
    return resultat


def logo(taille: int = 40) -> QPixmap:
    """Le logo de l'application, pour la fenêtre « À propos »."""
    return _rendre(_LOGO.format(trace=TRACES["balance"]), taille, _rapport_ecran())
