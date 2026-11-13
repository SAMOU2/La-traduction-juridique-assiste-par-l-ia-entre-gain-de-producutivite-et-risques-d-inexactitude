"""Exécuté au tout début du programme installé, avant l'application (« runtime hook » de PyInstaller).

Il ne fait rien pendant un lancement ordinaire. Quand le programme est lancé avec
``--controle=<dossier>`` (voir ``traducteur/controle.py``), il lance lui-même l'application et note,
dans ``<dossier>/erreur.txt``, toute erreur qui l'empêche de démarrer ; le programme s'arrête alors
avec le code 3.

Sans cela, le programme installé afficherait une fenêtre d'erreur et attendrait un clic : un contrôle
automatique, sans personne devant l'écran, resterait bloqué et ne dirait pas ce qui ne va pas.
"""
import sys


def _controler() -> None:
    option = "--controle="
    dossier = next((argument[len(option):] for argument in sys.argv[1:]
                    if argument.startswith(option) and len(argument) > len(option)), None)
    if dossier is None:
        return
    import pathlib
    import traceback

    try:
        from traducteur.application import main

        code = main()
    except BaseException as erreur:
        if isinstance(erreur, SystemExit):
            raise
        pathlib.Path(dossier).mkdir(parents=True, exist_ok=True)
        pathlib.Path(dossier, "erreur.txt").write_text(traceback.format_exc(), encoding="utf-8")
        code = 3
    sys.exit(code)


_controler()
