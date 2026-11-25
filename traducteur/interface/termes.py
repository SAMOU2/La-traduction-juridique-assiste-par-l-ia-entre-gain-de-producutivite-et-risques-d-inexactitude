"""Termes juridiques d'un texte : la liste placée sous le texte et sa traduction, sur l'écran « Texte ».

Chaque terme du glossaire relevé dans le texte a une case : le terme français à gauche, le terme
arabe à droite. Un clic sur une case ouvre la fiche du terme sur l'écran « Terme », où le menu
« Plus de détails » donne sa définition, ses exemples et ses références.

Une case peut être allumée : l'écran « Texte » allume celle du terme que le pointeur désigne, que
le pointeur soit sur la case ou sur le terme, dans le texte ou dans sa traduction.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ..glossaire import Entree, equivalent_a_verifier
from ..traduction import TermeDetecte, Traduction
from . import icones, theme
from .composants import (
    EtiquetteCourte,
    Panneau,
    ZoneDefilante,
    compte,
    etiquette,
    infobulle,
    nombre,
    pastille,
    separateur,
)
from .dessin import abreger, dessiner_ligne, police
from .fiche import CelluleEntree, GrilleEntrees


# ====================================================================== la case d'un terme
class CelluleTerme(CelluleEntree):
    """La case d'un terme relevé dans le texte : son entrée du glossaire, et ce que le texte en dit.

    L'infobulle donne le nombre d'occurrences du terme, et dit si son équivalent est à vérifier.
    Quand le terme a plusieurs sens dans le glossaire et que le contexte n'a pas permis de
    choisir, un signe orange précède le terme.
    """

    #: Le pointeur entre dans la case (le signal porte son entrée du glossaire) ou en sort (``None``).
    survol = Signal(object)

    #: Place du signe orange, devant le terme.
    LARGEUR_DU_SIGNE = 20

    def __init__(self, terme: TermeDetecte, cible: str, parent: QWidget | None = None) -> None:
        super().__init__(terme.entree, parent)
        #: Le terme relevé, avec toutes ses occurrences dans le texte.
        self.detecte = terme
        self.occurrences = compte(len(terme.occurrences), "occurrence")
        #: Vrai si le contexte n'a pas permis de choisir entre plusieurs sens du terme.
        self.incertain = terme.incertain
        autres = " / ".join(autre.terme(cible) for autre in terme.autres_candidats)
        #: Avertissement sur les autres sens du terme (vide s'il n'en a qu'un).
        self.alerte = "" if not autres else (f"Ambigu : aussi « {autres} »" if terme.incertain
                                             else f"Autre sens : « {autres} »")
        #: Vrai si le glossaire donne l'équivalent de ce terme comme « à vérifier » : c'est le cas de tous les
        #: termes du glossaire fourni (colonne « source_equivalent », version 0.16).
        self.a_verifier = equivalent_a_verifier(terme.entree) is not None
        self.retrait = self.LARGEUR_DU_SIGNE if self.incertain else 0
        self.setAccessibleDescription(". ".join(morceau for morceau in (
            self.occurrences, self.alerte, "Équivalent à vérifier" if self.a_verifier else "") if morceau))

    def ajuster(self) -> None:
        super().ajuster()
        lignes = [f"{self.entree.terme_fr} — {self.entree.terme_ar}", f"{self.occurrences} dans le texte."]
        if self.incertain:
            lignes.append(f"{self.alerte}. Le contexte n’a pas permis de choisir entre les sens de ce terme : "
                          "vérifiez l’équivalent.")
        elif self.alerte:
            lignes.append(f"{self.alerte}. Ce terme a d’autres sens dans le glossaire.")
        if self.a_verifier:
            lignes.append("Équivalent à vérifier : il n’est repris d’aucune source citée.")
        self.setToolTip(infobulle(*lignes))

    def enterEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().enterEvent(evenement)
        self.survol.emit(self.entree)

    def leaveEvent(self, evenement) -> None:  # noqa: N802
        super().leaveEvent(evenement)
        self.survol.emit(None)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        super().paintEvent(evenement)
        if self.incertain:
            peintre = QPainter(self)
            peintre.drawPixmap(QPointF(self.marge_gauche, (self.height() - 14) / 2),
                               icones.image("alerte", theme.AMBRE, 14, 1.6))


# ====================================================================== message d'un panneau vide
class MessageVide(QWidget):
    """Message centré, affiché à la place des termes quand il n'y en a aucun à montrer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.titre = self.texte = ""

    def definir(self, titre: str, texte: str) -> None:
        self.titre, self.texte = titre, texte
        self.setAccessibleName(titre)
        self.setAccessibleDescription(texte)
        self.update()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        du_titre, du_texte = police(self.font(), 13, gras=True), police(self.font(), 13)
        place = self.width() - 2 * theme.MARGE
        avec_disque = self.height() >= 124
        hauteur = (40 + 14 if avec_disque else 0) + 20 + 4 + 20
        y = max((self.height() - hauteur) / 2 - (4 if avec_disque else 0), 2)
        if avec_disque:
            centre = QPointF(self.width() / 2, y + 20)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_100))
            peintre.drawEllipse(centre, 20, 20)
            peintre.drawPixmap(QPointF(centre.x() - 9, centre.y() - 9), icones.image("texte", theme.TEXTE_4, 18))
            y += 54
        centre_h = Qt.AlignmentFlag.AlignHCenter
        dessiner_ligne(peintre, QRectF(theme.MARGE, y, place, 20), abreger(self.titre, du_titre, place),
                       du_titre, theme.TEXTE_2, alignement=centre_h)
        dessiner_ligne(peintre, QRectF(theme.MARGE, y + 24, place, 20), abreger(self.texte, du_texte, place),
                       du_texte, theme.TEXTE_3, alignement=centre_h)


# ====================================================================== le panneau
class PanneauTermes(Panneau):
    """Les termes du glossaire relevés dans le texte : une case par terme, sous le texte et sa traduction."""

    #: Demande d'ouverture de la fiche d'une entrée sur l'écran « Terme » (clic sur une case).
    ouverture = Signal(object)
    #: Le pointeur est entré dans la case d'une entrée (le signal porte l'entrée) ou en est sorti (``None``).
    survol = Signal(object)

    HAUTEUR_DU_TITRE = 42
    #: Hauteur du message affiché quand il n'y a aucun terme à montrer.
    HAUTEUR_DU_MESSAGE = 58
    #: Espace laissé sous la dernière ligne.
    MARGE_BASSE = 4
    #: Part de la hauteur de l'écran que les termes peuvent occuper ; au-delà, la liste défile.
    PART_DE_L_ECRAN = 0.36

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        titre = QWidget()
        titre.setFixedHeight(self.HAUTEUR_DU_TITRE)
        ligne = QHBoxLayout(titre)
        ligne.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        ligne.setSpacing(10)
        self.titre = etiquette("Termes juridiques détectés", "titrePanneau")
        self.nombre = pastille()
        self.aide = EtiquetteCourte("", "aidePanneau")
        self.aide.definir_texte("Cliquez sur un terme pour ouvrir sa fiche", "Cliquez sur un terme", "")
        self.aide.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ligne.addWidget(self.titre)
        ligne.addWidget(self.nombre)
        ligne.addWidget(self.aide, 1)
        ensemble.addWidget(titre)
        ensemble.addWidget(separateur())

        self.grille = GrilleEntrees()
        self.grille.ouverture.connect(self.ouverture)
        self.defilement = ZoneDefilante()
        self.defilement.definir_contenu(self.grille)
        ensemble.addWidget(self.defilement, 1)
        self.message = MessageVide()
        ensemble.addWidget(self.message, 1)
        self.afficher(None)

    # ------------------------------------------------------------------ contenu
    def afficher(self, traduction: Traduction | None, *, sans_glossaire: bool = False) -> None:
        """Affiche les termes relevés par une traduction ; sans traduction, un message d'attente."""
        termes = traduction.termes if traduction is not None else []
        cible = traduction.cible if traduction is not None else ""
        self.grille.definir(termes, lambda terme, parent: CelluleTerme(terme, cible, parent))
        for cellule in self.grille.cellules:
            cellule.survol.connect(self.survol)
        if sans_glossaire:
            self.message.definir("Aucun glossaire n’est chargé", "Choisissez un fichier CSV dans « Paramètres ».")
        elif traduction is None:
            self.message.definir("Les termes juridiques du texte s’afficheront ici",
                                 "Saisissez ou importez un texte, puis cliquez sur « Traduire ».")
        else:
            self.message.definir("Aucun terme du glossaire dans ce texte",
                                 "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
        self.nombre.setText(nombre(len(termes)))
        self.nombre.setVisible(traduction is not None)
        self.aide.setVisible(bool(termes))
        self.defilement.setVisible(bool(termes))
        self.message.setVisible(not termes)
        self.defilement.revenir_en_haut()

    @property
    def cellules(self) -> list[CelluleTerme]:
        """Les cases, dans l'ordre d'apparition des termes dans le texte."""
        return list(self.grille.cellules)

    def cellule_de(self, entree: Entree) -> CelluleTerme | None:
        return next((cellule for cellule in self.grille.cellules if cellule.entree is entree), None)

    def allumer(self, entree: Entree | None) -> None:
        """Allume la case d'une entrée et éteint les autres (``None`` : les éteint toutes). Rien ne défile."""
        for cellule in self.grille.cellules:
            cellule.definir_allumee(cellule.entree is entree)

    # ------------------------------------------------------------------ hauteur
    def hauteur_pour(self, largeur: int, hauteur_de_l_ecran: int) -> int:
        """Hauteur du panneau : le titre, puis les lignes de termes dans la limite d'une part de l'écran."""
        if not self.grille.cellules:
            return self.HAUTEUR_DU_TITRE + 1 + self.HAUTEUR_DU_MESSAGE
        ligne = GrilleEntrees.HAUTEUR_DE_LIGNE
        fixe = self.HAUTEUR_DU_TITRE + 1 + self.MARGE_BASSE
        permises = max(1, (round(hauteur_de_l_ecran * self.PART_DE_L_ECRAN) - fixe) // ligne)
        return fixe + min(self.grille.rangees(largeur), permises) * ligne


__all__ = ["CelluleTerme", "MessageVide", "PanneauTermes"]
