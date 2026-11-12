"""Fenêtre principale : menus, barre d'outils, les deux écrans, barre d'état.

Les deux écrans sont « Recherche d'un terme » (``PageRecherche``) et
« Traduction d'un texte » (``PageTexte``). Chacun garde son propre sens de
traduction ; la barre d'outils affiche celui de l'écran visible.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import NOM_APPLICATION, __version__
from ..glossaire import ErreurGlossaire, Glossaire
from ..langues import FR, NOM_EN_FRANCAIS, NOM_NATIF, autre_langue
from . import icones, theme
from .composants import GAUCHE, etiquette, infobulle, pastille_langue
from .recherche import PageRecherche
from .texte import PageTexte

#: Glossaire d'exemple fourni avec le projet (dossier « donnees » à la racine).
GLOSSAIRE_EXEMPLE = Path(__file__).resolve().parents[2] / "donnees" / "glossaire_juridique.csv"

#: Les deux écrans de l'application.
MODE_TERME = "terme"
MODE_TEXTE = "texte"

_CLE_GLOSSAIRE = "glossaire/chemin"


def _nombre(valeur: int) -> str:
    """Écrit un nombre à la française : 2 480."""
    return f"{valeur:,}".replace(",", "\u202f")


class PastilleLangue(QFrame):
    """Encadré de la barre d'outils qui rappelle la langue source ou la langue cible."""

    def __init__(self, legende: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pastilleLangue")
        # Largeur de la maquette ; la pastille rétrécit un peu dans une fenêtre étroite.
        self.setFixedHeight(44)
        self.setMinimumWidth(148)
        self.setMaximumWidth(176)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(10, 0, 12, 0)
        ligne.setSpacing(10)
        self.code = pastille_langue(FR)
        ligne.addWidget(self.code)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        colonne.addStretch(1)
        colonne.addWidget(etiquette(legende.upper(), "legende"))
        self.nom = etiquette("", "nomLangue")
        # Le nom reste aligné à gauche sous la légende, même écrit en arabe.
        self.nom.setAlignment(GAUCHE | Qt.AlignmentFlag.AlignVCenter)
        colonne.addWidget(self.nom)
        colonne.addStretch(1)
        ligne.addLayout(colonne, 1)

    def sizeHint(self):  # noqa: N802 (nom imposé par Qt)
        taille = super().sizeHint()
        taille.setWidth(176)
        return taille

    def definir_langue(self, langue: str) -> None:
        self.code.setText(langue.upper())
        self.nom.setText(NOM_NATIF[langue])


class FenetrePrincipale(QMainWindow):
    """La fenêtre de l'application."""

    def __init__(self, chemin_glossaire: str | Path | None = None, reglages: QSettings | None = None) -> None:
        super().__init__()
        self.reglages = reglages if reglages is not None else QSettings()
        self.glossaire: Glossaire | None = None
        self.mode = MODE_TERME

        self.setWindowTitle(f"{NOM_APPLICATION} — Français / Arabe")
        self.setWindowIcon(icones.icone_application())
        self.setStyleSheet(theme.FEUILLE_DE_STYLE)
        self.setMinimumSize(900, 560)

        centre = QWidget()
        centre.setObjectName("centre")
        centre.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ensemble = QVBoxLayout(centre)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        self.page = PageRecherche()
        self.page_texte = PageTexte()
        self.pile = QStackedWidget()
        self.pile.addWidget(self.page)
        self.pile.addWidget(self.page_texte)
        ensemble.addWidget(self._creer_barre_outils())
        ensemble.addWidget(self.pile, 1)
        self.setCentralWidget(centre)

        self._creer_menus()
        self._creer_barre_etat()
        for page in (self.page, self.page_texte):
            page.sens_change.connect(self._sens_change)
            page.message.connect(lambda texte: self.statusBar().showMessage(texte, 5000))
        self.page_texte.entree_demandee.connect(self.afficher_la_fiche)
        self.page_texte.traduction_changee.connect(self._actualiser_les_actions)
        self._taille_initiale()
        self._charger_au_demarrage(chemin_glossaire)
        self.definir_mode(MODE_TERME)

    # ------------------------------------------------------------------ construction
    def _creer_barre_outils(self) -> QFrame:
        barre = QFrame()
        barre.setObjectName("barreOutils")
        barre.setFixedHeight(64)
        grille = QGridLayout(barre)
        grille.setContentsMargins(24, 0, 24, 0)
        grille.setHorizontalSpacing(12)

        # À gauche : choix de l'écran, « Terme » ou « Texte ».
        self.selecteur = QFrame()
        self.selecteur.setObjectName("selecteurMode")
        self.selecteur.setFixedHeight(40)
        dans_le_selecteur = QHBoxLayout(self.selecteur)
        dans_le_selecteur.setContentsMargins(3, 3, 3, 3)
        dans_le_selecteur.setSpacing(2)
        self.groupe_modes = QButtonGroup(self)
        self.boutons_mode: dict[str, QPushButton] = {}
        for mode, libelle, nom_icone, info in (
                (MODE_TERME, "Terme", "terme", "Recherche d’un terme (Ctrl+1)"),
                (MODE_TEXTE, "Texte", "texte", "Traduction d’un texte (Ctrl+2)")):
            bouton = QPushButton(libelle)
            bouton.setProperty("classe", "mode")
            bouton.setCheckable(True)
            bouton.setIcon(icones.icone_a_deux_etats(nom_icone, theme.TEXTE_3, theme.BLEU_FONCE, 16, 2.1))
            bouton.setFixedHeight(32)
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton.setToolTip(info)
            bouton.clicked.connect(lambda _=False, choix=mode: self.definir_mode(choix))
            self.groupe_modes.addButton(bouton)
            self.boutons_mode[mode] = bouton
            dans_le_selecteur.addWidget(bouton)

        # Au centre : langue source, bouton d'inversion, langue cible.
        self.pastille_source = PastilleLangue("Source")
        self.pastille_cible = PastilleLangue("Cible")
        self.bouton_inverser = QToolButton()
        self.bouton_inverser.setObjectName("boutonInverser")
        self.bouton_inverser.setIcon(icones.icone("echange", theme.BLEU_FONCE, 20))
        self.bouton_inverser.setFixedSize(36, 36)
        self.bouton_inverser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_inverser.setToolTip("Inverser le sens de traduction (Ctrl+I)")
        self.bouton_inverser.clicked.connect(self.inverser_le_sens)
        sens = QHBoxLayout()
        sens.setSpacing(8)
        sens.addWidget(self.pastille_source)
        sens.addWidget(self.bouton_inverser)
        sens.addWidget(self.pastille_cible)

        # À droite : le glossaire (écran « Terme »), l'import et l'export d'un texte (écran « Texte »).
        def bouton_outil(texte: str, nom_icone: str, info: str, action) -> QPushButton:
            bouton = QPushButton(texte)
            bouton.setProperty("classe", "outil")
            bouton.setIcon(icones.icone(nom_icone, theme.TEXTE_2, 18))
            bouton.setFixedHeight(40)
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton.setToolTip(info)
            bouton.clicked.connect(action)
            return bouton

        self.bouton_glossaire = bouton_outil("Ouvrir un glossaire…", "tableau", "Ouvrir un fichier CSV (Ctrl+O)",
                                             self.ouvrir_glossaire)
        self.bouton_importer = bouton_outil("Importer", "importer",
                                            "Importer un texte : fichier .txt, .docx ou .doc (Ctrl+Maj+O)",
                                            self.importer_un_texte)
        self.bouton_exporter = bouton_outil("Exporter", "exporter",
                                            "Exporter la traduction : fichier .docx ou .txt (Ctrl+E)",
                                            self.exporter_la_traduction)
        outils = QHBoxLayout()
        outils.setSpacing(8)
        for bouton in (self.bouton_glossaire, self.bouton_importer, self.bouton_exporter):
            outils.addWidget(bouton)

        grille.addWidget(self.selecteur, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grille.addLayout(sens, 0, 1, Qt.AlignmentFlag.AlignCenter)
        grille.addLayout(outils, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Les deux côtés se partagent la place restante : le sens de traduction reste centré
        # tant que la fenêtre est assez large.
        grille.setColumnStretch(0, 1)
        grille.setColumnStretch(2, 1)
        return barre

    def _creer_menus(self) -> None:
        menu_fichier = self.menuBar().addMenu("&Fichier")
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

        menu_affichage = self.menuBar().addMenu("Aff&ichage")
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
        action_inverser = QAction("&Inverser le sens de traduction", self)
        action_inverser.setShortcut(QKeySequence("Ctrl+I"))
        action_inverser.triggered.connect(self.inverser_le_sens)
        menu_affichage.addAction(action_inverser)

        menu_recherche = self.menuBar().addMenu("&Recherche")
        action_champ = QAction("&Aller à la barre de recherche", self)
        action_champ.setShortcut(QKeySequence.StandardKey.Find)
        action_champ.triggered.connect(self._aller_a_la_recherche)
        menu_recherche.addAction(action_champ)

        menu_traduction = self.menuBar().addMenu("&Traduction")
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

        menu_aide = self.menuBar().addMenu("&Aide")
        action_format = QAction("&Format du glossaire CSV", self)
        action_format.triggered.connect(self.afficher_format)
        menu_aide.addAction(action_format)
        action_fonctionnement = QAction("&Traduction d’un texte : fonctionnement", self)
        action_fonctionnement.triggered.connect(self.afficher_fonctionnement)
        menu_aide.addAction(action_fonctionnement)
        action_a_propos = QAction("À &propos", self)
        action_a_propos.triggered.connect(self.afficher_a_propos)
        menu_aide.addAction(action_a_propos)

    def _creer_barre_etat(self) -> None:
        self.etat_glossaire = QLabel()
        self.etat_glossaire.setTextFormat(Qt.TextFormat.RichText)
        self.etat_sens = QLabel()
        self.statusBar().addWidget(self.etat_glossaire, 1)
        self.statusBar().addPermanentWidget(self.etat_sens)

    def _taille_initiale(self) -> None:
        """Taille de la maquette (1440 × 860), réduite si l'écran est plus petit ; fenêtre centrée."""
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
        self.page.definir_glossaire(glossaire)
        self.page_texte.definir_glossaire(glossaire)
        self.action_recharger.setEnabled(glossaire is not None and glossaire.chemin is not None)
        if glossaire is None:
            self.etat_glossaire.setText(f'<span style="color: {theme.AMBRE};">●</span>&nbsp; Aucun glossaire chargé')
            self.etat_glossaire.setToolTip("")
        else:
            entrees = "1 entrée" if len(glossaire) == 1 else f"{_nombre(len(glossaire))} entrées"
            self.etat_glossaire.setText(
                f'<span style="color: {theme.VERT};">●</span>&nbsp; Glossaire chargé : '
                f'<b style="color: {theme.TEXTE};">{escape(glossaire.nom)}</b>'
                f' &nbsp;|&nbsp; {entrees} &nbsp;|&nbsp; {glossaire.encodage}'
            )
            self.etat_glossaire.setToolTip(infobulle(str(glossaire.chemin)) if glossaire.chemin else "")
            if memoriser and glossaire.chemin is not None:
                chemin = glossaire.chemin.resolve()
                if chemin == GLOSSAIRE_EXEMPLE:
                    self.reglages.remove(_CLE_GLOSSAIRE)  # l'exemple est déjà le glossaire par défaut
                else:
                    self.reglages.setValue(_CLE_GLOSSAIRE, str(chemin))

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
            self.statusBar().showMessage(f"Glossaire chargé : {glossaire.nom}", 4000)
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
        separateur = {"\t": "tabulation", ";": "point-virgule", ",": "virgule"}.get(glossaire.separateur,
                                                                                    glossaire.separateur)
        entrees = "1 entrée" if len(glossaire) == 1 else f"{_nombre(len(glossaire))} entrées"
        lignes = [
            f"{glossaire.nom} : {entrees}.",
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
        self._boite(QMessageBox.Icon.Information, titre, texte)

    def _avertir(self, titre: str, texte: str) -> None:
        self._boite(QMessageBox.Icon.Warning, titre, texte)

    def _boite(self, icone: QMessageBox.Icon, titre: str, texte: str) -> None:
        """Boîte de message. Le texte est affiché tel quel (un nom de fichier peut contenir « & » ou « < »)."""
        boite = QMessageBox(icone, titre, texte, QMessageBox.StandardButton.Ok, self)
        boite.setTextFormat(Qt.TextFormat.PlainText)
        boite.exec()

    # ------------------------------------------------------------------ écrans
    def page_courante(self) -> PageRecherche | PageTexte:
        """L'écran visible."""
        return self.page if self.mode == MODE_TERME else self.page_texte

    def definir_mode(self, mode: str) -> None:
        """Affiche l'écran « Recherche d'un terme » ou l'écran « Traduction d'un texte »."""
        self.mode = mode
        self.pile.setCurrentWidget(self.page_courante())
        self.boutons_mode[mode].setChecked(True)
        self.actions_mode[mode].setChecked(True)
        self.bouton_glossaire.setVisible(mode == MODE_TERME)
        self.bouton_importer.setVisible(mode == MODE_TEXTE)
        self.bouton_exporter.setVisible(mode == MODE_TEXTE)
        self._afficher_sens(self.page_courante().source)
        self._actualiser_les_actions()
        (self.page.champ if mode == MODE_TERME else self.page_texte.zone_source).setFocus()

    def afficher_la_fiche(self, entree) -> None:
        """Ouvre, sur l'écran de recherche, la fiche d'un terme relevé dans un texte."""
        self.page.definir_sens(self.page_texte.source)
        self.definir_mode(MODE_TERME)
        self.page.ouvrir(entree)

    def inverser_le_sens(self) -> None:
        self.page_courante().inverser()

    def _sens_change(self, source: str) -> None:
        if self.sender() is self.page_courante():
            self._afficher_sens(source)

    def _actualiser_les_actions(self) -> None:
        """Active l'export et la copie seulement s'il y a une traduction."""
        traduction = self.page_texte.traduction is not None
        self.bouton_exporter.setEnabled(traduction)
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
        cible = autre_langue(source)
        self.pastille_source.definir_langue(source)
        self.pastille_cible.definir_langue(cible)
        self.etat_sens.setText(f"Sens : {NOM_EN_FRANCAIS[source]} › {NOM_EN_FRANCAIS[cible]}"
                               f"   |   Prototype v{'.'.join(__version__.split('.')[:2])}")

    def _aller_a_la_recherche(self) -> None:
        self.definir_mode(MODE_TERME)
        self.page.champ.setFocus()
        self.page.champ.selectAll()

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
            "traduits (en couleur), les autres mots restent dans la langue source (en gris) et l’ordre "
            "des mots n’est pas modifié.\n\n"
            "Le résultat est une aide : il doit être complété et vérifié par le traducteur.",
        )

    def afficher_a_propos(self) -> None:
        QMessageBox.about(
            self, f"À propos de {NOM_APPLICATION}",
            f"<b>{NOM_APPLICATION}</b> — prototype v{__version__}<br><br>"
            "Traduction juridique français ⇄ arabe à l’aide d’un glossaire CSV :<br>"
            "recherche d’un terme (terme, définition, équivalent, contextualisation, ressources) "
            "et traduction d’un texte.<br><br>"
            "Les équivalents proposés viennent du glossaire chargé ; ils doivent être "
            "vérifiés par le traducteur.",
        )
