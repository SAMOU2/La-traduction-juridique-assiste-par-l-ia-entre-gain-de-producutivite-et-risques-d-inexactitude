"""Petits composants réutilisés par les écrans : puces, étiquettes, disposition fluide."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ..langues import AR, CODE, est_rtl
from . import icones, theme

#: Marque invisible qui force l'écriture de droite à gauche d'une ligne arabe,
#: même si elle commence par un chiffre ou un mot en caractères latins.
MARQUE_RTL = "\u200F"
#: Espace sans largeur : elle autorise un retour à la ligne là où elle est placée.
ESPACE_INVISIBLE = "\u200B"

GAUCHE = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
DROITE = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute


def direction(langue: str) -> Qt.LayoutDirection:
    """Sens d'écriture d'une langue."""
    return Qt.LayoutDirection.RightToLeft if est_rtl(langue) else Qt.LayoutDirection.LeftToRight


def alignement(langue: str) -> Qt.AlignmentFlag:
    """Alignement horizontal du texte d'une langue : à droite pour l'arabe."""
    return DROITE if est_rtl(langue) else GAUCHE


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


def infobulle(texte: str) -> str:
    """Texte d'une infobulle. Les signes « < » et « & » y sont affichés tels quels."""
    return f"<qt>{escape(texte)}</qt>" if texte else ""


def pastille_langue(langue: str) -> QLabel:
    """Petite pastille « FR » ou « AR »."""
    label = QLabel(CODE[langue])
    label.setProperty("classe", "codeLangue")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return label


def puce(texte: str, classe: str = "puce", *, cochable: bool = False, info: str = "") -> QPushButton:
    """Puce cliquable (bouton arrondi)."""
    # Dans le libellé d'un bouton, « & » annonce un raccourci clavier : on le double pour l'afficher.
    bouton = QPushButton(texte.replace("&", "&&"))
    bouton.setProperty("classe", classe)
    bouton.setCheckable(cochable)
    bouton.setCursor(Qt.CursorShape.PointingHandCursor)
    bouton.setFixedHeight(theme.HAUTEUR_PUCE)
    bouton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    if cochable:
        # Une puce cochée est écrite en gras : on réserve la largeur du texte gras.
        police = QFont(bouton.font())
        police.setPixelSize(theme.TAILLE_PUCE)
        police.setWeight(QFont.Weight.DemiBold)
        bouton.setMinimumWidth(QFontMetrics(police).horizontalAdvance(texte) + 2 * theme.MARGE_PUCE + 6)
    if info:
        bouton.setToolTip(info)
    return bouton


def puce_fixe(texte: str) -> QLabel:
    """Puce non cliquable (simple étiquette arrondie)."""
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(texte)
    label.setProperty("classe", "puceFixe")
    label.setFixedHeight(theme.HAUTEUR_PUCE)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def icone_fixe(nom: str, couleur: str, taille: int = 16) -> QLabel:
    """Étiquette qui affiche une icône."""
    label = QLabel()
    label.setPixmap(icones.image(nom, couleur, taille))
    label.setFixedSize(taille, taille)
    return label


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


class DispositionFluide(QLayout):
    """Place les éléments à la suite et passe à la ligne quand la largeur manque.

    Qt ne fournit pas cette disposition ; elle sert aux rangées de puces. Les
    éléments sont posés de droite à gauche quand le sens d'écriture du parent
    est celui de l'arabe.
    """

    def __init__(self, parent: QWidget | None = None, espace_h: int = 8, espace_v: int = 8) -> None:
        super().__init__(parent)
        self._elements: list = []
        self._espace_h = espace_h
        self._espace_v = espace_v
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
        parent = self.parentWidget()
        de_droite_a_gauche = parent is not None and parent.layoutDirection() == Qt.LayoutDirection.RightToLeft
        x, y, hauteur_ligne = zone.x(), zone.y(), 0
        for element in self._elements:
            widget = element.widget()
            if widget is not None and widget.isHidden():
                continue
            taille = element.sizeHint()
            largeur = min(taille.width(), max(zone.width(), 1))
            if x > zone.x() and x + largeur > zone.right() + 1:
                x = zone.x()
                y += hauteur_ligne + self._espace_v
                hauteur_ligne = 0
            if appliquer:
                gauche = zone.x() + zone.right() + 1 - x - largeur if de_droite_a_gauche else x
                element.setGeometry(QRect(QPoint(gauche, y), QSize(largeur, taille.height())))
            x += largeur + self._espace_h
            hauteur_ligne = max(hauteur_ligne, taille.height())
        return y + hauteur_ligne - rectangle.y() + marges.bottom()


class Fleche(QWidget):
    """Trait terminé par une pointe : relie le titre d'un champ au champ suivant."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setFixedHeight(12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        if self.width() < 24:
            return
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        stylo = QPen(QColor("#C3CDDC"), 1.5)
        stylo.setCapStyle(Qt.PenCapStyle.RoundCap)
        stylo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        peintre.setPen(stylo)
        milieu = self.height() / 2
        bout = self.width() - 2
        peintre.drawLine(QPoint(2, round(milieu)), QPoint(bout, round(milieu)))
        peintre.drawLine(QPoint(bout - 5, round(milieu) - 4), QPoint(bout, round(milieu)))
        peintre.drawLine(QPoint(bout - 5, round(milieu) + 4), QPoint(bout, round(milieu)))


class LigneCliquable(QFrame):
    """Ligne sur laquelle on peut cliquer (une expression du glossaire)."""

    cliquee = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ligneExpression")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disposition = QHBoxLayout(self)
        self.disposition.setContentsMargins(4, 9, 4, 9)
        self.disposition.setSpacing(10)

    def mouseReleaseEvent(self, evenement) -> None:  # noqa: N802
        if evenement.button() == Qt.MouseButton.LeftButton and self.rect().contains(evenement.position().toPoint()):
            self.cliquee.emit()
        super().mouseReleaseEvent(evenement)


class EtiquetteCourte(QLabel):
    """Étiquette sur une seule ligne : un texte trop long est abrégé par « … ».

    Le texte complet reste disponible dans l'infobulle et par ``texte_complet``.
    L'étiquette peut aussi recevoir des formes plus courtes du même texte : elle
    affiche alors la première qui tient dans la largeur (voir ``definir_texte``).
    """

    def __init__(self, texte: str = "", classe: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        if classe:
            self.setProperty("classe", classe)
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
        return QSize(24, super().minimumSizeHint().height())

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._abreger()

    def _abreger(self) -> None:
        self.ensurePolished()
        largeur = max(self.contentsRect().width(), 0)
        metrique = self.fontMetrics()
        visible = next((forme for forme in self._formes if metrique.horizontalAdvance(forme) <= largeur), None)
        if visible is None:
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
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setProperty("classe", classe)
        self.setLayoutDirection(direction(langue))
        self.setAlignment(alignement(langue) | Qt.AlignmentFlag.AlignTop)
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


def separateur() -> QFrame:
    """Filet horizontal d'un pixel."""
    filet = QFrame()
    filet.setObjectName("separateur")
    filet.setFixedHeight(1)
    return filet
