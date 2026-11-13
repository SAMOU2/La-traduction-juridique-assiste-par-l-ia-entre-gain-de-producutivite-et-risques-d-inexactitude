"""Composants réutilisés par les écrans : étiquettes, puces, panneaux, dispositions."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from html import escape

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QBoxLayout,
    QFrame,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

from ..langues import AR, FR, deviner_langue, est_rtl
from . import dessin, icones, theme

#: Marque invisible qui force l'écriture de droite à gauche d'une ligne arabe,
#: même si elle commence par un chiffre ou un mot en caractères latins.
MARQUE_RTL = "\u200F"
#: Espace sans largeur : elle autorise un retour à la ligne là où elle est placée.
ESPACE_INVISIBLE = "\u200B"

GAUCHE = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
DROITE = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute


# ====================================================================== textes
def nombre(valeur: int) -> str:
    """Écrit un nombre à la française : 1 000."""
    return f"{valeur:,}".replace(",", "\u202f")


def compte(valeur: int, singulier: str, pluriel: str | None = None) -> str:
    """« 1 phrase », « 4 phrases », « 2 480 mots »."""
    return f"{nombre(valeur)} {singulier if valeur < 2 else (pluriel or singulier + 's')}"


def direction(langue: str) -> Qt.LayoutDirection:
    """Sens d'écriture d'une langue."""
    return Qt.LayoutDirection.RightToLeft if est_rtl(langue) else Qt.LayoutDirection.LeftToRight


def alignement(langue: str) -> Qt.AlignmentFlag:
    """Alignement horizontal du texte d'une langue : à droite pour l'arabe."""
    return DROITE if est_rtl(langue) else GAUCHE


@contextmanager
def sablier() -> Iterator[None]:
    """Affiche le pointeur d'attente pendant une opération qui peut durer (texte long).

    La fenêtre ne répond pas pendant l'opération : le pointeur le fait savoir. Il est rétabli
    dans tous les cas, même si l'opération échoue.
    """
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def infobulle(*paragraphes: str, espace: int = 6) -> str:
    """Texte d'une infobulle, en un ou plusieurs paragraphes séparés par ``espace`` pixels.

    Les signes « < » et « & » y sont affichés tels quels. Chaque paragraphe est écrit dans le
    sens de sa langue : dans une infobulle écrite de gauche à droite, une phrase arabe aurait
    son point final du mauvais côté.
    """
    paragraphes = tuple(texte for texte in paragraphes if texte)
    if not paragraphes:
        return ""
    if len(paragraphes) == 1 and deviner_langue(paragraphes[0]) != AR:
        return f"<qt>{escape(paragraphes[0])}</qt>"
    morceaux = []
    for rang, texte in enumerate(paragraphes):
        marge = f"margin: {espace if rang else 0}px 0 0 0;"
        if deviner_langue(texte) == AR:
            morceaux.append(f'<p dir="rtl" align="right" style="{marge} font-size: 14px;">'
                            f"{MARQUE_RTL}{escape(texte)}</p>")
        else:
            morceaux.append(f'<p dir="ltr" align="left" style="{marge}">{escape(texte)}</p>')
    return "<qt>" + "".join(morceaux) + "</qt>"


def paragraphe(html: str, langue: str, interligne: int, style: str = "") -> str:
    """Paragraphe HTML d'une étiquette : sens d'écriture de la langue, lignes de hauteur fixe.

    Une hauteur de ligne fixe garde des lignes régulières quand un même paragraphe mêle des
    mots français et des mots arabes, dont les caractères n'ont pas la même hauteur.
    """
    style = f"margin: 0; line-height: {interligne}px; -qt-line-height-type: fixed; {style}".strip()
    if langue == AR:
        return f'<p dir="rtl" align="right" style="{style}">{MARQUE_RTL}{html}</p>'
    return f'<p dir="ltr" align="left" style="{style}">{html}</p>'


# ====================================================================== étiquettes, puces, icônes
def etiquette(texte: str = "", classe: str = "", langue: str | None = None, *, retour_ligne: bool = False,
              selectionnable: bool = False, riche: bool = False) -> QLabel:
    """Crée une étiquette de texte.

    ``classe`` choisit son apparence dans la feuille de style ; ``langue`` fixe
    le sens d'écriture et l'alignement (à droite pour l'arabe).
    """
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText if riche else Qt.TextFormat.PlainText)
    if classe:
        label.setProperty("classe", classe)
    if langue is not None:
        label.setProperty("arabe", langue == AR)
        label.setLayoutDirection(direction(langue))
        label.setAlignment(alignement(langue) | Qt.AlignmentFlag.AlignTop)
        if langue == AR and texte and not riche:
            texte = MARQUE_RTL + texte
    label.setText(texte)
    label.setWordWrap(retour_ligne)
    if selectionnable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setCursor(Qt.CursorShape.IBeamCursor)
    return label


def capitales(texte: str, classe: str = "capitales") -> QLabel:
    """Petit titre en capitales espacées (« DOMAINE », « FRANÇAIS · SOURCE »…)."""
    label = etiquette(texte.upper(), classe)
    police = QFont(label.font())
    police.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    label.setFont(police)
    return label


def puce(texte: str, langue: str = FR, *, classe: str = "puce", hauteur: int = theme.HAUTEUR_PUCE,
         info: str = "") -> QPushButton:
    """Puce cliquable : elle ouvre une entrée du glossaire."""
    # Dans le libellé d'un bouton, « & » annonce un raccourci clavier : on le double pour l'afficher.
    bouton = QPushButton(texte.replace("&", "&&"))
    bouton.setProperty("classe", classe)
    bouton.setProperty("arabe", langue == AR)
    bouton.setCursor(Qt.CursorShape.PointingHandCursor)
    bouton.setFixedHeight(hauteur)
    bouton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    if info:
        bouton.setToolTip(info)
    return bouton


def puce_neutre(texte: str, langue: str = FR, *, hauteur: int = theme.HAUTEUR_PUCE) -> QLabel:
    """Puce non cliquable : un terme cité par le glossaire, mais qui n'y a pas d'entrée."""
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(texte)
    label.setProperty("classe", "puceNeutre")
    label.setProperty("arabe", langue == AR)
    label.setFixedHeight(hauteur)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def pastille(texte: str = "") -> QLabel:
    """Petit compteur arrondi, placé après un titre."""
    label = QLabel(texte)
    label.setProperty("classe", "pastille")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedHeight(18)
    label.setMinimumWidth(22)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def icone_fixe(nom: str, couleur: str, taille: int = 16, epaisseur: float = 1.5) -> QLabel:
    """Étiquette qui affiche une icône."""
    label = QLabel()
    label.setPixmap(icones.image(nom, couleur, taille, epaisseur))
    label.setFixedSize(taille, taille)
    return label


def rond(nom_objet: str, diametre: int, nom_icone: str, couleur: str, taille_icone: int,
         epaisseur: float = 1.5) -> QLabel:
    """Icône au centre d'un disque (la couleur du disque est donnée par la feuille de style)."""
    label = QLabel()
    label.setObjectName(nom_objet)
    label.setPixmap(icones.image(nom_icone, couleur, taille_icone, epaisseur))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setFixedSize(diametre, diametre)
    return label


def separateur(nom_objet: str = "separateur") -> QFrame:
    """Filet horizontal d'un pixel."""
    filet = QFrame()
    filet.setObjectName(nom_objet)
    filet.setFixedHeight(1)
    return filet


def espace_souple(disposition: QBoxLayout, largeur: int, minimum: int) -> None:
    """Ajoute à une ligne un espace de ``largeur`` pixels, réduit jusqu'à ``minimum`` si la place manque.

    Dans une fenêtre étroite, ou avec une police plus large que prévu, la ligne se resserre
    ainsi un peu au lieu de déborder.
    """
    disposition.addSpacing(minimum)
    disposition.addSpacerItem(QSpacerItem(largeur - minimum, 0, QSizePolicy.Policy.Maximum,
                                          QSizePolicy.Policy.Minimum))


def repeindre(widget: QWidget) -> None:
    """Applique de nouveau la feuille de style après le changement d'une propriété."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def vider(disposition: QLayout) -> None:
    """Retire et détruit tout le contenu d'une disposition."""
    while disposition.count():
        element = disposition.takeAt(0)
        widget, sous_disposition = element.widget(), element.layout()
        if widget is not None:
            widget.setParent(None)  # disparaît tout de suite de l'écran
            widget.deleteLater()
        elif sous_disposition is not None:
            vider(sous_disposition)
            sous_disposition.deleteLater()


class Numero(QWidget):
    """Numéro d'une étape, dans un disque qui peut s'allumer (voir ``animation.Allumage``)."""

    #: Marge gardée autour du disque pour le halo.
    MARGE = 6

    def __init__(self, numero: int, parent: QWidget | None = None, *, rayon: int = 10, carre: bool = False) -> None:
        super().__init__(parent)
        self.numero = numero
        self._rayon, self._carre = rayon, carre
        self.niveau, self.halo = 0.0, 0.0
        cote = 2 * (rayon + self.MARGE)
        self.setFixedSize(cote, cote)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def definir(self, niveau: float, halo: float = 0.0) -> None:
        """Fixe le niveau d'allumage (0 : éteint, 1 : allumé) et l'intensité du halo."""
        if (niveau, halo) != (self.niveau, self.halo):
            self.niveau, self.halo = niveau, halo
            self.update()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        taille = 12 if self._rayon >= 10 else 11 if self._rayon >= 9 else 10
        dessin.dessiner_numero(peintre, QPointF(self.width() / 2, self.height() / 2), self._rayon,
                               str(self.numero), dessin.police(self.font(), taille, gras=True),
                               self.niveau, self.halo, carre=self._carre)


class Interrupteur(QAbstractButton):
    """Interrupteur à deux positions (un réglage activé ou non)."""

    LARGEUR, HAUTEUR = 40, 22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(self.LARGEUR, self.HAUTEUR)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(self.LARGEUR, self.HAUTEUR)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        peintre.setPen(Qt.PenStyle.NoPen)
        peintre.setBrush(QColor(theme.BLEU if active else theme.GRIS_300))
        peintre.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), self.height() / 2, self.height() / 2)
        peintre.setBrush(QColor(theme.SURFACE))
        x = self.width() - self.height() / 2 if active else self.height() / 2
        peintre.drawEllipse(QPointF(x, self.height() / 2), self.height() / 2 - 3, self.height() / 2 - 3)
        if self.hasFocus():
            peintre.setPen(QPen(QColor(theme.BLEU_200), 2))
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            peintre.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), self.height() / 2 - 1,
                                    self.height() / 2 - 1)


# ====================================================================== panneaux
class _Angles(QWidget):
    """Calque posé sur un panneau : il redessine ses angles arrondis et son filet."""

    def __init__(self, panneau: Panneau) -> None:
        super().__init__(panneau)
        self._panneau = panneau
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        cadre = QRectF(self.rect())
        rayon = self._panneau.rayon
        dehors = QPainterPath()
        dehors.addRect(cadre)
        dedans = QPainterPath()
        dedans.addRoundedRect(cadre.adjusted(0.5, 0.5, -0.5, -0.5), rayon, rayon)
        peintre.fillPath(dehors.subtracted(dedans), QColor(theme.FOND))
        peintre.setPen(QPen(QColor(theme.FILET), 1))
        peintre.drawPath(dedans)


class Panneau(QFrame):
    """Panneau blanc à angles arrondis, bordé d'un filet.

    Le contenu peut peindre jusqu'aux bords (colonne teintée, ligne survolée…) : un calque
    posé par-dessus redessine les quatre angles et le filet. Le panneau est prévu pour être
    posé sur le fond de la fenêtre.
    """

    def __init__(self, parent: QWidget | None = None, *, rayon: int = theme.RAYON) -> None:
        super().__init__(parent)
        self.rayon = rayon
        self._angles = _Angles(self)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        QPainter(self).fillRect(self.rect(), QColor(theme.SURFACE))

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._angles.setGeometry(self.rect())
        self._angles.raise_()

    def showEvent(self, evenement) -> None:  # noqa: N802
        super().showEvent(evenement)
        self._angles.raise_()


class ZoneDefilante(QScrollArea):
    """Zone à défilement vertical, sans cadre ni fond.

    La barre de défilement est posée par-dessus le bord droit du contenu, et n'apparaît que
    s'il y a quelque chose à faire défiler : la largeur du contenu ne change donc jamais.
    Le contenu doit garder une marge à droite, où la barre vient se placer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("zoneDefilante")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # La barre de Qt reste cachée (elle prendrait de la largeur) ; « barre » la remplace à l'écran.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)
        self.barre = QScrollBar(Qt.Orientation.Vertical, self)
        self.barre.setCursor(Qt.CursorShape.ArrowCursor)
        self.barre.hide()
        interne = self.verticalScrollBar()
        interne.rangeChanged.connect(self._synchroniser)
        interne.valueChanged.connect(self.barre.setValue)
        self.barre.valueChanged.connect(interne.setValue)

    def definir_contenu(self, contenu: QWidget) -> None:
        self.setWidget(contenu)
        contenu.setAutoFillBackground(False)  # Qt donne un fond au contenu d'une zone défilante

    def revenir_en_haut(self) -> None:
        self.verticalScrollBar().setValue(0)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self.barre.setGeometry(self.width() - theme.LARGEUR_BARRE, 0, theme.LARGEUR_BARRE, self.height())
        self._synchroniser()

    def _synchroniser(self, *_) -> None:
        interne = self.verticalScrollBar()
        self.barre.setRange(interne.minimum(), interne.maximum())
        self.barre.setPageStep(interne.pageStep())
        self.barre.setSingleStep(interne.singleStep())
        self.barre.setValue(interne.value())
        self.barre.setVisible(interne.maximum() > interne.minimum())
        self.barre.raise_()


# ====================================================================== dispositions
class DispositionFluide(QLayout):
    """Place les éléments à la suite et passe à la ligne quand la largeur manque.

    Qt ne fournit pas cette disposition ; elle sert aux rangées de puces. Les
    éléments sont posés de droite à gauche quand le sens d'écriture du parent
    est celui de l'arabe. Avec ``centre``, chaque ligne est centrée.
    """

    def __init__(self, parent: QWidget | None = None, espace_h: int = 6, espace_v: int = 6, *,
                 centre: bool = False) -> None:
        super().__init__(parent)
        self._elements: list = []
        self._espace_h = espace_h
        self._espace_v = espace_v
        self._centre = centre
        self.setContentsMargins(0, 0, 0, 0)

    # --- méthodes demandées par Qt -------------------------------------------------
    def addItem(self, element) -> None:  # noqa: N802 (nom imposé par Qt)
        self._elements.append(element)

    def count(self) -> int:
        return len(self._elements)

    def itemAt(self, index: int):  # noqa: N802
        return self._elements[index] if 0 <= index < len(self._elements) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._elements.pop(index) if 0 <= index < len(self._elements) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, largeur: int) -> int:  # noqa: N802
        return self._disposer(QRect(0, 0, largeur, 0), appliquer=False)

    def setGeometry(self, rectangle: QRect) -> None:  # noqa: N802
        super().setGeometry(rectangle)
        self._disposer(rectangle, appliquer=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        # Largeur minimale volontairement faible : un élément plus large que la
        # place disponible est rogné au lieu d'élargir tout le contenu.
        hauteur = max((element.minimumSize().height() for element in self._elements), default=0)
        marges = self.contentsMargins()
        return QSize(48 + marges.left() + marges.right(), hauteur + marges.top() + marges.bottom())

    # --- calcul des positions ---------------------------------------------------------
    def _disposer(self, rectangle: QRect, appliquer: bool) -> int:
        marges = self.contentsMargins()
        zone = rectangle.adjusted(marges.left(), marges.top(), -marges.right(), -marges.bottom())
        largeur_zone = max(zone.width(), 1)
        parent = self.parentWidget()
        de_droite_a_gauche = parent is not None and parent.layoutDirection() == Qt.LayoutDirection.RightToLeft

        # 1. Répartition des éléments en lignes.
        lignes: list[list[tuple[object, QSize]]] = []
        occupe = 0
        for element in self._elements:
            widget = element.widget()
            if widget is not None and widget.isHidden():
                continue
            taille = element.sizeHint()
            largeur = min(taille.width(), largeur_zone)
            if not lignes or occupe + self._espace_h + largeur > largeur_zone:
                lignes.append([])
                occupe = 0
            occupe += (self._espace_h if lignes[-1] else 0) + largeur
            lignes[-1].append((element, QSize(largeur, taille.height())))

        # 2. Position de chaque ligne.
        y = zone.y()
        for ligne in lignes:
            hauteur = max(taille.height() for _, taille in ligne)
            if appliquer:
                largeur_ligne = sum(taille.width() for _, taille in ligne) + self._espace_h * (len(ligne) - 1)
                x = zone.x() + ((largeur_zone - largeur_ligne) // 2 if self._centre else 0)
                for element, taille in ligne:
                    gauche = zone.x() + zone.right() + 1 - x - taille.width() if de_droite_a_gauche else x
                    element.setGeometry(QRect(QPoint(gauche, y + (hauteur - taille.height()) // 2), taille))
                    x += taille.width() + self._espace_h
            y += hauteur + self._espace_v
        if lignes:
            y -= self._espace_v
        return y - rectangle.y() + marges.bottom()


def bornes_des_colonnes(largeur: int, proportions: Sequence[int]) -> list[int]:
    """Abscisses des bords de colonnes de largeurs proportionnelles, de 0 à ``largeur``."""
    total = sum(proportions)
    bornes, cumul = [0], 0
    for proportion in proportions:
        cumul += proportion
        bornes.append(round(largeur * cumul / total))
    return bornes


class DispositionColonnes(QLayout):
    """Place les éléments côte à côte, dans des colonnes de largeurs proportionnelles.

    Les colonnes ne dépendent que de la largeur totale : deux dispositions de mêmes
    proportions et de même largeur (le corps et le pied de la fiche, par exemple) sont
    donc alignées.
    """

    def __init__(self, parent: QWidget | None, proportions: Sequence[int]) -> None:
        super().__init__(parent)
        self._elements: list = []
        self._proportions = tuple(proportions)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(0)

    def addItem(self, element) -> None:  # noqa: N802 (nom imposé par Qt)
        self._elements.append(element)

    def count(self) -> int:
        return len(self._elements)

    def itemAt(self, index: int):  # noqa: N802
        return self._elements[index] if 0 <= index < len(self._elements) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._elements.pop(index) if 0 <= index < len(self._elements) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, largeur: int) -> int:  # noqa: N802
        bornes = bornes_des_colonnes(largeur, self._proportions)
        hauteur = 0
        for rang, element in enumerate(self._elements[:len(self._proportions)]):
            colonne = max(bornes[rang + 1] - bornes[rang], 1)
            hauteur = max(hauteur, element.heightForWidth(colonne) if element.hasHeightForWidth()
                          else element.sizeHint().height())
        return hauteur

    def setGeometry(self, rectangle: QRect) -> None:  # noqa: N802
        super().setGeometry(rectangle)
        bornes = bornes_des_colonnes(rectangle.width(), self._proportions)
        for rang, element in enumerate(self._elements[:len(self._proportions)]):
            element.setGeometry(QRect(rectangle.x() + bornes[rang], rectangle.y(),
                                      max(bornes[rang + 1] - bornes[rang], 1), rectangle.height()))

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        hauteur = max((element.minimumSize().height() for element in self._elements), default=0)
        return QSize(48 * len(self._proportions), hauteur)


# ====================================================================== étiquettes ajustées
class EtiquetteCourte(QLabel):
    """Étiquette sur une seule ligne : un texte trop long est abrégé par « … ».

    Le texte complet reste disponible dans l'infobulle et par ``texte_complet``.
    L'étiquette peut aussi recevoir des formes plus courtes du même texte : elle
    affiche alors la première qui tient dans la largeur (voir ``definir_texte``).
    Avec ``par_le_debut``, c'est le début du texte qui est abrégé, mot par mot.
    Avec ``forme_minimale``, la forme la plus courte n'est jamais abrégée : sa largeur est
    la largeur minimale de l'étiquette.
    """

    def __init__(self, texte: str = "", classe: str = "", parent: QWidget | None = None, *,
                 par_le_debut: bool = False, forme_minimale: bool = False) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        if classe:
            self.setProperty("classe", classe)
        self._par_le_debut = par_le_debut
        self._forme_minimale = forme_minimale
        self._formes: tuple[str, ...] = (texte,)
        self._abreger()

    def texte_complet(self) -> str:
        return self._formes[0]

    def definir_texte(self, texte: str, *formes_courtes: str) -> None:
        """Change le texte de l'étiquette.

        ``formes_courtes`` donne des textes plus courts, essayés dans l'ordre quand
        le texte complet ne tient pas dans la largeur : « 83 mots trouvés sur 84 »,
        puis « 83 sur 84 ». Si aucune forme ne tient, la dernière est abrégée par
        « … » ; une dernière forme vide permet de ne rien afficher.
        """
        formes = (texte, *formes_courtes)
        if formes != self._formes:
            self._formes = formes
            self._abreger()
            self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802
        self.ensurePolished()
        marges = self.contentsMargins()
        largeur = self.fontMetrics().horizontalAdvance(self._formes[0]) + marges.left() + marges.right() + 4
        return QSize(largeur, super().sizeHint().height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        if self._formes[-1] == "":
            largeur = 0
        elif self._forme_minimale:
            self.ensurePolished()
            marges = self.contentsMargins()
            largeur = self.fontMetrics().horizontalAdvance(self._formes[-1]) + marges.left() + marges.right() + 2
        else:
            largeur = 24
        return QSize(largeur, super().minimumSizeHint().height())

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._abreger()

    def _abreger(self) -> None:
        self.ensurePolished()
        largeur = max(self.contentsRect().width(), 0)
        metrique = self.fontMetrics()
        visible = next((forme for forme in self._formes if metrique.horizontalAdvance(forme) <= largeur), None)
        if visible is None and self._par_le_debut:
            visible = dessin.abreger(self._formes[-1], self.font(), largeur, par_le_debut=True)
        elif visible is None:
            visible = metrique.elidedText(self._formes[-1], Qt.TextElideMode.ElideRight, largeur)
        if visible != self.text():
            self.setText(visible)
        self.setToolTip(infobulle(self._formes[0]) if visible != self._formes[0] else "")


class TermeAjuste(QLabel):
    """Terme affiché en grand : la taille des caractères diminue quand la largeur manque.

    Qt ne coupe pas un mot en fin de ligne : on réduit donc les caractères
    jusqu'à ce que le mot le plus long tienne dans la largeur disponible. Si un
    mot ne tient toujours pas à la plus petite taille, on autorise sa coupure
    (voir ``_afficher``).
    """

    def __init__(self, texte: str, classe: str, langue: str, taille_max: int, taille_min: int,
                 parent: QWidget | None = None, *, centre: bool = False) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setProperty("classe", classe)
        self.setLayoutDirection(direction(langue))
        horizontal = Qt.AlignmentFlag.AlignHCenter if centre else alignement(langue)
        self.setAlignment(horizontal | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        #: Le terme, tel qu'il figure dans le glossaire.
        self.terme = texte
        self._langue = langue
        self._taille_max, self._taille_min = taille_max, min(taille_min, taille_max)
        self.taille = 0
        self._appliquer(taille_max)
        self._afficher(frozenset())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(48, super().minimumSizeHint().height())

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._ajuster()

    def _appliquer(self, taille: int) -> None:
        if taille != self.taille:
            self.taille = taille
            self.setStyleSheet(f"font-size: {taille}px;")

    def _mots_trop_larges(self, taille: int) -> frozenset[str]:
        """Mots du terme plus larges que la place disponible, pour une taille de caractères."""
        police = QFont(self.font())
        police.setPixelSize(taille)
        metrique = QFontMetricsF(police)
        largeur = self.contentsRect().width()
        return frozenset(mot for mot in self.terme.split() if metrique.horizontalAdvance(mot) > largeur)

    def _ajuster(self) -> None:
        self.ensurePolished()
        taille = self._taille_max
        while taille > self._taille_min and self._mots_trop_larges(taille):
            taille -= 1
        self._appliquer(taille)
        self._afficher(self._mots_trop_larges(taille))

    def _afficher(self, a_couper: frozenset[str]) -> None:
        """Écrit le terme ; les mots de ``a_couper`` peuvent être coupés en fin de ligne.

        La coupure passe par des espaces invisibles glissées entre les lettres.
        Le terme n'est alors plus sélectionnable à la souris, pour que ces
        espaces ne soient pas copiées avec lui. Un mot arabe n'est jamais
        coupé : ses lettres sont liées.
        """
        if self._langue == AR:
            a_couper = frozenset()
        mots = [ESPACE_INVISIBLE.join(mot) if mot in a_couper else mot for mot in self.terme.split()]
        self.setText((MARQUE_RTL if self._langue == AR else "") + " ".join(mots))
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction if a_couper
                                     else Qt.TextInteractionFlag.TextSelectableByMouse)
