"""Écrans d'information : « Paramètres », « Description de la plateforme » et « Centre d'aide ».

Chacun est une colonne de cartes, qui défile si la fenêtre est petite. Ces écrans
ne font aucun traitement : ils affichent des réglages et des explications, et transmettent
les demandes de l'utilisateur à la fenêtre par des signaux.
"""

from __future__ import annotations

import platform
from collections.abc import Sequence
from html import escape
from urllib.parse import quote

import regex
from PySide6.QtCore import QSettings, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import NOM_APPLICATION, __version__
from ..glossaire import Glossaire
from ..langues import FR
from . import icones, theme
from .composants import (
    EtiquetteCourte,
    Interrupteur,
    Numero,
    Panneau,
    ZoneDefilante,
    compte,
    etiquette,
    paragraphe,
    repeindre,
    rond,
    separateur,
)

#: Clés des réglages enregistrés.
CLE_ANIMATIONS = "affichage/animations"
CLE_ECRAN_DE_DEMARRAGE = "affichage/ecran_de_demarrage"
CLE_ADRESSE = "aide/adresse"

_ADRESSE = regex.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")

#: Les cinq champs de l'enchaînement : (titre, ce que contient le champ).
CHAMPS = (
    ("Terme", "Le terme cherché, sa catégorie grammaticale, son domaine, ses synonymes."),
    ("Définition", "Ce que le terme signifie, en français et en arabe, avec la source de la définition."),
    ("Équivalent", "Le terme qui lui correspond dans l’autre langue, et ses autres équivalents."),
    ("Contextualisation", "Des phrases qui emploient le terme, dans les deux langues."),
    ("Ressources", "Les textes de loi, les ouvrages et les sites à consulter et à citer."),
)
#: Les cinq étapes de la traduction d'un texte.
TRAITEMENT = (
    ("Segmentation", "Le texte est découpé en phrases."),
    ("Découpage", "Chaque phrase est découpée en mots."),
    ("Recherche dans le glossaire", "La phrase entière est cherchée parmi les exemples du glossaire, puis les "
                                    "expressions les plus longues, puis les mots un par un."),
    ("Règles linguistiques", "Synonymes, pluriel, article, complément du nom, choix entre plusieurs sens "
                             "d’après le contexte."),
    ("Reconstruction", "Chaque phrase est récrite dans la langue cible, avec sa ponctuation."),
)
#: Questions fréquentes du centre d'aide : (question, paragraphes de la réponse).
QUESTIONS = (
    ("Comment chercher un terme ?",
     ("Ouvrez l’écran « Terme » (première icône de la barre de gauche). Écrivez le terme, en français ou en "
      "arabe, puis appuyez sur Entrée.",
      "La fiche affiche les cinq étapes : terme, définition, équivalent, contextualisation, ressources. Les "
      "étapes s’allument quand elles sont renseignées.")),
    ("Comment traduire un texte ?",
     ("Ouvrez l’écran « Texte » (deuxième icône). Écrivez, collez ou importez le texte : fichier .txt, .docx "
      "ou .doc. Cliquez ensuite sur « Traduire ».",
      "La traduction s’affiche sous le texte. À droite, chaque terme juridique du texte a sa définition, son "
      "équivalent, son contexte et ses références : cliquez sur un terme pour les afficher.")),
    ("Pourquoi des mots restent-ils dans la langue d’origine ?",
     ("L’application traduit avec le glossaire, et avec lui seul. Un mot absent du glossaire reste dans sa "
      "langue, écrit en gris : il est à traduire à la main.",)),
    ("Que signifie la mention « À vérifier » ?",
     ("Le glossaire ne cite pas de source pour cette définition. Contrôlez-la dans un texte officiel ou un "
      "dictionnaire juridique avant de la citer.",)),
    ("Comment utiliser un autre glossaire ?",
     ("Dans « Paramètres », choisissez un fichier CSV. Il contient une ligne par terme ; la première ligne "
      "donne le nom des colonnes. Les colonnes terme_fr et terme_ar sont obligatoires.",
      "Colonnes facultatives : categorie_fr, categorie_ar, pluriel_fr, pluriel_ar, domaine, synonymes_fr, "
      "synonymes_ar, termes_associes, definition_fr, definition_ar, source_definition, contexte_fr, "
      "contexte_ar, source_contexte, ressources.",
      "Dans une cellule, plusieurs valeurs se séparent par une barre verticale : convention | accord. Depuis "
      "Excel : Enregistrer sous → « CSV UTF-8 (délimité par des virgules) ».")),
)
#: Raccourcis rappelés dans le centre d'aide : (touches, action).
RACCOURCIS = (
    ("Ctrl+1", "écran « Terme »"),
    ("Ctrl+2", "écran « Texte »"),
    ("Ctrl+F", "aller à la barre de recherche"),
    ("Ctrl+I", "inverser le sens de traduction"),
    ("Ctrl+Return", "traduire le texte"),
    ("Ctrl+Shift+O", "importer un texte"),
    ("Ctrl+E", "exporter la traduction"),
    ("Ctrl+Shift+C", "copier la traduction"),
    ("F1", "centre d’aide"),
)


def ouvrir_lien(adresse: str) -> bool:
    """Ouvre une adresse avec le logiciel prévu par le système (messagerie pour « mailto: »)."""
    return QDesktopServices.openUrl(QUrl(adresse))


def adresse_valide(adresse: str) -> bool:
    """Vrai si le texte a la forme d'une adresse électronique."""
    return bool(_ADRESSE.fullmatch(adresse.strip()))


def _bouton(texte: str, classe: str = "contour", nom_icone: str = "", info: str = "") -> QPushButton:
    bouton = QPushButton(texte)
    bouton.setProperty("classe", classe)
    if nom_icone:
        couleur = theme.SURFACE if classe == "principal" else theme.TEXTE_2
        bouton.setIcon(icones.icone(nom_icone, couleur, 16, 1.6, marge=3,
                                    couleur_inactive=theme.SURFACE if classe == "principal" else theme.TEXTE_4))
        bouton.setIconSize(QSize(19, 16))
    bouton.setFixedHeight(36)
    bouton.setCursor(Qt.CursorShape.PointingHandCursor)
    bouton.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    if info:
        bouton.setToolTip(info)
    return bouton


def _texte(contenu: str, classe: str = "texteCarte", *, interligne: int = 22) -> QLabel:
    """Paragraphe d'une carte : il passe à la ligne, avec des lignes régulières."""
    label = etiquette(paragraphe(escape(contenu), FR, interligne), classe, retour_ligne=True, riche=True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


# ====================================================================== cartes
class Carte(Panneau):
    """Une carte d'un écran d'information : un titre, puis son contenu."""

    def __init__(self, titre: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.disposition = QVBoxLayout(self)
        self.disposition.setContentsMargins(theme.MARGE, 20, theme.MARGE, 22)
        self.disposition.setSpacing(0)
        self.titre = etiquette(titre, "titreCarte")
        self.disposition.addWidget(self.titre)

    def ajouter(self, element: QWidget, espace: int = 10) -> QWidget:
        self.disposition.addSpacing(espace)
        self.disposition.addWidget(element)
        return element

    def ajouter_texte(self, contenu: str, classe: str = "texteCarte", espace: int = 10) -> QLabel:
        return self.ajouter(_texte(contenu, classe), espace)

    def ajouter_ligne(self, elements: Sequence[QWidget], espace: int = 16) -> QHBoxLayout:
        """Ajoute des éléments côte à côte, alignés à gauche."""
        ligne = QHBoxLayout()
        ligne.setSpacing(10)
        for element in elements:
            ligne.addWidget(element)
        ligne.addStretch(1)
        self.disposition.addSpacing(espace)
        self.disposition.addLayout(ligne)
        return ligne


class LigneNumerotee(QWidget):
    """Une étape dans une liste : son numéro (allumé), son titre, une phrase d'explication."""

    def __init__(self, numero: int, titre: str, texte: str, parent: QWidget | None = None, *,
                 carre: bool = False) -> None:
        super().__init__(parent)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(8)
        self.numero = Numero(numero, rayon=10, carre=carre)
        self.numero.definir(1.0)
        ligne.addWidget(self.numero, 0, Qt.AlignmentFlag.AlignTop)
        textes = QVBoxLayout()
        textes.setContentsMargins(0, 5, 0, 0)
        textes.setSpacing(1)
        self.titre = etiquette(titre, "question")
        self.texte = _texte(texte, "noteCarte", interligne=20)
        textes.addWidget(self.titre)
        textes.addWidget(self.texte)
        ligne.addLayout(textes, 1)


class LigneReglage(QWidget):
    """Un réglage à deux positions : un titre, une explication, un interrupteur."""

    def __init__(self, titre: str, texte: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(16)
        textes = QVBoxLayout()
        textes.setSpacing(1)
        self.titre = etiquette(titre, "question")
        self.texte = _texte(texte, "noteCarte", interligne=20)
        textes.addWidget(self.titre)
        textes.addWidget(self.texte)
        ligne.addLayout(textes, 1)
        self.interrupteur = Interrupteur()
        self.interrupteur.setAccessibleName(titre)
        ligne.addWidget(self.interrupteur, 0, Qt.AlignmentFlag.AlignVCenter)


class PageInformation(QWidget):
    """Écran fait de cartes, dans une colonne qui défile, alignée à gauche sous le titre de l'écran."""

    #: Titre et sous-titre de l'écran, affichés par la fenêtre au-dessus de la page.
    TITRE = ""
    SOUS_TITRE = ""
    LARGEUR_MAXIMALE = 980

    #: Message passager à afficher dans la barre d'état.
    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cartes: list[Carte] = []
        contenu = QWidget()
        rangee = QHBoxLayout(contenu)
        rangee.setContentsMargins(theme.MARGE, 0, theme.MARGE, 20)
        rangee.setSpacing(0)
        colonne = QWidget()
        colonne.setMaximumWidth(self.LARGEUR_MAXIMALE)
        self.colonne = QVBoxLayout(colonne)
        self.colonne.setContentsMargins(0, 0, 0, 0)
        self.colonne.setSpacing(16)
        rangee.addWidget(colonne, 1000)
        rangee.addStretch(1)
        self.defilement = ZoneDefilante()
        self.setFocusProxy(self.defilement)
        self.defilement.definir_contenu(contenu)
        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        page.addWidget(self.defilement)

    def ajouter_carte(self, titre: str) -> Carte:
        carte = Carte(titre)
        self.cartes.append(carte)
        self.colonne.addWidget(carte)
        return carte

    def terminer(self) -> None:
        """À appeler après la dernière carte : les cartes restent en haut de la page."""
        self.colonne.addStretch(1)


# ====================================================================== paramètres
class PageParametres(PageInformation):
    """Réglages : le glossaire utilisé, l'affichage, l'adresse du service informatique."""

    TITRE = "Paramètres"
    SOUS_TITRE = "Glossaire, affichage, service informatique"

    #: Demandes transmises à la fenêtre.
    glossaire_a_choisir = Signal()
    glossaire_a_recharger = Signal()
    glossaire_fourni_demande = Signal()
    #: Le réglage « Étapes animées » a changé.
    animations_changees = Signal(bool)
    #: L'adresse du service informatique a été enregistrée.
    adresse_changee = Signal(str)

    def __init__(self, reglages: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reglages = reglages

        # ---------------------------------------------------------- glossaire
        carte = self.carte_glossaire = self.ajouter_carte("Glossaire")
        carte.ajouter_texte("Le glossaire est chargé automatiquement à l’ouverture de l’application. "
                            "Il fournit les termes, les définitions, les équivalents, les exemples et les références.")
        cadre = QFrame()
        cadre.setObjectName("cadreGlossaire")
        dans_le_cadre = QHBoxLayout(cadre)
        dans_le_cadre.setContentsMargins(16, 12, 16, 12)
        dans_le_cadre.setSpacing(12)
        self.point = QFrame()
        self.point.setObjectName("pointGlossaire")
        self.point.setFixedSize(8, 8)
        dans_le_cadre.addWidget(self.point, 0, Qt.AlignmentFlag.AlignVCenter)
        textes = QVBoxLayout()
        textes.setSpacing(2)
        self.nom_du_glossaire = EtiquetteCourte("", "nomGlossaire")
        self.dossier_du_glossaire = EtiquetteCourte("", "noteCarte", par_le_debut=True)
        textes.addWidget(self.nom_du_glossaire)
        textes.addWidget(self.dossier_du_glossaire)
        dans_le_cadre.addLayout(textes, 1)
        self.taille_du_glossaire = etiquette("", "tailleGlossaire")
        dans_le_cadre.addWidget(self.taille_du_glossaire, 0, Qt.AlignmentFlag.AlignVCenter)
        carte.ajouter(cadre, 14)
        self.bouton_choisir = _bouton("Choisir un autre fichier…", "contour", "dossier",
                                      "Ouvrir un autre glossaire : fichier CSV (Ctrl+O)")
        self.bouton_recharger = _bouton("Recharger", "contour", "recharger",
                                        "Relire le fichier après l’avoir modifié (F5)")
        self.bouton_fourni = _bouton("Revenir au glossaire fourni", "contour",
                                     info="Reprendre le glossaire livré avec l’application")
        self.bouton_choisir.clicked.connect(self.glossaire_a_choisir)
        self.bouton_recharger.clicked.connect(self.glossaire_a_recharger)
        self.bouton_fourni.clicked.connect(self.glossaire_fourni_demande)
        carte.ajouter_ligne([self.bouton_choisir, self.bouton_recharger, self.bouton_fourni])
        carte.ajouter_texte("Le format du fichier est décrit dans le centre d’aide.", "noteCarte", 12)

        # ---------------------------------------------------------- affichage
        carte = self.carte_affichage = self.ajouter_carte("Affichage")
        self.reglage_animations = LigneReglage(
            "Étapes animées",
            "Les étapes s’allument l’une après l’autre quand un résultat s’affiche.")
        self.reglage_demarrage = LigneReglage(
            "Écran de démarrage",
            "Le logo animé s’affiche pendant l’ouverture de l’application.")
        self.interrupteur_animations = self.reglage_animations.interrupteur
        self.interrupteur_demarrage = self.reglage_demarrage.interrupteur
        self.interrupteur_animations.setChecked(self.reglages.value(CLE_ANIMATIONS, True, bool))
        self.interrupteur_demarrage.setChecked(self.reglages.value(CLE_ECRAN_DE_DEMARRAGE, True, bool))
        self.interrupteur_animations.toggled.connect(self._animations_basculees)
        self.interrupteur_demarrage.toggled.connect(
            lambda actif: self.reglages.setValue(CLE_ECRAN_DE_DEMARRAGE, actif))
        carte.ajouter(self.reglage_animations, 14)
        carte.ajouter(separateur(), 14)
        carte.ajouter(self.reglage_demarrage, 14)

        # ---------------------------------------------------------- service informatique
        carte = self.carte_service = self.ajouter_carte("Service informatique")
        carte.ajouter_texte("Adresse électronique du service informatique. Le centre d’aide l’utilise pour "
                            "préparer un message.")
        self.champ_adresse = QLineEdit(self.reglages.value(CLE_ADRESSE, "", str))
        self.champ_adresse.setObjectName("champAdresse")
        self.champ_adresse.setPlaceholderText("nom@domaine.dz")
        self.champ_adresse.setFixedSize(340, 36)
        self.champ_adresse.setAccessibleName("Adresse du service informatique")
        self.champ_adresse.returnPressed.connect(self.enregistrer_l_adresse)
        self.bouton_enregistrer = _bouton("Enregistrer", "principal")
        self.bouton_enregistrer.clicked.connect(self.enregistrer_l_adresse)
        carte.ajouter_ligne([self.champ_adresse, self.bouton_enregistrer], 14)
        self.retour_adresse = etiquette("", "noteCarte")
        carte.ajouter(self.retour_adresse, 8)
        self.retour_adresse.hide()
        self.terminer()
        self.afficher_glossaire(None, False)

    # ------------------------------------------------------------------ glossaire
    def afficher_glossaire(self, glossaire: Glossaire | None, fourni: bool) -> None:
        """Affiche le glossaire chargé. ``fourni`` : vrai si c'est le glossaire livré avec l'application."""
        absent = glossaire is None
        if self.point.property("absent") != absent:
            self.point.setProperty("absent", absent)
            repeindre(self.point)
        if absent:
            self.nom_du_glossaire.definir_texte("Aucun glossaire chargé")
            self.dossier_du_glossaire.definir_texte("Choisissez un fichier CSV pour chercher un terme "
                                                    "ou traduire un texte.")
            self.taille_du_glossaire.setText("")
        else:
            self.nom_du_glossaire.definir_texte(glossaire.nom)
            self.dossier_du_glossaire.definir_texte(
                "Glossaire fourni avec l’application" if fourni
                else str(glossaire.chemin.parent) if glossaire.chemin else "")
            self.taille_du_glossaire.setText(compte(len(glossaire), "entrée"))
        self.bouton_recharger.setEnabled(not absent and glossaire.chemin is not None)
        self.bouton_fourni.setEnabled(absent or not fourni)

    # ------------------------------------------------------------------ réglages
    def _animations_basculees(self, actives: bool) -> None:
        self.reglages.setValue(CLE_ANIMATIONS, actives)
        self.animations_changees.emit(actives)

    def adresse(self) -> str:
        """L'adresse enregistrée du service informatique (vide si elle n'est pas renseignée)."""
        return self.reglages.value(CLE_ADRESSE, "", str)

    def montrer_l_adresse(self) -> None:
        """Fait défiler la page jusqu'au champ de l'adresse et y place le curseur."""
        self.defilement.ensureWidgetVisible(self.carte_service)
        self.champ_adresse.setFocus()
        self.champ_adresse.selectAll()

    def enregistrer_l_adresse(self) -> bool:
        """Enregistre l'adresse saisie, si elle a la forme d'une adresse électronique (ou si elle est vide)."""
        adresse = self.champ_adresse.text().strip()
        if adresse and not adresse_valide(adresse):
            self._retour("Cette adresse n’est pas complète : il faut un nom, le signe @ et un domaine.", True)
            return False
        self.champ_adresse.setText(adresse)
        self.reglages.setValue(CLE_ADRESSE, adresse)
        self._retour("Adresse enregistrée." if adresse else "Adresse effacée.", False)
        self.adresse_changee.emit(adresse)
        return True

    def _retour(self, texte: str, erreur: bool) -> None:
        self.retour_adresse.setText(texte)
        if self.retour_adresse.property("erreur") != erreur:
            self.retour_adresse.setProperty("erreur", erreur)
            repeindre(self.retour_adresse)
        self.retour_adresse.show()


# ====================================================================== description
class PageDescription(PageInformation):
    """Présentation de l'application : ce qu'elle fait, comment, et ce qu'il faut savoir."""

    TITRE = "Description de la plateforme"
    SOUS_TITRE = "Ce que fait l’application, et comment"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        carte = self.carte_presentation = self.ajouter_carte(NOM_APPLICATION)
        entete = QHBoxLayout()
        entete.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(icones.logo(48))
        logo.setFixedSize(48, 48)
        entete.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        textes = QVBoxLayout()
        textes.setSpacing(6)
        textes.addWidget(_texte("Aide à la traduction juridique entre le français et l’arabe, à partir d’un "
                                "glossaire."))
        textes.addWidget(_texte("L’application ne remplace pas le traducteur. Pour chaque terme, elle réunit ce "
                                "qu’il lui faut pour choisir un équivalent et le justifier.", "noteCarte",
                                interligne=20))
        entete.addLayout(textes, 1)
        carte.disposition.addSpacing(12)
        carte.disposition.addLayout(entete)

        carte = self.carte_enchainement = self.ajouter_carte("L’enchaînement en cinq étapes")
        carte.ajouter_texte("Chaque terme est présenté dans le même ordre. Une étape s’allume quand le "
                            "glossaire la renseigne.")
        self.etapes = [carte.ajouter(LigneNumerotee(rang, titre, texte), 12 if rang == 1 else 8)
                       for rang, (titre, texte) in enumerate(CHAMPS, start=1)]

        carte = self.carte_ecrans = self.ajouter_carte("Deux écrans de travail")
        carte.ajouter(self._ecran("loupe", "Terme",
                                  "Chercher un terme, en français ou en arabe. Sa fiche affiche les cinq étapes ; "
                                  "les expressions qui contiennent le terme sont listées sous la fiche."), 12)
        carte.ajouter(self._ecran("document", "Texte",
                                  "Écrire, coller ou importer un texte, puis le traduire. La traduction s’affiche "
                                  "sous le texte ; à droite, chaque terme juridique du texte a ses informations."), 12)

        carte = self.carte_traduction = self.ajouter_carte("Comment un texte est traduit")
        carte.ajouter_texte("La traduction utilise le glossaire, et lui seul : ni dictionnaire général, ni service "
                            "en ligne.")
        self.traitement = [carte.ajouter(LigneNumerotee(rang, titre, texte, carre=True), 12 if rang == 1 else 8)
                           for rang, (titre, texte) in enumerate(TRAITEMENT, start=1)]

        carte = self.carte_a_savoir = self.ajouter_carte("À savoir")
        for rang, texte in enumerate((
                "Les termes du glossaire sont traduits. Les autres mots restent dans la langue d’origine, en gris : "
                "ils sont à traduire à la main.",
                "Un mot courant qui s’écrit comme un terme juridique est traduit comme ce terme. Chaque terme "
                "traduit est donc à relire.",
                "Les définitions marquées « À vérifier » ne citent pas de source. Les équivalents proposés "
                "viennent du glossaire : l’application ne les vérifie pas.")):
            carte.ajouter(self._puce(texte), 12 if rang == 0 else 8)

        self.note = etiquette("", "noteCarte")
        self.note.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.colonne.addWidget(self.note)
        self.terminer()
        self.definir_glossaire(None)

    @staticmethod
    def _ecran(nom_icone: str, titre: str, texte: str) -> QWidget:
        element = QWidget()
        ligne = QHBoxLayout(element)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(12)
        ligne.addWidget(rond("rondEcran", 36, nom_icone, theme.BLEU, 18), 0, Qt.AlignmentFlag.AlignTop)
        textes = QVBoxLayout()
        textes.setContentsMargins(0, 1, 0, 0)
        textes.setSpacing(1)
        textes.addWidget(etiquette(titre, "question"))
        textes.addWidget(_texte(texte, "noteCarte", interligne=20))
        ligne.addLayout(textes, 1)
        return element

    @staticmethod
    def _puce(texte: str) -> QWidget:
        element = QWidget()
        ligne = QHBoxLayout(element)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(10)
        point = QFrame()
        point.setObjectName("pointListe")
        point.setFixedSize(6, 6)
        cadre = QVBoxLayout()
        cadre.setContentsMargins(0, 8, 0, 0)
        cadre.addWidget(point)
        cadre.addStretch(1)
        ligne.addLayout(cadre)
        ligne.addWidget(_texte(texte), 1)
        return element

    def definir_glossaire(self, glossaire: Glossaire | None) -> None:
        """Rappelle, au bas de la page, la version de l'application et la taille du glossaire chargé."""
        elements = [f"{NOM_APPLICATION} · version {__version__}"]
        if glossaire is not None:
            elements.append(f"glossaire de {compte(len(glossaire), 'entrée')}")
        self.note.setText(" · ".join(elements))


# ====================================================================== centre d'aide
class PageAide(PageInformation):
    """Centre d'aide : contact du service informatique, questions fréquentes, raccourcis."""

    TITRE = "Centre d’aide"
    SOUS_TITRE = "Contacter le service informatique, questions fréquentes"

    #: L'utilisateur veut indiquer l'adresse du service informatique (écran « Paramètres »).
    parametres_demandes = Signal()

    def __init__(self, reglages: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reglages = reglages
        self.glossaire: Glossaire | None = None

        # ---------------------------------------------------------- contact
        carte = self.carte_contact = self.ajouter_carte("Contacter le service informatique")
        entete = QHBoxLayout()
        entete.setSpacing(16)
        entete.addWidget(rond("rondContact", 44, "enveloppe", theme.BLEU, 22), 0, Qt.AlignmentFlag.AlignTop)
        textes = QVBoxLayout()
        textes.setSpacing(4)
        textes.addWidget(_texte("Un problème d’installation, d’ouverture de fichier ou d’affichage ? "
                                "Écrivez au service informatique."))
        self.etat_adresse = etiquette("", "noteCarte", retour_ligne=True)
        textes.addWidget(self.etat_adresse)
        entete.addLayout(textes, 1)
        carte.disposition.addSpacing(12)
        carte.disposition.addLayout(entete)
        self.bouton_ecrire = _bouton("Écrire au service informatique", "principal", "enveloppe",
                                     "Préparer un message dans votre logiciel de messagerie")
        self.bouton_copier = _bouton("Copier l’adresse", "contour", "copier")
        self.bouton_parametres = _bouton("Indiquer l’adresse dans Paramètres", "principal", "reglages")
        self.bouton_ecrire.clicked.connect(self.ecrire)
        self.bouton_copier.clicked.connect(self.copier_l_adresse)
        self.bouton_parametres.clicked.connect(self.parametres_demandes)
        carte.ajouter_ligne([self.bouton_ecrire, self.bouton_copier, self.bouton_parametres])
        self.note_message = carte.ajouter_texte(
            "Le message est préparé avec la version de l’application et le système utilisé : "
            "il ne reste qu’à décrire le problème.", "noteCarte", 12)

        # ---------------------------------------------------------- questions fréquentes
        carte = self.carte_questions = self.ajouter_carte("Questions fréquentes")
        self.questions: list[QLabel] = []
        for rang, (question, reponse) in enumerate(QUESTIONS):
            if rang:
                carte.ajouter(separateur(), 14)
            self.questions.append(carte.ajouter(etiquette(question, "question", retour_ligne=True), 14))
            for paragraphe_de_reponse in reponse:
                carte.ajouter_texte(paragraphe_de_reponse, "noteCarte", 4)

        # ---------------------------------------------------------- raccourcis
        carte = self.carte_raccourcis = self.ajouter_carte("Raccourcis du clavier")
        grille = QVBoxLayout()
        grille.setSpacing(8)
        for touches, action in RACCOURCIS:
            ligne = QHBoxLayout()
            ligne.setSpacing(10)
            # Les touches sont écrites comme sur le clavier du système (« ⌘F » sur un Mac).
            touche = etiquette(QKeySequence(touches).toString(QKeySequence.SequenceFormat.NativeText), "touche")
            touche.setFixedHeight(22)
            touche.setMinimumWidth(96)
            touche.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ligne.addWidget(touche)
            ligne.addWidget(etiquette(action, "noteCarte"), 1)
            grille.addLayout(ligne)
        carte.disposition.addSpacing(14)
        carte.disposition.addLayout(grille)
        self.terminer()
        self.definir_adresse(self.reglages.value(CLE_ADRESSE, "", str))

    # ------------------------------------------------------------------ état
    def definir_glossaire(self, glossaire: Glossaire | None) -> None:
        """Le glossaire chargé est cité dans le message préparé pour le service informatique."""
        self.glossaire = glossaire

    def definir_adresse(self, adresse: str) -> None:
        """Adresse du service informatique ; sans adresse, la carte invite à la renseigner."""
        self.adresse = adresse.strip()
        connue = bool(self.adresse)
        self.etat_adresse.setText(f"Adresse : {self.adresse}" if connue
                                  else "L’adresse du service informatique n’est pas encore indiquée.")
        self.bouton_ecrire.setVisible(connue)
        self.bouton_copier.setVisible(connue)
        self.note_message.setVisible(connue)
        self.bouton_parametres.setVisible(not connue)

    # ------------------------------------------------------------------ message
    def informations_techniques(self) -> list[str]:
        """Ce que le service informatique a besoin de savoir : version, système, glossaire."""
        import PySide6  # la version de la bibliothèque graphique fait partie du diagnostic

        lignes = [f"Application : {NOM_APPLICATION} {__version__}",
                  f"Système : {platform.system()} {platform.release()} · Python {platform.python_version()} · "
                  f"PySide6 {PySide6.__version__}"]
        if self.glossaire is not None:
            lignes.append(f"Glossaire : {self.glossaire.nom}, {compte(len(self.glossaire), 'entrée')}")
        else:
            lignes.append("Glossaire : aucun glossaire chargé")
        return lignes

    def lien_du_message(self) -> str:
        """Adresse « mailto: » du message préparé : destinataire, objet, informations techniques."""
        objet = f"{NOM_APPLICATION} : demande d’aide"
        corps = "\n".join(["Bonjour,", "", "(Décrivez ici le problème rencontré.)", "", "--",
                           *self.informations_techniques()])
        return f"mailto:{self.adresse}?subject={quote(objet)}&body={quote(corps)}"

    def ecrire(self) -> bool:
        """Ouvre le logiciel de messagerie sur un message adressé au service informatique."""
        if not self.adresse:
            self.parametres_demandes.emit()
            return False
        if ouvrir_lien(self.lien_du_message()):
            self.message.emit("Message préparé dans votre logiciel de messagerie.")
            return True
        self.copier_l_adresse()
        self.message.emit(f"Aucun logiciel de messagerie n’a répondu : l’adresse {self.adresse} a été copiée.")
        return False

    def copier_l_adresse(self) -> None:
        if self.adresse:
            QGuiApplication.clipboard().setText(self.adresse)
            self.message.emit(f"Adresse copiée : {self.adresse}")


__all__ = ["CHAMPS", "CLE_ADRESSE", "CLE_ANIMATIONS", "CLE_ECRAN_DE_DEMARRAGE", "QUESTIONS", "RACCOURCIS",
           "TRAITEMENT", "Carte", "PageAide", "PageDescription", "PageInformation", "PageParametres",
           "adresse_valide", "ouvrir_lien"]
