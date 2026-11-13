"""Barre latérale : le choix de l'écran, par une colonne d'icônes à gauche de la fenêtre.

De haut en bas : le logo, les deux écrans de travail (« Terme », « Texte »), puis
« Paramètres » et « Description de la plateforme » ; en bas, le « Centre d'aide ».
L'écran affiché est repéré par une icône dorée et un trait doré sur le bord gauche.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QVBoxLayout, QWidget

from . import icones, theme
from .composants import infobulle

#: Les écrans de l'application, dans l'ordre de la barre latérale.
MODE_TERME = "terme"
MODE_TEXTE = "texte"
MODE_PARAMETRES = "parametres"
MODE_DESCRIPTION = "description"
MODE_AIDE = "aide"

#: écran -> (titre, icône, ce que fait l'écran, raccourci)
ECRANS = {
    MODE_TERME: ("Terme", "loupe", "Rechercher un terme dans le glossaire", "Ctrl+1"),
    MODE_TEXTE: ("Texte", "document", "Traduire un texte", "Ctrl+2"),
    MODE_PARAMETRES: ("Paramètres", "reglages", "Glossaire, affichage, service informatique", "Ctrl+3"),
    MODE_DESCRIPTION: ("Description de la plateforme", "information", "Ce que fait l’application", "Ctrl+4"),
    MODE_AIDE: ("Centre d’aide", "aide", "Questions fréquentes, contact du service informatique", "F1"),
}
#: Largeur de la barre latérale.
LARGEUR = 64


class BoutonRail(QAbstractButton):
    """Un bouton de la barre latérale : une icône dans un carré arrondi."""

    HAUTEUR = 52
    COTE = 42

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        titre, self._icone, description, raccourci = ECRANS[mode]
        self.setText(titre)
        self.setCheckable(True)
        self.setFixedSize(LARGEUR, self.HAUTEUR)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setToolTip(infobulle(f"{titre} ({raccourci})", description, espace=2))
        self.setAccessibleName(titre)
        self.setAccessibleDescription(description)
        #: Vrai si le bouton a reçu le curseur par le clavier : un anneau l'entoure alors.
        self._atteint_au_clavier = False

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(LARGEUR, self.HAUTEUR)

    def focusInEvent(self, evenement) -> None:  # noqa: N802
        self._atteint_au_clavier = evenement.reason() in (
            Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(evenement)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        choisi, survol = self.isChecked(), self.underMouse()
        cadre = QRectF((self.width() - self.COTE) / 2, (self.height() - self.COTE) / 2, self.COTE, self.COTE)
        if choisi or survol or self.isDown():
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.RAIL_ACTIF if choisi else theme.RAIL_SURVOL))
            peintre.drawRoundedRect(cadre, 12, 12)
        if self.hasFocus() and self._atteint_au_clavier:
            peintre.setPen(QPen(QColor(theme.RAIL_ICONE), 1.25))
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            peintre.drawRoundedRect(cadre.adjusted(0.6, 0.6, -0.6, -0.6), 11.5, 11.5)
        if choisi:
            # Trait doré sur le bord gauche de la barre : il repère l'écran affiché.
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.OR))
            peintre.drawRoundedRect(QRectF(0, (self.height() - 24) / 2, 3.5, 24), 1.75, 1.75)
        couleur = theme.OR if choisi else theme.RAIL_ICONE_SURVOL if survol else theme.RAIL_ICONE
        image = icones.image(self._icone, couleur, 22, 1.45)
        peintre.drawPixmap(QPointF((self.width() - 22) / 2, (self.height() - 22) / 2), image)


class BarreLaterale(QWidget):
    """La colonne d'icônes : logo, écrans, centre d'aide."""

    #: Un écran a été choisi ; le signal porte son nom (``MODE_TERME``…).
    choisi = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(LARGEUR)
        self.setAccessibleName("Écrans de l’application")
        self.boutons: dict[str, BoutonRail] = {}
        self._groupe = QButtonGroup(self)
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 62, 0, 10)
        colonne.setSpacing(2)
        for mode in ECRANS:
            if mode == MODE_PARAMETRES:
                colonne.addSpacing(17)  # un filet est dessiné dans cet espace
            if mode == MODE_AIDE:
                colonne.addStretch(1)
            bouton = BoutonRail(mode)
            bouton.clicked.connect(lambda _=False, ecran=mode: self.choisi.emit(ecran))
            self._groupe.addButton(bouton)
            self.boutons[mode] = bouton
            colonne.addWidget(bouton)

    def definir(self, mode: str) -> None:
        """Repère l'écran affiché."""
        self.boutons[mode].setChecked(True)

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        peintre.fillRect(self.rect(), QColor(theme.RAIL))
        # Le logo : la balance dorée, dans un carré arrondi.
        cadre = QRectF((self.width() - 38) / 2, 12, 38, 38)
        peintre.setPen(QPen(QColor(theme.RAIL_FILET), 1))
        peintre.setBrush(QColor(theme.RAIL_SURVOL))
        peintre.drawRoundedRect(cadre, 11, 11)
        peintre.drawPixmap(QPointF(cadre.x() + 7, cadre.y() + 7), icones.image("balance", "#F4C95D", 24, 1.35))
        # Filet entre les écrans de travail et les écrans d'information.
        y = self.boutons[MODE_PARAMETRES].y() - 9
        peintre.setPen(QPen(QColor(theme.RAIL_FILET), 1))
        peintre.drawLine(QPointF(20, y + 0.5), QPointF(self.width() - 20, y + 0.5))


__all__ = ["ECRANS", "LARGEUR", "MODE_AIDE", "MODE_DESCRIPTION", "MODE_PARAMETRES", "MODE_TERME", "MODE_TEXTE",
           "BarreLaterale", "BoutonRail"]
