"""Démarrage de l'application de bureau."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, Qt, QTranslator
from PySide6.QtWidgets import QApplication

from . import NOM_APPLICATION, __version__


def liaison_qt_instable(version_de_python: tuple[int, ...] = sys.version_info[:2]) -> bool:
    """Détecte un défaut de PySide6 observé avec PySide6 6.12.0 et Python 3.11.

    Avec ces versions, chaque appel d'une méthode de Qt qui ne renvoie rien retire à tort une
    référence à l'objet ``None`` de Python. Au bout de quelques milliers d'appels, Python
    s'arrête brutalement (« Fatal Python error: none_dealloc ») et l'application se ferme.
    À partir de Python 3.12, ``None`` ne peut plus être détruit : le défaut est sans effet.

    Le défaut est mesuré, et non déduit du numéro de version de PySide6 : on appelle une
    méthode sans résultat et on regarde si le nombre de références à ``None`` a baissé.
    """
    if version_de_python >= (3, 12) or not hasattr(sys, "getrefcount"):
        return False
    from PySide6.QtCore import QSize

    essais = 64
    taille = QSize()
    avant = sys.getrefcount(None)
    for _ in range(essais):
        taille.setWidth(0)
    return sys.getrefcount(None) - avant <= -essais // 2


AVERTISSEMENT_LIAISON = (
    "Cette installation associe Python {python} et PySide6 {pyside}. Avec ces deux versions, "
    "l’application peut se fermer brutalement pendant l’utilisation.\n\n"
    "Pour corriger, fermez l’application, puis lancez dans un terminal, depuis le dossier du projet :\n\n"
    "    python -m pip install -r requirements.txt\n\n"
    "Cette commande installe une version de PySide6 qui convient. "
    "Installer une version récente de Python (3.12 ou plus) règle aussi le problème."
)


def installer_les_textes_de_qt(application: QApplication) -> QTranslator | None:
    """Met en français les textes fournis par Qt lui-même.

    Il s'agit surtout du menu contextuel des zones de texte (« Annuler », « Copier »,
    « Coller »…) et du nom des touches dans les raccourcis (« Maj »). Renvoie les textes
    installés, ou ``None`` si l'installation de Qt ne les contient pas : ils restent alors
    en anglais.
    """
    textes = QTranslator(application)
    dossier = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if textes.load(QLocale(QLocale.Language.French), "qtbase", "_", dossier) and application.installTranslator(textes):
        return textes
    textes.deleteLater()
    return None


def ouvrir(application: QApplication, chemin_glossaire: str | None = None, reglages: QSettings | None = None):
    """Affiche l'écran de démarrage (s'il est activé), construit la fenêtre principale, puis l'affiche.

    Renvoie la fenêtre et l'écran de démarrage (``None`` s'il est désactivé dans les réglages).
    La fenêtre s'affiche quand l'écran de démarrage a fini ; sans lui, tout de suite.
    """
    from .interface import boites
    from .interface.demarrage import EcranDemarrage
    from .interface.fenetre import FenetrePrincipale
    from .interface.pages import CLE_ECRAN_DE_DEMARRAGE

    reglages = reglages if reglages is not None else QSettings()
    ecran = None
    if reglages.value(CLE_ECRAN_DE_DEMARRAGE, True, bool):
        ecran = EcranDemarrage()
        ecran.show()
        application.processEvents()  # l'écran est dessiné avant le chargement du glossaire
    fenetre = FenetrePrincipale(chemin_glossaire, reglages=reglages)

    def montrer() -> None:
        fenetre.show()
        fenetre.raise_()
        fenetre.activateWindow()
        if liaison_qt_instable():
            import PySide6

            boites.afficher(fenetre, boites.ALERTE, "Installation à corriger", AVERTISSEMENT_LIAISON.format(
                python=".".join(map(str, sys.version_info[:2])), pyside=PySide6.__version__))

    if ecran is None:
        montrer()
    else:
        ecran.termine.connect(montrer)
        ecran.passer_la_main()
    return fenetre, ecran


def main(arguments: list[str] | None = None) -> int:
    """Ouvre l'application. Un chemin de glossaire CSV peut être passé en argument.

    Avec ``--controle=<dossier>``, l'application se contrôle elle-même, écrit un rapport dans ce
    dossier et se ferme : voir le module ``controle``.
    """
    arguments = list(sys.argv if arguments is None else arguments)
    if sys.platform == "win32":
        # Icône propre à l'application dans la barre des tâches de Windows.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TraducteurJuridique.Prototype")
        except (AttributeError, OSError):
            pass
    application = QApplication(arguments)
    application.setApplicationName(NOM_APPLICATION)
    application.setOrganizationName("TraducteurJuridique")
    application.setApplicationVersion(__version__)
    try:
        # L'interface est dessinée en clair : on garde des menus et des dialogues
        # clairs même si le système est en mode sombre (Qt 6.8 ou plus récent).
        application.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass

    from .interface import theme

    theme.appliquer(application)
    installer_les_textes_de_qt(application)

    from . import controle

    dossier_du_controle = controle.dossier_demande(arguments)
    if dossier_du_controle is not None:
        return controle.executer(application, dossier_du_controle)
    chemins = [argument for argument in application.arguments()[1:] if not argument.startswith("-")]
    # La fenêtre et l'écran de démarrage doivent rester référencés tant que l'application tourne.
    fenetre, ecran = ouvrir(application, chemins[0] if chemins else None)
    resultat = application.exec()
    del fenetre, ecran
    return resultat
