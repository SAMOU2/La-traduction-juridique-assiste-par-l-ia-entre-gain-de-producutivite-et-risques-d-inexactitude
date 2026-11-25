"""Écran « Texte » : traduction d'un texte à l'aide du glossaire.

Le texte source et sa traduction sont côte à côte. Dessous, la liste des termes du glossaire
relevés dans le texte (voir ``termes.py``). Un clic sur un terme, dans la liste ou dans l'un
des deux textes, ouvre sa fiche sur l'écran « Terme ».

Le terme que le pointeur désigne s'allume partout où il figure : il prend un fond dans le texte,
dans la traduction et dans la liste (voir ``PageTexte.allumer``).

Les cinq étapes du traitement et leur résultat ne sont pas affichés en permanence : un clic
sur l'état de la traduction les ouvre dans une petite fenêtre (``VoletEtapes``).

Les boutons « Importer », « Exporter » et « Traduire » appartiennent à cet écran ; la
fenêtre les place dans la barre d'outils.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from types import MappingProxyType

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .. import documents
from ..glossaire import Entree, Glossaire
from ..langues import (
    AR,
    FR,
    NOM_EN_FRANCAIS,
    NOM_NATIF,
    autre_langue,
    contient_arabe,
    contient_latin,
    deviner_langue,
)
from ..segmentation import compter
from ..traduction import SOURCE, TERME, Traducteur, Traduction
from . import boites, icones, theme
from .animation import Allumage
from .composants import (
    MARQUE_RTL,
    BoutonAjuste,
    EtiquetteCourte,
    Panneau,
    compte,
    direction,
    espace_souple,
    etiquette,
    icone_fixe,
    infobulle,
    nombre,
    repeindre,
    sablier,
    separateur,
)
from .dessin import abreger, dessiner_ligne, dessiner_numero, largeur_du_texte, melanger, police
from .termes import CelluleTerme, PanneauTermes

#: Texte proposé par « Insérer un exemple » : les articles 106 et 107 du Code civil (phrases reprises
#: des exemples du glossaire fourni), puis une phrase qui n'y figure pas, traduite mot à mot.
EXEMPLES = {
    FR: ("Le contrat fait la loi des parties. Il ne peut être révoqué, ni modifié que de leur consentement mutuel "
         "ou pour les causes prévues par la loi. Le contrat doit être exécuté conformément à son contenu, et de "
         "bonne foi. Il oblige le contractant, non seulement à ce qui y est exprimé, mais encore à tout ce que la "
         "loi, l’usage et l’équité considèrent comme une suite nécessaire de ce contrat d’après la nature de "
         "l’obligation.\nLa nullité du contrat de vente protège l’acheteur."),
    AR: ("العقد شريعة المتعاقدين. فلا يجوز نقضه، ولا تعديله إلا باتفاق الطرفين، أو للأسباب التي يقررها القانون. "
         "يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية. ولا يقتصر العقد على إلزام المتعاقد بما ورد فيه فحسب، "
         "بل يتناول أيضا ما هو من مستلزماته وفقا للقانون، والعرف، والعدالة، بحسب طبيعة الالتزام.\n"
         "بطلان عقد البيع يحمي المشتري."),
}

_ROLES = {"source": "texte source", "cible": "traduction"}
#: Textes gris des zones vides, écrits dans la langue de la zone (une phrase française écrite
#: de droite à gauche aurait son point final du mauvais côté).
_INVITES = {
    FR: "Saisissez, collez ou importez le texte à traduire…",
    AR: "أدخل النص المراد ترجمته أو الصقه أو استورده...",
}
_INVITES_CIBLE = {FR: "La traduction s’affichera ici.", AR: "ستظهر الترجمة هنا."}
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : choisissez un fichier CSV dans « Paramètres »."
_TEXTE_MODIFIE = "Le texte source a changé : cliquez sur « Traduire » pour mettre la traduction à jour."
#: Rappelé sous les états « Traduction terminée » et « Traduction partielle ».
_A_RELIRE = "Le traducteur ne connaît que les termes du glossaire : relisez et complétez la traduction."
#: Ajouté à l'infobulle de l'état de la traduction : un clic ouvre le détail du traitement.
_VOIR_LES_ETAPES = "Cliquez pour voir les étapes du traitement."

#: Les cinq étapes du traitement : (nom, nom court, ce que fait l'étape).
ETAPES = (
    ("Segmentation", "Segmentation", "Le texte est découpé en phrases."),
    ("Découpage", "Découpage", "Chaque phrase est découpée en mots."),
    ("Recherche dans le glossaire", "Recherche",
     "Les phrases, puis les expressions, puis les mots sont cherchés dans le glossaire."),
    ("Règles linguistiques", "Règles",
     "Lexique, grammaire, sémantique : synonymes, pluriel, article, complément du nom, choix entre plusieurs sens."),
    ("Reconstruction", "Reconstruction", "Chaque phrase est récrite dans la langue cible, avec sa ponctuation."),
)
#: Hauteur d'une ligne des zones de texte, en pixels, selon la langue. Une hauteur fixe garde des
#: lignes régulières quand une même ligne mêle des mots français et des mots arabes.
INTERLIGNE = {FR: 26, AR: 32}
#: Espace entre deux paragraphes des zones de texte.
ESPACE_ENTRE_PARAGRAPHES = 8
#: Couleur des termes du glossaire, et couleur des mots absents du glossaire, dans les deux zones de texte.
COULEUR_TERME = theme.BLEU
COULEUR_ABSENT = theme.TEXTE_4
#: Le terme allumé (celui que le pointeur désigne), dans les deux zones de texte : son fond, sa couleur.
FOND_ALLUME = theme.FOND_TERME_ALLUME
COULEUR_ALLUME = theme.TERME_ALLUME


def _decompte(phrases: int, mots: int, caracteres: int) -> tuple[str, str, str]:
    """Décompte d'un texte, du plus long au plus court : « 4 phrases · 76 mots · 422 caractères », …, « 76 mots »."""
    elements = (compte(phrases, "phrase"), compte(mots, "mot"), compte(caracteres, "caractère"))
    return " · ".join(elements), " · ".join(elements[:2]), elements[1]


def _bouton(texte: str, classe: str, largeur: int, hauteur: int, nom_icone: str = "", info: str = "") -> QPushButton:
    """Bouton de l'écran : « principal » (plein) ou « contour »."""
    bouton = BoutonAjuste(texte, largeur, hauteur)
    bouton.setProperty("classe", classe)
    if nom_icone:
        couleur = theme.SURFACE if classe == "principal" else theme.TEXTE_2
        bouton.setIcon(icones.icone(nom_icone, couleur, 16, 1.6, marge=3,
                                    couleur_inactive=theme.SURFACE if classe == "principal" else theme.TEXTE_4))
        bouton.setIconSize(QSize(19, 16))
    bouton.setCursor(Qt.CursorShape.PointingHandCursor)
    if info:
        bouton.setToolTip(info)
    return bouton


def _mise_en_forme(couleur: str, fond: str = "") -> QTextCharFormat:
    """Couleur, et fond s'il y en a un, à donner à un passage d'une zone de texte."""
    mise_en_forme = QTextCharFormat()
    mise_en_forme.setForeground(QColor(couleur))
    if fond:
        mise_en_forme.setBackground(QColor(fond))
    return mise_en_forme


def _passage(zone: QTextEdit, debut: int, fin: int, mise_en_forme: QTextCharFormat) -> QTextEdit.ExtraSelection:
    """Passage d'une zone de texte à afficher avec une mise en forme ; le texte lui-même n'est pas modifié."""
    curseur = QTextCursor(zone.document())
    curseur.setPosition(debut)
    curseur.setPosition(fin, QTextCursor.MoveMode.KeepAnchor)
    passage = QTextEdit.ExtraSelection()
    passage.cursor = curseur
    passage.format = mise_en_forme
    return passage


# ====================================================================== zones de texte
class ChampTexte(QTextEdit):
    """Zone de saisie d'un texte : marges de la proposition, lignes de hauteur fixe."""

    MARGE_HAUTE = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("zoneTexte")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptRichText(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(self.MARGE_HAUTE)
        cote = theme.MARGE - self.MARGE_HAUTE
        self.setViewportMargins(cote, 0, cote, 0)
        self.langue = FR
        self._invite = ""

    def definir_langue(self, langue: str) -> None:
        """Fixe la langue du texte : sens d'écriture, taille des caractères, hauteur des lignes."""
        self.langue = langue
        # Seul le texte change de sens : la barre de défilement reste à droite de la zone.
        option = self.document().defaultTextOption()
        option.setTextDirection(direction(langue))
        self.document().setDefaultTextOption(option)
        if self.property("arabe") != (langue == AR):
            self.setProperty("arabe", langue == AR)
            repeindre(self)
        self.appliquer_l_interligne()

    def definir_invite(self, texte: str) -> None:
        """Texte gris affiché tant que la zone est vide."""
        self._invite = texte
        self.setAccessibleDescription(texte)
        self.viewport().update()

    def invite(self) -> str:
        return self._invite

    def appliquer_l_interligne(self) -> None:
        """Espace les lignes et les paragraphes du texte (à refaire après chaque remplacement du texte)."""
        document = self.document()
        # Cette mise en forme ne doit pas pouvoir être annulée par Ctrl+Z.
        annulation = document.isUndoRedoEnabled()
        document.setUndoRedoEnabled(False)
        curseur = QTextCursor(document)
        curseur.select(QTextCursor.SelectionType.Document)
        mise_en_forme = QTextBlockFormat()
        mise_en_forme.setLineHeight(INTERLIGNE[self.langue], QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        mise_en_forme.setBottomMargin(ESPACE_ENTRE_PARAGRAPHES)
        curseur.mergeBlockFormat(mise_en_forme)
        document.setUndoRedoEnabled(annulation)

    def orienter_les_paragraphes(self) -> None:
        """Écrit dans son propre sens un paragraphe resté entièrement dans l'autre langue.

        Dans une traduction partielle, un paragraphe dont aucun mot n'a été traduit ne contient
        que l'écriture de l'autre langue. Affiché dans le sens d'écriture de la zone, il aurait
        son point final du mauvais côté.
        """
        dans_la_langue, dans_l_autre = ((contient_arabe, contient_latin) if self.langue == AR
                                        else (contient_latin, contient_arabe))
        sens_inverse = direction(autre_langue(self.langue))
        bloc = self.document().begin()
        while bloc.isValid():
            texte = bloc.text()
            if dans_l_autre(texte) and not dans_la_langue(texte):
                mise_en_forme = QTextBlockFormat()
                mise_en_forme.setLayoutDirection(sens_inverse)
                QTextCursor(bloc).mergeBlockFormat(mise_en_forme)
            bloc = bloc.next()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().paintEvent(evenement)
        if not self._invite or not self.document().isEmpty():
            return
        # L'invite est écrite sur la ligne de base de la première ligne du texte.
        peintre = QPainter(self.viewport())
        marge = self.MARGE_HAUTE
        cadre = QRectF(marge, marge, self.viewport().width() - 2 * marge, INTERLIGNE[self.langue])
        dessiner_ligne(peintre, cadre, abreger(self._invite, self.font(), cadre.width()), self.font(),
                       theme.TEXTE_4, langue=self.langue, base=INTERLIGNE[self.langue] * 0.8)


class Badge(QWidget):
    """État de la traduction, dans une pastille : une icône, un texte et un chevron.

    Le texte a plusieurs formes, de la plus longue à la plus courte. La pastille affiche la
    première qui tient dans la largeur reçue, et se place à droite de cette largeur. Un clic
    sur la pastille ouvre le détail du traitement : le chevron l'annonce.
    """

    #: La pastille a été cliquée.
    clique = Signal()

    HAUTEUR = 24
    #: Place du chevron, à droite du texte.
    CHEVRON = 18
    #: état -> (fond, filet, couleur du texte, icône)
    ASPECTS = MappingProxyType({
        "attente": (theme.GRIS_100, theme.FILET, theme.TEXTE_3, "information"),
        "partiel": (theme.AMBRE_50, theme.AMBRE_200, theme.AMBRE, "alerte"),
        "termine": (theme.VERT_50, theme.VERT_200, theme.VERT, "coche"),
    })

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HAUTEUR)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.etat = "attente"
        self._formes: tuple[str, ...] = ("",)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide()

    def definir(self, etat: str, *formes: str, explication: str = "") -> None:
        """Change l'état affiché ; sans texte, la pastille est cachée."""
        self.etat = etat
        self._formes = tuple(formes) or ("",)
        self.setToolTip(infobulle(explication, _VOIR_LES_ETAPES))
        self.setAccessibleName(self._formes[0])
        self.setVisible(bool(self._formes[0]))
        self.updateGeometry()
        self.update()

    def texte(self) -> str:
        """Le texte de l'état, dans sa forme longue."""
        return self._formes[0]

    def texte_affiche(self) -> str:
        """La forme du texte qui tient dans la largeur de la pastille."""
        return next((forme for forme in self._formes if self._largeur(forme) <= self.width()), self._formes[-1])

    def _largeur(self, forme: str) -> int:
        return round(10 + 14 + 7 + largeur_du_texte(forme, police(self.font(), 12, gras=True)) + 8 + self.CHEVRON)

    def mouseReleaseEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        if evenement.button() == Qt.MouseButton.LeftButton and self.rect().contains(evenement.position().toPoint()):
            self.clique.emit()
        super().mouseReleaseEvent(evenement)

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(self._largeur(self._formes[0]), self.HAUTEUR)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._largeur(self._formes[-1]), self.HAUTEUR)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        fond, filet, couleur, nom_icone = self.ASPECTS[self.etat]
        texte = self.texte_affiche()
        largeur = min(self._largeur(texte), self.width())
        gauche = self.width() - largeur
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        peintre.setPen(QPen(QColor(filet), 1))
        peintre.setBrush(QColor(fond))
        peintre.drawRoundedRect(QRectF(gauche + 0.5, 0.5, largeur - 1, self.height() - 1), 11.5, 11.5)
        peintre.drawPixmap(QPointF(gauche + 9, 5), icones.image(nom_icone, couleur, 14, 1.6))
        dessiner_ligne(peintre, QRectF(gauche + 30, 0, largeur - 30 - self.CHEVRON, self.height()), texte,
                       police(self.font(), 12, gras=True), couleur, base=16.4)
        peintre.drawPixmap(QPointF(gauche + largeur - self.CHEVRON - 2, 6), icones.image("chevron-b", couleur, 12, 1.7))


class RappelFichier(QFrame):
    """Rappel du fichier importé, dans l'en-tête du texte source : nom du fichier et bouton pour l'oublier."""

    #: Le bouton « × » a été cliqué.
    fermeture = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fichierImporte")
        self.setFixedHeight(24)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(9, 0, 4, 0)
        ligne.setSpacing(7)
        ligne.addWidget(icone_fixe("document", theme.TEXTE_3, 14))
        self.nom = EtiquetteCourte("", "nomFichier")
        self.nom.setMaximumWidth(220)
        ligne.addWidget(self.nom)
        self.bouton_fermer = QToolButton()
        self.bouton_fermer.setObjectName("fermerFichier")
        self.bouton_fermer.setIcon(icones.icone("croix", theme.TEXTE_3, 12, 1.7))
        self.bouton_fermer.setIconSize(QSize(12, 12))
        self.bouton_fermer.setFixedSize(18, 18)
        self.bouton_fermer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_fermer.setToolTip("Effacer le texte importé")
        self.bouton_fermer.clicked.connect(self.fermeture)
        ligne.addWidget(self.bouton_fermer)


class Legende(QWidget):
    """Légende sur une ligne, alignée à droite : des repères suivis de leur libellé.

    Un repère est un point de couleur ou une icône. Si la largeur manque, les repères les
    moins importants sont retirés.
    """

    ECART = 18

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        #: (icône ou « point », couleur, libellé, importance : 0 pour le plus important)
        self._reperes: list[tuple[str, str, str, int]] = []

    def definir(self, reperes: Sequence[tuple[str, str, str, int]]) -> None:
        self._reperes = list(reperes)
        self.setVisible(bool(self._reperes))
        self.setAccessibleName(" ; ".join(libelle for _, _, libelle, _ in self._reperes))
        self.updateGeometry()
        self.update()

    def libelles(self) -> list[str]:
        """Les libellés de la légende (tous, même ceux que la largeur ne permet pas d'afficher)."""
        return [libelle for _, _, libelle, _ in self._reperes]

    def _largeur_du_repere(self, repere: tuple[str, str, str, int]) -> float:
        genre, _, libelle, _ = repere
        return (8 + 7 if genre == "point" else 14 + 6) + largeur_du_texte(libelle, police(self.font(), 12))

    def _largeur(self, reperes: Sequence[tuple[str, str, str, int]]) -> int:
        if not reperes:
            return 0
        return round(sum(self._largeur_du_repere(repere) for repere in reperes) + self.ECART * (len(reperes) - 1)) + 1

    def reperes_affiches(self) -> list[tuple[str, str, str, int]]:
        """Les repères qui tiennent dans la largeur : les moins importants sont retirés d'abord."""
        visibles = list(self._reperes)
        while visibles and self._largeur(visibles) > self.width():
            visibles.remove(max(visibles, key=lambda repere: repere[3]))
        return visibles

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(self._largeur(self._reperes), 20)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 20)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        visibles = self.reperes_affiches()
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = float(self.width() - self._largeur(visibles))
        milieu = self.height() / 2
        for repere in visibles:
            genre, couleur, libelle, _ = repere
            if genre == "point":
                peintre.setPen(Qt.PenStyle.NoPen)
                peintre.setBrush(QColor(couleur))
                peintre.drawEllipse(QPointF(x + 4, milieu), 4, 4)
                decalage = 15
            else:
                peintre.drawPixmap(QPointF(x, milieu - 7), icones.image(genre, couleur, 14, 1.6))
                decalage = 20
            largeur = self._largeur_du_repere(repere)
            dessiner_ligne(peintre, QRectF(x + decalage, 0, largeur - decalage + 2, self.height()), libelle,
                           police(self.font(), 12), theme.TEXTE_3, base=milieu + 4.2)
            x += largeur + self.ECART


class ZoneTexte(QWidget):
    """Une moitié du panneau des textes : en-tête (langue), texte, pied (décompte et bouton)."""

    HAUTEUR_ENTETE, HAUTEUR_PIED = 40, 44

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.langue = FR
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        cadre_de_l_entete = QWidget()
        cadre_de_l_entete.setFixedHeight(self.HAUTEUR_ENTETE)
        self.entete = QHBoxLayout(cadre_de_l_entete)
        self.entete.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        self.entete.setSpacing(8)
        self.nom = etiquette("", "nomLangue")
        self.legende = etiquette(_ROLES[role], "roleZone")
        self.entete.addWidget(self.nom)
        self.entete.addWidget(self.legende)
        self.entete.addStretch(1)
        ensemble.addWidget(cadre_de_l_entete)
        ensemble.addWidget(separateur())

        self.zone = ChampTexte()
        self.zone.setMinimumHeight(56)
        ensemble.addWidget(self.zone, 1)
        ensemble.addWidget(separateur())

        cadre_du_pied = QWidget()
        cadre_du_pied.setFixedHeight(self.HAUTEUR_PIED)
        self.pied = QHBoxLayout(cadre_du_pied)
        self.pied.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        self.pied.setSpacing(16)
        self.decompte = EtiquetteCourte("", "decompte", forme_minimale=True)
        self.pied.addWidget(self.decompte, 1)
        ensemble.addWidget(cadre_du_pied)
        self.definir_langue(FR)

    def definir_langue(self, langue: str) -> None:
        """Fixe la langue de la zone : nom de la langue dans l'en-tête, sens d'écriture du texte."""
        self.langue = langue
        self.nom.setText(NOM_NATIF[langue])
        if self.nom.property("arabe") != (langue == AR):
            self.nom.setProperty("arabe", langue == AR)
            repeindre(self.nom)
        self.zone.definir_langue(langue)


# ====================================================================== étapes du traitement
@dataclass
class Etape:
    """Une étape du traitement et, après une traduction, son résultat."""

    nom: str
    nom_court: str
    description: str
    resultat: str = ""
    resultat_court: str = ""
    #: Détail du résultat, donné dans l'infobulle (mots absents, règles appliquées…).
    explication: str = ""


class BandeEtapes(QWidget):
    """Bande des cinq étapes du traitement : pour chacune, son numéro, son nom et, dessous, son résultat.

    L'écran « Texte » ne l'affiche pas en permanence : elle est placée dans ``VoletEtapes``.

    Les étapes occupent leur largeur propre et l'espace restant est réparti entre elles. Quand
    la place manque, les noms puis les résultats prennent leur forme courte, puis chaque nom
    passe sous son numéro ; dans une bande très étroite, il ne reste que les numéros et les
    résultats.

    Après une traduction, les cinq étapes s'allument l'une après l'autre.
    """

    HAUTEUR = 52
    #: Espace minimal entre deux étapes (un chevron y est dessiné).
    ECART_MINIMAL = 20
    #: Espace minimal entre deux étapes quand leur nom est écrit sous leur numéro.
    ECART_EMPILE = 10
    #: Marge à gauche et à droite de la bande.
    MARGE = 18

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HAUTEUR)
        self.setMinimumWidth(240)
        self.etapes = [Etape(nom, nom_court, description) for nom, nom_court, description in ETAPES]
        self.faite = False
        self.allumage = Allumage(len(self.etapes), self)
        self.allumage.change.connect(self.update)
        self.setAccessibleName("Étapes du traitement")
        self.afficher(None)

    # ------------------------------------------------------------------ résultats
    def afficher(self, traduction: Traduction | None, *, animer: bool = True) -> None:
        """Affiche le résultat de chaque étape ; sans traduction, seuls les noms des étapes sont affichés."""
        self.faite = traduction is not None
        for etape in self.etapes:
            etape.resultat = etape.resultat_court = etape.explication = ""
        if traduction is not None:
            self._renseigner(traduction)
        self.setAccessibleDescription(" ; ".join(
            f"{etape.nom} : {etape.resultat}" if etape.resultat else etape.nom for etape in self.etapes))
        self.allumage.definir([self.faite] * len(self.etapes), animer=animer)
        self.update()

    def rejouer(self) -> None:
        """Allume de nouveau les étapes l'une après l'autre (quand la bande vient d'être affichée)."""
        self.allumage.definir([self.faite] * len(self.etapes))

    def _renseigner(self, traduction: Traduction) -> None:
        segmentation, decoupage, recherche, regles, reconstruction = self.etapes
        phrases = len(traduction.phrases)
        segmentation.resultat, segmentation.resultat_court = compte(phrases, "phrase"), nombre(phrases)
        decoupage.resultat, decoupage.resultat_court = compte(traduction.mots, "mot"), nombre(traduction.mots)

        recherche.resultat = f"{compte(traduction.mots_reconnus, 'mot')} sur {nombre(traduction.mots)}"
        recherche.resultat_court = f"{nombre(traduction.mots_reconnus)} / {nombre(traduction.mots)}"
        if traduction.mots_absents:
            visibles = traduction.mots_absents[:40]
            recherche.explication = ("Mots absents du glossaire : " + ", ".join(visibles)
                                     + ("…" if len(traduction.mots_absents) > len(visibles) else "."))
        else:
            recherche.explication = "Tous les mots du texte ont été trouvés dans le glossaire."

        appliquees = sum(traduction.regles.values())
        regles.resultat = ("aucune appliquée" if not appliquees
                           else f"{nombre(appliquees)} appliquée{'s' if appliquees > 1 else ''}")
        regles.resultat_court = nombre(appliquees)
        details = []
        for famille, lignes in traduction.regles_par_famille().items():
            details.extend(f"{famille.capitalize()} — {libelle} : {nombre_de_fois}"
                           for libelle, nombre_de_fois in lignes)
        regles.explication = "\n".join(details)

        reprises, a_verifier = traduction.phrases_attestees, traduction.phrases_a_verifier
        reconstruction.resultat, reconstruction.resultat_court = compte(phrases, "phrase"), nombre(phrases)
        reconstruction.explication = (
            f"{compte(reprises, 'phrase reprise', 'phrases reprises')} des exemples du glossaire"
            + (f" (dont {nombre(a_verifier)} d’un exemple à vérifier)" if a_verifier else "")
            + f", {compte(phrases - reprises, 'phrase traduite', 'phrases traduites')} mot à mot.")

    # ------------------------------------------------------------------ mise en place
    def _polices(self):
        """Police du nom d'une étape, police de son résultat, police du nom dans la forme empilée."""
        return police(self.font(), 13, gras=True), police(self.font(), 12), police(self.font(), 12)

    def _formes(self) -> list[tuple[bool, list[tuple[str, str]]]]:
        """Les formes de la bande, de la plus large à la plus étroite.

        Chaque forme donne sa disposition (empilée ou non) et, pour chaque étape, son nom et
        son résultat. Dans la forme empilée, le nom passe sous le numéro : la bande garde ses
        noms dans une colonne étroite.
        """
        etapes = self.etapes
        formes = [(False, [(etape.nom, etape.resultat) for etape in etapes]),
                  (False, [(etape.nom_court, etape.resultat) for etape in etapes]),
                  (False, [(etape.nom_court, etape.resultat_court) for etape in etapes]),
                  (True, [(etape.nom_court, etape.resultat_court) for etape in etapes]),
                  (False, [("", etape.resultat_court) for etape in etapes]),
                  (False, [("", "") for etape in etapes])]
        return [forme for rang, forme in enumerate(formes) if forme not in formes[:rang]]

    def _largeurs(self, empilee: bool, forme: Sequence[tuple[str, str]]) -> list[float]:
        """Largeur de chaque étape.

        Disposition normale : le numéro, puis le nom au-dessus du résultat (ou le résultat seul).
        Disposition empilée : le numéro et le résultat, au-dessus du nom.
        """
        gras, normal, petit = self._polices()
        largeurs = []
        for nom, resultat in forme:
            if empilee:
                largeurs.append(max(20 + (6 + largeur_du_texte(resultat, normal) if resultat else 0),
                                    largeur_du_texte(nom, petit)))
            else:
                textes = max(largeur_du_texte(nom, gras), largeur_du_texte(resultat, normal))
                largeurs.append(20 + ((9 if nom else 6) + textes if nom or resultat else 0))
        return largeurs

    def _forme_choisie(self) -> tuple[bool, list[tuple[str, str]]]:
        """La première forme qui tient dans la largeur de la bande."""
        place = self.width() - 2 * self.MARGE
        formes = self._formes()
        for empilee, forme in formes:
            # Dans la forme empilée, les étapes peuvent se rapprocher : le chevron est alors omis.
            ecart = self.ECART_EMPILE if empilee else self.ECART_MINIMAL
            if sum(self._largeurs(empilee, forme)) + ecart * (len(forme) - 1) <= place:
                return empilee, forme
        return formes[-1]

    def empilee(self) -> bool:
        """Vrai si le nom de chaque étape est écrit sous son numéro (bande étroite)."""
        return self._forme_choisie()[0]

    def largeur_confortable(self) -> int:
        """Largeur qu'il faut à la bande pour écrire le nom court de chaque étape et son résultat en entier."""
        forme = [(etape.nom_court, etape.resultat) for etape in self.etapes]
        return math.ceil(sum(self._largeurs(False, forme)) + self.ECART_MINIMAL * (len(forme) - 1) + 2 * self.MARGE)

    def disposition(self) -> tuple[list[tuple[str, str]], list[float], float]:
        """Les textes affichés (nom, résultat), l'abscisse de chaque étape et l'espace entre deux étapes."""
        place = self.width() - 2 * self.MARGE
        empilee, choisie = self._forme_choisie()
        largeurs = self._largeurs(empilee, choisie)
        ecart = max((place - sum(largeurs)) / (len(choisie) - 1), 4.0)
        abscisses, x = [], float(self.MARGE)
        for largeur in largeurs:
            abscisses.append(x)
            x += largeur + ecart
        return choisie, abscisses, ecart

    def textes_affiches(self) -> list[tuple[str, str]]:
        """Pour chaque étape, le nom et le résultat tels qu'ils sont affichés."""
        return self.disposition()[0]

    def infobulle(self, rang: int) -> str:
        """Texte de l'infobulle d'une étape : son nom, ce qu'elle fait, son résultat."""
        etape = self.etapes[rang]
        lignes = [f"<b>{rang + 1}. {escape(etape.nom)}</b>", escape(etape.description)]
        if etape.resultat:
            lignes.append(f"Résultat : {escape(etape.resultat)}.")
        if etape.explication:
            lignes.append(escape(etape.explication).replace("\n", "<br>"))
        return "<qt>" + "<br>".join(lignes) + "</qt>"

    def etape_a(self, x: float) -> int | None:
        """Rang de l'étape dessinée à l'abscisse ``x``."""
        textes, abscisses, _ = self.disposition()
        largeurs = self._largeurs(self.empilee(), textes)
        for rang, (gauche, largeur) in enumerate(zip(abscisses, largeurs, strict=True)):
            if gauche - 4 <= x <= gauche + largeur + 4:
                return rang
        return None

    def event(self, evenement) -> bool:
        if evenement.type() == QEvent.Type.ToolTip:
            rang = self.etape_a(evenement.pos().x())
            if rang is None:
                QToolTip.hideText()
                evenement.ignore()
            else:
                QToolTip.showText(evenement.globalPos(), self.infobulle(rang), self)
            return True
        return super().event(evenement)

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        peintre.setPen(QPen(QColor(theme.FILET), 1))
        peintre.setBrush(QColor(theme.SURFACE))
        peintre.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        gras, normal, petit = self._polices()
        empilee = self.empilee()
        textes, abscisses, ecart = self.disposition()
        milieu = self.height() / 2
        hauteur = self.height()
        for rang, ((nom, resultat), x) in enumerate(zip(textes, abscisses, strict=True)):
            niveau = self.allumage.niveau(rang)
            if rang and ecart >= 18:
                # Le chevron qui mène à l'étape se colore quand elle s'allume.
                couleur = melanger(theme.TEXTE_4, theme.OR_FONCE, niveau).name()
                peintre.drawPixmap(QPointF(x - ecart / 2 - 7, milieu - 7), icones.image("chevron-d", couleur, 14, 1.5))
            couleur_du_nom = melanger(theme.TEXTE_3, theme.TEXTE, niveau).name()
            centre = QPointF(x + 10, milieu - 9 if empilee else milieu)
            dessiner_numero(peintre, centre, 10, str(rang + 1), police(self.font(), 12, gras=True), niveau,
                            self.allumage.halo(rang), carre=True)
            if empilee:
                # Bande étroite : le numéro et son résultat, puis le nom dessous.
                if resultat:
                    dessiner_ligne(peintre, QRectF(x + 26, 0, largeur_du_texte(resultat, normal) + 2, hauteur),
                                   resultat, normal, theme.TEXTE_2, base=milieu - 4.5)
                dessiner_ligne(peintre, QRectF(x, 0, largeur_du_texte(nom, petit) + 2, hauteur), nom, petit,
                               couleur_du_nom, base=milieu + 18)
            elif nom and resultat:
                # Le nom de l'étape, et son résultat dessous.
                dessiner_ligne(peintre, QRectF(x + 29, 0, largeur_du_texte(nom, gras) + 2, hauteur), nom, gras,
                               couleur_du_nom, base=milieu - 4)
                dessiner_ligne(peintre, QRectF(x + 29, 0, largeur_du_texte(resultat, normal) + 2, hauteur),
                               resultat, normal, theme.TEXTE_3, base=milieu + 13)
            elif nom:
                dessiner_ligne(peintre, QRectF(x + 29, 0, largeur_du_texte(nom, gras) + 2, hauteur), nom, gras,
                               couleur_du_nom, base=milieu + 4.5)
            elif resultat:
                dessiner_ligne(peintre, QRectF(x + 26, 0, largeur_du_texte(resultat, normal) + 2, hauteur),
                               resultat, normal, theme.TEXTE_2, base=milieu + 4.5)


class VoletEtapes(QFrame):
    """Petite fenêtre des cinq étapes du traitement, ouverte à la demande sous l'état de la traduction.

    L'écran « Texte » ne montre que le texte, sa traduction et ses termes. Le détail du
    traitement (phrases, mots, mots trouvés, règles appliquées) reste disponible ici. Un clic
    en dehors de la petite fenêtre, ou la touche Échap, la referme.
    """

    #: Largeur habituelle de la petite fenêtre ; elle s'élargit si les résultats n'y tiennent pas en entier.
    LARGEUR = 720

    def __init__(self, bande: BandeEtapes, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("voletEtapes")
        self.bande = bande
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(16, 12, 16, 16)
        colonne.setSpacing(10)
        ligne = QHBoxLayout()
        ligne.setSpacing(12)
        self.titre = etiquette("Étapes du traitement", "titrePanneau")
        self.aide = EtiquetteCourte("", "aidePanneau")
        self.aide.definir_texte("Laissez le pointeur sur une étape pour voir son détail", "")
        self.aide.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ligne.addWidget(self.titre)
        ligne.addWidget(self.aide, 1)
        colonne.addLayout(ligne)
        colonne.addWidget(bande)

    def ouvrir_sous(self, ancre: QWidget, largeur_disponible: int) -> None:
        """Ouvre la petite fenêtre sous ``ancre``, alignée sur son bord droit, sans sortir de la fenêtre."""
        marges = self.layout().contentsMargins()
        autour = marges.left() + marges.right() + 2 * self.frameWidth()
        souhaitee = max(self.LARGEUR, self.bande.largeur_confortable() + autour)
        largeur = max(min(souhaitee, largeur_disponible), 300)
        self.setFixedWidth(largeur)
        self.adjustSize()
        coin = ancre.mapToGlobal(QPoint(ancre.width(), ancre.height() + 6))
        gauche = coin.x() - largeur
        fenetre = ancre.window()
        if fenetre is not None:
            bord = fenetre.mapToGlobal(QPoint(0, 0)).x()
            gauche = max(min(gauche, bord + fenetre.width() - largeur - 8), bord + 8)
        self.move(gauche, coin.y())
        self.bande.rejouer()
        self.show()


# ====================================================================== l'écran
class PageTexte(QWidget):
    """L'écran de traduction d'un texte."""

    #: Le sens de traduction a changé ; le signal porte la nouvelle langue source.
    sens_change = Signal(str)
    #: Message passager à afficher dans la barre d'état (une confirmation, par exemple).
    message = Signal(str)
    #: État de l'écran, affiché dans la barre d'état tant qu'il ne change pas (vide : rien à signaler).
    etat_change = Signal(str)
    #: Demande d'affichage de la fiche d'une entrée du glossaire (écran « Terme »).
    entree_demandee = Signal(object)
    #: Une traduction vient d'être affichée ou effacée.
    traduction_changee = Signal()

    #: Espace entre les panneaux, et marge sous le dernier.
    ECART, MARGE_BASSE = 16, 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.traducteur: Traducteur | None = None
        self.traduction: Traduction | None = None
        self.source = FR
        self.etat = ""
        #: Fichier d'où vient le texte source, s'il a été importé.
        self.fichier: Path | None = None
        self._modification_interne = False

        self._creer_les_outils()

        # ---------------------------------------------------------- texte source
        self.panneau_source = ZoneTexte("source")
        self.zone_source = self.panneau_source.zone
        self.zone_source.textChanged.connect(self._texte_modifie)
        self.lien_exemple = QPushButton("Insérer un exemple")
        self.lien_exemple.setProperty("classe", "lien")
        self.lien_exemple.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lien_exemple.setToolTip("Remplir la zone avec un texte d’exemple (articles 106 et 107 du Code civil)")
        self.lien_exemple.clicked.connect(self.inserer_un_exemple)
        self.panneau_source.entete.addWidget(self.lien_exemple)
        self.importe_de = EtiquetteCourte("", "decompte")
        self.importe_de.definir_texte("Importé de", "")
        self.importe_de.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.panneau_source.entete.addWidget(self.importe_de)
        self.fichier_importe = RappelFichier()
        self.fichier_importe.fermeture.connect(self.effacer)
        self.nom_du_fichier = self.fichier_importe.nom
        self.panneau_source.entete.addWidget(self.fichier_importe)

        self.decompte_source = self.panneau_source.decompte
        self.bouton_effacer = _bouton("Effacer", "contour", 84, 30, info="Effacer le texte et sa traduction")
        self.bouton_effacer.clicked.connect(self.effacer)
        self.panneau_source.pied.addWidget(self.bouton_effacer)

        # ---------------------------------------------------------- traduction
        self.panneau_cible = ZoneTexte("cible")
        self.zone_cible = self.panneau_cible.zone
        self.zone_cible.setReadOnly(True)
        self.badge = Badge()
        self.badge.clique.connect(self.montrer_les_etapes)
        self.panneau_cible.entete.addWidget(self.badge)

        self.decompte_cible = self.panneau_cible.decompte
        self.legende = Legende()
        self.bouton_copier = _bouton("Copier", "contour", 96, 30, "copier",
                                     "Copier la traduction dans le presse-papiers")
        self.bouton_copier.clicked.connect(self.copier)
        self._retour_copier = QTimer(self)
        self._retour_copier.setSingleShot(True)
        self._retour_copier.setInterval(1600)
        self._retour_copier.timeout.connect(lambda: self.bouton_copier.setText("Copier"))
        self.panneau_cible.pied.addWidget(self.legende)
        self.panneau_cible.pied.addWidget(self.bouton_copier)

        # ---------------------------------------------------------- termes du texte, étapes du traitement
        self.termes = PanneauTermes()
        self.termes.ouverture.connect(self.entree_demandee)
        self.termes.survol.connect(self.allumer)
        # Les étapes ne sont pas affichées en permanence : un clic sur l'état de la traduction les ouvre.
        self.bande = BandeEtapes()
        self.volet_etapes = VoletEtapes(self.bande, self)

        # Le texte et sa traduction, côte à côte ; dessous, les termes juridiques du texte.
        self.cadre_source = self._encadrer(self.panneau_source)
        self.cadre_cible = self._encadrer(self.panneau_cible)
        self.rangee_des_textes = QWidget()
        rangee = QHBoxLayout(self.rangee_des_textes)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.setSpacing(self.ECART)
        rangee.addWidget(self.cadre_source, 1)
        rangee.addWidget(self.cadre_cible, 1)
        page = QVBoxLayout(self)
        page.setContentsMargins(theme.MARGE, 0, theme.MARGE, self.MARGE_BASSE)
        page.setSpacing(self.ECART)
        page.addWidget(self.rangee_des_textes, 1)
        page.addWidget(self.termes)

        # Un clic sur un terme coloré, dans l'une ou l'autre zone, ouvre sa fiche sur l'écran « Terme ».
        self._termes_des_zones: dict[ChampTexte, list[tuple[int, int, Entree]]] = {}
        #: Les passages qui colorent les termes du texte source, dans l'ordre de ``_termes_des_zones``.
        self._couleurs_de_la_source: list[QTextEdit.ExtraSelection] = []
        # Le terme que le pointeur désigne est allumé partout où il figure (voir ``allumer``).
        self._terme_allume: Entree | None = None
        self._format_terme = _mise_en_forme(COULEUR_TERME)
        self._format_allume = _mise_en_forme(COULEUR_ALLUME, FOND_ALLUME)
        # La liste : chaque case dit quand le pointeur y entre et quand il la quitte (signal ``survol``). Mais Qt
        # ne prévient pas une case arrivée sous un pointeur immobile : elle ne saurait pas qu'il est reparti. Le
        # fond de la liste le dit à sa place, quand le pointeur y passe ou quitte la liste.
        self._fonds_de_la_liste = (self.termes.grille, self.termes.defilement.viewport())
        # Les deux textes et le fond de la liste : le pointeur y est suivi sans qu'un bouton soit enfoncé.
        for zone in (self.zone_source, self.zone_cible):
            zone.viewport().installEventFilter(self)
            zone.viewport().setMouseTracking(True)
        for fond in self._fonds_de_la_liste:
            fond.installEventFilter(self)
            fond.setMouseTracking(True)
        # Quand un texte ou la liste défile sous un pointeur immobile (molette, clavier), quand le texte est traduit
        # de nouveau ou quand cet écran s'affiche, le terme désigné n'est plus le même, et Qt ne prévient pas : le
        # pointeur est relu juste après (voir ``_relire_le_pointeur``).
        self._relecture_du_pointeur = QTimer(self)
        self._relecture_du_pointeur.setSingleShot(True)
        self._relecture_du_pointeur.setInterval(0)
        self._relecture_du_pointeur.timeout.connect(self._relire_le_pointeur)
        for barre in (self.zone_source.verticalScrollBar(), self.zone_cible.verticalScrollBar(),
                      self.termes.defilement.verticalScrollBar()):
            barre.valueChanged.connect(self._defilement)

        raccourci = QShortcut(QKeySequence("Ctrl+Return"), self)
        raccourci.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        raccourci.activated.connect(self.traduire)
        self._decompte_differe = QTimer(self)
        self._decompte_differe.setSingleShot(True)
        self._decompte_differe.setInterval(200)
        self._decompte_differe.timeout.connect(self._afficher_le_decompte_source)

        self._appliquer_sens()
        self._afficher(None)

    @staticmethod
    def _encadrer(zone: ZoneTexte) -> Panneau:
        """Place une zone de texte dans son panneau."""
        cadre = Panneau()
        dans_le_cadre = QVBoxLayout(cadre)
        dans_le_cadre.setContentsMargins(0, 0, 0, 0)
        dans_le_cadre.addWidget(zone)
        return cadre

    def _creer_les_outils(self) -> None:
        """Les commandes que la fenêtre place dans la barre d'outils : importer, exporter, traduire."""
        self.outils = QWidget()
        ligne = QHBoxLayout(self.outils)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        # Le rappel des formats occupe la place libre ; il disparaît quand elle manque.
        self.aide_outils = EtiquetteCourte("", "aideOutils")
        self.aide_outils.definir_texte("Import : .txt, .docx, .doc · Export : .docx, .txt", "")
        self.aide_outils.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.aide_outils.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.aide_outils.setContentsMargins(0, 0, 16, 0)
        self.bouton_importer = _bouton("Importer", "contour", 116, 38, "importer",
                                       "Importer un texte : fichier .txt, .docx ou .doc (Ctrl+Maj+O)")
        self.bouton_importer.clicked.connect(lambda: self.importer())
        self.bouton_exporter = _bouton("Exporter", "contour", 116, 38, "exporter",
                                       "Exporter la traduction : fichier .docx ou .txt (Ctrl+E)")
        self.bouton_exporter.clicked.connect(lambda: self.exporter())
        self.bouton_traduire = _bouton("Traduire", "principal", 132, 38, "echange",
                                       "Traduire le texte (Ctrl+Entrée)")
        self.bouton_traduire.clicked.connect(lambda: self.traduire())
        ligne.addWidget(self.aide_outils, 1)
        ligne.addWidget(self.bouton_importer)
        espace_souple(ligne, 12, 6)
        ligne.addWidget(self.bouton_exporter)
        espace_souple(ligne, 12, 6)
        ligne.addWidget(self.bouton_traduire)

    # ------------------------------------------------------------------ glossaire et sens
    @property
    def cible(self) -> str:
        return autre_langue(self.source)

    def definir_glossaire(self, glossaire: Glossaire | None) -> None:
        """Change de glossaire ; la traduction affichée est refaite avec le nouveau glossaire."""
        self.glossaire = glossaire
        self.traducteur = Traducteur(glossaire) if glossaire is not None and len(glossaire) else None
        if self.traduction is not None and self.traducteur is not None:
            self.traduire(deviner=False)
        else:
            self._afficher(None)

    def definir_sens(self, source: str) -> None:
        """Fixe la langue source (l'autre langue devient la langue cible)."""
        if source == self.source:
            return
        self.source = source
        self._appliquer_sens()
        self._afficher(None)
        self.sens_change.emit(source)

    def inverser(self) -> None:
        """Inverse le sens de traduction. Le texte source est conservé ; la traduction est effacée."""
        self.definir_sens(autre_langue(self.source))

    def _appliquer_sens(self) -> None:
        self.panneau_source.definir_langue(self.source)
        self.panneau_cible.definir_langue(self.cible)
        self.zone_source.definir_invite(_INVITES[self.source])
        self.zone_cible.definir_invite(_INVITES_CIBLE[self.cible])

    # ------------------------------------------------------------------ texte source
    def texte(self) -> str:
        """Le texte source, tel qu'il est saisi."""
        return self.zone_source.toPlainText()

    def definir_texte(self, texte: str, fichier: Path | None = None) -> None:
        """Remplace le texte source (texte importé ou exemple)."""
        self._modification_interne = True
        try:
            self.zone_source.setPlainText(texte)
            self.zone_source.appliquer_l_interligne()
        finally:
            self._modification_interne = False
        self.fichier = fichier
        self._afficher(None)

    def inserer_un_exemple(self) -> None:
        self.definir_texte(EXEMPLES[self.source])
        self.zone_source.setFocus()

    def effacer(self) -> None:
        """Vide le texte source et la traduction."""
        self.definir_texte("")
        self.zone_source.setFocus()

    def _texte_modifie(self) -> None:
        self._decompte_differe.start()
        if self._modification_interne:
            return
        self._actualiser_l_entete_source()
        if self.traduction is not None and self.traduction.texte_source != self.texte():
            # Le texte ne correspond plus à la traduction affichée : ses termes ne sont plus colorés, ni cliquables,
            # et plus aucun terme n'est allumé.
            self._termes_des_zones[self.zone_source] = []
            self._couleurs_de_la_source = []
            self._terme_allume = None
            self.termes.allumer(None)
            self._peindre_les_termes()
            self.badge.definir("attente", "Texte modifié · traduction à refaire", "Texte modifié",
                               explication=_TEXTE_MODIFIE)
            self._definir_etat(_TEXTE_MODIFIE)

    def _actualiser_l_entete_source(self) -> None:
        """En-tête du texte source : le fichier importé, ou le lien « Insérer un exemple » si la zone est vide."""
        vide = not self.texte().strip()
        self.lien_exemple.setVisible(vide and self.fichier is None)
        self.importe_de.setVisible(self.fichier is not None)
        self.fichier_importe.setVisible(self.fichier is not None)
        self.bouton_effacer.setEnabled(not vide or self.fichier is not None or self.traduction is not None)
        if self.fichier is not None:
            self.nom_du_fichier.definir_texte(self.fichier.name)
            self.fichier_importe.setToolTip(infobulle(f"Texte importé depuis {self.fichier}"))

    def _afficher_le_decompte_source(self) -> None:
        self.decompte_source.definir_texte(*_decompte(*compter(self.texte())))

    # ------------------------------------------------------------------ traduction
    def traduire(self, *, deviner: bool = True) -> None:
        """Traduit le texte source et affiche le résultat.

        Si le texte est écrit dans l'autre langue, le sens de traduction est
        d'abord inversé (comme sur l'écran « Terme »).

        ``deviner`` ne peut être donné que par son nom : un bouton relié à cette
        méthode lui passerait sinon son état (« coché » ou non) à la place.
        """
        texte = self.texte()
        if not texte.strip():
            self._afficher(None)
            self.message.emit("Saisissez, collez ou importez d’abord un texte à traduire.")
            return
        if self.traducteur is None:
            self._afficher(None)
            self.message.emit(_AUCUN_GLOSSAIRE)
            return
        if deviner:
            langue = deviner_langue(texte)
            if langue is not None and langue != self.source:
                self.definir_sens(langue)
                self.message.emit(f"Texte écrit en {NOM_EN_FRANCAIS[langue]} : le sens de traduction a été inversé.")
        with sablier():
            self._afficher(self.traducteur.traduire(texte, self.source))

    def _afficher(self, traduction: Traduction | None) -> None:
        """Affiche une traduction, ou l'état initial si ``traduction`` est vide."""
        self.traduction = traduction
        self._terme_allume = None  # la liste des termes est refaite : toutes ses cases sont éteintes
        self._afficher_le_decompte_source()
        self._actualiser_l_entete_source()
        self.bande.afficher(traduction)
        self.termes.afficher(traduction, sans_glossaire=self.traducteur is None)
        self._ajuster_les_termes()
        self._reperer_les_termes(traduction)
        self.bouton_copier.setEnabled(traduction is not None)
        self.bouton_exporter.setEnabled(traduction is not None)
        if traduction is None:
            self.zone_cible.clear()
            self.decompte_cible.definir_texte("")
            self.legende.definir([])
            if self.traducteur is None:
                self.badge.definir("partiel", "Aucun glossaire chargé", "Aucun glossaire", explication=_AUCUN_GLOSSAIRE)
                self._definir_etat(_AUCUN_GLOSSAIRE)
            else:
                self.badge.definir("attente")
                self._definir_etat("")
        else:
            self.zone_cible.setHtml(self._html(traduction))
            self.zone_cible.appliquer_l_interligne()
            self.zone_cible.orienter_les_paragraphes()
            self.decompte_cible.definir_texte(*_decompte(*traduction.decompte_cible()))
            self._afficher_le_bilan(traduction)
        self._peindre_les_termes()
        self._relecture_du_pointeur.start()  # le terme resté sous le pointeur se rallume
        self.traduction_changee.emit()

    def _afficher_le_bilan(self, traduction: Traduction) -> None:
        """État de la traduction (pastille de l'en-tête), légende du pied et barre d'état."""
        mots, trouves = traduction.mots, traduction.mots_reconnus
        restants = mots - trouves
        decompte = f"{compte(trouves, 'mot')} sur {nombre(mots)} {'trouvé' if trouves < 2 else 'trouvés'}"
        court = f"{nombre(trouves)} / {nombre(mots)}"
        reperes = []
        if any(morceau.nature == TERME for morceau in traduction.morceaux):
            reperes.append(("point", COULEUR_TERME, "terme du glossaire", 1))
        # Une phrase reprise d'un exemple « à vérifier » est signalée : sa traduction n'est celle d'aucun texte cité.
        a_verifier = traduction.phrases_a_verifier
        rappel = _A_RELIRE if not a_verifier else (
            f"{_A_RELIRE} {compte(a_verifier, 'phrase est reprise', 'phrases sont reprises')} "
            "d’un exemple du glossaire qui porte la mention « à vérifier ».")
        if traduction.complete:
            self.badge.definir(
                "termine", f"Traduction terminée · {decompte}", f"Traduction terminée · {court}", "Traduction terminée",
                explication=f"Tous les mots du texte ont été trouvés dans le glossaire. {rappel}")
        elif not trouves:
            self.badge.definir(
                "partiel", "Aucun mot trouvé dans le glossaire", "Aucun mot trouvé",
                explication="Aucun mot de ce texte ne figure dans le glossaire : le texte est recopié tel quel.")
        else:
            self.badge.definir(
                "partiel", f"Traduction partielle · {decompte}", f"Traduction partielle · {court}",
                "Traduction partielle",
                explication=f"{compte(restants, 'mot')} sur {nombre(mots)} ne "
                            f"{'figure' if restants < 2 else 'figurent'} pas dans le glossaire : "
                            f"{'il reste' if restants < 2 else 'ils restent'} à traduire. {rappel}")
        if restants:
            reperes.append(("point", COULEUR_ABSENT, "mot absent, à traduire", 0))
        self.legende.definir(reperes)
        self._definir_etat(f"Traduction : {decompte} dans le glossaire.")

    def _definir_etat(self, texte: str) -> None:
        self.etat = texte
        self.etat_change.emit(texte)

    # ------------------------------------------------------------------ termes du texte, étapes du traitement
    def _ajuster_les_termes(self) -> None:
        """Donne à la liste des termes la hauteur de ses lignes, dans la limite d'une part de l'écran."""
        self.termes.setFixedHeight(self.termes.hauteur_pour(self.width() - 2 * theme.MARGE,
                                                            self.height() - self.MARGE_BASSE))

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self._ajuster_les_termes()

    def montrer_les_etapes(self) -> None:
        """Ouvre la petite fenêtre des cinq étapes du traitement, sous l'état de la traduction."""
        ancre = self.badge if self.badge.isVisible() else self.panneau_cible.nom
        self.volet_etapes.ouvrir_sous(ancre, self.width() - 2 * theme.MARGE)

    def showEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().showEvent(evenement)
        self._relecture_du_pointeur.start()  # l'écran s'affiche peut-être sous le pointeur : son terme s'allume

    def hideEvent(self, evenement) -> None:  # noqa: N802
        super().hideEvent(evenement)
        self.allumer(None)  # l'écran n'est plus affiché : le pointeur ne désigne plus aucun de ses termes

    # ------------------------------------------------------------------ couleur des termes, terme allumé
    @property
    def terme_allume(self) -> Entree | None:
        """L'entrée du glossaire dont le terme est allumé ; ``None`` si aucun terme n'est allumé."""
        return self._terme_allume

    def allumer(self, entree: Entree | None) -> None:
        """Allume un terme partout où il figure ; ``None`` éteint le terme allumé.

        Le terme prend un fond à chacune de ses occurrences dans le texte source, à chacun des
        passages de la traduction qui le rendent, et sur sa case dans la liste des termes. Un seul
        terme est allumé à la fois : celui que le pointeur désigne. Rien ne défile : un passage ou
        une case hors de la vue s'allume sans être montré.

        Le pointeur désigne un terme quand il est sur ce terme dans l'un des deux textes (voir
        ``eventFilter``), ou sur sa case (signal ``PanneauTermes.survol``).
        """
        if entree is self._terme_allume:
            return
        self._terme_allume = entree
        self.termes.allumer(entree)
        self._peindre_les_termes()

    def _designer(self, zone: ChampTexte, point: QPoint) -> None:
        """Le pointeur est à ``point`` dans une zone de texte : le terme écrit là s'allume, et le pointeur prend la
        forme d'une main ; ailleurs que sur un terme, plus rien n'est allumé."""
        entree = self.terme_a(zone, point)
        zone.viewport().setCursor(Qt.CursorShape.PointingHandCursor if entree is not None
                                  else Qt.CursorShape.IBeamCursor)
        self.allumer(entree)

    def _defilement(self, _valeur: int = 0) -> None:
        self._relecture_du_pointeur.start()

    def _relire_le_pointeur(self) -> None:
        """Après un défilement, une nouvelle traduction ou le retour à cet écran : allume le terme qui se trouve
        maintenant sous le pointeur, s'il est sur un des deux textes ou sur la liste. Ailleurs, rien ne change ;
        pendant qu'un bouton de la souris est enfoncé non plus.

        Deux précautions. Qt doit avoir annoncé le pointeur sur la zone (``underMouse``) : ce n'est plus le cas
        quand il a quitté la fenêtre ou qu'une autre fenêtre la recouvre, et la position que Qt donne peut alors
        être un vieux souvenir. Et la zone doit être ce que la fenêtre affiche à cet endroit (``childAt``).
        """
        if not self.isVisible() or QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            return
        position = QCursor.pos()
        fenetre = self.window()
        dessous = fenetre.childAt(fenetre.mapFromGlobal(position))
        for zone in (self.zone_source, self.zone_cible):
            vue = zone.viewport()
            if dessous is vue and vue.underMouse():
                self._designer(zone, vue.mapFromGlobal(position))
                return
        if self.termes.defilement.viewport().underMouse():
            # Sur la liste : la case qui se trouve là ; entre deux cases ou sous la dernière ligne, aucune.
            self.allumer(dessous.entree if isinstance(dessous, CelluleTerme) else None)

    def _peindre_les_termes(self) -> None:
        """Colore les termes du texte source et donne son fond au terme allumé, dans les deux zones de texte."""
        for zone in (self.zone_source, self.zone_cible):
            # Seul le texte source reçoit ici la couleur de ses termes : la traduction l'a déjà (voir ``_html``).
            passages = list(self._couleurs_de_la_source) if zone is self.zone_source else []
            if self._terme_allume is not None:
                for rang, (debut, fin, entree) in enumerate(self._termes_des_zones.get(zone, ())):
                    if entree is self._terme_allume:
                        allume = _passage(zone, debut, fin, self._format_allume)
                        if zone is self.zone_source:
                            passages[rang] = allume  # à la place de la couleur du terme : un passage, une mise en forme
                        else:
                            passages.append(allume)
            zone.setExtraSelections(passages)

    # ------------------------------------------------------------------ clic sur un terme du texte, pointeur
    def _reperer_les_termes(self, traduction: Traduction | None) -> None:
        """Note la place des termes dans les deux zones, en positions de Qt (unités UTF-16)."""
        self._termes_des_zones = {self.zone_source: [], self.zone_cible: []}
        self._couleurs_de_la_source = []
        for zone in (self.zone_source, self.zone_cible):
            zone.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        if traduction is None:
            return

        def positions(texte: str, decalage: int):
            hors_plan = [rang for rang, caractere in enumerate(texte) if ord(caractere) > 0xFFFF]
            return lambda indice: decalage + indice + sum(1 for rang in hors_plan if rang < indice)

        dans_la_source = positions(traduction.texte_source, 0)
        self._termes_des_zones[self.zone_source] = [
            (dans_la_source(occurrence.debut), dans_la_source(occurrence.fin), occurrence.entree)
            for occurrence in traduction.occurrences]
        # La traduction d'un texte arabe commence par une marque de direction invisible.
        dans_la_cible = positions(traduction.texte, 1 if traduction.cible == AR else 0)
        indice = 0
        for morceau in traduction.morceaux:
            if morceau.nature == TERME and morceau.entree is not None:
                self._termes_des_zones[self.zone_cible].append(
                    (dans_la_cible(indice), dans_la_cible(indice + len(morceau.texte)), morceau.entree))
            indice += len(morceau.texte)
        self._couleurs_de_la_source = [_passage(self.zone_source, debut, fin, self._format_terme)
                                       for debut, fin, _ in self._termes_des_zones[self.zone_source]]

    def terme_a(self, zone: ChampTexte, point) -> Entree | None:
        """L'entrée du glossaire dont le terme est écrit sous ``point``, dans une des deux zones de texte."""
        termes = self._termes_des_zones.get(zone)
        if not termes or not zone.viewport().rect().contains(point):
            return None  # aucun terme repéré, ou un point hors de la partie du texte affichée
        curseur = zone.cursorForPosition(point)
        cadre = zone.cursorRect(curseur)
        # Dans une marge ou après la fin d'une ligne, la position la plus proche est loin du point.
        if not (cadre.top() - 2 <= point.y() <= cadre.bottom() + 2) or abs(point.x() - cadre.center().x()) > 14:
            return None
        position = curseur.position()
        return next((entree for debut, fin, entree in termes if debut <= position <= fin), None)

    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802 (nom imposé par Qt)
        if any(objet is fond for fond in self._fonds_de_la_liste):
            # Le pointeur est sur la liste sans être sur une case, ou il la quitte : aucune case n'est désignée.
            if (evenement.type() == QEvent.Type.Leave
                    or (evenement.type() == QEvent.Type.MouseMove and not evenement.buttons())):
                self.allumer(None)
            return super().eventFilter(objet, evenement)
        for zone in (self.zone_source, self.zone_cible):
            if objet is not zone.viewport():
                continue
            if evenement.type() == QEvent.Type.MouseButtonRelease:
                point = evenement.position().toPoint()
                if evenement.button() == Qt.MouseButton.LeftButton and not zone.textCursor().hasSelection():
                    # Un simple clic sur un terme coloré (et non la sélection d'un passage) ouvre sa fiche.
                    entree = self.terme_a(zone, point)
                    if entree is not None:
                        self.entree_demandee.emit(entree)
                # Tant que le bouton était enfoncé, le terme allumé n'a pas suivi le pointeur : il le rattrape
                # (sauf si le clic vient d'ouvrir une fiche : cet écran n'est plus affiché).
                if self.isVisible() and not evenement.buttons():
                    self._designer(zone, point)
            elif evenement.type() == QEvent.Type.MouseMove and not evenement.buttons():
                self._designer(zone, evenement.position().toPoint())
            elif evenement.type() == QEvent.Type.Leave:
                self.allumer(None)
        return super().eventFilter(objet, evenement)

    def _html(self, traduction: Traduction) -> str:
        """Texte traduit : termes du glossaire en bleu, mots non traduits en gris italique."""
        morceaux = []
        for morceau in traduction.morceaux:
            texte = escape(morceau.texte)
            if morceau.nature == TERME:
                texte = f'<span style="color: {COULEUR_TERME};">{texte}</span>'
            elif morceau.nature == SOURCE:
                texte = f'<span style="color: {COULEUR_ABSENT}; font-style: italic;">{texte}</span>'
            morceaux.append(texte)
        sens = "rtl" if traduction.cible == AR else "ltr"
        marque = MARQUE_RTL if traduction.cible == AR else ""
        return f'<div dir="{sens}" style="white-space: pre-wrap;">{marque}{"".join(morceaux)}</div>'

    # ------------------------------------------------------------------ presse-papiers et fichiers
    def copier(self) -> None:
        """Copie la traduction dans le presse-papiers."""
        if self.traduction is None:
            return
        QGuiApplication.clipboard().setText(self.traduction.texte)
        self.bouton_copier.setText("Copié")
        self._retour_copier.start()
        self.message.emit("Traduction copiée dans le presse-papiers")

    def importer(self, chemin: str | Path | None = None) -> bool:
        """Importe un fichier .txt, .docx ou .doc dans la zone source, puis le traduit."""
        if chemin is None:
            depart = str(self.fichier.parent) if self.fichier is not None else ""
            chemin, _ = QFileDialog.getOpenFileName(self, "Importer un texte", depart, documents.FILTRE_IMPORT)
            if not chemin:
                return False
        try:
            texte = documents.lire(chemin)
        except documents.ErreurDocument as erreur:
            self._avertir("Import impossible", str(erreur))
            return False
        if not texte.strip():
            self._avertir("Import impossible", f"« {Path(chemin).name} » ne contient pas de texte.")
            return False
        self.definir_texte(texte, Path(chemin))
        self.traduire()
        return True

    def exporter(self, chemin: str | Path | None = None) -> bool:
        """Enregistre la traduction dans un fichier .docx ou .txt."""
        if self.traduction is None:
            self.message.emit("Il n’y a pas encore de traduction à exporter.")
            return False
        if chemin is None:
            # À côté du fichier importé ; sinon dans le dossier « Documents ».
            documents_de_l_utilisateur = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation)
            dossier = self.fichier.parent if self.fichier is not None else Path(documents_de_l_utilisateur
                                                                                 or Path.home())
            propose = dossier / documents.nom_d_export(self.fichier)
            chemin, filtre = QFileDialog.getSaveFileName(self, "Exporter la traduction", str(propose),
                                                         ";;".join(documents.FILTRES_EXPORT.values()))
            if not chemin:
                return False
            if not Path(chemin).suffix:
                # Aucune extension saisie : on prend celle du format choisi dans la fenêtre.
                extension = next((ext for ext, nom in documents.FILTRES_EXPORT.items() if nom == filtre), ".docx")
                chemin += extension
        try:
            documents.ecrire(chemin, self.traduction.texte, self.traduction.cible)
        except documents.ErreurDocument as erreur:
            self._avertir("Export impossible", str(erreur))
            return False
        self.message.emit(f"Traduction enregistrée : {Path(chemin).name}")
        return True

    def _avertir(self, titre: str, texte: str) -> None:
        boites.afficher(self.window(), "alerte", titre, texte)
