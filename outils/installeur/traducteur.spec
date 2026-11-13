# -*- mode: python ; coding: utf-8 -*-
"""Recette de PyInstaller : rassemble l'application, Python et Qt dans un seul dossier.

« construire.py » enchaîne toutes les étapes ; cette recette n'est pas lancée à la main. À titre
d'information, la commande est :

    python -m PyInstaller --noconfirm --distpath build/installeur/dist \
        --workpath build/installeur/pyinstaller outils/installeur/traducteur.spec

Résultat : le dossier ``build/installeur/dist/TraducteurJuridique``. Il contient
``TraducteurJuridique.exe`` et un dossier ``_internal`` (Python, Qt, le code de l'application et le
glossaire fourni). Ce dossier fonctionne sur un ordinateur où Python n'est pas installé ;
l'installeur le copie tel quel.
"""
import sys
from pathlib import Path

RACINE = Path(SPECPATH).resolve().parents[1]  # noqa: F821 (SPECPATH est fourni par PyInstaller)
sys.path.insert(0, str(RACINE))

from traducteur import NOM_APPLICATION, __version__  # noqa: E402

NOM_DU_PROGRAMME = "TraducteurJuridique"
#: Dossier de travail de « construire.py » : l'icône y est déjà écrite.
PREPARATION = RACINE / "build" / "installeur"

icone = None
informations = None
if sys.platform == "win32":
    icone = PREPARATION / "traducteur.ico"
    if not icone.is_file():
        raise SystemExit(f"Icône absente ({icone}) : lancez « python outils/installeur/construire.py ».")
    # Ce que Windows affiche dans les propriétés du fichier .exe et dans le gestionnaire des tâches.
    numeros = (*(int(partie) for partie in __version__.split(".")[:3]), 0)
    informations = PREPARATION / "version.txt"
    informations.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros}, prodvers={numeros}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', {NOM_APPLICATION!r}),
      StringStruct('FileDescription', {NOM_APPLICATION!r}),
      StringStruct('FileVersion', {__version__!r}),
      StringStruct('InternalName', {NOM_DU_PROGRAMME!r}),
      StringStruct('OriginalFilename', {NOM_DU_PROGRAMME + '.exe'!r}),
      StringStruct('ProductName', {NOM_APPLICATION!r}),
      StringStruct('ProductVersion', {__version__!r})])]),
    VarFileInfo([VarStruct('Translation', [0x040C, 1200])])
  ]
)
""", encoding="utf-8")

analyse = Analysis(  # noqa: F821 (Analysis, PYZ, EXE et COLLECT sont fournis par PyInstaller)
    [str(RACINE / "main.py")],
    pathex=[str(RACINE)],
    # Le glossaire fourni garde sa place par rapport au code : « donnees », à côté du paquet « traducteur ».
    datas=[(str(RACINE / "donnees" / "glossaire_juridique.csv"), "donnees")],
    # Avec l'option --controle, le programme installé se contrôle sans jamais attendre un clic.
    runtime_hooks=[str(RACINE / "outils" / "installeur" / "crochet_controle.py")],
)
archive = PYZ(analyse.pure)  # noqa: F821
programme = EXE(  # noqa: F821
    archive,
    analyse.scripts,
    [],
    exclude_binaries=True,
    name=NOM_DU_PROGRAMME,
    console=False,  # application à fenêtres : pas de console noire à l'ouverture
    upx=False,
    icon=str(icone) if icone else None,
    version=str(informations) if informations else None,
)
dossier = COLLECT(programme, analyse.binaries, analyse.datas, upx=False, name=NOM_DU_PROGRAMME)  # noqa: F821
