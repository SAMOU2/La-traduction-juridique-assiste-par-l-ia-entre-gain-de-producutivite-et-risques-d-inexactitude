"""Fenêtre principale : barre de menus, barre d'outils, les deux écrans, barre d'état.

Les deux écrans sont « Terme » (``PageRecherche``) et « Texte » (``PageTexte``). Chacun garde
son propre sens de traduction. La barre d'outils affiche le sens de l'écran visible et ses
commandes : la barre de recherche, ou l'import, l'export et la traduction d'un texte.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import NOM_APPLICATION, __version__
from ..glossaire import ErreurGlossaire, Glossaire
from ..langues import AR, NOM_EN_FRANCAIS, NOM_NATIF, autre_langue
from . import boites, icones, theme
from .composants import EtiquetteCourte, compte, etiquette, icone_fixe, repeindre
from .recherche import PageRecherche
from .texte import PageTexte

#: Glossaire d'exemple fourni avec le projet (dossier « donnees » à la racine).
GLOSSAIRE_EXEMPLE = Path(__file__).resolve().parents[2] / "donnees" / "glossaire_juridique.csv"

#: Les deux écrans de l'application.
MODE_TERME = "terme"
MODE_TEXTE = "texte"

_CLE_GLOSSAIRE = "glossaire/chemin"
_SEPARATEURS = {"\t": "tabulation", ";": "point-virgule", ",": "virgule"}


def version_courte() -> str:
    """« 0.3 » pour la version « 0.3.0 »."""
    return ".".join(__version__.split(".")[:2])


def _filet_vertical(hauteur: int) -> QFrame:
    filet = QFrame()
    filet.setObjectName("filetVertical")
    filet.setFixedSize(1, hauteur)
    return filet


# ====================================================================== barre de menus : le glossaire chargé
class IndicateurGlossaire(QPushButton):
    """Rappel du glossaire chargé, à droite de la barre de menus : nom du fichier et nombre d'entrées.

    Un clic ouvre un menu : ouvrir un autre glossaire, le recharger, revenir au glossaire d'exemple.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("indicateurGlossaire")
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(10, 0, 10, 0)
        ligne.setSpacing(0)
        self.point = QFrame()
        self.point.setObjectName("pointGlossaire")
        self.point.setFixedSize(7, 7)
        self.nom = EtiquetteCourte("", "glossaireNom")
        self.nom.setMaximumWidth(280)
        self.detail = etiquette("", "glossaireDetail")
        self.chevron = icone_fixe("chevron-b", theme.TEXTE_3, 12, 1.6)
        ligne.addWidget(self.point)
        ligne.addSpacing(7)
        ligne.addWidget(self.nom)
        ligne.addWidget(self.detail)
        ligne.addSpacing(8)
        ligne.addWidget(self.chevron)
        # Les clics traversent les étiquettes : c'est le bouton qui les reçoit.
        for element in (self.point, self.nom, self.detail, self.chevron):
            element.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(self.layout().sizeHint().width(), 24)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.layout().minimumSize().width(), 24)

    def afficher(self, glossaire: Glossaire | None) -> None:
        """Affiche le nom et la taille du glossaire chargé."""
        absent = glossaire is None
        if self.point.property("absent") != absent:
            self.point.setProperty("absent", absent)
            repeindre(self.point)
        if absent:
            self.nom.definir_texte("Aucun glossaire chargé")
            self.detail.setText("")
            self.setToolTip("Ouvrir un fichier CSV")
        else:
            self.nom.definir_texte(glossaire.nom)
            self.detail.setText(f" · {compte(len(glossaire), 'entrée')}")
            separateur = _SEPARATEURS.get(glossaire.separateur, glossaire.separateur)
            lignes = [str(glossaire.chemin)] if glossaire.chemin else []
            lignes.append(f"Encodage {glossaire.encodage}, séparateur : {separateur}")
            self.setToolTip("<qt>" + "<br>".join(escape(ligne) for ligne in lignes) + "</qt>")
        self.setAccessibleName(f"Glossaire : {self.nom.texte_complet()}{self.detail.text()}")
        self.updateGeometry()


# ====================================================================== barre d'outils
class SelecteurMode(QFrame):
    """Choix de l'écran : « Terme » ou « Texte »."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("selecteurMode")
        self.setFixedSize(200, 44)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(4, 4, 4, 4)
        ligne.setSpacing(0)
        self.groupe = QButtonGroup(self)
        self.boutons: dict[str, QPushButton] = {}
        for mode, libelle, nom_icone, info in (
                (MODE_TERME, "Terme", "fiche", "Recherche d’un terme (Ctrl+1)"),
                (MODE_TEXTE, "Texte", "texte", "Traduction d’un texte (Ctrl+2)")):
            bouton = QPushButton(libelle)
            bouton.setProperty("classe", "mode")
            bouton.setCheckable(True)
            bouton.setIcon(icones.icone_a_deux_etats(nom_icone, theme.TEXTE_3, theme.BLEU_FONCE, 16, 1.6, marge=3))
            bouton.setIconSize(QSize(19, 16))
            bouton.setFixedSize(96, 36)
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton.setToolTip(info)
            self.groupe.addButton(bouton)
            self.boutons[mode] = bouton
            ligne.addWidget(bouton)


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


# ====================================================================== barre d'état
class BarreEtat(QFrame):
    """Barre d'état : à gauche, l'état de l'écran ou un message passager ; à droite, le sens et la version."""

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
        ligne.addSpacing(16)
        # « français → arabe » : la flèche est dessinée (ce signe manque dans certaines polices).
        self.sens_source = etiquette("", "etat")
        self.sens_cible = etiquette("", "etat")
        ligne.addWidget(self.sens_source)
        ligne.addSpacing(5)
        ligne.addWidget(icone_fixe("fleche", theme.TEXTE_3, 12, 1.4))
        ligne.addSpacing(5)
        ligne.addWidget(self.sens_cible)
        ligne.addSpacing(12)
        ligne.addWidget(_filet_vertical(12))
        ligne.addSpacing(12)
        self.version = etiquette(f"Version {version_courte()}", "etat")
        ligne.addWidget(self.version)
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
        """Le texte affiché à gauche (non abrégé)."""
        return self.message.texte_complet()

    def etat(self) -> str:
        return self._etat

    def definir_sens(self, source: str) -> None:
        self.sens_source.setText(f"Sens : {NOM_EN_FRANCAIS[source]}")
        self.sens_cible.setText(NOM_EN_FRANCAIS[autre_langue(source)])

    def sens(self) -> str:
        """Le sens affiché, en toutes lettres : « Sens : français → arabe »."""
        return f"{self.sens_source.text()} → {self.sens_cible.text()}"


# ====================================================================== la fenêtre
class FenetrePrincipale(QMainWindow):
    """La fenêtre de l'application."""

    def __init__(self, chemin_glossaire: str | Path | None = None, reglages: QSettings | None = None) -> None:
        super().__init__()
        self.reglages = reglages if reglages is not None else QSettings()
        self.glossaire: Glossaire | None = None
        self.mode = MODE_TERME

        self.setWindowTitle(NOM_APPLICATION)
        self.setWindowIcon(icones.icone_application())
        self.setPalette(theme.palette())
        self.setStyleSheet(theme.FEUILLE_DE_STYLE)
        self.setMinimumSize(900, 560)

        self.page = PageRecherche()
        self.page_texte = PageTexte()
        self.pile = QStackedWidget()
        self.pile.addWidget(self.page)
        self.pile.addWidget(self.page_texte)
        self.barre_etat = BarreEtat()

        centre = QWidget()
        centre.setObjectName("centre")
        centre.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensemble = QVBoxLayout(centre)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        ensemble.addWidget(self._creer_barre_outils())
        ensemble.addWidget(self.pile, 1)
        ensemble.addWidget(self.barre_etat)
        self.setCentralWidget(centre)
        self._creer_barre_menus()

        for page in (self.page, self.page_texte):
            page.sens_change.connect(self._sens_change)
            page.message.connect(self.barre_etat.afficher_message)
            page.etat_change.connect(self._etat_change)
        self.page.glossaire_demande.connect(self.ouvrir_glossaire)
        self.page_texte.entree_demandee.connect(self.afficher_la_fiche)
        self.page_texte.traduction_changee.connect(self._actualiser_les_actions)
        self._taille_initiale()
        self._charger_au_demarrage(chemin_glossaire)
        self.definir_mode(MODE_TERME)

    # ------------------------------------------------------------------ construction
    def _creer_barre_outils(self) -> QWidget:
        """Sélecteur d'écran, sens de traduction, puis les commandes de l'écran visible."""
        barre = QWidget()
        barre.setObjectName("barreOutils")
        barre.setFixedHeight(74)
        ligne = QHBoxLayout(barre)
        # La barre de recherche est entourée d'un halo de 3 pixels : les marges en tiennent compte.
        ligne.setContentsMargins(theme.MARGE, 11, theme.MARGE - 3, 13)
        ligne.setSpacing(0)

        self.selecteur = SelecteurMode()
        self.boutons_mode = self.selecteur.boutons
        for mode, bouton in self.boutons_mode.items():
            bouton.clicked.connect(lambda _=False, choix=mode: self.definir_mode(choix))
        self.sens = SelecteurSens()
        self.etiquette_source, self.etiquette_cible = self.sens.source, self.sens.cible
        self.bouton_inverser = self.sens.bouton_inverser
        self.bouton_inverser.clicked.connect(self.inverser_le_sens)

        # Les commandes appartiennent aux écrans ; la barre d'outils montre celles de l'écran visible.
        self.outils = QStackedWidget()
        self.outils.setFixedHeight(50)
        self.outils.addWidget(self.page.barre)
        cadre = QWidget()
        dans_le_cadre = QHBoxLayout(cadre)
        dans_le_cadre.setContentsMargins(3, 0, 3, 0)
        dans_le_cadre.addWidget(self.page_texte.outils)
        self.outils.addWidget(cadre)
        self.bouton_importer = self.page_texte.bouton_importer
        self.bouton_exporter = self.page_texte.bouton_exporter

        ligne.addWidget(self.selecteur)
        ligne.addSpacing(16)
        ligne.addWidget(self.sens)
        ligne.addSpacing(13)
        ligne.addWidget(self.outils, 1)
        return barre

    def _creer_barre_menus(self) -> None:
        """Barre de menus ; à droite, le glossaire chargé."""
        cadre = QFrame()
        cadre.setObjectName("barreMenus")
        cadre.setFixedHeight(35)
        ligne = QHBoxLayout(cadre)
        ligne.setContentsMargins(5, 0, theme.MARGE, 1)
        ligne.setSpacing(12)
        self.menus = QMenuBar()
        self.menus.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.indicateur = IndicateurGlossaire()
        ligne.addWidget(self.menus, 0, Qt.AlignmentFlag.AlignVCenter)
        ligne.addStretch(1)
        ligne.addWidget(self.indicateur, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setMenuWidget(cadre)
        self._creer_menus()

        menu_glossaire = QMenu(self.indicateur)
        for action in (self.action_ouvrir, self.action_recharger, self.action_exemple):
            menu_glossaire.addAction(action)
        menu_glossaire.addSeparator()
        menu_glossaire.addAction(self.action_format)
        self.indicateur.setMenu(menu_glossaire)

    def _creer_menus(self) -> None:
        menu_fichier = self.menus.addMenu("&Fichier")
        self.action_ouvrir = QAction("&Ouvrir un glossaire…", self)
        self.action_ouvrir.setShortcut(QKeySequence.StandardKey.Open)
        self.action_ouvrir.triggered.connect(self.ouvrir_glossaire)
        menu_fichier.addAction(self.action_ouvrir)
        self.action_recharger = QAction("&Recharger le glossaire", self)
        self.action_recharger.setShortcut(QKeySequence("F5"))
        self.action_recharger.triggered.connect(self.recharger_glossaire)
        menu_fichier.addAction(self.action_recharger)
        self.action_exemple = QAction("Revenir au glossaire d’&exemple", self)
        self.action_exemple.triggered.connect(lambda: self.charger_glossaire(GLOSSAIRE_EXEMPLE))
        menu_fichier.addAction(self.action_exemple)
        menu_fichier.addSeparator()
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

        menu_affichage = self.menus.addMenu("Aff&ichage")
        groupe = QActionGroup(self)
        self.actions_mode: dict[str, QAction] = {}
        for mode, libelle, raccourci in ((MODE_TERME, "Recherche d’un &terme", "Ctrl+1"),
                                         (MODE_TEXTE, "Traduction d’un te&xte", "Ctrl+2")):
            action = QAction(libelle, self)
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

        menu_recherche = self.menus.addMenu("&Recherche")
        action_champ = QAction("&Aller à la barre de recherche", self)
        action_champ.setShortcut(QKeySequence.StandardKey.Find)
        action_champ.triggered.connect(self._aller_a_la_recherche)
        menu_recherche.addAction(action_champ)
        action_effacer_recherche = QAction("&Effacer la recherche", self)
        action_effacer_recherche.triggered.connect(self._effacer_la_recherche)
        menu_recherche.addAction(action_effacer_recherche)

        menu_traduction = self.menus.addMenu("&Traduction")
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

        menu_aide = self.menus.addMenu("&Aide")
        self.action_format = QAction("&Format du glossaire CSV", self)
        self.action_format.triggered.connect(self.afficher_format)
        menu_aide.addAction(self.action_format)
        action_fonctionnement = QAction("&Traduction d’un texte : fonctionnement", self)
        action_fonctionnement.triggered.connect(self.afficher_fonctionnement)
        menu_aide.addAction(action_fonctionnement)
        action_a_propos = QAction("À &propos", self)
        action_a_propos.triggered.connect(self.afficher_a_propos)
        menu_aide.addAction(action_a_propos)

    def _taille_initiale(self) -> None:
        """Taille de la proposition (1440 × 860), réduite si l'écran est plus petit ; fenêtre centrée."""
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
        """Charge le glossaire demandé, sinon le dernier glossaire ouvert, sinon l'exemple."""
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
        if erreurs:
            # Le message est affiché une fois la fenêtre ouverte.
            QTimer.singleShot(0, lambda: self._avertir("Glossaire non chargé", "\n\n".join(erreurs)))

    def _installer(self, glossaire: Glossaire | None, *, memoriser: bool = False) -> None:
        self.glossaire = glossaire
        self.indicateur.afficher(glossaire)
        self.page.definir_glossaire(glossaire)
        self.page_texte.definir_glossaire(glossaire)
        self.action_recharger.setEnabled(glossaire is not None and glossaire.chemin is not None)
        if glossaire is not None and memoriser and glossaire.chemin is not None:
            chemin = glossaire.chemin.resolve()
            if chemin == GLOSSAIRE_EXEMPLE:
                self.reglages.remove(_CLE_GLOSSAIRE)  # l'exemple est déjà le glossaire par défaut
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
            self, "Ouvrir un glossaire", depart, "Glossaire CSV (*.csv *.tsv *.txt);;Tous les fichiers (*)")
        if chemin:
            self.charger_glossaire(chemin, bilan=True)

    def recharger_glossaire(self) -> None:
        """Relit le fichier du glossaire (après l'avoir modifié dans un tableur, par exemple)."""
        if self.glossaire is not None and self.glossaire.chemin is not None:
            self.charger_glossaire(self.glossaire.chemin)

    @staticmethod
    def bilan_de_lecture(glossaire: Glossaire) -> str:
        """Résumé de ce qui a été lu dans le fichier : entrées, colonnes reconnues ou ignorées."""
        separateur = _SEPARATEURS.get(glossaire.separateur, glossaire.separateur)
        lignes = [
            f"{glossaire.nom} : {compte(len(glossaire), 'entrée')}.",
            f"Encodage {glossaire.encodage}, séparateur : {separateur}.",
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

    def _boite(self, genre: str, titre: str, texte: str) -> None:
        """Boîte de message. Le texte est affiché tel quel (un nom de fichier peut contenir « & » ou « < »)."""
        boites.afficher(self, genre, titre, texte)

    # ------------------------------------------------------------------ écrans
    def page_courante(self) -> PageRecherche | PageTexte:
        """L'écran visible."""
        return self.page if self.mode == MODE_TERME else self.page_texte

    def definir_mode(self, mode: str) -> None:
        """Affiche l'écran « Terme » (recherche d'un terme) ou l'écran « Texte » (traduction d'un texte)."""
        self.mode = mode
        self.pile.setCurrentWidget(self.page_courante())
        self.outils.setCurrentIndex(0 if mode == MODE_TERME else 1)
        self.boutons_mode[mode].setChecked(True)
        self.actions_mode[mode].setChecked(True)
        self._afficher_sens(self.page_courante().source)
        self._actualiser_les_actions()
        self._actualiser_l_etat()
        (self.page.champ if mode == MODE_TERME else self.page_texte.zone_source).setFocus()

    def afficher_la_fiche(self, entree) -> None:
        """Ouvre, sur l'écran « Terme », la fiche d'un terme relevé dans un texte."""
        self.page.definir_sens(self.page_texte.source)
        self.definir_mode(MODE_TERME)
        self.page.ouvrir(entree)

    def inverser_le_sens(self) -> None:
        self.page_courante().inverser()

    def _sens_change(self, source: str) -> None:
        if self.sender() is self.page_courante():
            self._afficher_sens(source)

    def _etat_change(self, _texte: str) -> None:
        if self.sender() is self.page_courante():
            self._actualiser_l_etat()

    def _actualiser_l_etat(self) -> None:
        """Barre d'état : l'état de l'écran visible ; s'il n'a rien à signaler, le glossaire chargé."""
        self.barre_etat.definir_etat(self.page_courante().etat or self.etat_du_glossaire())

    def etat_du_glossaire(self) -> str:
        if self.glossaire is None:
            return "Aucun glossaire chargé."
        return f"Glossaire chargé : {compte(len(self.glossaire), 'entrée')}."

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

    # ------------------------------------------------------------------ autres actions
    def _afficher_sens(self, source: str) -> None:
        self.sens.afficher(source)
        self.barre_etat.definir_sens(source)

    def _aller_a_la_recherche(self) -> None:
        self.definir_mode(MODE_TERME)
        self.page.champ.setFocus()
        self.page.champ.selectAll()

    def _effacer_la_recherche(self) -> None:
        self.definir_mode(MODE_TERME)
        self.page.effacer()

    def afficher_format(self) -> None:
        self._informer(
            "Format du glossaire CSV",
            "Le glossaire est un fichier CSV : une ligne par terme, la première ligne donne le nom des colonnes.\n\n"
            "Colonnes obligatoires :\n"
            "    terme_fr, terme_ar\n\n"
            "Colonnes facultatives :\n"
            "    categorie_fr, categorie_ar, pluriel_fr, pluriel_ar, domaine,\n"
            "    synonymes_fr, synonymes_ar, termes_associes,\n"
            "    definition_fr, definition_ar, source_definition,\n"
            "    contexte_fr, contexte_ar, source_contexte, ressources\n\n"
            "Dans une cellule, plusieurs valeurs se séparent par une barre verticale : convention | accord.\n\n"
            "Depuis Excel : Enregistrer sous → « CSV UTF-8 (délimité par des virgules) ». "
            "Le séparateur (point-virgule, virgule ou tabulation) est reconnu automatiquement.",
        )

    def afficher_fonctionnement(self) -> None:
        self._informer(
            "Traduction d’un texte : fonctionnement",
            "Le texte est traduit à l’aide du glossaire, en cinq étapes :\n\n"
            "1. Segmentation : le texte est découpé en phrases.\n"
            "2. Découpage : chaque phrase est découpée en mots.\n"
            "3. Recherche dans le CSV : la phrase entière est cherchée parmi les exemples du glossaire, "
            "puis les expressions les plus longues, puis les mots un par un.\n"
            "4. Règles linguistiques : synonymes, pluriel, article, complément du nom, choix entre "
            "plusieurs équivalents d’après le contexte.\n"
            "5. Reconstruction : chaque phrase est récrite dans la langue cible, avec sa ponctuation.\n\n"
            "Une phrase qui figure parmi les exemples du glossaire est remplacée par la traduction de "
            "l’exemple. Les autres phrases sont traduites mot à mot : les termes du glossaire sont "
            "traduits (en bleu), les autres mots restent dans la langue source (en gris) et l’ordre "
            "des mots n’est pas modifié.\n\n"
            "Le résultat est une aide : il doit être complété et vérifié par le traducteur.",
        )

    def afficher_a_propos(self) -> None:
        boites.afficher(
            self, boites.INFORMATION, f"À propos de {NOM_APPLICATION}",
            f"<b>{escape(NOM_APPLICATION)}</b> — version {escape(__version__)}<br><br>"
            "Traduction juridique français ⇄ arabe à l’aide d’un glossaire CSV :<br>"
            "recherche d’un terme (terme, définition, équivalent, contextualisation, ressources) "
            "et traduction d’un texte.<br><br>"
            "Les équivalents proposés viennent du glossaire chargé ; ils doivent être "
            "vérifiés par le traducteur.",
            image=icones.logo(40), riche=True)


__all__ = ["GLOSSAIRE_EXEMPLE", "MODE_TERME", "MODE_TEXTE", "BarreEtat", "FenetrePrincipale", "IndicateurGlossaire",
           "SelecteurMode", "SelecteurSens", "version_courte"]
