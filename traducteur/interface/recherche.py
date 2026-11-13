"""Écran « Terme » : recherche d'un terme dans le glossaire.

La barre de recherche est placée par la fenêtre dans la barre d'outils. L'écran affiche la
fiche du terme trouvé (les cinq champs de l'enchaînement) et, sous la fiche, les autres
entrées trouvées ; sans fiche à afficher, un panneau invite à chercher un terme ou propose
les termes proches.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QRect, QRectF, QSize, QStringListModel, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..glossaire import Entree, Glossaire
from ..langues import AR, FR, NOM_EN_FRANCAIS, autre_langue, cle_souple, deviner_langue
from . import icones, theme
from .composants import (
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
from .fiche import PROPORTIONS, EnteteEtapes, Fiche, ListeEntrees

#: Nombre de termes du glossaire proposés comme exemples avant la première recherche.
NOMBRE_EXEMPLES = 5

_INVITES = {
    FR: "Saisir un terme juridique, en français ou en arabe…",
    AR: "أدخل مصطلحا قانونيا، بالعربية أو بالفرنسية...",
}
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : choisissez un fichier CSV dans « Paramètres »."
#: Rappel affiché quand un terme n'est pas dans le glossaire : les fiches viennent du fichier CSV, et de lui seul.
_TERME_A_AJOUTER = "Pour obtenir sa fiche, ajoutez ce terme au fichier CSV, puis rechargez le glossaire (F5)."

#: Sous chaque étape du panneau d'accueil : ce que contient le champ (forme longue, forme courte).
LEGENDES = (
    ("catégorie, domaine, synonymes", "catégorie, domaine"),
    ("en français et en arabe, avec sa source", "dans les deux langues"),
    ("dans la langue cible", "langue cible"),
    ("exemples d’emploi dans les deux langues", "exemples d’emploi"),
    ("textes de loi, ouvrages, sites officiels", "textes, ouvrages, sites"),
)
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
        self.bouton = QPushButton("Rechercher")
        self.bouton.setProperty("classe", "principal")
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton.setFixedSize(112, 34)
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

    En haut, le rappel des cinq champs de l'enchaînement ; au centre, un message et des termes
    à ouvrir (exemples ou termes proches) ; au pied, les raccourcis ou un conseil.
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
        self.entete = EnteteEtapes(LEGENDES)
        ensemble.addWidget(self.entete)

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
        peintre.drawLine(0, self.entete.height(), self.width(), self.entete.height())
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


# ====================================================================== fiche et liste
class DispositionFiche(QLayout):
    """Partage la hauteur de l'écran entre la fiche et la liste des autres entrées.

    La fiche reçoit sa hauteur de référence. La liste prend ce qu'il lui faut dans la place
    restante (elle défile si la place manque). S'il reste encore de la place, la fiche
    s'agrandit jusqu'à montrer tout son contenu.
    """

    ECART = 16

    def __init__(self, parent: QWidget, defilement: QScrollArea, fiche: Fiche, liste: ListeEntrees) -> None:
        super().__init__(parent)
        self._elements: list = []
        self._defilement, self._fiche, self._liste = defilement, fiche, liste
        self.setContentsMargins(0, 0, 0, 0)
        self.addWidget(defilement)
        self.addWidget(liste)

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
        return QSize(1392, 710)

    def minimumSize(self) -> QSize:  # noqa: N802
        return QSize(400, self._fiche.hauteur_minimale() + 14 + self.ECART + self._liste.hauteur_minimale())

    def hauteurs(self, largeur: int, hauteur: int) -> tuple[int, int]:
        """Hauteur donnée à la fiche (barre de défilement horizontale comprise) et à la liste."""
        # Dans une fenêtre étroite, la fiche défile horizontalement : sa barre prend de la hauteur.
        barre = self._defilement.horizontalScrollBar().sizeHint().height() if largeur < self._fiche.minimumWidth() \
            else 0
        naturelle = 0 if self._liste.isHidden() else self._liste.hauteur_naturelle(largeur)
        ecart = self.ECART if naturelle else 0
        minimum_liste = min(naturelle, self._liste.hauteur_minimale())
        fiche = max(self._fiche.hauteur_minimale() + barre,
                    min(self._fiche.hauteur_de_reference() + barre, hauteur - ecart - minimum_liste))
        liste = max(0, min(naturelle, hauteur - ecart - fiche))
        reste = hauteur - ecart - fiche - liste
        if reste > 0:
            fiche += max(0, min(reste, self._fiche.hauteur_du_contenu(largeur) + barre - fiche))
        return fiche, liste

    def setGeometry(self, rectangle: QRect) -> None:  # noqa: N802
        super().setGeometry(rectangle)
        fiche, liste = self.hauteurs(rectangle.width(), rectangle.height())
        self._defilement.setGeometry(QRect(rectangle.x(), rectangle.y(), rectangle.width(), fiche))
        if not self._liste.isHidden():
            self._liste.setGeometry(QRect(rectangle.x(), rectangle.y() + fiche + self.ECART, rectangle.width(), liste))


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

        # ---------------------------------------------------------- fiche et autres entrées trouvées
        self.fiche = Fiche()
        self.fiche.entree_demandee.connect(self.ouvrir)
        self.fiche.sens_choisi.connect(self.afficher_entree)
        self.fiche.message.connect(self.message)
        # Dans une fenêtre étroite, la fiche garde sa largeur minimale et défile horizontalement.
        self.defilement_fiche = QScrollArea()
        self.defilement_fiche.setObjectName("zoneDefilante")
        self.defilement_fiche.setWidgetResizable(True)
        self.defilement_fiche.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement_fiche.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.defilement_fiche.viewport().setAutoFillBackground(False)
        self.defilement_fiche.setWidget(self.fiche)
        self.liste = ListeEntrees()
        self.liste.ouverture.connect(self.afficher_entree)
        self.vue_fiche = QWidget()
        self._disposition_fiche = DispositionFiche(self.vue_fiche, self.defilement_fiche, self.fiche, self.liste)

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
        termes: dict[str, str] = {}
        if self.glossaire is not None:
            for entree in self.glossaire.entrees:
                termes.setdefault(cle_souple(entree.terme(self.source)), entree.terme(self.source))
        self._modele_suggestions.setStringList([termes[cle] for cle in sorted(termes)])

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
        """Affiche la fiche d'une entrée et, dessous, les autres entrées trouvées."""
        self.entree = entree
        sens = self.glossaire.homonymes(entree, self.source)
        autres = [autre for autre in self.resultats if not any(autre is homonyme for homonyme in sens)]
        self.fiche.afficher(self.glossaire, entree, self.source, sens)
        if any(entree is exacte for exacte in self._exacts()):
            titre = (f"Expressions avec « {entree.terme(self.source)} »" if self._que_des_expressions(entree, autres)
                     else "Expressions et termes proches")
        else:
            titre = f"Autres résultats pour « {_abrege(self.requete)} »"
        self.liste.definir(titre, autres)
        self.liste.setVisible(bool(autres))
        self.defilement_fiche.horizontalScrollBar().setValue(0)
        self.pile.setCurrentWidget(self.vue_fiche)
        self._disposition_fiche.invalidate()
        self._disposition_fiche.activate()

    def _afficher_sans_fiche(self) -> None:
        self.entree = None
        self.fiche.afficher(self.glossaire, None, self.source)
        self.liste.definir("", [])
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
        """Quelques entrées prises à intervalles réguliers dans le glossaire, sans terme répété."""
        entrees = self.glossaire.entrees if self.glossaire is not None else []
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


__all__ = ["LEGENDES", "NOMBRE_EXEMPLES", "PROPORTIONS", "RACCOURCIS", "BarreRecherche", "PageRecherche",
           "PanneauAccueil"]
