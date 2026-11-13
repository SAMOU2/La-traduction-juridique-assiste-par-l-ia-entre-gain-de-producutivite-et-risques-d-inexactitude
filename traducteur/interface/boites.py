"""Boîtes de message de l'application : information, avertissement, aide.

Elles reprennent l'apparence de l'interface : une icône dans un disque, un titre, un texte
et, au pied, le bouton « OK ».
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QVBoxLayout, QWidget

from .. import NOM_APPLICATION
from . import icones, theme
from .composants import ZoneDefilante, etiquette

#: Les deux genres de boîte.
INFORMATION, ALERTE = "information", "alerte"
#: genre -> (icône, couleur de l'icône)
_ICONES = {INFORMATION: ("information", theme.BLEU), ALERTE: ("alerte", theme.AMBRE)}

#: Largeur d'une boîte, et largeur laissée au texte (à droite de l'icône).
LARGEUR = 520
LARGEUR_DU_TEXTE = LARGEUR - 2 * theme.MARGE - 40 - 16
#: Hauteur du texte au-delà de laquelle il défile, si l'écran est petit.
HAUTEUR_MINIMALE_DU_TEXTE = 200


class BoiteMessage(QDialog):
    """Boîte de message : icône, titre, texte, bouton « OK ».

    Le texte est affiché tel quel : un nom de fichier peut contenir « & » ou « < ». Un texte
    trop long pour l'écran (une liste d'erreurs, par exemple) défile dans la boîte.
    """

    def __init__(self, parent: QWidget | None, genre: str, titre: str, texte: str, *,
                 image: QPixmap | None = None) -> None:
        super().__init__(parent)
        self.genre = genre if genre in _ICONES else INFORMATION
        self.setObjectName("boite")
        self.setWindowTitle(NOM_APPLICATION)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(theme.FEUILLE_DE_STYLE + theme.STYLE_DES_BOITES)

        # ---------------------------------------------------------- icône, titre, texte
        self.signe = QLabel(self)
        self.signe.setFixedSize(40, 40)
        self.signe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image is not None:
            self.signe.setPixmap(image)
        else:
            nom_icone, couleur = _ICONES[self.genre]
            self.signe.setObjectName("rondBoite")
            self.signe.setProperty("alerte", self.genre == ALERTE)
            self.signe.setPixmap(icones.image(nom_icone, couleur, 20, 1.5))

        self.titre = etiquette(titre, "boiteTitre", retour_ligne=True)
        self.texte = etiquette(texte, "boiteTexte", retour_ligne=True, selectionnable=True)
        self.texte.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.defilement: ZoneDefilante | None = None
        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 8, 0, 0)
        colonne.setSpacing(8)
        colonne.addWidget(self.titre)
        # Les étiquettes reçoivent la feuille de style (taille des caractères) avant d'être mesurées.
        for label in (self.titre, self.texte):
            label.setParent(self)
            label.ensurePolished()
        self.titre.setFixedSize(LARGEUR_DU_TEXTE, self.titre.heightForWidth(LARGEUR_DU_TEXTE))
        ecran = self.screen() or QGuiApplication.primaryScreen()
        hauteur_de_l_ecran = ecran.availableGeometry().height() if ecran is not None else 800
        limite = max(hauteur_de_l_ecran - 300 - self.titre.height(), HAUTEUR_MINIMALE_DU_TEXTE)
        hauteur = self.texte.heightForWidth(LARGEUR_DU_TEXTE)
        if hauteur <= limite:
            self.texte.setFixedSize(LARGEUR_DU_TEXTE, hauteur)
            colonne.addWidget(self.texte)
        else:
            # La barre de défilement se pose sur le bord droit : le texte lui laisse de la place.
            reserve = theme.LARGEUR_BARRE + 6
            self.texte.setContentsMargins(0, 0, reserve, 0)
            self.texte.setFixedSize(LARGEUR_DU_TEXTE, self.texte.heightForWidth(LARGEUR_DU_TEXTE))
            self.defilement = ZoneDefilante(self)
            self.defilement.definir_contenu(self.texte)
            self.defilement.setFixedSize(LARGEUR_DU_TEXTE, limite)
            colonne.addWidget(self.defilement)
        colonne.addStretch(1)

        corps = QHBoxLayout()
        corps.setContentsMargins(theme.MARGE, theme.MARGE, theme.MARGE, theme.MARGE)
        corps.setSpacing(16)
        corps.addWidget(self.signe, 0, Qt.AlignmentFlag.AlignTop)
        corps.addLayout(colonne, 1)

        # ---------------------------------------------------------- pied : le bouton « OK »
        pied = QFrame(self)
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

        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        ensemble.addLayout(corps, 1)
        ensemble.addWidget(pied)
        # La boîte prend la taille de son contenu et ne peut pas être redimensionnée.
        ensemble.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.bouton.setFocus()


def afficher(parent: QWidget | None, genre: str, titre: str, texte: str, *, image: QPixmap | None = None) -> None:
    """Affiche une boîte de message et attend que l'utilisateur la ferme."""
    BoiteMessage(parent, genre, titre, texte, image=image).exec()
