"""Écran de recherche d'un terme (écran 1 de la maquette).

Une barre de recherche, la liste des entrées trouvées, puis les cinq champs
côte à côte : Terme → Définition → Équivalent → Contextualisation → Ressources.
"""

from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..glossaire import Entree, Glossaire
from ..langues import AR, FR, NOM_EN_FRANCAIS, autre_langue, cle_souple, deviner_langue
from . import theme
from .cartes import Carte, CarteContexte, CarteDefinition, CarteEquivalent, CarteRessources, CarteTerme
from .composants import DispositionFluide, direction, etiquette, icone_fixe, puce, vider

#: Nombre maximal d'entrées proposées sous la barre de recherche.
MAX_PUCES = 8
#: Nombre de termes du glossaire proposés comme exemples avant la première recherche.
NOMBRE_EXEMPLES = 5

_INVITES = {FR: "Saisir un terme juridique…", AR: "أدخل مصطلحا قانونيا…"}
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : ouvrez un fichier CSV (menu Fichier → Ouvrir un glossaire)."
#: Affiché quand un terme n'a ni entrée ni terme proche dans le glossaire.
_TERME_A_AJOUTER = "Pour obtenir sa fiche, ajoutez ce terme au fichier CSV, puis rechargez le glossaire (F5)."


class PageRecherche(QWidget):
    """L'écran de recherche : il interroge le glossaire et remplit les cinq cartes."""

    #: Le sens de traduction a changé ; le signal porte la nouvelle langue source.
    sens_change = Signal(str)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.source = FR
        self.entree: Entree | None = None
        self.resultats: list[Entree] = []
        self.requete = ""

        page = QVBoxLayout(self)
        page.setContentsMargins(24, 20, 24, 20)
        page.setSpacing(14)

        # ---------------------------------------------------------- barre de recherche
        self.barre = QFrame()
        self.barre.setObjectName("barreRecherche")
        self.barre.setFixedHeight(58)
        dans_la_barre = QHBoxLayout(self.barre)
        dans_la_barre.setContentsMargins(18, 0, 8, 0)
        dans_la_barre.setSpacing(12)
        dans_la_barre.addWidget(icone_fixe("loupe", theme.BLEU, 22))
        self.champ = QLineEdit()
        self.champ.setObjectName("champRecherche")
        self.champ.setClearButtonEnabled(True)
        self.champ.setFrame(False)
        self.champ.returnPressed.connect(self.lancer_recherche)
        dans_la_barre.addWidget(self.champ, 1)
        self.bouton = QPushButton("Rechercher")
        self.bouton.setObjectName("boutonRechercher")
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton.setFixedHeight(42)
        self.bouton.clicked.connect(self.lancer_recherche)
        dans_la_barre.addWidget(self.bouton)

        # Suggestions pendant la saisie : les termes du glossaire qui contiennent le texte tapé.
        self._modele_suggestions = QStringListModel(self)
        self.suggestions = QCompleter(self._modele_suggestions, self)
        self.suggestions.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.suggestions.setFilterMode(Qt.MatchFlag.MatchContains)
        self.suggestions.setMaxVisibleItems(8)
        self.suggestions.popup().setStyleSheet(theme.STYLE_DES_SUGGESTIONS)
        self.suggestions.activated[str].connect(self._suggestion_choisie)
        self.champ.setCompleter(self.suggestions)

        # ---------------------------------------------------------- entrées trouvées
        self.zone_resultats = QWidget()
        self.rangee_resultats = DispositionFluide(self.zone_resultats, 8, 8)
        self.groupe_resultats = QButtonGroup(self)
        self.groupe_resultats.setExclusive(True)

        conteneur = QWidget()
        colonne = QVBoxLayout(conteneur)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(12)
        colonne.addWidget(self.barre)
        colonne.addWidget(self.zone_resultats)
        conteneur.setMaximumWidth(900)
        conteneur.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        centrage = QHBoxLayout()
        centrage.addStretch(1)
        centrage.addWidget(conteneur, 6)
        centrage.addStretch(1)
        page.addLayout(centrage)

        # ---------------------------------------------------------- les cinq champs
        self.carte_terme = CarteTerme()
        self.carte_definition = CarteDefinition()
        self.carte_equivalent = CarteEquivalent(accent=True)
        self.carte_contexte = CarteContexte()
        self.carte_ressources = CarteRessources(derniere=True)
        self.cartes: list[Carte] = [self.carte_terme, self.carte_definition, self.carte_equivalent,
                                    self.carte_contexte, self.carte_ressources]
        contenu = QWidget()
        contenu.setObjectName("rangeeCartes")
        rangee = QHBoxLayout(contenu)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.setSpacing(18)
        for carte in self.cartes:
            carte.entree_demandee.connect(self.ouvrir)
            carte.message.connect(self.message)
            rangee.addWidget(carte, 1)
        # Dans une fenêtre étroite, les cartes gardent leur largeur minimale et la
        # rangée défile horizontalement.
        self.defilement_cartes = QScrollArea()
        self.defilement_cartes.setObjectName("defilementCartes")
        self.defilement_cartes.setWidgetResizable(True)
        self.defilement_cartes.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement_cartes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.defilement_cartes.setWidget(contenu)
        page.addSpacing(4)
        page.addWidget(self.defilement_cartes, 1)

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
        entree = selection if selection in self.resultats else self.resultats[0]
        self._afficher_resultats(entree)
        self._afficher_entree(entree)

    def ouvrir(self, entree: Entree) -> None:
        """Ouvre une entrée précise du glossaire (clic sur une puce ou sur une expression)."""
        self.rechercher(entree.terme(self.source), deviner=False, selection=entree)

    # ------------------------------------------------------------------ affichage
    def _afficher_entree(self, entree: Entree | None) -> None:
        self.entree = entree
        for carte in self.cartes:
            carte.afficher(self.glossaire, entree, self.source)

    def _vider_les_resultats(self) -> None:
        for bouton in self.groupe_resultats.buttons():
            self.groupe_resultats.removeButton(bouton)
        vider(self.rangee_resultats)
        self.zone_resultats.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    def _ajouter_texte(self, texte: str) -> None:
        label = etiquette(texte, "resultats")
        label.setFixedHeight(theme.HAUTEUR_PUCE)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.rangee_resultats.addWidget(label)

    def _afficher_accueil(self) -> None:
        """État initial : aucune recherche, quelques termes du glossaire proposés en exemple."""
        self.resultats = []
        self._vider_les_resultats()
        if self.glossaire is None or not len(self.glossaire):
            self._ajouter_texte(_AUCUN_GLOSSAIRE)
        else:
            self._ajouter_texte("Saisissez un terme, puis appuyez sur Entrée. Par exemple :")
            for entree in self._exemples():
                bouton = puce(self.glossaire.libelle(entree, self.source))
                bouton.clicked.connect(lambda _=False, cible=entree: self.ouvrir(cible))
                self.rangee_resultats.addWidget(bouton)
        self._afficher_entree(None)

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

    def _afficher_resultats(self, selection: Entree) -> None:
        self._vider_les_resultats()
        nombre = len(self.resultats)
        visibles = self.resultats[:MAX_PUCES]
        if selection not in visibles:
            visibles[-1] = selection
        if nombre == 1:
            self._ajouter_texte("1 entrée trouvée dans le glossaire :")
        else:
            self._ajouter_texte(f"{nombre} entrées trouvées dans le glossaire :")
        for entree in visibles:
            bouton = puce(self.glossaire.libelle(entree, self.source), cochable=True)
            bouton.setChecked(entree is selection)
            bouton.clicked.connect(lambda _=False, cible=entree: self._afficher_entree(cible))
            self.groupe_resultats.addButton(bouton)
            self.rangee_resultats.addWidget(bouton)
        reste = nombre - len(visibles)
        if reste:
            self._ajouter_texte(("et 1 autre" if reste == 1 else f"et {reste} autres") + " : précisez la recherche.")

    def _afficher_aucun_resultat(self, texte: str) -> None:
        self._vider_les_resultats()
        if self.glossaire is None or not len(self.glossaire):
            self._ajouter_texte(_AUCUN_GLOSSAIRE)
        else:
            proches = self.glossaire.propositions(texte, self.source)
            abrege = texte if len(texte) <= 40 else texte[:39] + "…"
            self._ajouter_texte(f"Aucune entrée du glossaire ne correspond à « {abrege} »."
                                + (" Termes proches :" if proches else ""))
            for entree in proches:
                bouton = puce(self.glossaire.libelle(entree, self.source))
                bouton.clicked.connect(lambda _=False, cible=entree: self.ouvrir(cible))
                self.rangee_resultats.addWidget(bouton)
            if not proches:
                # Les fiches viennent du fichier CSV, et de lui seul : on le rappelle.
                self._ajouter_texte(_TERME_A_AJOUTER)
        self._afficher_entree(None)
