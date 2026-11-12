"""Démarrage de l'application de bureau."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from . import NOM_APPLICATION, __version__


def main(arguments: list[str] | None = None) -> int:
    """Ouvre la fenêtre principale. Un chemin de glossaire CSV peut être passé en argument."""
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

    from .interface.fenetre import FenetrePrincipale

    chemins = [argument for argument in application.arguments()[1:] if not argument.startswith("-")]
    fenetre = FenetrePrincipale(chemins[0] if chemins else None)
    fenetre.show()
    return application.exec()
