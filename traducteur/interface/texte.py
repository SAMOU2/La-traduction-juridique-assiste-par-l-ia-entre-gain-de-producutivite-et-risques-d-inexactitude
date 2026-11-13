"""Écran « Texte » : traduction d'un texte à l'aide du glossaire.

De haut en bas : le texte source et sa traduction, côte à côte dans un même panneau ; la
bande des cinq étapes du traitement ; le tableau des termes du glossaire relevés dans le
texte, qui reprend en colonnes l'enchaînement de l'écran « Terme » :

① Terme → ② Définition → ③ Équivalent → ④ Contextualisation → ⑤ Ressources

Les boutons « Importer », « Exporter » et « Traduire » appartiennent à cet écran ; la
fenêtre les place dans la barre d'outils.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from types import MappingProxyType

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
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
    QAbstractButton,
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
from ..glossaire import Glossaire
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
from ..traduction import SOURCE, TERME, TermeDetecte, Traducteur, Traduction
from . import boites, icones, theme
from .composants import (
    MARQUE_RTL,
    EtiquetteCourte,
    Panneau,
    ZoneDefilante,
    bornes_des_colonnes,
    compte,
    direction,
    etiquette,
    icone_fixe,
    infobulle,
    nombre,
    pastille,
    repeindre,
    separateur,
)
from .dessin import abreger, couper_en_lignes, dessiner_ligne, extrait_autour, largeur_du_texte, police
from .fiche import ETAPES as CHAMPS
from .fiche import categorie_et_pluriel, mention_a_verifier

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
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : ouvrez un fichier CSV (menu Fichier → Ouvrir un glossaire)."
_TEXTE_MODIFIE = "Le texte source a changé : cliquez sur « Traduire » pour mettre la traduction à jour."
#: Rappelé sous les états « Traduction terminée » et « Traduction partielle ».
_A_RELIRE = "Le traducteur ne connaît que les termes du glossaire : relisez et complétez la traduction."

#: Les cinq étapes du traitement : (nom, nom court, ce que fait l'étape).
ETAPES = (
    ("Segmentation", "Segmentation", "Le texte est découpé en phrases."),
    ("Découpage", "Découpage", "Chaque phrase est découpée en mots."),
    ("Recherche dans le CSV", "Recherche",
     "Les phrases, puis les expressions, puis les mots sont cherchés dans le glossaire."),
    ("Règles linguistiques", "Règles",
     "Lexique, grammaire, sémantique : synonymes, pluriel, article, complément du nom, choix entre plusieurs sens."),
    ("Reconstruction", "Reconstruction", "Chaque phrase est récrite dans la langue cible, avec sa ponctuation."),
)
#: Largeurs relatives des colonnes du tableau des termes (celles de la proposition).
COLONNES = (224, 340, 208, 320, 300)

#: Hauteur d'une ligne des zones de texte, en pixels, selon la langue. Une hauteur fixe garde des
#: lignes régulières quand une même ligne mêle des mots français et des mots arabes.
INTERLIGNE = {FR: 26, AR: 32}
#: Espace entre deux paragraphes des zones de texte.
ESPACE_ENTRE_PARAGRAPHES = 8
#: Couleur des termes du glossaire, et couleur des mots absents du glossaire, dans les deux zones de texte.
COULEUR_TERME = theme.BLEU
COULEUR_ABSENT = theme.TEXTE_4


def _decompte(phrases: int, mots: int, caracteres: int) -> tuple[str, str, str]:
    """Décompte d'un texte, du plus long au plus court : « 4 phrases · 76 mots · 422 caractères », …, « 76 mots »."""
    elements = (compte(phrases, "phrase"), compte(mots, "mot"), compte(caracteres, "caractère"))
    return " · ".join(elements), " · ".join(elements[:2]), elements[1]


def _bouton(texte: str, classe: str, largeur: int, hauteur: int, nom_icone: str = "", info: str = "") -> QPushButton:
    """Bouton de l'écran : « principal » (plein) ou « contour »."""
    bouton = QPushButton(texte)
    bouton.setProperty("classe", classe)
    if nom_icone:
        couleur = theme.SURFACE if classe == "principal" else theme.TEXTE_2
        bouton.setIcon(icones.icone(nom_icone, couleur, 16, 1.6, marge=3,
                                    couleur_inactive=theme.SURFACE if classe == "principal" else theme.TEXTE_4))
        bouton.setIconSize(QSize(19, 16))
    bouton.setFixedSize(largeur, hauteur)
    bouton.setCursor(Qt.CursorShape.PointingHandCursor)
    if info:
        bouton.setToolTip(info)
    return bouton


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
    """État de la traduction, dans une pastille : une icône et un texte.

    Le texte a plusieurs formes, de la plus longue à la plus courte. La pastille affiche la
    première qui tient dans la largeur reçue, et se place à droite de cette largeur.
    """

    HAUTEUR = 24
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
        self.hide()

    def definir(self, etat: str, *formes: str, explication: str = "") -> None:
        """Change l'état affiché ; sans texte, la pastille est cachée."""
        self.etat = etat
        self._formes = tuple(formes) or ("",)
        self.setToolTip(infobulle(explication))
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
        return round(10 + 14 + 7 + largeur_du_texte(forme, police(self.font(), 12, gras=True)) + 16)

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
        dessiner_ligne(peintre, QRectF(gauche + 30, 0, largeur - 30 - 8, self.height()), texte,
                       police(self.font(), 12, gras=True), couleur, base=16.4)


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
    """Bande des cinq étapes du traitement, sur une ligne : numéro, nom, résultat.

    Les étapes occupent leur largeur propre et l'espace restant est réparti entre elles. Quand
    la place manque, les noms puis les résultats prennent leur forme courte.
    """

    HAUTEUR = 44
    #: Espace minimal entre deux étapes (un chevron y est dessiné).
    ECART_MINIMAL = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HAUTEUR)
        self.etapes = [Etape(nom, nom_court, description) for nom, nom_court, description in ETAPES]
        self.faite = False
        self.setAccessibleName("Étapes du traitement")
        self.afficher(None)

    # ------------------------------------------------------------------ résultats
    def afficher(self, traduction: Traduction | None) -> None:
        """Affiche le résultat de chaque étape ; sans traduction, seuls les noms des étapes sont affichés."""
        self.faite = traduction is not None
        for etape in self.etapes:
            etape.resultat = etape.resultat_court = etape.explication = ""
        if traduction is not None:
            self._renseigner(traduction)
        self.setAccessibleDescription(" ; ".join(
            f"{etape.nom} : {etape.resultat}" if etape.resultat else etape.nom for etape in self.etapes))
        self.update()

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

        reprises = traduction.phrases_attestees
        reconstruction.resultat, reconstruction.resultat_court = compte(phrases, "phrase"), nombre(phrases)
        reconstruction.explication = (
            f"{compte(reprises, 'phrase reprise', 'phrases reprises')} des exemples du glossaire, "
            f"{compte(phrases - reprises, 'phrase traduite', 'phrases traduites')} mot à mot.")

    # ------------------------------------------------------------------ mise en place
    def _polices(self):
        return police(self.font(), 13, gras=True), police(self.font(), 13)

    def _formes(self) -> list[list[tuple[str, str]]]:
        """Les textes des cinq étapes (nom, résultat), de la forme la plus longue à la plus courte."""
        etapes = self.etapes
        formes = [[(etape.nom, etape.resultat) for etape in etapes],
                  [(etape.nom_court, etape.resultat) for etape in etapes],
                  [(etape.nom_court, etape.resultat_court) for etape in etapes],
                  [(etape.nom_court, "") for etape in etapes]]
        return [forme for rang, forme in enumerate(formes) if forme not in formes[:rang]]

    def _largeurs(self, forme: Sequence[tuple[str, str]]) -> list[float]:
        gras, normal = self._polices()
        return [20 + 10 + largeur_du_texte(nom, gras)
                + (4 + largeur_du_texte(" " + resultat, normal) if resultat else 0) for nom, resultat in forme]

    def disposition(self) -> tuple[list[tuple[str, str]], list[float], float]:
        """Les textes affichés (nom, résultat), l'abscisse de chaque étape et l'espace entre deux étapes."""
        place = self.width() - 2 * theme.MARGE
        formes = self._formes()
        choisie = next((forme for forme in formes
                        if sum(self._largeurs(forme)) + self.ECART_MINIMAL * (len(forme) - 1) <= place), formes[-1])
        largeurs = self._largeurs(choisie)
        ecart = max((place - sum(largeurs)) / (len(choisie) - 1), 4.0)
        abscisses, x = [], float(theme.MARGE)
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
        for rang, (gauche, largeur) in enumerate(zip(abscisses, self._largeurs(textes), strict=True)):
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
        gras, normal = self._polices()
        textes, abscisses, ecart = self.disposition()
        chevron = icones.image("chevron-d", theme.TEXTE_4, 14, 1.5) if ecart >= 20 else None
        for rang, ((nom, resultat), x) in enumerate(zip(textes, abscisses, strict=True)):
            if rang and chevron is not None:
                peintre.drawPixmap(QPointF(x - ecart / 2 - 7, 15), chevron)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_100))
            peintre.drawRoundedRect(QRectF(x, 12, 20, 20), 6, 6)
            dessiner_ligne(peintre, QRectF(x, 12, 20, 20), str(rang + 1), police(self.font(), 12, gras=True),
                           theme.TEXTE_2 if self.faite else theme.TEXTE_4, alignement=Qt.AlignmentFlag.AlignHCenter)
            largeur_du_nom = largeur_du_texte(nom, gras)
            dessiner_ligne(peintre, QRectF(x + 30, 0, largeur_du_nom + 2, self.height()), nom, gras,
                           theme.TEXTE if self.faite else theme.TEXTE_3, base=26.5)
            if resultat:
                cadre = QRectF(x + 30 + largeur_du_nom + 4, 0, largeur_du_texte(" " + resultat, normal) + 2,
                               self.height())
                dessiner_ligne(peintre, cadre, " " + resultat, normal, theme.TEXTE_3, base=26.5)


# ====================================================================== tableau des termes
def passage_du_terme(terme: TermeDetecte, traduction: Traduction) \
        -> tuple[tuple[str, list[tuple[int, int]]], tuple[str, list[tuple[int, int]]]]:
    """Le passage du texte qui illustre un terme : une phrase du texte source et sa traduction.

    Renvoie, pour chacune, son texte et les positions (début, fin) du terme à mettre en
    évidence. Parmi les phrases où le terme figure, on retient la première dont la traduction
    contient l'équivalent du terme ; à défaut, la première phrase.
    """
    choix = None
    for occurrence in terme.occurrences:
        phrase = traduction.phrases[occurrence.phrase]
        evidences, position = [], 0
        for morceau in phrase.morceaux:
            if morceau.nature == TERME and morceau.entree is terme.entree:
                evidences.append((position, position + len(morceau.texte)))
            position += len(morceau.texte)
        if choix is None or evidences:
            choix = (phrase, evidences)
        if evidences:
            break
    phrase, evidences_cible = choix
    debut = phrase.source.debut
    evidences_source = [(occurrence.debut - debut, occurrence.fin - debut)
                        for occurrence in phrase.occurrences if occurrence.entree is terme.entree]
    return (phrase.source.texte, evidences_source), (phrase.texte, evidences_cible)


class LigneTerme(QAbstractButton):
    """Une ligne du tableau : terme, définition, équivalent, contextualisation, ressources.

    La ligne est dessinée directement : chaque texte est abrégé à la largeur exacte de sa case.
    Un clic ouvre la fiche du terme.
    """

    HAUTEUR = 62

    def __init__(self, terme: TermeDetecte, traduction: Traduction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detecte = terme
        entree = self.entree = terme.entree
        source = self.source = traduction.source
        cible = self.cible = traduction.cible
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(self.HAUTEUR)

        # ① Terme
        self.libelle = entree.terme(source)
        self.categorie = entree.categorie(source)
        self.occurrences = compte(len(terme.occurrences), "occurrence")
        self.occurrences_en_bref = f"{nombre(len(terme.occurrences))} occ."
        # ② Définition : dans la langue du texte ; à défaut, dans l'autre langue.
        self.langue_definition = next((langue for langue in (source, cible) if entree.definition(langue)), source)
        self.definition = entree.definition(self.langue_definition)
        #: Vrai si la définition n'est reprise d'aucune source citée.
        self.a_verifier = not entree.source_definition or mention_a_verifier(entree.source_definition) is not None
        # ③ Équivalent ; s'il y a plusieurs sens, la seconde ligne le signale à la place de la grammaire.
        self.equivalent = entree.terme(cible)
        self.grammaire = categorie_et_pluriel(entree, cible)
        self.categorie_cible = entree.categorie(cible)
        self.incertain = terme.incertain
        autres = " / ".join(autre.terme(cible) for autre in terme.autres_candidats)
        self.alerte = "" if not autres else (f"Ambigu : aussi « {autres} »" if terme.incertain
                                             else f"Autre sens : « {autres} »")
        # ④ Contextualisation : la phrase du texte et sa traduction.
        self.passage_source, self.passage_cible = passage_du_terme(terme, traduction)
        # ⑤ Ressources : la première référence écrite dans la langue du texte ; à défaut, la première.
        self.ressource = next((ressource for ressource in entree.ressources
                               if (deviner_langue(ressource) or FR) == source),
                              entree.ressources[0] if entree.ressources else "")
        self.langue_ressource = deviner_langue(self.ressource) or FR
        titre, virgule, detail = self.ressource.partition("،" if self.langue_ressource == AR else ",")
        self.titre_ressource, self.detail_ressource = (titre.strip(), detail.strip()) if virgule else (self.ressource,
                                                                                                    "")
        self.autres_ressources = max(len(entree.ressources) - 1, 0)

        self.setText(f"{self.libelle} — {self.equivalent}")
        self.setAccessibleDescription(self.definition)
        self._ajuste_pour = -1
        self._lignes_de_definition: list[str] = []
        self._definition_abregee = False
        self._passages: list[tuple[str, str, list[tuple[int, int]]]] = []

    # ------------------------------------------------------------------ textes ajustés à la largeur
    def _cases(self) -> list[tuple[int, int]]:
        """Abscisse et largeur utile de chaque case (marges retirées)."""
        return cases_du_tableau(self.width())

    def _police_de_definition(self):
        return police(self.font(), 15 if self.langue_definition == AR else 13)

    def _police_de_passage(self, langue: str):
        return police(self.font(), 14 if langue == AR else 13)

    def ajuster(self) -> None:
        """Coupe la définition en deux lignes et choisit les passages qui tiennent dans leur case."""
        if self._ajuste_pour == self.width():
            return
        self._ajuste_pour = self.width()
        cases = self._cases()
        self._lignes_de_definition, self._definition_abregee = couper_en_lignes(
            self.definition, self._police_de_definition(), cases[1][1] - 22, 2)
        largeur = cases[3][1]
        (texte_source, evidences_source), (texte_cible, evidences_cible) = self.passage_source, self.passage_cible
        self._passages = [(self.source, *extrait_autour(texte_source, evidences_source,
                                                        self._police_de_passage(self.source), largeur))]
        if texte_cible.strip():
            # Sans équivalent à mettre en évidence, le passage est pris au même endroit de la phrase.
            repere = (evidences_source[0][0] / max(len(texte_source), 1)) if evidences_source else 0.0
            self._passages.append((self.cible, *extrait_autour(texte_cible, evidences_cible,
                                                               self._police_de_passage(self.cible), largeur, repere)))

    def _polices_du_terme(self):
        """Sous le terme : la police de la catégorie et celle du nombre d'occurrences."""
        if self.source == AR:
            return police(self.font(), 14), police(self.font(), 12)
        return police(self.font(), 12, italique=True), police(self.font(), 12)

    def sous_le_terme(self, place: float | None = None) -> tuple[str, str]:
        """Sous le terme : sa catégorie et son nombre d'occurrences, tels qu'ils sont affichés.

        Quand la case est étroite, « occurrences » est abrégé, puis la catégorie est retirée.
        """
        if place is None:
            place = self._cases()[0][1]
        de_categorie, du_nombre = self._polices_du_terme()
        separateur = 3 * largeur_du_texte(" ", du_nombre) + largeur_du_texte("·", du_nombre)
        formes = [(self.categorie, self.occurrences), (self.categorie, self.occurrences_en_bref),
                  ("", self.occurrences), ("", self.occurrences_en_bref)]
        for categorie, occurrences in formes:
            largeur = largeur_du_texte(occurrences, du_nombre)
            if categorie:
                largeur += largeur_du_texte(categorie, de_categorie) + separateur
            if largeur <= place:
                return categorie, occurrences
        return formes[-1]

    def grammaire_affichee(self, place: float | None = None) -> str:
        """Sous l'équivalent : sa catégorie et son pluriel ; la catégorie seule si le pluriel ne tient pas."""
        if place is None:
            place = self._cases()[2][1]
        de_grammaire = police(self.font(), 13 if self.cible == AR else 12)
        if self.categorie_cible and largeur_du_texte(self.grammaire, de_grammaire) > place:
            return self.categorie_cible
        return self.grammaire

    def lignes_de_definition(self) -> list[str]:
        """La définition telle qu'elle est affichée : deux lignes au plus."""
        self.ajuster()
        return list(self._lignes_de_definition)

    def passages_affiches(self) -> list[tuple[str, str]]:
        """Les passages affichés dans la colonne « Contextualisation » : (langue, texte)."""
        self.ajuster()
        return [(langue, texte) for langue, texte, _ in self._passages]

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self.ajuster()

    # ------------------------------------------------------------------ infobulles
    def infobulle(self, colonne: int) -> str:
        """Texte de l'infobulle d'une case : ce que la case abrège ou ne peut pas montrer."""
        entree = self.entree
        if colonne == 1 and self.definition:
            source = entree.source_definition
            mention = ("Définition à vérifier : elle n’est reprise d’aucune source citée." if self.a_verifier
                       else f"Source : {source}")
            return f"<qt>{escape(self.definition)}<br><br>{escape(mention)}</qt>"
        if colonne == 2 and self.alerte:
            detail = ("Le contexte n’a pas permis de choisir entre les sens de ce terme : vérifiez l’équivalent."
                      if self.incertain else "Ce terme a d’autres sens dans le glossaire.")
            return f"<qt>{escape(self.alerte)}<br>{escape(detail)}</qt>"
        if colonne == 3:
            lignes = [texte.strip() for texte in (self.passage_source[0], self.passage_cible[0]) if texte.strip()]
            return "<qt>" + "<br><br>".join(escape(ligne) for ligne in lignes) + "</qt>"
        if colonne == 4 and entree.ressources:
            return "<qt>" + "<br>".join(escape(ressource) for ressource in entree.ressources) + "</qt>"
        return infobulle(f"Ouvrir la fiche de « {self.libelle} »")

    def colonne_a(self, x: float) -> int:
        bornes = bornes_des_colonnes(self.width(), COLONNES)
        return next((rang for rang in range(len(COLONNES)) if x < bornes[rang + 1]), len(COLONNES) - 1)

    def event(self, evenement) -> bool:
        if evenement.type() == QEvent.Type.ToolTip:
            QToolTip.showText(evenement.globalPos(), self.infobulle(self.colonne_a(evenement.pos().x())), self)
            return True
        return super().event(evenement)

    # ------------------------------------------------------------------ dessin
    def paintEvent(self, evenement) -> None:  # noqa: N802
        self.ajuster()
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        largeur, hauteur = self.width(), self.height()
        survol = self.underMouse() or self.hasFocus()
        dessiner_le_fond(peintre, largeur, 0, hauteur, survol=survol)
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, hauteur - 1, largeur, hauteur - 1)
        if self.hasFocus():
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1))
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            peintre.drawRect(QRectF(0.5, 0.5, largeur - 1, hauteur - 2))
        base = self.font()
        cases = self._cases()
        droite = Qt.AlignmentFlag.AlignRight

        def ecrire(x: float, place: float, ligne_de_base: float, texte: str, police_du_texte, couleur: str, *,
                   langue: str = FR, alignement=None, evidences=()) -> None:
            dessiner_ligne(peintre, QRectF(x, 0, place, hauteur), texte, police_du_texte, couleur, langue=langue,
                           alignement=alignement, base=ligne_de_base, evidences=evidences)

        def ecrire_la_categorie(x: float, place: float, ligne_de_base: float, categorie: str, suite: str) -> None:
            """En français : la catégorie grammaticale en italique (comme sur la fiche), puis sa suite."""
            de_categorie, de_suite = police(base, 12, italique=True), police(base, 12)
            categorie = abreger(categorie, de_categorie, max(place - largeur_du_texte(suite, de_suite), 40))
            ecrire(x, place, ligne_de_base, categorie, de_categorie, theme.TEXTE_3)
            decalage = largeur_du_texte(categorie, de_categorie)
            ecrire(x + decalage, place - decalage, ligne_de_base, abreger(suite, de_suite, place - decalage),
                   de_suite, theme.TEXTE_3)

        # ① Terme, catégorie et nombre d'occurrences
        x, place = cases[0]
        categorie, occurrences = self.sous_le_terme(place)
        if self.source == AR:
            du_terme = police(base, 17, gras=True)
            ecrire(x, place, 28, abreger(self.libelle, du_terme, place), du_terme, theme.BLEU_FONCE, langue=AR)
            de_categorie, du_nombre = self._polices_du_terme()
            ecrire(x, place, 49, categorie, de_categorie, theme.TEXTE_3, langue=AR)
            reste = place - (largeur_du_texte(categorie, de_categorie) + largeur_du_texte(" ", du_nombre)
                             if categorie else 0)
            suite = occurrences + (" ·" if categorie else "")
            ecrire(x, reste, 49, abreger(suite, du_nombre, reste), du_nombre, theme.TEXTE_3, alignement=droite)
        else:
            du_terme = police(base, 14, gras=True)
            ecrire(x, place, 26, abreger(self.libelle, du_terme, place), du_terme, theme.BLEU_FONCE)
            ecrire_la_categorie(x, place, 45, categorie, (" · " if categorie else "") + occurrences)

        # ② Définition : un signe dit si elle est à vérifier, puis deux lignes au plus
        x, place = cases[1]
        if self.definition:
            signe = ("alerte", theme.AMBRE) if self.a_verifier else ("document", theme.TEXTE_3)
            peintre.drawPixmap(QPointF(x, 15), icones.image(*signe, 14, 1.6))
            arabe = self.langue_definition == AR
            for rang, ligne in enumerate(self._lignes_de_definition):
                ecrire(x + 22, place - 22, (26 + 22 * rang) if arabe else (26 + 19 * rang), ligne,
                       self._police_de_definition(), theme.TEXTE_2, langue=self.langue_definition)
        else:
            ecrire(x, place, 26, "Aucune définition", police(base, 13), theme.TEXTE_4)

        # ③ Équivalent ; dessous, sa grammaire, ou l'avertissement s'il y a plusieurs sens
        x, place = cases[2]
        cote = droite if self.cible == AR else Qt.AlignmentFlag.AlignLeft
        de_l_equivalent = police(base, 17 if self.cible == AR else 14, gras=True)
        ligne_basse = 49 if self.cible == AR else 45
        ecrire(x, place, 29 if self.cible == AR else 26, abreger(self.equivalent, de_l_equivalent, place),
               de_l_equivalent, theme.BLEU_FONCE, langue=self.cible)
        if self.alerte:
            de_l_alerte = police(base, 12, gras=self.incertain)
            ecrire(x, place, ligne_basse, abreger(self.alerte, de_l_alerte, place), de_l_alerte,
                   theme.AMBRE if self.incertain else theme.TEXTE_3, alignement=cote)
        elif self.grammaire:
            de_grammaire = police(base, 13 if self.cible == AR else 12)
            grammaire = self.grammaire_affichee(place)
            if self.cible == AR or not self.categorie_cible:
                ecrire(x, place, ligne_basse, abreger(grammaire, de_grammaire, place), de_grammaire, theme.TEXTE_3,
                       langue=self.cible)
            else:
                ecrire_la_categorie(x, place, ligne_basse, self.categorie_cible,
                                    grammaire[len(self.categorie_cible):])

        # ④ Contextualisation : le passage du texte, puis sa traduction
        x, place = cases[3]
        for rang, (langue, texte, evidences) in enumerate(self._passages):
            ligne_de_base = (27 if langue == AR else 26) if rang == 0 else (48 if langue == AR else 46)
            ecrire(x, place, ligne_de_base, texte, self._police_de_passage(langue), theme.TEXTE_2, langue=langue,
                   evidences=evidences)

        # ⑤ Ressources : la référence, le nombre des autres références, puis le détail (début abrégé)
        x, place = cases[4]
        if not self.ressource:
            ecrire(x, place, 26, "Aucune ressource", police(base, 13), theme.TEXTE_4)
            return
        arabe = self.langue_ressource == AR
        reserve = 0
        if self.autres_ressources:
            autres = f"+{self.autres_ressources}"
            de_pastille = police(base, 11, gras=True)
            reserve = max(round(largeur_du_texte(autres, de_pastille)) + 12, 22)
            cadre = QRectF(x if arabe else x + place - reserve, 13, reserve, 18)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_100))
            peintre.drawRoundedRect(cadre, 9, 9)
            dessiner_ligne(peintre, cadre, autres, de_pastille, theme.TEXTE_2,
                           alignement=Qt.AlignmentFlag.AlignHCenter)
            reserve += 8
        du_titre = police(base, 15 if arabe else 13, gras=True)
        ecrire(x + (reserve if arabe else 0), place - reserve, 27 if arabe else 26,
               abreger(self.titre_ressource, du_titre, place - reserve), du_titre, theme.TEXTE,
               langue=self.langue_ressource)
        du_detail = police(base, 13 if arabe else 12)
        ecrire(x, place, 48 if arabe else 45, abreger(self.detail_ressource, du_detail, place - 8, par_le_debut=True),
               du_detail, theme.TEXTE_3, langue=self.langue_ressource)


def cases_du_tableau(largeur: int) -> list[tuple[int, int]]:
    """Abscisse et largeur utile de chaque case du tableau, marges retirées.

    Les bords du tableau gardent la marge des panneaux ; entre deux colonnes, la marge est
    réduite quand le tableau est étroit, pour laisser plus de place aux textes.
    """
    bornes = bornes_des_colonnes(largeur, COLONNES)
    interieure = theme.MARGE if largeur >= 1240 else 18 if largeur >= 1040 else 14
    dernier = len(COLONNES) - 1
    cases = []
    for rang in range(len(COLONNES)):
        gauche = bornes[rang] + (theme.MARGE if rang == 0 else interieure)
        droite = bornes[rang + 1] - (theme.MARGE if rang == dernier else interieure)
        cases.append((gauche, max(droite - gauche, 10)))
    return cases


def dessiner_le_fond(peintre: QPainter, largeur: int, haut: int, hauteur: int, *, survol: bool = False) -> None:
    """Fond d'une ligne du tableau : colonne « Équivalent » teintée, filets entre les colonnes."""
    bornes = bornes_des_colonnes(largeur, COLONNES)
    peintre.fillRect(0, haut, largeur, hauteur, QColor(theme.GRIS_50 if survol else theme.SURFACE))
    peintre.fillRect(bornes[2], haut, bornes[3] - bornes[2], hauteur,
                     QColor(theme.BLEU_50 if survol else theme.TEINTE_TABLEAU))
    peintre.setPen(QColor(theme.FILET_DOUX))
    for borne in bornes[1:-1]:
        peintre.drawLine(borne, haut, borne, haut + hauteur)


class EnteteColonnes(QWidget):
    """Ligne de titres du tableau : les cinq champs de l'enchaînement, numérotés."""

    HAUTEUR = 30

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HAUTEUR)
        self.titres = list(CHAMPS)
        #: Les filets entre les colonnes ne sont dessinés que s'il y a des lignes dessous.
        self.filets = False
        self.setAccessibleName(" ; ".join(CHAMPS))

    def definir_filets(self, visibles: bool) -> None:
        self.filets = visibles
        self.update()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        peintre.fillRect(self.rect(), QColor(theme.GRIS_50))
        bornes = bornes_des_colonnes(self.width(), COLONNES)
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, 0, self.width(), 0)
        peintre.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        if self.filets:
            for borne in bornes[1:-1]:
                peintre.drawLine(borne, 0, borne, self.height())
        du_numero = police(self.font(), 10, gras=True)
        du_titre = police(self.font(), 11, gras=True, espacement=0.6)
        cases = cases_du_tableau(self.width())
        for rang, titre in enumerate(self.titres):
            gauche, largeur_utile = cases[rang]
            accent = rang == 2  # l'équivalent est le champ mis en avant
            centre = QPointF(gauche + 8, 15)
            if accent:
                peintre.setPen(Qt.PenStyle.NoPen)
                peintre.setBrush(QColor(theme.BLEU))
                peintre.drawEllipse(centre, 8, 8)
            else:
                peintre.setPen(QPen(QColor(theme.BLEU_200), 1.5))
                peintre.setBrush(QColor(theme.SURFACE))
                peintre.drawEllipse(centre, 7.25, 7.25)
            dessiner_ligne(peintre, QRectF(gauche, 7, 16, 16), str(rang + 1), du_numero,
                           theme.SURFACE if accent else theme.BLEU, alignement=Qt.AlignmentFlag.AlignHCenter)
            place = largeur_utile - 23
            dessiner_ligne(peintre, QRectF(gauche + 23, 0, place, self.height()),
                           abreger(titre.upper(), du_titre, place), du_titre,
                           theme.BLEU_FONCE if accent else theme.TEXTE_3, base=18.8)


class LignesTermes(QWidget):
    """Les lignes du tableau, ou un message centré quand il n'y a aucun terme à montrer."""

    #: Demande d'ouverture de la fiche d'une entrée (clic sur une ligne).
    ouverture = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lignes: list[LigneTerme] = []
        self.titre_du_message = self.texte_du_message = ""

    def definir(self, traduction: Traduction | None) -> None:
        for ligne in self.lignes:
            ligne.setParent(None)
            ligne.deleteLater()
        self.lignes = []
        for terme in (traduction.termes if traduction is not None else []):
            ligne = LigneTerme(terme, traduction, self)
            ligne.clicked.connect(lambda _=False, entree=terme.entree: self.ouverture.emit(entree))
            ligne.show()
            self.lignes.append(ligne)
        self._placer()
        self.updateGeometry()
        self.update()

    def definir_message(self, titre: str, texte: str) -> None:
        """Message affiché quand le tableau n'a pas de ligne."""
        self.titre_du_message, self.texte_du_message = titre, texte
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(max(self.width(), 400), len(self.lignes) * LigneTerme.HAUTEUR)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, len(self.lignes) * LigneTerme.HAUTEUR)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer()

    def _placer(self) -> None:
        for rang, ligne in enumerate(self.lignes):
            ligne.setGeometry(0, rang * LigneTerme.HAUTEUR, self.width(), LigneTerme.HAUTEUR)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.lignes:
            # Sous la dernière ligne, les colonnes se prolongent jusqu'au bas du panneau.
            haut = len(self.lignes) * LigneTerme.HAUTEUR
            if haut < self.height():
                dessiner_le_fond(peintre, self.width(), haut, self.height() - haut)
            return
        # Aucun terme : une icône dans un disque (si la hauteur le permet), un titre, une explication.
        du_titre, du_texte = police(self.font(), 13, gras=True), police(self.font(), 13)
        place = self.width() - 2 * theme.MARGE
        avec_disque = self.height() >= 124
        hauteur = (40 + 14 if avec_disque else 0) + 20 + 4 + 20
        y = max((self.height() - hauteur) / 2 - 4, 4)
        if avec_disque:
            centre = QPointF(self.width() / 2, y + 20)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_100))
            peintre.drawEllipse(centre, 20, 20)
            peintre.drawPixmap(QPointF(centre.x() - 9, centre.y() - 9), icones.image("texte", theme.TEXTE_4, 18))
            y += 54
        centre_h = Qt.AlignmentFlag.AlignHCenter
        dessiner_ligne(peintre, QRectF(theme.MARGE, y, place, 20), abreger(self.titre_du_message, du_titre, place),
                       du_titre, theme.TEXTE_2, alignement=centre_h)
        dessiner_ligne(peintre, QRectF(theme.MARGE, y + 24, place, 20), abreger(self.texte_du_message, du_texte, place),
                       du_texte, theme.TEXTE_3, alignement=centre_h)


class TableauTermes(Panneau):
    """Tableau des termes du glossaire relevés dans le texte."""

    #: Demande d'ouverture de la fiche d'une entrée (clic sur une ligne).
    ouverture = Signal(object)

    HAUTEUR_DU_TITRE = 42

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        titre = QWidget()
        titre.setFixedHeight(self.HAUTEUR_DU_TITRE)
        ligne = QHBoxLayout(titre)
        ligne.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        ligne.setSpacing(12)
        self.titre = etiquette("Termes juridiques détectés", "titrePanneau")
        self.nombre = pastille()
        self.aide = EtiquetteCourte("", "aidePanneau")
        self.aide.definir_texte("Cliquez sur un terme pour ouvrir sa fiche", "")
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.legende = Legende()
        ligne.addWidget(self.titre)
        ligne.addWidget(self.nombre)
        ligne.addWidget(self.aide, 1)
        ligne.addWidget(self.legende)
        ensemble.addWidget(titre)

        self.entete = EnteteColonnes()
        ensemble.addWidget(self.entete)
        self.contenu = LignesTermes()
        self.contenu.ouverture.connect(self.ouverture)
        self.defilement = ZoneDefilante()
        self.defilement.definir_contenu(self.contenu)
        ensemble.addWidget(self.defilement, 1)
        self.setMinimumHeight(self.HAUTEUR_DU_TITRE + EnteteColonnes.HAUTEUR + LigneTerme.HAUTEUR + 4)
        self.afficher(None)

    def afficher(self, traduction: Traduction | None, *, sans_glossaire: bool = False) -> None:
        """Affiche les termes relevés par une traduction ; sans traduction, un message d'attente."""
        termes = traduction.termes if traduction is not None else []
        self.contenu.definir(traduction)
        if sans_glossaire:
            self.contenu.definir_message("Aucun glossaire n’est chargé",
                                         "Ouvrez un fichier CSV : menu Fichier → Ouvrir un glossaire.")
        elif traduction is None:
            self.contenu.definir_message("Les termes juridiques du texte s’afficheront ici",
                                         "Saisissez ou importez un texte, puis cliquez sur « Traduire ».")
        else:
            self.contenu.definir_message("Aucun terme du glossaire dans ce texte",
                                         "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
        self.nombre.setText(nombre(len(termes)))
        self.nombre.setVisible(traduction is not None)
        self.aide.setVisible(bool(termes))
        self.entete.definir_filets(bool(termes))
        # La légende ne cite que les signes présents dans le tableau.
        lignes = self.contenu.lignes
        reperes = []
        if any(ligne.definition and ligne.a_verifier for ligne in lignes):
            reperes.append(("alerte", theme.AMBRE, "Définition à vérifier", 0))
        if any(ligne.definition and not ligne.a_verifier for ligne in lignes):
            reperes.append(("document", theme.TEXTE_3, "Source citée", 1))
        self.legende.definir(reperes)
        self.defilement.revenir_en_haut()

    def lignes_affichees(self) -> list[LigneTerme]:
        return list(self.contenu.lignes)


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

        # Les deux zones partagent un panneau ; un filet vertical les sépare.
        self.panneau = Panneau()
        textes = QHBoxLayout(self.panneau)
        textes.setContentsMargins(0, 0, 0, 0)
        textes.setSpacing(0)
        filet = QFrame()
        filet.setObjectName("filetVertical")
        filet.setFixedWidth(1)
        textes.addWidget(self.panneau_source, 1)
        textes.addWidget(filet)
        textes.addWidget(self.panneau_cible, 1)

        # ---------------------------------------------------------- étapes et termes
        self.bande = BandeEtapes()
        self.termes = TableauTermes()
        self.termes.ouverture.connect(self.entree_demandee)

        page = QVBoxLayout(self)
        page.setContentsMargins(theme.MARGE, 0, theme.MARGE, 16)
        page.setSpacing(16)
        # Hauteurs de la proposition : 296 pour les textes, 338 pour le tableau.
        page.addWidget(self.panneau, 148)
        page.addWidget(self.bande)
        page.addWidget(self.termes, 169)

        raccourci = QShortcut(QKeySequence("Ctrl+Return"), self)
        raccourci.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        raccourci.activated.connect(self.traduire)
        self._decompte_differe = QTimer(self)
        self._decompte_differe.setSingleShot(True)
        self._decompte_differe.setInterval(200)
        self._decompte_differe.timeout.connect(self._afficher_le_decompte_source)

        self._appliquer_sens()
        self._afficher(None)

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
        ligne.addSpacing(12)
        ligne.addWidget(self.bouton_exporter)
        ligne.addSpacing(12)
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
            # Le texte ne correspond plus à la traduction affichée.
            self.zone_source.setExtraSelections([])
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
        self._afficher(self.traducteur.traduire(texte, self.source))

    def _afficher(self, traduction: Traduction | None) -> None:
        """Affiche une traduction, ou l'état initial si ``traduction`` est vide."""
        self.traduction = traduction
        self._afficher_le_decompte_source()
        self._actualiser_l_entete_source()
        self.bande.afficher(traduction)
        self.termes.afficher(traduction, sans_glossaire=self.traducteur is None)
        self.bouton_copier.setEnabled(traduction is not None)
        self.bouton_exporter.setEnabled(traduction is not None)
        if traduction is None:
            self.zone_source.setExtraSelections([])
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
            self._surligner_les_termes(traduction)
            self.zone_cible.setHtml(self._html(traduction))
            self.zone_cible.appliquer_l_interligne()
            self.zone_cible.orienter_les_paragraphes()
            self.decompte_cible.definir_texte(*_decompte(*traduction.decompte_cible()))
            self._afficher_le_bilan(traduction)
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
        if traduction.complete:
            self.badge.definir(
                "termine", f"Traduction terminée · {decompte}", f"Traduction terminée · {court}", "Traduction terminée",
                explication=f"Tous les mots du texte ont été trouvés dans le glossaire. {_A_RELIRE}")
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
                            f"{'il reste' if restants < 2 else 'ils restent'} à traduire. {_A_RELIRE}")
        if restants:
            reperes.append(("point", COULEUR_ABSENT, "mot absent, à traduire", 0))
        self.legende.definir(reperes)
        self._definir_etat(f"Traduction : {decompte} dans le glossaire.")

    def _definir_etat(self, texte: str) -> None:
        self.etat = texte
        self.etat_change.emit(texte)

    def _surligner_les_termes(self, traduction: Traduction) -> None:
        """Colore, dans le texte source, les termes trouvés dans le glossaire."""
        texte = traduction.texte_source
        # Qt compte les positions en unités UTF-16 : un caractère hors du plan de base en occupe deux.
        decalages = [rang for rang, caractere in enumerate(texte) if ord(caractere) > 0xFFFF]

        def position(indice: int) -> int:
            return indice + sum(1 for rang in decalages if rang < indice)

        couleur = QTextCharFormat()
        couleur.setForeground(QColor(COULEUR_TERME))
        selections = []
        for occurrence in traduction.occurrences:
            curseur = QTextCursor(self.zone_source.document())
            curseur.setPosition(position(occurrence.debut))
            curseur.setPosition(position(occurrence.fin), QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = curseur
            selection.format = couleur
            selections.append(selection)
        self.zone_source.setExtraSelections(selections)

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
