"""Fenêtre principale : menus, barre d'outils, écran de recherche, barre d'état."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
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

#: Glossaire d'exemple fourni avec le projet (dossier « donnees » à la racine).
GLOSSAIRE_EXEMPLE = Path(__file__).resolve().parents[2] / "donnees" / "glossaire_juridique.csv"

_CLE_GLOSSAIRE = "glossaire/chemin"


def _nombre(valeur: int) -> str:
    """Écrit un nombre à la française : 2 480."""
    return f"{valeur:,}".replace(",", "\u202f")


class PastilleLangue(QFrame):
    """Encadré de la barre d'outils qui rappelle la langue source ou la langue cible."""

    def __init__(self, legende: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pastilleLangue")
        self.setFixedSize(176, 44)
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

    def definir_langue(self, langue: str) -> None:
        self.code.setText(langue.upper())
        self.nom.setText(NOM_NATIF[langue])


class FenetrePrincipale(QMainWindow):
    """La fenêtre de l'application."""

    def __init__(self, chemin_glossaire: str | Path | None = None, reglages: QSettings | None = None) -> None:
        super().__init__()
        self.reglages = reglages if reglages is not None else QSettings()
        self.glossaire: Glossaire | None = None

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
        ensemble.addWidget(self._creer_barre_outils())
        ensemble.addWidget(self.page, 1)
        self.setCentralWidget(centre)

        self._creer_menus()
        self._creer_barre_etat()
        self.page.sens_change.connect(self._afficher_sens)
        self.page.message.connect(lambda texte: self.statusBar().showMessage(texte, 5000))
        self._afficher_sens(self.page.source)
        self._taille_initiale()
        self._charger_au_demarrage(chemin_glossaire)
        self.page.champ.setFocus()

    # ------------------------------------------------------------------ construction
    def _creer_barre_outils(self) -> QFrame:
        barre = QFrame()
        barre.setObjectName("barreOutils")
        barre.setFixedHeight(64)
        grille = QGridLayout(barre)
        grille.setContentsMargins(24, 0, 24, 0)
        grille.setHorizontalSpacing(12)

        # Au centre : langue source, bouton d'inversion, langue cible.
        self.pastille_source = PastilleLangue("Source")
        self.pastille_cible = PastilleLangue("Cible")
        self.bouton_inverser = QToolButton()
        self.bouton_inverser.setObjectName("boutonInverser")
        self.bouton_inverser.setIcon(icones.icone("echange", theme.BLEU_FONCE, 20))
        self.bouton_inverser.setFixedSize(36, 36)
        self.bouton_inverser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_inverser.setToolTip("Inverser le sens de traduction (Ctrl+I)")
        self.bouton_inverser.clicked.connect(self.page.inverser)
        sens = QHBoxLayout()
        sens.setSpacing(8)
        sens.addWidget(self.pastille_source)
        sens.addWidget(self.bouton_inverser)
        sens.addWidget(self.pastille_cible)

        # À droite : ouverture d'un autre glossaire.
        self.bouton_glossaire = QPushButton("Ouvrir un glossaire…")
        self.bouton_glossaire.setObjectName("boutonGlossaire")
        self.bouton_glossaire.setIcon(icones.icone("tableau", theme.TEXTE_2, 18))
        self.bouton_glossaire.setFixedHeight(40)
        self.bouton_glossaire.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_glossaire.setToolTip("Ouvrir un fichier CSV (Ctrl+O)")
        self.bouton_glossaire.clicked.connect(self.ouvrir_glossaire)

        grille.addLayout(sens, 0, 1, Qt.AlignmentFlag.AlignCenter)
        grille.addWidget(self.bouton_glossaire, 0, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Colonnes latérales de même largeur : le sens de traduction reste centré.
        largeur = self.bouton_glossaire.sizeHint().width()
        for colonne in (0, 2):
            grille.setColumnMinimumWidth(colonne, largeur)
            grille.setColumnStretch(colonne, 1)
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
        action_quitter = QAction("&Quitter", self)
        action_quitter.setShortcut(QKeySequence("Ctrl+Q"))
        action_quitter.triggered.connect(self.close)
        menu_fichier.addAction(action_quitter)

        menu_recherche = self.menuBar().addMenu("&Recherche")
        action_champ = QAction("&Aller à la barre de recherche", self)
        action_champ.setShortcut(QKeySequence.StandardKey.Find)
        action_champ.triggered.connect(self._aller_a_la_recherche)
        menu_recherche.addAction(action_champ)
        action_inverser = QAction("&Inverser le sens de traduction", self)
        action_inverser.setShortcut(QKeySequence("Ctrl+I"))
        action_inverser.triggered.connect(self.page.inverser)
        menu_recherche.addAction(action_inverser)

        menu_aide = self.menuBar().addMenu("&Aide")
        action_format = QAction("&Format du glossaire CSV", self)
        action_format.triggered.connect(self.afficher_format)
        menu_aide.addAction(action_format)
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

    # ------------------------------------------------------------------ autres actions
    def _afficher_sens(self, source: str) -> None:
        cible = autre_langue(source)
        self.pastille_source.definir_langue(source)
        self.pastille_cible.definir_langue(cible)
        self.etat_sens.setText(f"Sens : {NOM_EN_FRANCAIS[source]} › {NOM_EN_FRANCAIS[cible]}"
                               f"   |   Prototype v{'.'.join(__version__.split('.')[:2])}")

    def _aller_a_la_recherche(self) -> None:
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

    def afficher_a_propos(self) -> None:
        QMessageBox.about(
            self, f"À propos de {NOM_APPLICATION}",
            f"<b>{NOM_APPLICATION}</b> — prototype v{__version__}<br><br>"
            "Recherche de termes juridiques français ⇄ arabe dans un glossaire CSV :<br>"
            "terme, définition, équivalent, contextualisation, ressources.<br><br>"
            "Les équivalents proposés viennent du glossaire chargé ; ils doivent être "
            "vérifiés par le traducteur.",
        )
