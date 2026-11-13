"""Écran de démarrage : le logo, entre deux rangées de tirets qui ondulent et changent de couleur.

    - - - - - - - - - -  [ logo ]  - - - - - - - - - -

Il s'affiche pendant l'ouverture de l'application (construction de la fenêtre, chargement du
glossaire), puis laisse la place à la fenêtre principale. Un clic le ferme sans attendre.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .. import NOM_APPLICATION
from . import icones, theme
from .dessin import dessiner_ligne, melanger, police

#: Couleurs que prennent tour à tour les tirets (la dernière rejoint la première).
PALETTE = ("#FFB703", "#FB8500", "#FF4D8D", "#8B5CF6", "#3B82F6", "#22D3EE", "#34D399")


def couleur_de_la_palette(position: float) -> QColor:
    """Couleur de la palette à une position donnée ; la palette est parcourue en boucle (0 et 1 se rejoignent)."""
    position = position % 1.0 * len(PALETTE)
    rang = int(position)
    return melanger(PALETTE[rang % len(PALETTE)], PALETTE[(rang + 1) % len(PALETTE)], position - rang)


class EcranDemarrage(QWidget):
    """Fenêtre sans bordure affichée à l'ouverture de l'application."""

    #: L'écran de démarrage a fini : la fenêtre principale peut s'afficher.
    termine = Signal()

    LARGEUR, HAUTEUR = 680, 340
    #: Nombre de tirets de chaque côté du logo.
    TIRETS = 10
    #: Durée minimale d'affichage, en millisecondes : le temps de voir l'animation.
    DUREE_MINIMALE = 2000
    #: Durée d'une ondulation complète et d'un tour complet des couleurs, en secondes.
    PERIODE_DE_L_ONDE, PERIODE_DES_COULEURS = 1.5, 2.6
    #: Hauteur du centre du logo, et taille du logo.
    MILIEU, COTE_DU_LOGO = 126, 88

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(self.LARGEUR, self.HAUTEUR)
        self.setWindowTitle(NOM_APPLICATION)
        self.setWindowIcon(icones.icone_application())
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{NOM_APPLICATION} : chargement")
        self._pret = False
        self._fini = False
        self._horloge = QElapsedTimer()
        self._horloge.start()
        self._images = QTimer(self)
        self._images.setInterval(16)
        self._images.timeout.connect(self.update)
        self._attente = QTimer(self)
        self._attente.setSingleShot(True)
        self._attente.timeout.connect(self._finir)
        ecran = QGuiApplication.primaryScreen()
        if ecran is not None:
            cadre = ecran.availableGeometry()
            self.move(cadre.x() + (cadre.width() - self.LARGEUR) // 2,
                      cadre.y() + (cadre.height() - self.HAUTEUR) // 2)

    # ------------------------------------------------------------------ déroulement
    def showEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().showEvent(evenement)
        self._images.start()

    def hideEvent(self, evenement) -> None:  # noqa: N802
        super().hideEvent(evenement)
        self._images.stop()

    def passer_la_main(self, duree_minimale: int | None = None) -> None:
        """La fenêtre principale est prête : l'écran se ferme quand il a été affiché assez longtemps."""
        self._pret = True
        duree = self.DUREE_MINIMALE if duree_minimale is None else duree_minimale
        self._attente.start(max(0, duree - self._horloge.elapsed()))

    def mousePressEvent(self, evenement) -> None:  # noqa: N802
        # Un clic ferme l'écran sans attendre, si la fenêtre principale est prête.
        if self._pret:
            self._finir()

    def _finir(self) -> None:
        if self._fini:
            return
        self._fini = True
        self._attente.stop()
        self.termine.emit()  # la fenêtre principale s'affiche avant que cet écran disparaisse
        self.close()

    # ------------------------------------------------------------------ animation
    def tirets(self, instant: float) -> list[tuple[QPointF, float, float, QColor]]:
        """Les tirets à l'instant donné (en secondes) : centre, largeur, inclinaison en degrés, couleur.

        Chaque rangée ondule comme une nageoire : presque immobile près du logo, de plus en
        plus ample vers son extrémité. Les couleurs s'éloignent du logo, d'un tiret au suivant.
        """
        resultat = []
        depart = self.COTE_DU_LOGO / 2 + 30
        pas = 25.0
        for rang in range(self.TIRETS):
            part = rang / (self.TIRETS - 1)
            amplitude = 1.5 + 10.0 * part ** 1.25
            phase = 2 * math.pi * (instant / self.PERIODE_DE_L_ONDE - rang / 9.0)
            hauteur = amplitude * math.sin(phase)
            # Le tiret suit la pente de l'onde.
            pente = -amplitude * math.cos(phase) * (2 * math.pi / 9.0) / pas
            couleur = couleur_de_la_palette(part * 0.55 - instant / self.PERIODE_DES_COULEURS)
            largeur = 16.0 - 4.0 * part
            for cote in (-1, 1):
                centre = QPointF(self.LARGEUR / 2 + cote * (depart + rang * pas), self.MILIEU + hauteur)
                resultat.append((centre, largeur, math.degrees(math.atan(pente)) * cote, couleur))
        return resultat

    def paintEvent(self, evenement) -> None:  # noqa: N802
        instant = self._horloge.elapsed() / 1000.0
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        fond = QLinearGradient(0, 0, 0, self.height())
        fond.setColorAt(0.0, QColor("#102043"))
        fond.setColorAt(1.0, QColor(theme.RAIL))
        peintre.fillRect(self.rect(), fond)
        peintre.setPen(QPen(QColor(theme.RAIL_FILET), 1))
        peintre.setBrush(Qt.BrushStyle.NoBrush)
        peintre.drawRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1))

        # Lueur dorée derrière le logo : elle respire lentement.
        centre = QPointF(self.width() / 2, self.MILIEU)
        souffle = 0.5 + 0.5 * math.sin(2 * math.pi * instant / 2.2)
        lueur = QRadialGradient(centre, 120)
        teinte = QColor(theme.OR)
        teinte.setAlphaF(0.10 + 0.10 * souffle)
        lueur.setColorAt(0.0, teinte)
        teinte.setAlphaF(0.0)
        lueur.setColorAt(1.0, teinte)
        peintre.setPen(Qt.PenStyle.NoPen)
        peintre.setBrush(lueur)
        peintre.drawEllipse(centre, 120, 120)

        # Les deux rangées de tirets.
        for position, largeur, inclinaison, couleur in self.tirets(instant):
            peintre.save()
            peintre.translate(position)
            peintre.rotate(inclinaison)
            peintre.setBrush(couleur)
            peintre.drawRoundedRect(QRectF(-largeur / 2, -2.5, largeur, 5.0), 2.5, 2.5)
            peintre.restore()

        # Le logo : la balance dorée, dans un carré arrondi.
        cote = self.COTE_DU_LOGO
        cadre = QRectF(centre.x() - cote / 2, centre.y() - cote / 2, cote, cote)
        peintre.setPen(QPen(QColor("#2B4071"), 1.25))
        peintre.setBrush(QColor(theme.RAIL_SURVOL))
        peintre.drawRoundedRect(cadre, 24, 24)
        peintre.drawPixmap(QPointF(centre.x() - 28, centre.y() - 28), icones.image("balance", "#F4C95D", 56, 1.25))

        # Le nom de l'application, puis l'état du chargement.
        largeur = self.width()
        dessiner_ligne(peintre, QRectF(0, 198, largeur, 34), NOM_APPLICATION, police(self.font(), 22, gras=True),
                       "#FFFFFF", alignement=Qt.AlignmentFlag.AlignHCenter)
        dessiner_ligne(peintre, QRectF(0, 232, largeur, 24), "Traduction juridique français – arabe",
                       police(self.font(), 13), theme.RAIL_ICONE, alignement=Qt.AlignmentFlag.AlignHCenter)
        points = "." * (1 + int(instant / 0.4) % 3)
        dessiner_ligne(peintre, QRectF(largeur / 2 - 40, self.height() - 46, 200, 22), f"Chargement{points}",
                       police(self.font(), 12), "#7F92B3", alignement=Qt.AlignmentFlag.AlignLeft)


__all__ = ["PALETTE", "EcranDemarrage", "couleur_de_la_palette"]
