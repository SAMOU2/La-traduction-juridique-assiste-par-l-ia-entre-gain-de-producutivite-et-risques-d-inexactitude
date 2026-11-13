"""Boîtes de message de l'application : information, avertissement, aide.

Elles reprennent l'apparence de l'interface : une icône dans un disque, un titre, un texte
et, au pied, le bouton « OK ».
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from . import icones, theme
from .composants import etiquette

#: Les deux genres de boîte : genre -> (icône, couleur de l'icône).
INFORMATION, ALERTE = "information", "alerte"
_ICONES = {INFORMATION: ("information", theme.BLEU), ALERTE: ("alerte", theme.AMBRE)}

LARGEUR = 520
LARGEUR_DU_TEXTE = LARGEUR - 2 * theme.MARGE - 40 - 16


class BoiteMessage(QDialog):
    """Boîte de message : icône, titre, texte, bouton « OK ».

    Le texte est affiché tel quel (un nom de fichier peut contenir « & » ou « < »), sauf si
    ``riche`` est vrai : il est alors lu comme du HTML.
    """

    def __init__(self, parent: QWidget | None, genre: str, titre: str, texte: str, *,
                 image: QPixmap | None = None, riche: bool = False) -> None:
        super().__init__(parent)
        self.genre = genre if genre in _ICONES else INFORMATION
        self.setObjectName("boite")
        self.setWindowTitle(titre)
        self.setModal(True)
        self.setStyleSheet(theme.FEUILLE_DE_STYLE + theme.STYLE_DES_BOITES)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        corps = QHBoxLayout()
        corps.setContentsMargins(theme.MARGE, theme.MARGE, theme.MARGE, theme.MARGE)
        corps.setSpacing(16)
        self.signe = QLabel()
        self.signe.setFixedSize(40, 40)
        self.signe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image is not None:
            self.signe.setPixmap(image)
        else:
            nom_icone, couleur = _ICONES[self.genre]
            self.signe.setObjectName("rondBoite")
            self.signe.setProperty("alerte", self.genre == ALERTE)
            self.signe.setPixmap(icones.image(nom_icone, couleur, 20, 1.5))
        corps.addWidget(self.signe, 0, Qt.AlignmentFlag.AlignTop)

        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 2, 0, 0)
        colonne.setSpacing(8)
        self.titre = etiquette(titre, "boiteTitre", retour_ligne=True)
        self.titre.setFixedWidth(LARGEUR_DU_TEXTE)
        colonne.addWidget(self.titre)
        self.texte = etiquette(texte, "boiteTexte", retour_ligne=True, riche=riche)
        self.texte.setFixedWidth(LARGEUR_DU_TEXTE)
        self.texte.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.texte.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                           | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.texte.setOpenExternalLinks(True)
        # Un texte très long (une liste d'erreurs, par exemple) défile au lieu d'agrandir la boîte sans limite.
        hauteur_du_texte = self.texte.heightForWidth(LARGEUR_DU_TEXTE)
        ecran = QGuiApplication.primaryScreen()
        limite = max(int((ecran.availableGeometry().height() if ecran else 800) * 0.6), 240)
        if hauteur_du_texte > limite:
            defilement = QScrollArea()
            defilement.setObjectName("zoneDefilante")
            defilement.setFrameShape(QFrame.Shape.NoFrame)
            defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            defilement.setWidgetResizable(False)
            defilement.viewport().setAutoFillBackground(False)
            self.texte.setFixedHeight(hauteur_du_texte)
            self.texte.setAutoFillBackground(False)
            defilement.setWidget(self.texte)
            defilement.setFixedSize(LARGEUR_DU_TEXTE + theme.LARGEUR_BARRE + 2, limite)
            colonne.addWidget(defilement)
        else:
            self.texte.setFixedHeight(hauteur_du_texte)
            colonne.addWidget(self.texte)
        colonne.addStretch(1)
        corps.addLayout(colonne, 1)
        ensemble.addLayout(corps, 1)

        pied = QFrame()
        pied.setObjectName("piedBoite")
        pied.setFixedHeight(58)
        dans_le_pied = QHBoxLayout(pied)
        dans_le_pied.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        dans_le_pied.addStretch(1)
        self.bouton = QPushButton("OK")
        self.bouton.setProperty("classe", "principal")
        self.bouton.setFixedSize(96, 34)
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton.setDefault(True)
        self.bouton.clicked.connect(self.accept)
        dans_le_pied.addWidget(self.bouton)
        ensemble.addWidget(pied)
        self.setFixedWidth(max(LARGEUR, ensemble.sizeHint().width()))
        self.setFixedHeight(ensemble.sizeHint().height())


def afficher(parent: QWidget | None, genre: str, titre: str, texte: str, *, image: QPixmap | None = None,
             riche: bool = False) -> None:
    """Affiche une boîte de message et attend que l'utilisateur la ferme."""
    BoiteMessage(parent, genre, titre, texte, image=image, riche=riche).exec()
