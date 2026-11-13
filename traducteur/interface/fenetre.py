"""Fenêtre principale : barre latérale, barre de menus, barre d'outils, écrans, barre d'état.

La barre latérale (à gauche) choisit l'écran : « Terme » (``PageRecherche``), « Texte »
(``PageTexte``), « Paramètres », « Description de la plateforme », « Centre d'aide ». Les deux
premiers sont les écrans de travail : chacun garde son propre sens de traduction, et la barre
d'outils affiche ses commandes (la barre de recherche, ou l'import, l'export et la traduction
d'un texte). Pour les autres écrans, la barre d'outils affiche le titre de l'écran.

Le glossaire est chargé à l'ouverture de la fenêtre ; l'écran « Paramètres » permet d'en
choisir un autre.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import NOM_APPLICATION
from ..glossaire import ErreurGlossaire, Glossaire
from ..langues import AR, NOM_EN_FRANCAIS, NOM_NATIF, autre_langue
from . import animation, boites, icones, theme
from .composants import EtiquetteCourte, compte, espace_souple, etiquette, icone_fixe, repeindre
from .navigation import (
    ECRANS,
    MODE_AIDE,
    MODE_DESCRIPTION,
    MODE_PARAMETRES,
    MODE_TERME,
    MODE_TEXTE,
    BarreLaterale,
)
from .pages import CLE_ANIMATIONS, PageAide, PageDescription, PageParametres
from .recherche import PageRecherche
from .texte import PageTexte

#: Glossaire fourni avec le projet (dossier « donnees » à la racine).
GLOSSAIRE_EXEMPLE = Path(__file__).resolve().parents[2] / "donnees" / "glossaire_juridique.csv"

_CLE_GLOSSAIRE = "glossaire/chemin"
#: Les écrans de travail : ils ont un sens de traduction et des commandes dans la barre d'outils.
_ECRANS_DE_TRAVAIL = (MODE_TERME, MODE_TEXTE)


def _filet_vertical(hauteur: int) -> QFrame:
    filet = QFrame()
    filet.setObjectName("filetVertical")
    filet.setFixedSize(1, hauteur)
    return filet


# ====================================================================== barre d'outils
class SelecteurSens(QFrame):
    """Sens de traduction : langue source, flèche, langue cible, et bouton d'inversion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sens")
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(16, 1, 1, 1)
        ligne.setSpacing(0)
        self.source = etiquette("", "langueSens")
        self.cible = etiquette("", "langueSens")
        ligne.addWidget(self.source)
        ligne.addSpacing(12)
        ligne.addWidget(icone_fixe("fleche", theme.TEXTE_4, 16, 1.6))
        ligne.addSpacing(12)
        ligne.addWidget(self.cible)
        ligne.addSpacing(16)
        ligne.addWidget(_filet_vertical(24))
        self.bouton_inverser = QToolButton()
        self.bouton_inverser.setObjectName("boutonInverser")
        self.bouton_inverser.setIcon(icones.icone("echange", theme.BLEU, 18, 1.6))
        self.bouton_inverser.setIconSize(QSize(18, 18))
        self.bouton_inverser.setFixedSize(43, 42)
        self.bouton_inverser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_inverser.setToolTip("Inverser le sens de traduction (Ctrl+I)")
        self.bouton_inverser.setAccessibleName("Inverser le sens de traduction")
        ligne.addWidget(self.bouton_inverser)

    def afficher(self, source: str) -> None:
        for label, langue in ((self.source, source), (self.cible, autre_langue(source))):
            label.setText(NOM_NATIF[langue])
            if label.property("arabe") != (langue == AR):
                label.setProperty("arabe", langue == AR)
                repeindre(label)
        self.setAccessibleName(f"Sens de traduction : {NOM_EN_FRANCAIS[source]} vers "
                               f"{NOM_EN_FRANCAIS[autre_langue(source)]}")
        self.updateGeometry()


class TitreDePage(QWidget):
    """Titre d'un écran d'information, affiché dans la barre d'outils : un titre et une ligne d'explication."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 2, 0, 0)
        colonne.setSpacing(1)
        self.titre = etiquette("", "titrePage")
        self.sous_titre = EtiquetteCourte("", "sousTitrePage")
        colonne.addWidget(self.titre)
        colonne.addWidget(self.sous_titre)
        colonne.addStretch(1)

    def definir(self, titre: str, sous_titre: str) -> None:
        self.titre.setText(titre)
        self.sous_titre.definir_texte(sous_titre)


# ====================================================================== barre d'état
class BarreEtat(QFrame):
    """Barre d'état : l'état de l'écran affiché (le résultat d'une recherche…) ou un message passager."""

    #: Un message passager plus jeune que ce délai (en millisecondes) n'est pas remplacé par un changement d'état.
    DELAI_DE_GARDE = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("barreEtat")
        self.setFixedHeight(26)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(theme.MARGE, 1, theme.MARGE, 0)
        ligne.setSpacing(0)
        self.message = EtiquetteCourte("", "etat")
        self.message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ligne.addWidget(self.message, 1)
        self._etat = ""
        self._passager = ""
        self._age = QElapsedTimer()
        self._retour = QTimer(self)
        self._retour.setSingleShot(True)
        self._retour.timeout.connect(self._oublier_le_message)

    def definir_etat(self, texte: str) -> None:
        """Texte affiché en permanence, tant qu'aucun message passager ne le remplace."""
        self._etat = texte
        if self._passager and self._age.elapsed() > self.DELAI_DE_GARDE:
            self._oublier_le_message()
        self._actualiser()

    def afficher_message(self, texte: str, duree: int = 5000) -> None:
        """Message passager : il remplace l'état pendant ``duree`` millisecondes."""
        self._passager = texte
        self._age.start()
        self._retour.start(duree)
        self._actualiser()

    def _oublier_le_message(self) -> None:
        self._retour.stop()
        self._passager = ""
        self._actualiser()

    def _actualiser(self) -> None:
        self.message.definir_texte(self._passager or self._etat)

    def texte(self) -> str:
        """Le texte affiché (non abrégé)."""
        return self.message.texte_complet()

    def etat(self) -> str:
        return self._etat


# ====================================================================== la fenêtre
class FenetrePrincipale(QMainWindow):
    """La fenêtre de l'application."""

    def __init__(self, chemin_glossaire: str | Path | None = None, reglages: QSettings | None = None) -> None:
        super().__init__()
        self.reglages = reglages if reglages is not None else QSettings()
        self.glossaire: Glossaire | None = None
        self.mode = MODE_TERME
        #: Erreurs de lecture du glossaire au démarrage, à signaler quand la fenêtre s'affiche.
        self._erreurs_au_demarrage: list[str] = []
        animation.definir_actives(self.reglages.value(CLE_ANIMATIONS, True, bool))

        self.setWindowTitle(NOM_APPLICATION)
        self.setWindowIcon(icones.icone_application())
        self.setPalette(theme.palette())
        self.setStyleSheet(theme.FEUILLE_DE_STYLE)
        self.setMinimumSize(900, 560)

        self.page = PageRecherche()
        self.page_texte = PageTexte()
        self.page_parametres = PageParametres(self.reglages)
        self.page_description = PageDescription()
        self.page_aide = PageAide(self.reglages)
        self.pages: dict[str, QWidget] = {
            MODE_TERME: self.page, MODE_TEXTE: self.page_texte, MODE_PARAMETRES: self.page_parametres,
            MODE_DESCRIPTION: self.page_description, MODE_AIDE: self.page_aide}
        self.pile = QStackedWidget()
        for page in self.pages.values():
            self.pile.addWidget(page)
        self.rail = BarreLaterale()
        self.rail.choisi.connect(self.definir_mode)
        self.barre_etat = BarreEtat()

        centre = QWidget()
        centre.setObjectName("centre")
        centre.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rangee = QHBoxLayout(centre)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.setSpacing(0)
        rangee.addWidget(self.rail)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addWidget(self._creer_barre_menus())
        colonne.addWidget(self._creer_barre_outils())
        colonne.addWidget(self.pile, 1)
        colonne.addWidget(self.barre_etat)
        rangee.addLayout(colonne, 1)
        self.setCentralWidget(centre)

        for page in (self.page, self.page_texte):
            page.sens_change.connect(self._sens_change)
            page.etat_change.connect(self._etat_change)
        for page in self.pages.values():
            page.message.connect(self.barre_etat.afficher_message)
        self.page.glossaire_demande.connect(lambda: self.definir_mode(MODE_PARAMETRES))
        self.page_texte.entree_demandee.connect(self.afficher_la_fiche)
        self.page_texte.traduction_changee.connect(self._actualiser_les_actions)
        self.page_parametres.glossaire_a_choisir.connect(self.ouvrir_glossaire)
        self.page_parametres.glossaire_a_recharger.connect(self.recharger_glossaire)
        self.page_parametres.glossaire_fourni_demande.connect(lambda: self.charger_glossaire(GLOSSAIRE_EXEMPLE))
        self.page_parametres.animations_changees.connect(animation.definir_actives)
        self.page_parametres.adresse_changee.connect(self.page_aide.definir_adresse)
        self.page_aide.parametres_demandes.connect(self.indiquer_l_adresse)
        self._taille_initiale()
        self._charger_au_demarrage(chemin_glossaire)
        self.definir_mode(MODE_TERME)

    # ------------------------------------------------------------------ construction
    def _creer_barre_outils(self) -> QWidget:
        """Le sens de traduction, puis les commandes de l'écran affiché (ou son titre)."""
        barre = QWidget()
        barre.setObjectName("barreOutils")
        barre.setFixedHeight(74)
        ligne = QHBoxLayout(barre)
        # La barre de recherche est entourée d'un halo de 3 pixels : les marges en tiennent compte.
        ligne.setContentsMargins(theme.MARGE, 11, theme.MARGE - 3, 13)
        ligne.setSpacing(0)

        self.sens = SelecteurSens()
        self.etiquette_source, self.etiquette_cible = self.sens.source, self.sens.cible
        self.bouton_inverser = self.sens.bouton_inverser
        self.bouton_inverser.clicked.connect(self.inverser_le_sens)
        # Le sens et l'espace qui le suit disparaissent ensemble sur les écrans d'information.
        self.cadre_sens = QWidget()
        dans_le_cadre = QHBoxLayout(self.cadre_sens)
        dans_le_cadre.setContentsMargins(0, 0, 0, 0)
        dans_le_cadre.setSpacing(0)
        dans_le_cadre.addWidget(self.sens)
        # L'espace se resserre un peu si la fenêtre est étroite et la police du système large.
        espace_souple(dans_le_cadre, 13, 5)

        # Les commandes appartiennent aux écrans ; la barre d'outils montre celles de l'écran affiché.
        self.outils = QStackedWidget()
        self.outils.setFixedHeight(50)
        self.outils.addWidget(self.page.barre)
        cadre = QWidget()
        dans_le_cadre = QHBoxLayout(cadre)
        dans_le_cadre.setContentsMargins(3, 0, 3, 0)
        dans_le_cadre.addWidget(self.page_texte.outils)
        self.outils.addWidget(cadre)
        self.titre_de_page = TitreDePage()
        self.outils.addWidget(self.titre_de_page)
        self.bouton_importer = self.page_texte.bouton_importer
        self.bouton_exporter = self.page_texte.bouton_exporter

        ligne.addWidget(self.cadre_sens)
        ligne.addWidget(self.outils, 1)
        return barre

    def _creer_barre_menus(self) -> QWidget:
        """Barre de menus, au-dessus de la barre d'outils."""
        cadre = QFrame()
        cadre.setObjectName("barreMenus")
        cadre.setFixedHeight(35)
        ligne = QHBoxLayout(cadre)
        ligne.setContentsMargins(5, 0, theme.MARGE, 1)
        ligne.setSpacing(12)
        self.menus = QMenuBar()
        self.menus.setNativeMenuBar(False)
        self.menus.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        #: Les menus, par titre.
        self.menus_par_titre: dict[str, QMenu] = {}
        ligne.addWidget(self.menus, 0, Qt.AlignmentFlag.AlignVCenter)
        ligne.addStretch(1)
        self._creer_menus()
        return cadre

    def _ajouter_menu(self, titre: str, lettre: str) -> QMenu:
        """Ajoute un menu à la barre ; « Alt » + ``lettre`` l'ouvre.

        Le titre ne contient pas de « & » : selon le style, Qt soulignerait en permanence une
        lettre du titre. Le raccourci est donc créé à part.
        """
        menu = self.menus.addMenu(titre)
        self.menus_par_titre[titre] = menu
        action = menu.menuAction()
        raccourci = QShortcut(QKeySequence(f"Alt+{lettre}"), self)
        raccourci.activated.connect(lambda: self.menus.setActiveAction(action))
        return menu

    def _creer_menus(self) -> None:
        # Le glossaire est chargé à l'ouverture : ces commandes n'ont pas de menu. Elles sont
        # proposées par l'écran « Paramètres » et gardent leur raccourci.
        self.action_ouvrir = QAction("Choisir un autre glossaire…", self)
        self.action_ouvrir.setShortcut(QKeySequence.StandardKey.Open)
        self.action_ouvrir.triggered.connect(self.ouvrir_glossaire)
        self.action_recharger = QAction("Recharger le glossaire", self)
        self.action_recharger.setShortcut(QKeySequence("F5"))
        self.action_recharger.triggered.connect(self.recharger_glossaire)
        self.addActions([self.action_ouvrir, self.action_recharger])

        menu_fichier = self._ajouter_menu("Fichier", "F")
        self.action_importer = QAction("&Importer un texte…", self)
        self.action_importer.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.action_importer.triggered.connect(self.importer_un_texte)
        menu_fichier.addAction(self.action_importer)
        self.action_exporter = QAction("E&xporter la traduction…", self)
        self.action_exporter.setShortcut(QKeySequence("Ctrl+E"))
        self.action_exporter.triggered.connect(self.exporter_la_traduction)
        menu_fichier.addAction(self.action_exporter)
        menu_fichier.addSeparator()
        action_quitter = QAction("&Quitter", self)
        action_quitter.setShortcut(QKeySequence("Ctrl+Q"))
        action_quitter.triggered.connect(self.close)
        menu_fichier.addAction(action_quitter)

        menu_affichage = self._ajouter_menu("Affichage", "I")
        groupe = QActionGroup(self)
        self.actions_mode: dict[str, QAction] = {}
        libelles = {MODE_TERME: "Recherche d’un &terme", MODE_TEXTE: "Traduction d’un te&xte",
                    MODE_PARAMETRES: "&Paramètres", MODE_DESCRIPTION: "&Description de la plateforme",
                    MODE_AIDE: "&Centre d’aide"}
        for mode, (_, _, _, raccourci) in ECRANS.items():
            if mode == MODE_PARAMETRES:
                menu_affichage.addSeparator()
            action = QAction(libelles[mode], self)
            action.setCheckable(True)
            action.setShortcut(QKeySequence(raccourci))
            action.triggered.connect(lambda _=False, choix=mode: self.definir_mode(choix))
            groupe.addAction(action)
            menu_affichage.addAction(action)
            self.actions_mode[mode] = action
        menu_affichage.addSeparator()
        self.action_inverser = QAction("&Inverser le sens de traduction", self)
        self.action_inverser.setShortcut(QKeySequence("Ctrl+I"))
        self.action_inverser.triggered.connect(self.inverser_le_sens)
        menu_affichage.addAction(self.action_inverser)

        menu_recherche = self._ajouter_menu("Recherche", "R")
        action_champ = QAction("&Aller à la barre de recherche", self)
        action_champ.setShortcut(QKeySequence.StandardKey.Find)
        action_champ.triggered.connect(self._aller_a_la_recherche)
        menu_recherche.addAction(action_champ)
        action_effacer_recherche = QAction("&Effacer la recherche", self)
        action_effacer_recherche.triggered.connect(self._effacer_la_recherche)
        menu_recherche.addAction(action_effacer_recherche)

        menu_traduction = self._ajouter_menu("Traduction", "T")
        # Le raccourci Ctrl+Entrée est géré par l'écran « Texte » : il est seulement rappelé ici.
        action_traduire = QAction("&Traduire le texte\tCtrl+Entrée", self)
        action_traduire.triggered.connect(self._traduire_le_texte)
        menu_traduction.addAction(action_traduire)
        self.action_copier = QAction("&Copier la traduction", self)
        self.action_copier.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.action_copier.triggered.connect(self.page_texte.copier)
        menu_traduction.addAction(self.action_copier)
        menu_traduction.addSeparator()
        action_exemple = QAction("Insérer un texte d’&exemple", self)
        action_exemple.triggered.connect(self._inserer_un_exemple)
        menu_traduction.addAction(action_exemple)
        action_effacer = QAction("E&ffacer le texte", self)
        action_effacer.triggered.connect(self._effacer_le_texte)
        menu_traduction.addAction(action_effacer)

    def _taille_initiale(self) -> None:
        """Taille de départ (1440 × 860), réduite si l'écran est plus petit ; fenêtre centrée."""
        largeur, hauteur = 1440, 860
        ecran = self.screen().availableGeometry() if self.screen() is not None else None
        if ecran is None:
            self.resize(largeur, hauteur)
            return
        largeur = max(self.minimumWidth(), min(largeur, ecran.width() - 40))
        hauteur = max(self.minimumHeight(), min(hauteur, ecran.height() - 60))
        self.resize(largeur, hauteur)
        # La hauteur ne compte pas la barre de titre : on lui garde une quarantaine de pixels.
        self.move(ecran.x() + max(0, (ecran.width() - largeur) // 2),
                  ecran.y() + max(0, (ecran.height() - hauteur - 40) // 2))

    # ------------------------------------------------------------------ glossaire
    def _charger_au_demarrage(self, chemin: str | Path | None) -> None:
        """Charge le glossaire demandé, sinon le dernier glossaire choisi, sinon le glossaire fourni."""
        essais: list[tuple[Path, str]] = []
        if chemin:
            essais.append((Path(chemin), "demande"))
        memorise = self.reglages.value(_CLE_GLOSSAIRE, "", str)
        if memorise:
            essais.append((Path(memorise), "memorise"))
        essais.append((GLOSSAIRE_EXEMPLE, "exemple"))

        erreurs: list[str] = []
        for candidat, origine in essais:
            try:
                glossaire = Glossaire.charger(candidat)
            except ErreurGlossaire as erreur:
                erreurs.append(f"{candidat}\n{erreur}")
                if origine == "memorise":
                    self.reglages.remove(_CLE_GLOSSAIRE)  # ne pas répéter l'erreur au prochain démarrage
                continue
            self._installer(glossaire, memoriser=origine == "demande")
            break
        else:
            self._installer(None)
        # Le message est affiché une fois la fenêtre ouverte, après l'écran de démarrage : voir ``showEvent``.
        self._erreurs_au_demarrage = erreurs

    def showEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().showEvent(evenement)
        if self._erreurs_au_demarrage:
            erreurs, self._erreurs_au_demarrage = self._erreurs_au_demarrage, []
            QTimer.singleShot(0, lambda: self._avertir("Glossaire non chargé", "\n\n".join(erreurs)))

    def glossaire_fourni(self) -> bool:
        """Vrai si le glossaire chargé est celui qui est livré avec l'application."""
        return (self.glossaire is not None and self.glossaire.chemin is not None
                and self.glossaire.chemin.resolve() == GLOSSAIRE_EXEMPLE)

    def _installer(self, glossaire: Glossaire | None, *, memoriser: bool = False) -> None:
        self.glossaire = glossaire
        self.page.definir_glossaire(glossaire)
        self.page_texte.definir_glossaire(glossaire)
        self.page_parametres.afficher_glossaire(glossaire, self.glossaire_fourni())
        self.page_description.definir_glossaire(glossaire)
        self.page_aide.definir_glossaire(glossaire)
        self.action_recharger.setEnabled(glossaire is not None and glossaire.chemin is not None)
        if glossaire is not None and memoriser and glossaire.chemin is not None:
            chemin = glossaire.chemin.resolve()
            if chemin == GLOSSAIRE_EXEMPLE:
                self.reglages.remove(_CLE_GLOSSAIRE)  # le glossaire fourni est déjà le glossaire par défaut
            else:
                self.reglages.setValue(_CLE_GLOSSAIRE, str(chemin))
        self._actualiser_l_etat()

    def charger_glossaire(self, chemin: str | Path, *, bilan: bool = False) -> bool:
        """Charge un fichier CSV. En cas d'erreur, le glossaire actuel est conservé."""
        try:
            glossaire = Glossaire.charger(chemin)
        except ErreurGlossaire as erreur:
            self._avertir("Glossaire non chargé", f"{Path(chemin).name}\n\n{erreur}")
            return False
        self._installer(glossaire, memoriser=True)
        if bilan:
            self._informer("Glossaire chargé", self.bilan_de_lecture(glossaire))
        else:
            self.barre_etat.afficher_message(
                f"Glossaire chargé : {glossaire.nom}, {compte(len(glossaire), 'entrée')}.", 4000)
        return True

    def ouvrir_glossaire(self) -> None:
        """Demande un fichier CSV à l'utilisateur, puis le charge."""
        depart = str(self.glossaire.chemin.parent) if self.glossaire and self.glossaire.chemin else ""
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir un glossaire", depart, "Glossaire CSV (*.csv *.tsv *.txt);;Tous les fichiers (*)")
        if chemin:
            self.charger_glossaire(chemin, bilan=True)

    def recharger_glossaire(self) -> None:
        """Relit le fichier du glossaire (après l'avoir modifié dans un tableur, par exemple)."""
        if self.glossaire is not None and self.glossaire.chemin is not None:
            self.charger_glossaire(self.glossaire.chemin)

    @staticmethod
    def bilan_de_lecture(glossaire: Glossaire) -> str:
        """Résumé de ce qui a été lu dans le fichier : entrées, colonnes reconnues ou ignorées."""
        lignes = [
            f"{glossaire.nom} : {compte(len(glossaire), 'entrée')}.",
            "",
            "Colonnes reconnues : " + ", ".join(glossaire.colonnes) + ".",
        ]
        if glossaire.colonnes_ignorees:
            lignes.append("Colonnes ignorées (nom inconnu) : " + ", ".join(glossaire.colonnes_ignorees) + ".")
        if glossaire.lignes_ignorees:
            pluriel = "s" if glossaire.lignes_ignorees > 1 else ""
            lignes.append(f"{glossaire.lignes_ignorees} ligne{pluriel} ignorée{pluriel} "
                          "(terme français ou terme arabe manquant).")
        return "\n".join(lignes)

    def _informer(self, titre: str, texte: str) -> None:
        self._boite(boites.INFORMATION, titre, texte)

    def _avertir(self, titre: str, texte: str) -> None:
        self._boite(boites.ALERTE, titre, texte)

    def _boite(self, genre: str, titre: str, texte: str, image: QPixmap | None = None) -> None:
        """Boîte de message. Le texte est affiché tel quel (un nom de fichier peut contenir « & » ou « < »)."""
        boites.afficher(self, genre, titre, texte, image=image)

    # ------------------------------------------------------------------ écrans
    def page_courante(self) -> QWidget:
        """L'écran affiché."""
        return self.pages[self.mode]

    def ecran_de_travail(self) -> PageRecherche | PageTexte | None:
        """L'écran affiché si c'est « Terme » ou « Texte » ; sinon ``None``."""
        return self.pages[self.mode] if self.mode in _ECRANS_DE_TRAVAIL else None

    def definir_mode(self, mode: str) -> None:
        """Affiche un écran, désigné par son nom : ``MODE_TERME``, ``MODE_TEXTE``, ``MODE_PARAMETRES``…"""
        self.mode = mode
        page = self.pages[mode]
        self.pile.setCurrentWidget(page)
        travail = mode in _ECRANS_DE_TRAVAIL
        self.cadre_sens.setVisible(travail)
        self.outils.setCurrentIndex(_ECRANS_DE_TRAVAIL.index(mode) if travail else 2)
        if travail:
            self.sens.afficher(page.source)
        else:
            self.titre_de_page.definir(page.TITRE, page.SOUS_TITRE)
        self.rail.definir(mode)
        self.actions_mode[mode].setChecked(True)
        self.action_inverser.setEnabled(travail)
        self._actualiser_les_actions()
        self._actualiser_l_etat()
        if mode == MODE_TERME:
            self.page.champ.setFocus()
        elif mode == MODE_TEXTE:
            self.page_texte.zone_source.setFocus()
        else:
            page.setFocus()  # les flèches du clavier font défiler la page

    def indiquer_l_adresse(self) -> None:
        """Ouvre « Paramètres » sur le champ de l'adresse du service informatique."""
        self.definir_mode(MODE_PARAMETRES)
        self.page_parametres.montrer_l_adresse()

    def afficher_la_fiche(self, entree) -> None:
        """Ouvre, sur l'écran « Terme », la fiche d'un terme relevé dans un texte."""
        self.page.definir_sens(self.page_texte.source)
        self.definir_mode(MODE_TERME)
        self.page.ouvrir(entree)

    def inverser_le_sens(self) -> None:
        ecran = self.ecran_de_travail()
        if ecran is not None:
            ecran.inverser()

    def _sens_change(self, source: str) -> None:
        if self.sender() is self.page_courante():
            self.sens.afficher(source)

    def _etat_change(self, _texte: str) -> None:
        if self.sender() is self.page_courante():
            self._actualiser_l_etat()

    def _actualiser_l_etat(self) -> None:
        """Barre d'état : ce que l'écran affiché a à signaler (le résultat d'une recherche, par exemple)."""
        ecran = self.ecran_de_travail()
        self.barre_etat.definir_etat(ecran.etat if ecran is not None else "")

    def _actualiser_les_actions(self) -> None:
        """Active l'export et la copie seulement s'il y a une traduction."""
        traduction = self.page_texte.traduction is not None
        self.action_exporter.setEnabled(traduction)
        self.action_copier.setEnabled(traduction)

    # ------------------------------------------------------------------ texte : import, export, traduction
    def importer_un_texte(self) -> None:
        self.definir_mode(MODE_TEXTE)
        self.page_texte.importer()

    def exporter_la_traduction(self) -> None:
        self.definir_mode(MODE_TEXTE)
        self.page_texte.exporter()

    def _traduire_le_texte(self) -> None:
        self.definir_mode(MODE_TEXTE)
        self.page_texte.traduire()

    def _inserer_un_exemple(self) -> None:
        self.definir_mode(MODE_TEXTE)
        self.page_texte.inserer_un_exemple()

    def _effacer_le_texte(self) -> None:
        self.definir_mode(MODE_TEXTE)
        self.page_texte.effacer()

    # ------------------------------------------------------------------ recherche
    def _aller_a_la_recherche(self) -> None:
        self.definir_mode(MODE_TERME)
        self.page.champ.setFocus()
        self.page.champ.selectAll()

    def _effacer_la_recherche(self) -> None:
        self.definir_mode(MODE_TERME)
        self.page.effacer()


__all__ = ["GLOSSAIRE_EXEMPLE", "MODE_AIDE", "MODE_DESCRIPTION", "MODE_PARAMETRES", "MODE_TERME", "MODE_TEXTE",
           "BarreEtat", "FenetrePrincipale", "SelecteurSens", "TitreDePage"]
