"""Réglages de l'intelligence artificielle : la partie « Intelligence artificielle » de l'écran « Paramètres ».

L'IA est facultative, et éteinte au départ. Éteinte, cette partie ne se connecte à rien. Allumée,
elle ne se connecte que sur un clic : le bouton « Tester la connexion ». Pour l'instant, c'est le
seul usage de l'IA dans l'application : la traduction se fait toujours avec le glossaire, et avec
lui seul.

Les réglages sont rangés avec ceux de l'application, sur l'ordinateur. La clé d'accès n'y est pas
chiffrée. Elle n'est écrite nulle part ailleurs : ni dans le message préparé pour le service
informatique, ni dans un fichier exporté.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from html import escape

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..ia import essai, service
from ..langues import FR
from . import boites
from .composants import etiquette, paragraphe, repeindre, separateur
from .pages import Carte, LigneReglage, _bouton

#: Clés des réglages enregistrés.
CLE_ACTIVE = "ia/active"
CLE_ADRESSE_DU_SERVICE = "ia/adresse"
CLE_CLE = "ia/cle"
CLE_MODELE = "ia/modele"
#: L'avertissement du premier allumage a été lu et accepté.
CLE_AVERTISSEMENT = "ia/avertissement_lu"

#: Modèle proposé tant que l'utilisateur n'en a pas saisi un autre.
MODELE_PAR_DEFAUT = "google/gemma-4-31b-it"

PRESENTATION = ("Facultatif. L’application peut se relier à un service d’intelligence artificielle en ligne, par "
                "exemple NVIDIA Build. Pour l’instant, ces réglages servent à préparer et à essayer la connexion : "
                "la traduction se fait toujours avec le glossaire, et avec lui seul.")
#: Ce que dit la ligne « Utiliser l'IA », selon la position de l'interrupteur.
IA_ETEINTE = "Éteinte : l’application ne se connecte à aucun service."
IA_ALLUMEE = "Allumée : l’application ne se connecte que lorsque vous cliquez sur « Tester la connexion »."
NOTE_SUR_LA_CLE = ("La clé est enregistrée sur cet ordinateur, sans chiffrement : une personne qui ouvre votre "
                   "session peut la lire. Elle n’est envoyée qu’au service indiqué ci-dessus.")
TITRE_DE_L_AVERTISSEMENT = "Avant d’allumer l’IA"
AVERTISSEMENT = (
    "L’IA est un service en ligne. Quand vous cliquez sur un bouton qui s’en sert, l’application envoie une "
    "demande à l’adresse indiquée dans « Paramètres ».\n\n"
    "• N’envoyez jamais de texte confidentiel ni de données personnelles : le service peut enregistrer ce "
    "qu’il reçoit.\n"
    "• Rien n’est envoyé sans un clic de votre part.\n"
    "• Ce qu’écrit une IA est toujours à vérifier.\n\n"
    "Pour l’instant, seul le bouton « Tester la connexion » se sert de l’IA. Il n’envoie aucun de vos textes.")

#: États d'une ligne du résultat de l'essai.
ATTENTE, REUSSI, ECHEC = "attente", "reussi", "echec"
#: Le mot qui précède la clé dans un exemple de code : « Bearer nvapi-… ».
_BEARER = re.compile(r"\Abearer(?:\s+|\Z)", re.IGNORECASE)


# ====================================================================== réglages
@dataclass(frozen=True)
class ReglagesIA:
    """Les réglages de l'IA, tels qu'ils sont enregistrés."""

    active: bool
    adresse: str
    cle: str
    modele: str


def lire(reglages: QSettings) -> ReglagesIA:
    """Lit les réglages de l'IA. Sans réglage enregistré : IA éteinte, adresse de NVIDIA, modèle proposé, pas de clé."""
    return ReglagesIA(
        active=reglages.value(CLE_ACTIVE, False, bool),
        adresse=reglages.value(CLE_ADRESSE_DU_SERVICE, "", str).strip() or service.ADRESSE_PAR_DEFAUT,
        cle=reglages.value(CLE_CLE, "", str).strip(),
        modele=reglages.value(CLE_MODELE, "", str).strip() or MODELE_PAR_DEFAUT)


def nettoyer_la_cle(texte: str) -> str:
    """La clé telle qu'elle doit être envoyée.

    Une clé copiée d'un exemple de code arrive parfois entre guillemets, ou précédée du mot
    « Bearer » : ils sont retirés, avec les espaces autour.
    """
    cle = texte
    for _ in range(2):  # des guillemets, le mot « Bearer », puis parfois des guillemets encore
        cle = cle.strip().strip("\"'«»“”").strip()
        cle = _BEARER.sub("", cle)
    return cle.strip()


def _ranger(reglages: QSettings, nom: str, valeur: str, valeur_de_depart: str) -> None:
    """Enregistre un réglage. La valeur de départ n'est pas enregistrée : le réglage est simplement retiré."""
    if valeur == valeur_de_depart:
        reglages.remove(nom)
    else:
        reglages.setValue(nom, valeur)


# ====================================================================== avertissement du premier allumage
class BoiteAllumage(boites.BoiteMessage):
    """L'avertissement affiché la première fois que l'IA est allumée : « Allumer l'IA » ou « Annuler »."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, boites.ALERTE, TITRE_DE_L_AVERTISSEMENT, AVERTISSEMENT)
        self.bouton.setText("Allumer l’IA")
        self.bouton.setFixedSize(132, 34)
        self.bouton_annuler = QPushButton("Annuler")
        self.bouton_annuler.setProperty("classe", "contour")
        self.bouton_annuler.setFixedSize(96, 34)
        self.bouton_annuler.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_annuler.clicked.connect(self.reject)
        pied = self.bouton.parentWidget().layout()
        pied.setSpacing(10)
        pied.insertWidget(pied.indexOf(self.bouton), self.bouton_annuler)
        # La touche Entrée ne doit pas allumer l'IA par mégarde : le bouton par défaut est « Annuler ».
        self.bouton.setDefault(False)
        self.bouton.setAutoDefault(False)
        self.bouton_annuler.setDefault(True)
        self.bouton_annuler.setFocus()


def confirmer_l_allumage(parent: QWidget | None) -> bool:
    """Affiche l'avertissement du premier allumage. Vrai si l'utilisateur choisit « Allumer l'IA »."""
    return BoiteAllumage(parent).exec() == QDialog.DialogCode.Accepted


# ====================================================================== éléments de la carte
def _insecable(texte: str) -> str:
    """Le texte, où un guillemet n'est jamais séparé de ce qu'il entoure par un retour à la ligne."""
    return texte.replace("« ", "«\u00a0").replace(" »", "\u00a0»")


def _champ(texte: str, exemple: str, nom: str, info: str) -> QLineEdit:
    champ = QLineEdit(texte)
    champ.setProperty("classe", "champReglage")
    champ.setPlaceholderText(exemple)
    champ.setFixedHeight(36)
    champ.setMinimumWidth(160)
    champ.setMaximumWidth(440)
    champ.setAccessibleName(nom)
    champ.setToolTip(info)
    return champ


class LigneChamp(QWidget):
    """Un réglage à saisir : son nom, son champ, et parfois un bouton à droite du champ."""

    LARGEUR_DU_NOM = 150

    def __init__(self, nom: str, champ: QLineEdit, bouton: QPushButton | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(10)
        self.nom = etiquette(nom, "nomReglage")
        self.nom.setFixedWidth(self.LARGEUR_DU_NOM)
        self.champ = champ
        ligne.addWidget(self.nom)
        # Le champ prend la place libre, jusqu'à sa largeur maximale ; le reste de la ligne est vide.
        ligne.addWidget(champ, 100)
        if bouton is not None:
            ligne.addWidget(bouton)
        ligne.addStretch(1)


class LigneConstat(QWidget):
    """Une ligne du résultat de l'essai : un point de couleur, puis une phrase."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(10)
        self.etat = ATTENTE
        self.point = QFrame()
        self.point.setObjectName("pointEssai")
        self.point.setProperty("etat", ATTENTE)
        self.point.setFixedSize(8, 8)
        sous_le_point = QVBoxLayout()
        sous_le_point.setContentsMargins(0, 6, 0, 0)  # le point est à la hauteur de la première ligne du texte
        sous_le_point.addWidget(self.point)
        sous_le_point.addStretch(1)
        ligne.addLayout(sous_le_point)
        #: La phrase affichée, telle qu'elle a été donnée.
        self.phrase = ""
        self.texte = etiquette("", "resultatEssai", retour_ligne=True, selectionnable=True, riche=True)
        ligne.addWidget(self.texte, 1)

    def definir(self, etat: str, phrase: str) -> None:
        self.etat = etat
        self.phrase = phrase
        if self.point.property("etat") != etat:
            self.point.setProperty("etat", etat)
            repeindre(self.point)
        # La phrase peut citer la réponse du service : « < » et « & » y sont affichés tels quels.
        self.texte.setText(paragraphe(escape(_insecable(phrase)), FR, 19))


# ====================================================================== essai de la connexion
class _Essai(QObject):
    """Un essai de connexion, mené dans un fil d'exécution à part : la fenêtre continue de répondre.

    Les signaux sont émis depuis ce fil ; Qt les remet à la fenêtre dans son propre fil. Le fil ne
    retient pas l'application : si elle est fermée pendant l'essai, il est abandonné.
    """

    #: Un temps de l'essai a donné son constat : (cet essai, le constat).
    constate = Signal(object, object)
    #: L'essai est fini : (cet essai).
    termine = Signal(object)

    def __init__(self, reglages: ReglagesIA, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.reglages = reglages
        self._arret = threading.Event()
        self._fil = threading.Thread(target=self._mener, name="essai-de-l-ia", daemon=True)

    def demarrer(self) -> None:
        self._fil.start()

    def arreter(self) -> None:
        """Demande l'arrêt : il est pris en compte avant le prochain envoi."""
        self._arret.set()

    def _mener(self) -> None:
        temps = essai.SERVICE
        try:
            for constat in essai.essayer(self.reglages.adresse, self.reglages.cle, self.reglages.modele,
                                         arret=self._arret.is_set):
                self._emettre(self.constate, self, constat)
                temps = essai.MODELE
        except Exception as erreur:  # une erreur du programme : elle est montrée, et l'essai se termine
            self._emettre(self.constate, self, essai.Constat(
                temps, False, f"L’essai s’est arrêté sur une erreur inattendue : {erreur!r}"))
        finally:
            self._emettre(self.termine, self)

    def _emettre(self, signal, *arguments) -> None:
        try:
            signal.emit(*arguments)
        except RuntimeError:
            # La fenêtre a été fermée pendant l'essai : personne n'attend plus le résultat, et rien d'autre ne part.
            self._arret.set()


# ====================================================================== la partie « Intelligence artificielle »
class PartieIA(QObject):
    """Remplit la carte « Intelligence artificielle » de l'écran « Paramètres » et tient ses réglages."""

    #: Message passager à afficher dans la barre d'état.
    message = Signal(str)
    #: L'IA vient d'être allumée (vrai) ou éteinte (faux).
    basculee = Signal(bool)
    #: Un essai de connexion vient de finir : vrai si les deux temps ont réussi.
    essai_fini = Signal(bool)

    def __init__(self, carte: Carte, reglages: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.carte = carte
        self.reglages = reglages
        self._essai: _Essai | None = None
        #: Constats du dernier essai, dans l'ordre : un ou deux.
        self.constats: list[essai.Constat] = []
        actuels = lire(reglages)

        carte.ajouter_texte(PRESENTATION)
        self.reglage = LigneReglage("Utiliser l’IA", IA_ETEINTE)
        self.interrupteur = self.reglage.interrupteur
        self.interrupteur.setChecked(actuels.active)
        self.interrupteur.toggled.connect(self._basculer)
        carte.ajouter(self.reglage, 18)
        carte.ajouter(separateur(), 14)

        # ---------------------------------------------------------- adresse, clé, modèle
        self.champ_adresse = _champ(actuels.adresse, service.ADRESSE_PAR_DEFAUT, "Adresse du service d’IA",
                                    "Adresse du service d’IA. Celle de NVIDIA Build est déjà saisie.")
        self.champ_cle = _champ(actuels.cle, "nvapi-…", "Clé d’accès au service d’IA",
                                "La clé créée sur le site du service. Chez NVIDIA, elle commence par « nvapi- ».")
        self.champ_cle.setEchoMode(QLineEdit.EchoMode.Password)
        self.champ_cle.setInputMethodHints(Qt.InputMethodHint.ImhSensitiveData | Qt.InputMethodHint.ImhNoPredictiveText
                                           | Qt.InputMethodHint.ImhNoAutoUppercase)
        self.champ_modele = _champ(actuels.modele, MODELE_PAR_DEFAUT, "Modèle d’IA",
                                   "Nom du modèle, tel que le service l’écrit. Exemple : " + MODELE_PAR_DEFAUT)
        self.bouton_afficher = _bouton("Afficher", "contour", info="Afficher ou masquer la clé à l’écran")
        self.bouton_afficher.setCheckable(True)
        self.bouton_afficher.toggled.connect(self._afficher_la_cle)
        self.ligne_adresse = carte.ajouter(LigneChamp("Adresse du service", self.champ_adresse), 14)
        self.ligne_cle = carte.ajouter(LigneChamp("Clé d’accès", self.champ_cle, self.bouton_afficher), 10)
        self.ligne_modele = carte.ajouter(LigneChamp("Modèle", self.champ_modele), 10)
        for champ in (self.champ_adresse, self.champ_cle, self.champ_modele):
            champ.textChanged.connect(self._ranger_la_saisie)
            champ.editingFinished.connect(self.enregistrer)
        self.champ_cle.textChanged.connect(self._actualiser)

        # ---------------------------------------------------------- essai de la connexion
        self.bouton_tester = _bouton("Tester la connexion", "principal",
                                     info="Demander au service la liste de ses modèles, puis un mot au modèle")
        self.bouton_effacer = _bouton("Effacer la clé", "contour", info="Retirer la clé des réglages de l’application")
        self.bouton_tester.clicked.connect(self.tester)
        self.bouton_effacer.clicked.connect(self.effacer_la_cle)
        carte.ajouter_ligne([self.bouton_tester, self.bouton_effacer], 16)
        self.cadre_essai = QFrame()
        self.cadre_essai.setObjectName("cadreEssai")
        dans_le_cadre = QVBoxLayout(self.cadre_essai)
        dans_le_cadre.setContentsMargins(16, 12, 16, 12)
        dans_le_cadre.setSpacing(8)
        self.constat_du_service = LigneConstat()
        self.constat_du_modele = LigneConstat()
        dans_le_cadre.addWidget(self.constat_du_service)
        dans_le_cadre.addWidget(self.constat_du_modele)
        carte.ajouter(self.cadre_essai, 12)
        self.cadre_essai.hide()
        self.note = carte.ajouter_texte(NOTE_SUR_LA_CLE, "noteCarte", 8)
        self._actualiser()

    # ------------------------------------------------------------------ état
    def active(self) -> bool:
        """Vrai si l'IA est allumée."""
        return self.interrupteur.isChecked()

    def essai_en_cours(self) -> bool:
        return self._essai is not None

    def _actualiser(self, *_) -> None:
        """Éteinte, la partie est grisée : rien ne s'y saisit et rien ne s'y essaie."""
        active = self.active()
        self.reglage.texte.setText(paragraphe(escape(IA_ALLUMEE if active else IA_ETEINTE), FR, 20))
        for ligne in (self.ligne_adresse, self.ligne_cle, self.ligne_modele):
            ligne.setEnabled(active)
        en_cours = self.essai_en_cours()
        self.bouton_tester.setEnabled(active and not en_cours)
        self.bouton_tester.setText("Essai en cours…" if en_cours else "Tester la connexion")
        self.bouton_effacer.setEnabled(active and bool(self.champ_cle.text().strip()))

    # ------------------------------------------------------------------ allumer, éteindre
    def _basculer(self, active: bool) -> None:
        if active and not self.reglages.value(CLE_AVERTISSEMENT, False, bool):
            if not confirmer_l_allumage(self.carte.window()):
                # Refus : l'interrupteur revient à sa place, sans rien enregistrer.
                self.interrupteur.blockSignals(True)
                self.interrupteur.setChecked(False)
                self.interrupteur.blockSignals(False)
                return
            self.reglages.setValue(CLE_AVERTISSEMENT, True)
        self.reglages.setValue(CLE_ACTIVE, active)
        if not active:
            self._abandonner_l_essai()
        self._actualiser()
        self.basculee.emit(active)
        self.message.emit("IA allumée." if active else "IA éteinte : l’application ne se connecte à aucun service.")

    # ------------------------------------------------------------------ réglages saisis
    def _saisie(self) -> tuple[str, str, str]:
        """L'adresse, la clé et le modèle saisis, tels qu'ils doivent être enregistrés.

        Une adresse ou un modèle effacé reprend sa valeur de départ : l'adresse de NVIDIA, le modèle proposé.
        """
        return (self.champ_adresse.text().strip() or service.ADRESSE_PAR_DEFAUT,
                nettoyer_la_cle(self.champ_cle.text()),
                self.champ_modele.text().strip() or MODELE_PAR_DEFAUT)

    def _ranger_la_saisie(self, *_) -> None:
        """Enregistre ce qui est saisi, à chaque changement, sans toucher aux champs.

        Rien n'est perdu si l'application est fermée avant que le champ soit quitté.
        """
        adresse, cle, modele = self._saisie()
        _ranger(self.reglages, CLE_ADRESSE_DU_SERVICE, adresse, service.ADRESSE_PAR_DEFAUT)
        _ranger(self.reglages, CLE_CLE, cle, "")
        _ranger(self.reglages, CLE_MODELE, modele, MODELE_PAR_DEFAUT)

    def enregistrer(self) -> None:
        """Enregistre l'adresse, la clé et le modèle saisis, et montre dans les champs ce qui est enregistré.

        Appelée quand un champ est quitté : c'est le moment où il peut être réécrit sans gêner la saisie.
        """
        for champ, valeur in zip((self.champ_adresse, self.champ_cle, self.champ_modele), self._saisie(),
                                 strict=True):
            if champ.text() != valeur:
                champ.setText(valeur)
        self._ranger_la_saisie()
        self._actualiser()

    def effacer_la_cle(self) -> None:
        """Retire la clé de l'écran et des réglages enregistrés."""
        self._abandonner_l_essai()
        self.champ_cle.clear()  # le changement du champ retire la clé des réglages
        self.reglages.remove(CLE_CLE)
        self._actualiser()
        self.message.emit("Clé effacée des réglages de l’application.")

    def _afficher_la_cle(self, visible: bool) -> None:
        self.champ_cle.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.bouton_afficher.setText("Masquer" if visible else "Afficher")

    # ------------------------------------------------------------------ essai de la connexion
    def tester(self) -> None:
        """Essaie la connexion avec les réglages saisis. Rien ne part si l'IA est éteinte."""
        if self.essai_en_cours() or not self.active():
            return
        self.enregistrer()
        self.constats = []
        self.constat_du_service.definir(ATTENTE, "1. Le service répond-il ? La liste de ses modèles est demandée…")
        self.constat_du_modele.definir(ATTENTE, "2. Le modèle répond-il ?")
        self.cadre_essai.show()
        self._essai = _Essai(lire(self.reglages), self)
        self._essai.constate.connect(self._constater)
        self._essai.termine.connect(self._terminer)
        self._actualiser()
        self._essai.demarrer()

    def _constater(self, auteur: _Essai, constat: essai.Constat) -> None:
        if auteur is not self._essai:  # un essai abandonné : son résultat n'intéresse plus personne
            return
        self.constats.append(constat)
        ligne = self.constat_du_service if constat.temps == essai.SERVICE else self.constat_du_modele
        ligne.definir(REUSSI if constat.reussi else ECHEC, f"{constat.temps}. {constat.message}")
        if constat.temps == essai.SERVICE:
            self.constat_du_modele.definir(
                ATTENTE, "2. Le modèle répond-il ? Un mot à traduire lui est envoyé…" if constat.reussi
                else "2. Le modèle n’a pas été essayé.")

    def _terminer(self, auteur: _Essai) -> None:
        if auteur is not self._essai:
            auteur.deleteLater()
            return
        self._essai = None
        auteur.deleteLater()
        self._actualiser()
        reussi = len(self.constats) == 2 and all(constat.reussi for constat in self.constats)
        self.message.emit("La connexion au service d’IA fonctionne." if reussi
                          else "La connexion au service d’IA n’a pas fonctionné.")
        self.essai_fini.emit(reussi)

    def _abandonner_l_essai(self) -> None:
        """Arrête l'essai en cours, s'il y en a un, et retire son résultat de l'écran."""
        if self._essai is not None:
            self._essai.arreter()
            self._essai = None
        self.constats = []
        self.cadre_essai.hide()
