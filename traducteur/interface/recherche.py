"""Écran « Terme » : recherche d'un terme dans le glossaire.

La barre de recherche est placée par la fenêtre dans la barre d'outils. L'écran affiche la
fiche du terme trouvé : le terme et son équivalent, côte à côte. Sous la fiche, le menu « Plus
de détails » donne le reste à la demande : définition, contextualisation, ressources,
expressions, termes associés, synonymes. Sans fiche à afficher, un panneau invite à chercher
un terme ou propose les termes proches.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..glossaire import Entree, Glossaire, equivalent_a_verifier
from ..langues import AR, FR, NOM_EN_FRANCAIS, autre_langue, cle_souple, deviner_langue
from . import icones, theme
from .composants import (
    BoutonAjuste,
    DispositionFluide,
    EtiquetteCourte,
    Panneau,
    capitales,
    compte,
    direction,
    etiquette,
    icone_fixe,
    puce,
    repeindre,
    vider,
)
from .details import PanneauDetails
from .fiche import LARGEUR_MINIMALE, Fiche

#: Nombre de termes du glossaire proposés comme exemples avant la première recherche.
NOMBRE_EXEMPLES = 5

_INVITES = {
    FR: "Saisir un terme juridique, en français ou en arabe…",
    AR: "أدخل مصطلحا قانونيا، بالعربية أو بالفرنسية...",
}
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : choisissez un fichier CSV dans « Paramètres »."
#: Rappel affiché quand un terme n'est pas dans le glossaire : les fiches viennent du glossaire, et de lui seul.
_TERME_A_AJOUTER = "Les fiches viennent du glossaire. Le centre d’aide explique comment le compléter."

#: Raccourcis rappelés au pied du panneau d'accueil.
RACCOURCIS = (
    ("Ctrl+F", "aller à la barre de recherche"),
    ("Ctrl+I", "inverser le sens de traduction"),
    ("Ctrl+2", "traduire un texte"),
    ("F1", "centre d’aide"),
)


# ====================================================================== barre de recherche
class BarreRecherche(QWidget):
    """La barre de recherche : loupe, champ de saisie, résumé des résultats, bouton « Rechercher ».

    Un halo entoure la barre quand le champ a le curseur : le composant réserve sa place
    (``HALO`` pixels de chaque côté) et le dessine lui-même.
    """

    HALO = 3
    HAUTEUR = 44
    #: Largeur gardée au champ de saisie : le résumé des résultats n'est affiché que s'il reste cette place.
    LARGEUR_DU_CHAMP = 170

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HAUTEUR + 2 * self.HALO)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(self.HALO + 14, self.HALO, self.HALO + 5, self.HALO)
        ligne.setSpacing(12)
        ligne.addWidget(icone_fixe("loupe", theme.TEXTE_3, 18))
        self.champ = QLineEdit()
        self.champ.setObjectName("champRecherche")
        self.champ.setFrame(False)
        self.champ.setMinimumWidth(80)
        self.champ.installEventFilter(self)
        ligne.addWidget(self.champ, 1)
        self.resume = etiquette("", "resumeRecherche")
        self.resume.hide()
        ligne.addWidget(self.resume)
        self.effacer = QToolButton()
        self.effacer.setObjectName("effacerRecherche")
        self.effacer.setIcon(icones.icone("croix", theme.TEXTE_3, 11, 1.8))
        self.effacer.setIconSize(QSize(11, 11))
        self.effacer.setFixedSize(18, 18)
        self.effacer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.effacer.setToolTip("Effacer la recherche")
        self.effacer.hide()
        ligne.addWidget(self.effacer)
        ligne.addSpacing(3)
        self.bouton = BoutonAjuste("Rechercher", 112, 34)
        self.bouton.setProperty("classe", "principal")
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        ligne.addWidget(self.bouton)
        self._texte_du_resume = ""
        self.champ.textChanged.connect(self._texte_change)

    def definir_resume(self, texte: str) -> None:
        """Résumé des résultats, écrit dans la barre : « 1 terme · 23 expressions », « Aucun résultat »…"""
        self._texte_du_resume = texte
        self.resume.setText(texte)
        self._ajuster()

    def texte_du_resume(self) -> str:
        return self._texte_du_resume

    def _texte_change(self, texte: str) -> None:
        self.effacer.setVisible(bool(texte))
        self._ajuster()

    def _ajuster(self) -> None:
        """Affiche le résumé seulement s'il laisse assez de place au champ de saisie."""
        marges = self.layout().contentsMargins()
        fixe = marges.left() + marges.right() + 18 + self.bouton.width() + 3 + 3 * self.layout().spacing()
        if not self.effacer.isHidden():
            fixe += self.effacer.width() + self.layout().spacing()
        self.resume.ensurePolished()
        largeur = self.resume.fontMetrics().horizontalAdvance(self._texte_du_resume) + 4
        place = self.width() - fixe - self.layout().spacing() - largeur
        self.resume.setVisible(bool(self._texte_du_resume) and place >= self.LARGEUR_DU_CHAMP)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self._ajuster()

    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802
        if objet is self.champ and evenement.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.update()
        return False

    def mousePressEvent(self, evenement) -> None:  # noqa: N802
        self.champ.setFocus()
        super().mousePressEvent(evenement)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        actif = self.champ.hasFocus()
        if actif:
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.BLEU_100))
            peintre.drawRoundedRect(QRectF(self.rect()), 13, 13)
        retrait = self.HALO + (0.75 if actif else 0.5)
        peintre.setPen(QPen(QColor(theme.BLEU if actif else theme.FILET), 1.5 if actif else 1))
        peintre.setBrush(QColor(theme.SURFACE))
        peintre.drawRoundedRect(QRectF(self.rect()).adjusted(retrait, retrait, -retrait, -retrait), 10, 10)


# ====================================================================== panneau sans fiche
class PanneauAccueil(Panneau):
    """Panneau affiché quand il n'y a pas de fiche : avant la recherche, ou quand le terme est introuvable.

    Au centre, un message et des termes à ouvrir (exemples ou termes proches) ; au pied, les
    raccourcis ou un conseil.
    """

    #: Demande d'ouverture d'une entrée du glossaire (clic sur une puce).
    entree_demandee = Signal(object)
    #: Demande d'ouverture d'un fichier de glossaire.
    glossaire_demande = Signal()

    HAUTEUR_DU_PIED = 48

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.puces: list[QPushButton] = []
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        centre = QVBoxLayout()
        centre.setContentsMargins(theme.MARGE, 12, theme.MARGE, 12)
        centre.setSpacing(0)
        centre.addStretch(5)
        self.rond = QLabel()
        self.rond.setObjectName("rondAccueil")
        self.rond.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rond.setFixedSize(64, 64)
        centre.addWidget(self.rond, 0, Qt.AlignmentFlag.AlignHCenter)
        centre.addSpacing(22)
        self.titre = etiquette("", "accueilTitre", retour_ligne=True)
        self.titre.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        centre.addWidget(self.titre)
        centre.addSpacing(8)
        self.texte = etiquette("", "accueilTexte", retour_ligne=True, riche=True)
        self.texte.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        centre.addWidget(self.texte)
        centre.addSpacing(28)
        self.etiquette_puces = capitales("")
        self.etiquette_puces.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        centre.addWidget(self.etiquette_puces)
        centre.addSpacing(10)
        self._zone_puces = QWidget()
        self._rangee_puces = DispositionFluide(self._zone_puces, 8, 8, centre=True)
        centre.addWidget(self._zone_puces)
        self.bouton_glossaire = QPushButton("Ouvrir les paramètres")
        self.bouton_glossaire.setProperty("classe", "principal")
        self.bouton_glossaire.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_glossaire.setFixedHeight(38)
        self.bouton_glossaire.clicked.connect(self.glossaire_demande)
        centre.addWidget(self.bouton_glossaire, 0, Qt.AlignmentFlag.AlignHCenter)
        centre.addStretch(7)
        ensemble.addLayout(centre, 1)

        pied = QWidget()
        pied.setFixedHeight(self.HAUTEUR_DU_PIED)
        dans_le_pied = QHBoxLayout(pied)
        dans_le_pied.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        dans_le_pied.setSpacing(0)
        self.raccourcis = _Raccourcis()
        self.conseil = EtiquetteCourte("", "raccourci")
        self.conseil.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dans_le_pied.addWidget(self.raccourcis, 1)
        dans_le_pied.addWidget(self.conseil, 1)
        ensemble.addWidget(pied)
        self.afficher_accueil([], FR)

    # ------------------------------------------------------------------ les trois états
    def afficher_accueil(self, exemples: Sequence[tuple[str, Entree]], langue: str) -> None:
        """Avant toute recherche : invitation à chercher, quelques termes du glossaire en exemple."""
        self._composer(False, "Recherchez un terme juridique",
                       ("Saisissez un terme en français ou en arabe, puis appuyez sur Entrée.",
                        "Le sens de traduction s’adapte à la langue du terme."),
                       "Par exemple", exemples, langue)
        self.raccourcis.show()
        self.conseil.hide()

    def afficher_introuvable(self, requete: str, proches: Sequence[tuple[str, Entree]], langue: str) -> None:
        """Le terme cherché n'est pas dans le glossaire : les termes d'écriture proche sont proposés."""
        texte = "Ce terme n’est pas dans le glossaire. Vérifiez son orthographe"
        self._composer(True, f"Aucune entrée pour « {requete} »",
                       (texte + (", ou ouvrez un terme proche." if proches else "."),),
                       "Terme proche" if len(proches) == 1 else "Termes proches", proches, langue)
        self._conseiller(_TERME_A_AJOUTER)

    def afficher_sans_glossaire(self) -> None:
        """Aucun glossaire n'est chargé : il faut d'abord choisir un fichier CSV, dans « Paramètres »."""
        self._composer(True, "Aucun glossaire n’est chargé",
                       ("Les fiches viennent d’un fichier CSV : une ligne par terme, en français et en arabe.",
                        "Choisissez un glossaire dans « Paramètres » pour chercher un terme."), "", (), FR)
        self.bouton_glossaire.show()
        self._conseiller("Le format du fichier est décrit dans le centre d’aide.")

    def _conseiller(self, texte: str) -> None:
        self.conseil.definir_texte(texte)
        self.conseil.show()
        self.raccourcis.hide()

    def _composer(self, alerte: bool, titre: str, lignes: Sequence[str], etiquette_des_puces: str,
                  termes: Sequence[tuple[str, Entree]], langue: str) -> None:
        if self.rond.property("alerte") != alerte:
            self.rond.setProperty("alerte", alerte)
            repeindre(self.rond)
        self.rond.setPixmap(icones.image("loupe", theme.AMBRE if alerte else theme.BLEU, 28, 1.4))
        self.titre.setText(titre)
        self.texte.setText('<p align="center" style="margin: 0; line-height: 22px; -qt-line-height-type: fixed;">'
                           + "<br>".join(_echapper(ligne) for ligne in lignes) + "</p>")
        vider(self._rangee_puces)
        self.puces = []
        for libelle, entree in termes:
            bouton = puce(libelle, langue, classe="puceExemple", hauteur=30)
            bouton.clicked.connect(lambda _=False, cible=entree: self.entree_demandee.emit(cible))
            self._rangee_puces.addWidget(bouton)
            self.puces.append(bouton)
        self.etiquette_puces.setText(etiquette_des_puces.upper())
        self.etiquette_puces.setVisible(bool(termes))
        self._zone_puces.setVisible(bool(termes))
        self.bouton_glossaire.hide()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().paintEvent(evenement)
        peintre = QPainter(self)
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, self.height() - self.HAUTEUR_DU_PIED, self.width(), self.height() - self.HAUTEUR_DU_PIED)


def _echapper(texte: str) -> str:
    return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Raccourcis(QWidget):
    """Les raccourcis du pied de l'accueil, centrés ; les derniers sont retirés si la place manque."""

    ECART = 36

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.elements: list[QWidget] = []
        for touche, action in RACCOURCIS:
            element = QWidget(self)
            ligne = QHBoxLayout(element)
            ligne.setContentsMargins(0, 0, 0, 0)
            ligne.setSpacing(8)
            # La touche est écrite comme sur le clavier du système (« ⌘F » sur un Mac).
            nom = QKeySequence(touche).toString(QKeySequence.SequenceFormat.NativeText)
            cadre = etiquette(nom, "touche")
            cadre.setFixedHeight(22)
            cadre.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ligne.addWidget(cadre)
            ligne.addWidget(etiquette(action, "raccourci"))
            self.elements.append(element)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        tailles = [element.sizeHint() for element in self.elements]
        visibles = len(tailles)
        while visibles > 1 and sum(taille.width() for taille in tailles[:visibles]) + self.ECART * (visibles - 1) \
                > self.width():
            visibles -= 1
        occupe = sum(taille.width() for taille in tailles[:visibles]) + self.ECART * (visibles - 1)
        x = max((self.width() - occupe) // 2, 0)
        for rang, (element, taille) in enumerate(zip(self.elements, tailles, strict=True)):
            element.setVisible(rang < visibles)
            element.setGeometry(x, (self.height() - taille.height()) // 2, taille.width(), taille.height())
            x += taille.width() + self.ECART


# ====================================================================== fiche et détails
class DispositionFiche(QLayout):
    """Partage la hauteur de l'écran entre la fiche et le menu « Plus de détails ».

    La fiche reçoit sa hauteur de référence, et le menu le reste. Dans une petite fenêtre, la
    fiche se resserre dès que le menu n'aurait plus sa hauteur confortable, mais jamais au point
    de couper le terme ou son équivalent : c'est alors le menu qui rétrécit, jusqu'à sa hauteur
    minimale. Une fiche plus haute que la référence (un terme écrit sur deux lignes) reçoit de
    la même façon la hauteur qu'il lui faut.
    """

    ECART = 16

    def __init__(self, parent: QWidget, fiche: Fiche, details: PanneauDetails) -> None:
        super().__init__(parent)
        self._elements: list = []
        self._fiche, self._details = fiche, details
        self.setContentsMargins(0, 0, 0, 0)
        self.addWidget(fiche)
        self.addWidget(details)

    def addItem(self, element) -> None:  # noqa: N802 (nom imposé par Qt)
        self._elements.append(element)

    def count(self) -> int:
        return len(self._elements)

    def itemAt(self, index: int):  # noqa: N802
        return self._elements[index] if 0 <= index < len(self._elements) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._elements.pop(index) if 0 <= index < len(self._elements) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation.Horizontal | Qt.Orientation.Vertical

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(1328, 708)

    def minimumSize(self) -> QSize:  # noqa: N802
        return QSize(LARGEUR_MINIMALE, self._fiche.hauteur_minimale() + self.ECART + self._details.HAUTEUR_MINIMALE)

    def hauteurs(self, largeur: int, hauteur: int) -> tuple[int, int]:
        """Hauteur donnée à la fiche, puis au menu « Plus de détails »."""
        libre = hauteur - self.ECART
        # 1. La hauteur de référence, tant que le menu garde sa hauteur confortable.
        fiche = max(self._fiche.hauteur_minimale(),
                    min(self._fiche.hauteur_de_reference(), libre - self._details.HAUTEUR_CONFORTABLE))
        # 2. Au moins la hauteur qu'il faut à son contenu, tant que le menu garde sa hauteur minimale.
        fiche = max(fiche, min(self._fiche.hauteur_du_contenu(largeur), libre - self._details.HAUTEUR_MINIMALE))
        return fiche, max(libre - fiche, 0)

    def setGeometry(self, rectangle: QRect) -> None:  # noqa: N802
        super().setGeometry(rectangle)
        fiche, details = self.hauteurs(rectangle.width(), rectangle.height())
        self._fiche.setGeometry(QRect(rectangle.x(), rectangle.y(), rectangle.width(), fiche))
        self._details.setGeometry(QRect(rectangle.x(), rectangle.y() + fiche + self.ECART, rectangle.width(), details))


# ====================================================================== l'écran
class PageRecherche(QWidget):
    """L'écran de recherche : il interroge le glossaire et affiche la fiche du terme trouvé."""

    #: Le sens de traduction a changé ; le signal porte la nouvelle langue source.
    sens_change = Signal(str)
    #: Message passager à afficher dans la barre d'état (une confirmation, par exemple).
    message = Signal(str)
    #: État de l'écran, affiché dans la barre d'état tant qu'il ne change pas (vide : rien à signaler).
    etat_change = Signal(str)
    #: Demande d'ouverture d'un fichier de glossaire.
    glossaire_demande = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.source = FR
        self.entree: Entree | None = None
        self.resultats: list[Entree] = []
        self.requete = ""
        self.etat = ""

        # ---------------------------------------------------------- barre de recherche
        # Elle appartient à cet écran, mais c'est la fenêtre qui la place, dans la barre d'outils.
        self.barre = BarreRecherche()
        self.champ = self.barre.champ
        self.bouton = self.barre.bouton
        self.champ.returnPressed.connect(self.lancer_recherche)
        self.bouton.clicked.connect(self.lancer_recherche)
        self.barre.effacer.clicked.connect(self.effacer)

        # Suggestions pendant la saisie : les termes du glossaire qui contiennent le texte tapé.
        self._modele_suggestions = QStringListModel(self)
        self.suggestions = QCompleter(self._modele_suggestions, self)
        self.suggestions.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.suggestions.setFilterMode(Qt.MatchFlag.MatchContains)
        self.suggestions.setMaxVisibleItems(8)
        self.suggestions.popup().setStyleSheet(theme.STYLE_DES_SUGGESTIONS)
        self.suggestions.activated[str].connect(self._suggestion_choisie)
        self.champ.setCompleter(self.suggestions)

        # ---------------------------------------------------------- panneau sans fiche
        self.accueil = PanneauAccueil()
        self.accueil.entree_demandee.connect(self.ouvrir)
        self.accueil.glossaire_demande.connect(self.glossaire_demande)

        # ---------------------------------------------------------- fiche, puis menu « Plus de détails »
        self.fiche = Fiche()
        self.fiche.entree_demandee.connect(self.ouvrir)
        self.fiche.sens_choisi.connect(self.afficher_entree)
        self.fiche.message.connect(self.message)
        self.details = PanneauDetails()
        self.details.entree_demandee.connect(self.ouvrir)
        self.details.ouverture.connect(self.afficher_entree)
        self.details.message.connect(self.message)
        self.vue_fiche = QWidget()
        self._disposition_fiche = DispositionFiche(self.vue_fiche, self.fiche, self.details)

        self.pile = QStackedWidget()
        self.pile.addWidget(self.accueil)
        self.pile.addWidget(self.vue_fiche)
        page = QVBoxLayout(self)
        page.setContentsMargins(theme.MARGE, 0, theme.MARGE, 16)
        page.addWidget(self.pile)

        self._appliquer_sens()
        self._afficher_accueil()

    # ------------------------------------------------------------------ glossaire et sens
    def definir_glossaire(self, glossaire: Glossaire | None) -> None:
        """Change de glossaire ; la recherche en cours est relancée dans le nouveau glossaire."""
        ancienne = self.entree
        self.glossaire = glossaire
        self._mettre_a_jour_les_suggestions()
        if not self.requete:
            self._afficher_accueil()
            return
        # Après un rechargement, on retrouve l'entrée qui était affichée (même couple de termes).
        selection = None
        if ancienne is not None and glossaire is not None:
            selection = next((entree for entree in glossaire.entrees
                              if (entree.terme_fr, entree.terme_ar) == (ancienne.terme_fr, ancienne.terme_ar)), None)
        self.rechercher(self.requete, deviner=False, selection=selection)

    def definir_sens(self, source: str) -> None:
        """Fixe la langue source (l'autre langue devient la langue cible)."""
        if source == self.source:
            return
        self.source = source
        self._appliquer_sens()
        self.sens_change.emit(source)

    def inverser(self) -> None:
        """Inverse le sens de traduction ; l'entrée affichée est conservée."""
        entree = self.entree
        self.definir_sens(autre_langue(self.source))
        if entree is not None:
            self.ouvrir(entree)
            return
        if self.requete and self.champ.text().strip() == self.requete:
            self.champ.clear()  # une recherche restée sans résultat n'a plus d'objet dans l'autre langue
        self.requete = ""
        self._afficher_accueil()

    def _appliquer_sens(self) -> None:
        self.champ.setPlaceholderText(_INVITES[self.source])
        self.champ.setLayoutDirection(direction(self.source))
        self.suggestions.popup().setLayoutDirection(direction(self.source))
        self._mettre_a_jour_les_suggestions()

    def _mettre_a_jour_les_suggestions(self) -> None:
        # Un terme porté par plusieurs entrées (« droit ») n'est proposé qu'une fois ; deux termes que seuls
        # leurs accents distinguent (« grève », « grevé ») sont proposés tous les deux.
        entrees = self.glossaire.entrees if self.glossaire is not None else []
        termes = {entree.terme(self.source) for entree in entrees}
        self._modele_suggestions.setStringList(sorted(termes, key=lambda terme: (cle_souple(terme), terme)))

    # ------------------------------------------------------------------ recherche
    def lancer_recherche(self) -> None:
        """Recherche le texte saisi dans la barre de recherche."""
        self.rechercher(self.champ.text())

    def effacer(self) -> None:
        """Vide la barre de recherche et revient à l'accueil."""
        self.rechercher("")
        self.champ.setFocus()

    def _suggestion_choisie(self, terme: str) -> None:
        if terme != self.requete:
            self.rechercher(terme)

    def rechercher(self, texte: str, *, deviner: bool = True, selection: Entree | None = None) -> None:
        """Recherche ``texte`` dans le glossaire et affiche la première entrée trouvée.

        Si le texte est écrit dans l'autre langue (de l'arabe alors que la
        langue source est le français, ou l'inverse), le sens de traduction
        est inversé automatiquement. ``selection`` désigne l'entrée à afficher
        quand plusieurs entrées correspondent.
        """
        texte = " ".join(texte.split())
        if self.champ.text() != texte:
            self.champ.setText(texte)
        if not texte:
            self.requete = ""
            self._afficher_accueil()
            return
        if deviner:
            langue = deviner_langue(texte)
            if langue is not None and langue != self.source:
                self.definir_sens(langue)
                self.message.emit(f"Terme saisi en {NOM_EN_FRANCAIS[langue]} : le sens de traduction a été inversé.")
        self.requete = texte
        self.resultats = self.glossaire.chercher(texte, self.source) if self.glossaire is not None else []
        if not self.resultats:
            self._afficher_aucun_resultat(texte)
            return
        self.barre.definir_resume(self._resume())
        self._afficher_la_fiche(selection if selection in self.resultats else self.resultats[0])
        self._definir_etat(f"« {_abrege(texte)} » : "
                           f"{compte(len(self.resultats), 'entrée trouvée', 'entrées trouvées')} dans le glossaire.")

    def ouvrir(self, entree: Entree) -> None:
        """Ouvre une entrée précise du glossaire : son terme devient la recherche en cours."""
        self.rechercher(entree.terme(self.source), deviner=False, selection=entree)

    def afficher_entree(self, entree: Entree) -> None:
        """Affiche une autre entrée trouvée par la recherche en cours (la recherche est conservée)."""
        if self.glossaire is not None:
            self._afficher_la_fiche(entree)

    # ------------------------------------------------------------------ affichage
    def _exacts(self) -> list[Entree]:
        """Entrées dont le terme (ou le pluriel) est exactement le texte cherché."""
        return self.glossaire.trouver(self.requete, self.source) if self.glossaire is not None else []

    def _resume(self) -> str:
        """Résumé des résultats de la recherche : « 1 terme · 23 expressions », « 2 sens · 7 résultats proches »…"""
        principale = self.resultats[0]
        if not any(principale is exacte for exacte in self._exacts()):
            return compte(len(self.resultats), "résultat")
        sens = self.glossaire.homonymes(principale, self.source)
        autres = [entree for entree in self.resultats if not any(entree is autre for autre in sens)]
        tete = "1 terme" if len(sens) < 2 else f"{len(sens)} sens"
        if not autres:
            return tete
        if self._que_des_expressions(principale, autres):
            return f"{tete} · {compte(len(autres), 'expression')}"
        return f"{tete} · {compte(len(autres), 'résultat proche', 'résultats proches')}"

    def _que_des_expressions(self, entree: Entree, autres: Sequence[Entree]) -> bool:
        """Vrai si toutes les autres entrées trouvées sont des expressions qui contiennent le terme."""
        expressions = {id(expression) for expression in self.glossaire.expressions(entree, self.source)}
        return all(id(autre) in expressions for autre in autres)

    def _afficher_la_fiche(self, entree: Entree) -> None:
        """Affiche la fiche d'une entrée ; les autres entrées trouvées vont dans le menu « Plus de détails »."""
        self.entree = entree
        sens = self.glossaire.homonymes(entree, self.source)
        autres = [autre for autre in self.resultats if not any(autre is homonyme for homonyme in sens)]
        self.fiche.afficher(self.glossaire, entree, self.source, sens)
        exacte = any(entree is trouvee for trouvee in self._exacts())
        if exacte and self._que_des_expressions(entree, autres):
            titre, libelle = f"Expressions avec « {entree.terme(self.source)} »", ("Expressions", "Expressions")
        elif exacte:
            titre, libelle = "Expressions et termes proches", ("Termes proches", "Proches")
        else:
            titre, libelle = f"Autres résultats pour « {_abrege(self.requete)} »", ("Autres résultats", "Résultats")
        # Le terme affiché n'est pas celui qui a été saisi : la liste des résultats est montrée d'office,
        # pour choisir le bon.
        self.details.afficher(self.glossaire, entree, self.source, titre_des_autres=titre, autres=autres,
                              libelle_des_autres=libelle, suggestion="" if exacte or not autres else "expressions")
        self.pile.setCurrentWidget(self.vue_fiche)
        self._disposition_fiche.invalidate()
        self._disposition_fiche.activate()

    def _afficher_sans_fiche(self) -> None:
        self.entree = None
        self.fiche.afficher(self.glossaire, None, self.source)
        self.details.afficher(self.glossaire, None, self.source)
        self.pile.setCurrentWidget(self.accueil)

    def _proposer(self, entrees: Sequence[Entree]) -> list[tuple[str, Entree]]:
        return [(self.glossaire.libelle(entree, self.source), entree) for entree in entrees]

    def _afficher_accueil(self) -> None:
        """État initial : aucune recherche, quelques termes du glossaire proposés en exemple."""
        self.resultats = []
        self.barre.definir_resume("")
        if self.glossaire is None or not len(self.glossaire):
            self.accueil.afficher_sans_glossaire()
        else:
            self.accueil.afficher_accueil(self._proposer(self._exemples()), self.source)
        self._afficher_sans_fiche()
        self._definir_etat("")

    def _exemples(self) -> list[Entree]:
        """Quelques entrées prises à intervalles réguliers dans le glossaire, sans terme répété.

        Elles sont prises parmi les entrées qui ont une définition, s'il y en a : le terme proposé en
        exemple a ainsi de quoi remplir le menu « Plus de détails », et non son seul équivalent. Parmi
        elles, celles dont l'équivalent n'est pas « à vérifier » passent d'abord : ce sont les entrées
        les plus sûres du glossaire. Dans le glossaire fourni, tous les équivalents sont à vérifier
        (version 0.16) : les exemples sont pris dans tout le glossaire.
        """
        entrees = self.glossaire.entrees if self.glossaire is not None else []
        definies = [entree for entree in entrees if entree.definition_fr or entree.definition_ar]
        entrees = [entree for entree in definies if equivalent_a_verifier(entree) is None] or definies or entrees
        pas = max(1, len(entrees) // NOMBRE_EXEMPLES)
        exemples: list[Entree] = []
        for entree in entrees[::pas] + entrees:
            if len(exemples) == NOMBRE_EXEMPLES:
                break
            if all(cle_souple(entree.terme(self.source)) != cle_souple(autre.terme(self.source)) for autre in exemples):
                exemples.append(entree)
        return exemples

    def _afficher_aucun_resultat(self, texte: str) -> None:
        self.barre.definir_resume("Aucun résultat")
        if self.glossaire is None or not len(self.glossaire):
            self.accueil.afficher_sans_glossaire()
            self._afficher_sans_fiche()
            self._definir_etat(_AUCUN_GLOSSAIRE)
            return
        proches = self.glossaire.propositions(texte, self.source)
        self.accueil.afficher_introuvable(_abrege(texte), self._proposer(proches), self.source)
        self._afficher_sans_fiche()
        self._definir_etat(f"Aucune entrée du glossaire ne correspond à « {_abrege(texte)} ».")

    def _definir_etat(self, texte: str) -> None:
        self.etat = texte
        self.etat_change.emit(texte)


def _abrege(texte: str, longueur: int = 40) -> str:
    """Un texte cité dans un message : coupé au-delà de ``longueur`` caractères."""
    return texte if len(texte) <= longueur else texte[:longueur - 1] + "…"


__all__ = ["NOMBRE_EXEMPLES", "RACCOURCIS", "BarreRecherche", "DispositionFiche", "PageRecherche", "PanneauAccueil"]
