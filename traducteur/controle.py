"""Contrôle de l'installation : l'application s'ouvre, s'essaie elle-même, écrit un rapport et se ferme.

Emploi :

    TraducteurJuridique.exe --controle=<dossier>      (application installée sous Windows)
    python main.py --controle=<dossier>               (depuis le dossier du projet)

Personne n'a besoin d'être devant l'écran. L'application démarre comme d'habitude (écran de
démarrage, fenêtre, glossaire fourni), puis elle cherche un terme, traduit le texte d'exemple,
enregistre la traduction dans un document Word, le relit et affiche chaque écran. Elle vérifie
aussi que l'IA est éteinte tant que personne ne l'a allumée. Elle écrit ce qu'elle a constaté dans
``<dossier>/rapport.json``, puis elle se ferme : code de sortie 0 si tout a fonctionné, 1 sinon.
Elle laisse aussi deux images dans le dossier : ``fenetre.png``, sa fenêtre, et ``demarrage.png``,
l'écran de l'ordinateur à l'endroit de l'écran de démarrage (on y voit si son fond est bien
transparent).

Ce contrôle sert à vérifier l'installeur pour Windows (voir ``outils/installeur``). Il ne lit pas
et ne modifie pas les réglages de l'utilisateur : il range les siens dans ``<dossier>``.

Le contrôle ne se connecte à rien. Avec ``--controle-connexion`` en plus, il essaie une connexion
chiffrée : il demande au service d'IA proposé par défaut la liste de ses modèles, sans clé et sans
envoyer aucun texte. Le résultat est noté dans le rapport ; un échec ne fait pas échouer le
contrôle, car l'ordinateur peut ne pas avoir d'accès à Internet.
"""

from __future__ import annotations

import json
import platform
import sys
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QSettings, Qt, QTimer, Signal, qVersion
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from . import NOM_APPLICATION, __version__

#: Début de l'argument qui demande le contrôle ; la suite est le dossier du rapport.
OPTION = "--controle="
#: Argument qui demande, en plus, l'essai d'une connexion chiffrée au service d'IA proposé par défaut.
OPTION_DE_CONNEXION = "--controle-connexion"
#: Temps laissé à ce service pour chaque échange (ouvrir la connexion, puis répondre), en secondes.
DELAI_DE_LA_CONNEXION = 15.0
#: Durée maximale de cet essai, en secondes. Quand le réseau ne répond pas, les adresses du service sont
#: essayées l'une après l'autre : sans cette limite, l'essai pourrait retenir le contrôle plus longtemps que
#: ``DELAI`` et le faire échouer.
DUREE_MAXIMALE_DE_LA_CONNEXION = 25.0
NOM_DU_RAPPORT = "rapport.json"
NOM_DE_L_IMAGE = "fenetre.png"
NOM_DE_L_IMAGE_DU_DEMARRAGE = "demarrage.png"
#: Moment où l'écran de démarrage est photographié, en millisecondes après son affichage.
MOMENT_DE_L_IMAGE_DU_DEMARRAGE = 700
#: Affichages de Qt qui n'ont pas d'écran : il n'y a rien à y photographier.
AFFICHAGES_SANS_ECRAN = ("offscreen", "minimal")
#: Durée maximale du contrôle, en millisecondes. Au-delà, il est déclaré en échec.
DELAI = 60_000
#: Intervalle entre deux coups d'œil à la fenêtre pendant l'écran de démarrage, en millisecondes.
PAS = 50


def dossier_demande(arguments: Sequence[str]) -> Path | None:
    """Le dossier donné avec ``--controle=<dossier>`` ; ``None`` si le contrôle n'est pas demandé."""
    for argument in arguments[1:]:
        if argument.startswith(OPTION) and len(argument) > len(OPTION):
            return Path(argument[len(OPTION):])
    return None


def connexion_demandee(arguments: Sequence[str]) -> bool:
    """Vrai si ``--controle-connexion`` fait partie des arguments."""
    return OPTION_DE_CONNEXION in arguments[1:]


class Controle(QObject):
    """Un contrôle en cours : ses réglages, ce qu'il a constaté, les erreurs rencontrées."""

    #: Le contrôle est fini et le rapport est écrit. L'argument est le code de sortie : 0 ou 1.
    termine = Signal(int)

    def __init__(self, application: QApplication, dossier: Path, connexion: bool = False) -> None:
        super().__init__()
        self.application = application
        self.dossier = Path(dossier)
        #: Vrai si le contrôle doit aussi essayer une connexion chiffrée au service d'IA proposé par défaut.
        self.connexion = connexion
        self.dossier.mkdir(parents=True, exist_ok=True)
        for nom in (NOM_DU_RAPPORT, NOM_DE_L_IMAGE, NOM_DE_L_IMAGE_DU_DEMARRAGE, "reglages.ini", "traduction.docx"):
            (self.dossier / nom).unlink(missing_ok=True)  # rien ne doit rester d'un contrôle précédent
        #: Réglages propres au contrôle : ceux de l'utilisateur ne sont ni lus ni modifiés.
        self.reglages = QSettings(str(self.dossier / "reglages.ini"), QSettings.Format.IniFormat)
        self.constats: dict[str, object] = {}
        self.erreurs: list[str] = []
        #: Boîtes de message que l'application aurait ouvertes : (titre, texte).
        self.messages: list[tuple[str, str]] = []
        self.fenetre = None
        self.ecran = None
        self.code: int | None = None
        self._debut = time.monotonic()
        self._afficher_d_origine: Callable | None = None
        self._attente = QTimer(self)
        self._attente.setInterval(PAS)
        self._attente.timeout.connect(self._regarder)
        self._limite = QTimer(self)
        self._limite.setSingleShot(True)
        self._limite.timeout.connect(self._delai_depasse)

    # ------------------------------------------------------------------ déroulement
    def demarrer(self) -> None:
        """Ouvre l'application comme le fait un lancement ordinaire, puis attend que la fenêtre s'affiche."""
        from .application import ouvrir
        from .interface import boites

        # Une boîte de message attendrait un clic sur « OK » : le contrôle la note et continue.
        self._afficher_d_origine = boites.afficher
        boites.afficher = self._noter_le_message
        self._limite.start(DELAI)
        try:
            self.fenetre, self.ecran = ouvrir(self.application, None, self.reglages)
        except Exception:
            self.erreurs.append("ouverture : " + traceback.format_exc())
            QTimer.singleShot(0, self.terminer)
            return
        self.constats["demarrage"] = {
            "ecran_de_demarrage": self.ecran is not None,
            "fond_transparent": bool(self.ecran is not None and self.ecran.testAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground)),
        }
        if self.ecran is None:
            self.erreurs.append("démarrage : l'écran de démarrage ne s'est pas affiché")
        else:
            QTimer.singleShot(MOMENT_DE_L_IMAGE_DU_DEMARRAGE, self._photographier_le_demarrage)
        self._attente.start()

    def _photographier_le_demarrage(self) -> None:
        """Garde l'image de l'écran de l'ordinateur, à l'endroit de l'écran de démarrage.

        Autour du logo, cette image montre ce qui se trouve derrière lui si son fond est transparent,
        du noir si le système ne sait pas le rendre transparent. Le rapport note la couleur de ses quatre
        coins et celle du carré du logo.
        """
        if self.code is not None or self.ecran is None or not self.ecran.isVisible():
            return
        if self.application.platformName() in AFFICHAGES_SANS_ECRAN:
            return
        cadre = self.ecran.geometry()
        origine = self.ecran.screen().geometry().topLeft()
        image = self.ecran.screen().grabWindow(
            0, cadre.x() - origine.x(), cadre.y() - origine.y(), cadre.width(), cadre.height()).toImage()
        fichier = self.dossier / NOM_DE_L_IMAGE_DU_DEMARRAGE
        if image.isNull() or not image.save(str(fichier), "PNG"):
            return

        def couleur(x: int, y: int) -> str:
            return image.pixelColor(x, y).name(QColor.NameFormat.HexArgb)

        droite, bas = image.width() - 1, image.height() - 1
        self.constats["demarrage"].update({
            "image": fichier.name,
            "coins": [couleur(0, 0), couleur(droite, 0), couleur(0, bas), couleur(droite, bas)],
            # Un point du carré du logo, à gauche de la balance.
            "logo": couleur(round(image.width() * (0.5 - 36 / cadre.width())), image.height() // 2),
        })

    def _noter_le_message(self, parent, genre, titre, texte, **options) -> None:
        self.messages.append((titre, texte))

    def _regarder(self) -> None:
        """La fenêtre est-elle affichée, et l'écran de démarrage parti ?"""
        if self.fenetre.isVisible() and (self.ecran is None or not self.ecran.isVisible()):
            self._attente.stop()
            self._essayer()
            self.terminer()

    def _delai_depasse(self) -> None:
        self.erreurs.append(f"délai : le contrôle n'était pas fini après {DELAI // 1000} secondes")
        self.terminer()

    def _etape(self, nom: str, action: Callable[[], object]) -> None:
        """Exécute une étape ; une erreur est notée, et les étapes suivantes sont tout de même essayées."""
        try:
            self.constats[nom] = action()
        except AssertionError as erreur:  # une vérification du contrôle : son message suffit
            self.erreurs.append(f"{nom} : {erreur}")
        except Exception:  # une erreur inattendue : on garde tout ce que Python en dit
            self.erreurs.append(f"{nom} : {traceback.format_exc()}")
        self.application.processEvents()

    def _essayer(self) -> None:
        self._etape("glossaire", self._glossaire)
        self._etape("recherche", self._recherche)
        self._etape("traduction", self._traduction)
        self._etape("document", self._document)
        self._etape("ecrans", self._ecrans)
        self._etape("ia", self._ia)
        self._etape("textes_de_qt", self._textes_de_qt)
        self._etape("image", self._image)

    # ------------------------------------------------------------------ étapes
    def _exiger(self, condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def _glossaire(self) -> dict:
        glossaire = self.fenetre.glossaire
        self._exiger(glossaire is not None, "aucun glossaire n'est chargé")
        constat = {"fichier": str(glossaire.chemin), "fourni": self.fenetre.glossaire_fourni(),
                   "entrees": len(glossaire)}
        self._exiger(constat["fourni"], f"le glossaire chargé n'est pas le glossaire fourni : {glossaire.chemin}")
        self._exiger(len(glossaire) > 0, "le glossaire fourni est vide")
        return constat

    def _recherche(self) -> dict:
        from .interface.navigation import MODE_TERME
        from .langues import FR

        glossaire = self.fenetre.glossaire
        self._exiger(glossaire is not None and len(glossaire) > 0, "sans glossaire, aucun terme ne peut être cherché")
        entree = glossaire.entrees[0]
        terme = entree.terme(FR)
        self.fenetre.definir_mode(MODE_TERME)
        page = self.fenetre.page
        if page.source != FR:
            page.definir_sens(FR)
        page.rechercher(terme)
        self.application.processEvents()
        self._exiger(entree in page.resultats, f"le terme « {terme} » n'a pas été trouvé")
        return {"terme": terme, "entrees_trouvees": len(page.resultats)}

    def _traduction(self) -> dict:
        from .interface.navigation import MODE_TEXTE

        self.fenetre.definir_mode(MODE_TEXTE)
        page = self.fenetre.page_texte
        page.inserer_un_exemple()
        page.traduire()
        self.application.processEvents()
        traduction = page.traduction
        self._exiger(traduction is not None, "le texte d'exemple n'a pas été traduit")
        self._exiger(bool(traduction.texte.strip()), "la traduction est vide")
        self._exiger(len(traduction.termes) > 0, "aucun terme du glossaire n'a été reconnu dans le texte d'exemple")
        return {"sens": f"{traduction.source} -> {traduction.cible}", "caracteres": len(traduction.texte),
                "termes_reconnus": len(traduction.termes), "mots": traduction.mots,
                "mots_reconnus": traduction.mots_reconnus}

    def _document(self) -> dict:
        from . import documents

        page = self.fenetre.page_texte
        self._exiger(page.traduction is not None, "il n'y a pas de traduction à enregistrer")
        fichier = self.dossier / "traduction.docx"
        self._exiger(page.exporter(fichier), "la traduction n'a pas pu être enregistrée")
        relu = documents.lire(fichier)
        self._exiger(relu.split() == page.traduction.texte.split(),
                     "le document Word relu ne contient pas la traduction enregistrée")
        return {"fichier": fichier.name, "octets": fichier.stat().st_size}

    def _ecrans(self) -> list[str]:
        from .interface.navigation import MODE_AIDE, MODE_DESCRIPTION, MODE_PARAMETRES, MODE_TERME, MODE_TEXTE

        affiches = []
        for mode in (MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE, MODE_TEXTE, MODE_TERME):
            self.fenetre.definir_mode(mode)
            self.application.processEvents()
            self._exiger(self.fenetre.page_courante().isVisible(), f"l'écran « {mode} » ne s'affiche pas")
            affiches.append(mode)
        return affiches

    def _ia(self) -> dict:
        """L'IA est éteinte tant que personne ne l'a allumée, et aucune clé n'est enregistrée."""
        from .interface import ia

        reglages = ia.lire(self.reglages)
        partie = self.fenetre.page_parametres.ia
        self._exiger(not reglages.active and not partie.active(), "l'IA est allumée sans que personne l'ait demandé")
        self._exiger(not partie.bouton_tester.isEnabled(),
                     "IA éteinte, le bouton « Tester la connexion » peut encore être cliqué")
        self._exiger(not reglages.cle, "une clé d'accès est enregistrée dans des réglages neufs")
        constat: dict[str, object] = {"allumee": reglages.active, "adresse": reglages.adresse,
                                      "modele": reglages.modele}
        if self.connexion:
            constat["connexion"] = self._connexion()
        return constat

    def _connexion(self) -> dict:
        """Demande au service d'IA proposé par défaut la liste de ses modèles : sans clé, sans aucun texte.

        C'est l'essai d'une connexion chiffrée faite par le programme lui-même, avec ses propres
        bibliothèques et les certificats de l'ordinateur. Un échec est noté, sans plus : le service
        injoignable, ou muet, ne fait pas échouer le contrôle. Une erreur du programme, elle, le fait
        échouer.

        Le constat distingue deux choses : ``etablie``, vrai dès que le service a répondu, même par
        un refus (la connexion chiffrée fonctionne) ; ``reussie``, vrai s'il a donné sa liste.

        L'essai est mené dans un fil d'exécution à part, attendu ``DUREE_MAXIMALE_DE_LA_CONNEXION``
        secondes au plus. Passé ce temps, il est abandonné : le fil ne retient pas le programme. Le
        temps passé à attendre le service ne compte pas dans le délai du contrôle (``DELAI``).
        """
        from .ia import service

        adresse = service.ADRESSE_PAR_DEFAUT
        constat: dict[str, object] = {}
        erreurs: list[BaseException] = []

        def essayer() -> None:
            debut = time.monotonic()
            try:
                modeles = service.lister_les_modeles(adresse, delai=DELAI_DE_LA_CONNEXION, envois=1)
            except service.ErreurService as erreur:
                # Un code, ou une réponse illisible : le service a répondu, donc la connexion a été établie.
                repondu = erreur.code is not None or erreur.genre == service.REPONSE
                constat.update(etablie=repondu, reussie=False, genre=erreur.genre, message=str(erreur))
                if erreur.code is not None:
                    constat["code"] = erreur.code
            except Exception as erreur:  # une erreur du programme : elle est rendue au contrôle, qui la note
                erreurs.append(erreur)
            else:
                constat.update(etablie=True, reussie=True, modeles=len(modeles),
                               duree_en_secondes=round(time.monotonic() - debut, 1))

        reste = self._limite.remainingTime()  # -1 quand le délai du contrôle ne court pas
        self._limite.stop()
        fil = threading.Thread(target=essayer, name="controle-de-la-connexion", daemon=True)
        fil.start()
        fil.join(DUREE_MAXIMALE_DE_LA_CONNEXION)
        if reste >= 0:
            self._limite.start(reste)
        if fil.is_alive():
            duree = f"{DUREE_MAXIMALE_DE_LA_CONNEXION:g}".replace(".", ",")
            return {"adresse": adresse, "etablie": False, "reussie": False, "genre": service.DELAI_DEPASSE,
                    "message": f"Le service n’a pas répondu en {duree} secondes : l’essai a été abandonné."}
        if erreurs:
            raise erreurs[0]
        return {"adresse": adresse, **constat}

    def _textes_de_qt(self) -> dict:
        en_francais = QCoreApplication.translate("QShortcut", "Shift") == "Maj"
        self._exiger(en_francais, "les textes fournis par Qt (menus « Copier », « Coller »…) ne sont pas en français")
        return {"en_francais": en_francais}

    def _image(self) -> dict:
        image = self.fenetre.grab().toImage()
        fichier = self.dossier / NOM_DE_L_IMAGE
        self._exiger(image.save(str(fichier), "PNG"), "l'image de la fenêtre n'a pas pu être enregistrée")
        return {"fichier": fichier.name, "largeur": image.width(), "hauteur": image.height()}

    # ------------------------------------------------------------------ rapport
    def rapport(self) -> dict:
        """Ce que le contrôle a constaté, tel qu'il est écrit dans le fichier du rapport."""
        import PySide6

        ecran = self.application.primaryScreen()
        taille = ecran.size() if ecran is not None else None
        return {
            "reussi": not self.erreurs,
            "erreurs": self.erreurs,
            "application": {
                "nom": NOM_APPLICATION, "version": __version__,
                "installee": bool(getattr(sys, "frozen", False)), "programme": sys.executable,
            },
            "systeme": {
                "nom": platform.platform(), "python": platform.python_version(), "qt": qVersion(),
                "pyside": PySide6.__version__, "affichage": self.application.platformName(),
                "ecran": f"{taille.width()} x {taille.height()}" if taille is not None else "aucun",
                "police": self.application.font().family(),
            },
            **self.constats,
            "duree_en_secondes": round(time.monotonic() - self._debut, 1),
        }

    def terminer(self) -> None:
        """Écrit le rapport, ferme la fenêtre et annonce la fin du contrôle."""
        if self.code is not None:
            return
        self._attente.stop()
        self._limite.stop()
        # Une boîte de message signale toujours un problème : glossaire illisible, installation à corriger…
        self.erreurs.extend(f"message affiché : « {titre} » — {texte}" for titre, texte in self.messages)
        rapport = self.rapport()
        self.code = 0 if rapport["reussi"] else 1
        try:
            (self.dossier / NOM_DU_RAPPORT).write_text(
                json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            self.code = 1
        if self._afficher_d_origine is not None:
            from .interface import boites

            boites.afficher = self._afficher_d_origine
        for fenetre in (self.ecran, self.fenetre):
            if fenetre is not None:
                fenetre.close()
        self.termine.emit(self.code)


def executer(application: QApplication, dossier: Path, connexion: bool = False) -> int:
    """Lance le contrôle, attend sa fin et renvoie son code de sortie : 0 si tout a fonctionné, 1 sinon."""
    controle = Controle(application, dossier, connexion)
    controle.termine.connect(application.exit)
    QTimer.singleShot(0, controle.demarrer)
    application.exec()
    # Sans rapport (fenêtre fermée avant la fin, par exemple), le contrôle est un échec.
    return controle.code if controle.code is not None else 1
