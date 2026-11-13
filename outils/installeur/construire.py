#!/usr/bin/env python3
"""Fabrique l'installeur de l'application pour Windows (fichier .msi), puis le vérifie.

Emploi, sous Windows, depuis le dossier du projet :

    python -m pip install -r outils/installeur/requirements.txt
    python outils/installeur/construire.py

Résultat : ``build/installeur/Traducteur-juridique-<version>.msi``. L'installeur contient Python et
Qt : l'ordinateur où il est installé n'a besoin de rien d'autre.

Ce script ne fait pas partie de l'application. Il enchaîne ces étapes :

1. l'icône de l'application, au format de Windows (``icone.py``) ;
2. le dossier de l'application, avec Python et Qt (PyInstaller, recette ``traducteur.spec``) ;
3. le contrôle de ce dossier : le programme est lancé, se contrôle lui-même et écrit un rapport
   (``traducteur/controle.py``) ;
4. la liste des fichiers à installer (``fichiers.py``) ;
5. l'installeur (WiX Toolset 3, description ``traducteur.wxs``).

Avec ``--essayer-l-installation``, il essaie ensuite l'installeur sur cet ordinateur : installation,
contrôle de l'application installée, désinstallation, puis remplacement d'une ancienne version. Cette
option est faite pour une machine de fabrication (GitHub Actions) : elle refuse de démarrer si
l'application est déjà installée, car elle la désinstallerait.

WiX Toolset 3 est cherché sur l'ordinateur ; s'il est absent, il est téléchargé dans ``build``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import zipfile

ICI = pathlib.Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(ICI))

import fichiers as liste_des_fichiers  # noqa: E402

from traducteur import NOM_APPLICATION, __version__  # noqa: E402

TRAVAIL = RACINE / "build" / "installeur"
JOURNAUX = TRAVAIL / "journaux"
NOM_DU_PROGRAMME = "TraducteurJuridique"
PROGRAMME = NOM_DU_PROGRAMME + ".exe"
DOSSIER_DE_L_APPLICATION = TRAVAIL / "dist" / NOM_DU_PROGRAMME
NOM_DE_L_INSTALLEUR = f"Traducteur-juridique-{__version__}.msi"
GLOSSAIRE = pathlib.PurePath("_internal", "donnees", "glossaire_juridique.csv")
#: Numéro de version de l'« ancienne version » fabriquée pour essayer une mise à jour.
ANCIENNE_VERSION = "0.0.1"
#: WiX Toolset 3, téléchargé seulement s'il n'est pas déjà sur l'ordinateur.
ADRESSE_DE_WIX = "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip"
#: Durée maximale du contrôle du programme, en secondes (le contrôle lui-même s'arrête après 60 secondes).
DELAI_DU_CONTROLE = 180
#: Bibliothèques de Microsoft qui ne font pas partie de Windows : le dossier de l'application doit les contenir.
A_FOURNIR = ("vcruntime", "msvcp", "concrt", "vcomp", "vccorlib", "vcamp", "msvcr", "mfc", "atl1", "ucrtbased")


class Echec(Exception):
    """Une étape a échoué : ``etape`` la nomme, ``details`` donne la fin de ce que l'outil a affiché."""

    def __init__(self, etape: str, message: str, details: str = "") -> None:
        super().__init__(message)
        self.etape = etape
        self.details = details


# ---------------------------------------------------------------------- affichage
def dire(texte: str = "") -> None:
    print(texte, flush=True)


def titre(texte: str) -> None:
    dire()
    dire(f"=== {texte}")


def annoter(niveau: str, intitule: str, message: str) -> None:
    """Sous GitHub Actions, affiche un message sur la page de la fabrication (« notice », « warning », « error »)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    for caractere, code in (("%", "%25"), ("\r", "%0D"), ("\n", "%0A")):
        intitule = intitule.replace(caractere, code)
        message = message.replace(caractere, code)
    intitule = intitule.replace(":", "%3A").replace(",", "%2C")
    dire(f"::{niveau} title={intitule}::{message}")


class Resume:
    """Ce qui a été fabriqué et vérifié, ligne par ligne : affiché, puis écrit dans ``resume.md``."""

    def __init__(self) -> None:
        self.lignes: list[str] = []

    def noter(self, ligne: str) -> None:
        self.lignes.append(ligne)
        dire(f"  {ligne}")

    def texte(self) -> str:
        return "\n".join(f"- {ligne}" for ligne in self.lignes) + "\n"

    def ecrire(self) -> None:
        (TRAVAIL / "resume.md").write_text(self.texte(), encoding="utf-8")
        page = os.environ.get("GITHUB_STEP_SUMMARY")
        if page:
            with pathlib.Path(page).open("a", encoding="utf-8") as fichier:
                fichier.write(f"### Installeur de {NOM_APPLICATION} {__version__}\n\n{self.texte()}\n")


# ---------------------------------------------------------------------- outils
def lancer(etape: str, commande: list, *, delai: int | None = None, codes_acceptes: tuple[int, ...] = (0,),
           environnement: dict[str, str] | None = None) -> int:
    """Lance une commande, garde ce qu'elle affiche dans ``journaux/<etape>.txt`` et vérifie son code de sortie."""
    commande = [str(element) for element in commande]
    JOURNAUX.mkdir(parents=True, exist_ok=True)
    journal = JOURNAUX / f"{etape}.txt"
    dire(f"  > {subprocess.list2cmdline(commande)}")
    debut = time.monotonic()
    # Les scripts Python lancés ici écrivent en UTF-8, quel que soit le réglage de la console.
    environnement = {**(os.environ if environnement is None else environnement), "PYTHONIOENCODING": "utf-8:replace"}
    with journal.open("w", encoding="utf-8", errors="replace") as sortie:
        try:
            resultat = subprocess.run(commande, stdout=sortie, stderr=subprocess.STDOUT, timeout=delai, cwd=RACINE,
                                      env=environnement, check=False)
            code = resultat.returncode
        except subprocess.TimeoutExpired:
            code = None
        except OSError as erreur:
            raise Echec(etape, f"La commande n'a pas pu être lancée : {erreur}") from erreur
    affiche = journal.read_text(encoding="utf-8", errors="replace")
    dire(f"    code de sortie : {code if code is not None else 'aucun (délai dépassé)'} ; "
         f"durée : {time.monotonic() - debut:.0f} s ; journal : {journal.relative_to(RACINE)}")
    if code is None:
        raise Echec(etape, f"La commande ne s'est pas terminée en {delai} secondes.", fin_de(affiche))
    if code not in codes_acceptes:
        raise Echec(etape, f"La commande a échoué (code de sortie {code}).", fin_de(affiche))
    return code


def fin_de(texte: str, lignes: int = 60, caracteres: int = 6000) -> str:
    """Les dernières lignes d'un texte : c'est là que les outils écrivent leurs erreurs."""
    return "\n".join(texte.strip().splitlines()[-lignes:])[-caracteres:]


def lire_un_journal_de_windows(chemin: pathlib.Path) -> str:
    """Le texte d'un journal de Windows Installer (écrit en UTF-16)."""
    if not chemin.is_file():
        return ""
    brut = chemin.read_bytes()
    encodage = "utf-16" if brut[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    return brut.decode(encodage, "replace")


def taille(octets: int) -> str:
    return f"{octets / 1_000_000:.1f} Mo".replace(".", ",")


def empreinte(chemin: pathlib.Path) -> str:
    calcul = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1 << 20), b""):
            calcul.update(bloc)
    return calcul.hexdigest()


def fichiers_de(dossier: pathlib.Path) -> list[pathlib.Path]:
    return sorted(element for element in dossier.rglob("*") if element.is_file())


# ---------------------------------------------------------------------- étapes 1 et 2 : icône, dossier de l'application
def fabriquer_le_dossier(resume: Resume) -> None:
    titre("1. Icône de l'application")
    lancer("1-icone", [sys.executable, ICI / "icone.py", TRAVAIL / "traducteur.ico"])

    titre("2. Dossier de l'application, avec Python et Qt (PyInstaller)")
    lancer("2-pyinstaller", [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                             "--distpath", TRAVAIL / "dist", "--workpath", TRAVAIL / "pyinstaller",
                             ICI / "traducteur.spec"], delai=1500)
    if not (DOSSIER_DE_L_APPLICATION / PROGRAMME).is_file():
        raise Echec("2-pyinstaller", f"PyInstaller n'a pas produit {PROGRAMME}.")
    if not (DOSSIER_DE_L_APPLICATION / GLOSSAIRE).is_file():
        raise Echec("2-pyinstaller", f"Le glossaire fourni n'est pas dans le dossier de l'application ({GLOSSAIRE}).")
    contenu = fichiers_de(DOSSIER_DE_L_APPLICATION)
    total = sum(fichier.stat().st_size for fichier in contenu)
    resume.noter(f"Dossier de l'application : {len(contenu)} fichiers, {taille(total)} "
                 f"(Python {sys.version.split()[0]})")
    dire("  Les plus gros fichiers :")
    for fichier in sorted(contenu, key=lambda element: -element.stat().st_size)[:12]:
        dire(f"    {taille(fichier.stat().st_size):>9}  {fichier.relative_to(DOSSIER_DE_L_APPLICATION)}")


def bibliotheques_absentes(dossier: pathlib.Path, systeme: pathlib.Path) -> dict[str, list[str]]:
    """Bibliothèques (fichiers .dll) demandées par un fichier du dossier, absentes du dossier et de Windows.

    Renvoie, pour chaque bibliothèque absente, les fichiers qui la demandent. Une bibliothèque présente dans
    ``systeme`` (le dossier System32 de Windows) est considérée comme fournie par Windows, sauf celles de
    ``A_FOURNIR`` : un ordinateur ne les a que si un autre logiciel les a installées.
    """
    import pefile

    contenu = [fichier for fichier in fichiers_de(dossier) if fichier.suffix.lower() in (".exe", ".dll", ".pyd")]
    presentes = {fichier.name.lower() for fichier in contenu}
    absentes: dict[str, list[str]] = {}
    for fichier in contenu:
        try:
            binaire = pefile.PE(str(fichier), fast_load=True)
        except pefile.PEFormatError:
            continue  # ce n'est pas un programme de Windows, malgré son extension
        try:
            binaire.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
            demandees = [entree.dll.decode("ascii", "replace").lower()
                         for entree in getattr(binaire, "DIRECTORY_ENTRY_IMPORT", [])]
        finally:
            binaire.close()
        for nom in demandees:
            if nom in presentes or nom.startswith(("api-ms-win-", "ext-ms-")):
                continue
            if not nom.startswith(A_FOURNIR) and (systeme / nom).is_file():
                continue
            absentes.setdefault(nom, []).append(fichier.relative_to(dossier).as_posix())
    return absentes


def verifier_les_bibliotheques(resume: Resume) -> None:
    systeme = pathlib.Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    try:
        absentes = bibliotheques_absentes(DOSSIER_DE_L_APPLICATION, systeme)
    except ImportError:
        resume.noter("Bibliothèques : non vérifiées (le module pefile n'est pas installé)")
        return
    if not absentes:
        resume.noter("Bibliothèques : chaque fichier .dll demandé est dans le dossier ou fait partie de Windows")
        return
    lignes = [f"{nom} (demandée par {', '.join(demandeurs[:3])}{'…' if len(demandeurs) > 3 else ''})"
              for nom, demandeurs in sorted(absentes.items())]
    resume.noter("Bibliothèques absentes du dossier et de Windows : " + " ; ".join(lignes))
    annoter("warning", "Bibliothèques absentes", "\n".join(lignes))


# ---------------------------------------------------------------------- étape 3 : contrôle du programme
def controler(programme: pathlib.Path, nom: str, resume: Resume, quoi: str) -> dict:
    """Lance le programme avec ``--controle`` et renvoie son rapport ; échoue si le contrôle n'a pas réussi."""
    dossier = TRAVAIL / "controles" / nom
    shutil.rmtree(dossier, ignore_errors=True)
    dossier.mkdir(parents=True)
    etape = f"controle-{nom}"
    environnement = {cle: valeur for cle, valeur in os.environ.items() if cle != "QT_QPA_PLATFORM"}
    avant = fichiers_de(programme.parent)
    try:
        lancer(etape, [programme, f"--controle={dossier}"], delai=DELAI_DU_CONTROLE, codes_acceptes=(0, 1, 3),
               environnement=environnement)
    except Echec as echec:
        subprocess.run(["taskkill", "/F", "/T", "/IM", programme.name], capture_output=True, check=False)
        raise Echec(etape, f"{quoi} : {echec}", echec.details) from echec
    # L'application ne doit rien écrire dans son propre dossier : installé, il n'est pas fait pour cela.
    ajoutes = sorted(set(fichiers_de(programme.parent)) - set(avant))
    if ajoutes:
        raise Echec(etape, f"{quoi} : le programme a écrit dans son propre dossier.",
                    "\n".join(str(fichier.relative_to(programme.parent)) for fichier in ajoutes[:20]))
    erreur = dossier / "erreur.txt"
    if erreur.is_file():
        raise Echec(etape, f"{quoi} : le programme n'a pas pu démarrer.", fin_de(erreur.read_text(encoding="utf-8")))
    fichier = dossier / "rapport.json"
    if not fichier.is_file():
        raise Echec(etape, f"{quoi} : le programme n'a pas écrit son rapport.",
                    fin_de((JOURNAUX / f"{etape}.txt").read_text(encoding="utf-8", errors="replace")))
    rapport = json.loads(fichier.read_text(encoding="utf-8"))
    dire(json.dumps(rapport, ensure_ascii=False, indent=2))
    if not rapport.get("reussi"):
        raise Echec(etape, f"{quoi} : le contrôle a échoué.", "\n".join(rapport.get("erreurs", [])))
    if not rapport["application"]["installee"] or rapport["application"]["version"] != __version__:
        raise Echec(etape, f"{quoi} : le rapport ne vient pas du programme fabriqué.",
                    json.dumps(rapport["application"], ensure_ascii=False))
    attendu = (programme.parent / GLOSSAIRE).resolve()
    if pathlib.Path(rapport["glossaire"]["fichier"]).resolve() != attendu:
        raise Echec(etape, f"{quoi} : le glossaire chargé n'est pas celui du dossier de l'application.",
                    f"chargé : {rapport['glossaire']['fichier']}\nattendu : {attendu}")
    systeme = rapport["systeme"]
    resume.noter(
        f"{quoi} : le programme s'ouvre et son contrôle réussit en {rapport['duree_en_secondes']} s "
        f"({rapport['glossaire']['entrees']} entrées du glossaire, recherche, traduction, document Word, "
        f"cinq écrans ; {systeme['nom']}, Python {systeme['python']}, Qt {systeme['qt']}, "
        f"affichage « {systeme['affichage']} », écran {systeme['ecran']}, police {systeme['police']})")
    return rapport


# ---------------------------------------------------------------------- étapes 4 et 5 : installeur
def trouver_wix() -> pathlib.Path:
    """Le dossier qui contient candle.exe et light.exe ; WiX est téléchargé s'il n'est pas sur l'ordinateur."""
    candidats = []
    if os.environ.get("WIX"):
        candidats.append(pathlib.Path(os.environ["WIX"]) / "bin")
    # Sous Windows, le nom d'une variable d'environnement s'écrit indifféremment en majuscules ou en minuscules.
    for racine in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if racine:
            candidats.extend(sorted(pathlib.Path(racine).glob("WiX Toolset v3*/bin"), reverse=True))
    trouve = shutil.which("candle.exe")
    if trouve:
        candidats.append(pathlib.Path(trouve).parent)
    candidats.append(TRAVAIL / "wix")
    for dossier in candidats:
        if (dossier / "candle.exe").is_file() and (dossier / "light.exe").is_file():
            return dossier
    dire(f"  WiX Toolset 3 n'est pas sur cet ordinateur : téléchargement de {ADRESSE_DE_WIX}")
    import urllib.request

    archive = TRAVAIL / "wix314-binaries.zip"
    try:
        urllib.request.urlretrieve(ADRESSE_DE_WIX, archive)
        with zipfile.ZipFile(archive) as contenu:
            contenu.extractall(TRAVAIL / "wix")
    except (OSError, zipfile.BadZipFile) as erreur:
        raise Echec("4-wix", f"WiX Toolset 3 n'a pas pu être téléchargé : {erreur}") from erreur
    return TRAVAIL / "wix"


def fabriquer_l_installeur(wix: pathlib.Path, version: str, sortie: pathlib.Path, compression: str, nom: str) -> None:
    """Compile la description de l'installeur (candle), puis assemble le fichier .msi (light)."""
    objets = TRAVAIL / "wix-objets" / nom
    shutil.rmtree(objets, ignore_errors=True)
    objets.mkdir(parents=True)
    lancer(f"5-candle-{nom}", [
        wix / "candle.exe", "-nologo", "-arch", "x64", "-ext", "WixUIExtension",
        f"-dVersion={version}", f"-dSource={DOSSIER_DE_L_APPLICATION}", f"-dIcone={TRAVAIL / 'traducteur.ico'}",
        f"-dCompression={compression}", "-out", f"{objets}{os.sep}",
        ICI / "traducteur.wxs", TRAVAIL / "fichiers.wxs"], delai=600)
    sortie.unlink(missing_ok=True)
    lancer(f"5-light-{nom}", [
        wix / "light.exe", "-nologo", "-ext", "WixUIExtension", "-cultures:fr-FR", "-spdb",
        # Deux vérifications de Windows Installer ne donneraient que des avertissements attendus, un par
        # fichier pour la seconde. ICE61 : l'installeur remplace aussi une version de même numéro.
        # ICE91 : l'application s'installe dans le dossier de l'utilisateur. C'est voulu dans les deux cas.
        "-sice:ICE61", "-sice:ICE91",
        "-out", sortie, objets / "traducteur.wixobj", objets / "fichiers.wixobj"], delai=1500)
    if not sortie.is_file():
        raise Echec(f"5-light-{nom}", f"WiX n'a pas produit {sortie.name}.")


# ---------------------------------------------------------------------- essai de l'installation
def dossier_du_bureau() -> pathlib.Path:
    import ctypes
    from ctypes import wintypes

    chemin = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, chemin)  # 0x0010 : le Bureau de l'utilisateur
    return pathlib.Path(chemin.value)


def emplacements() -> dict[str, pathlib.Path]:
    """Ce que l'installeur doit créer, puis retirer."""
    installation = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Programs" / NOM_APPLICATION
    menu = pathlib.Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return {
        "dossier": installation,
        "programme": installation / PROGRAMME,
        "glossaire": installation / GLOSSAIRE,
        "raccourci du menu Démarrer": menu / f"{NOM_APPLICATION}.lnk",
        "raccourci du Bureau": dossier_du_bureau() / f"{NOM_APPLICATION}.lnk",
    }


def inscriptions() -> list[dict[str, str]]:
    """Les lignes « Traducteur juridique » de la liste des applications installées de l'utilisateur."""
    import winreg

    trouvees = []
    try:
        liste = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    except OSError:
        return trouvees
    with liste:
        for rang in range(winreg.QueryInfoKey(liste)[0]):
            nom = winreg.EnumKey(liste, rang)
            with winreg.OpenKey(liste, nom) as cle:
                valeurs = {}
                for champ in ("DisplayName", "DisplayVersion", "Publisher", "InstallLocation"):
                    try:
                        valeurs[champ] = str(winreg.QueryValueEx(cle, champ)[0])
                    except OSError:
                        valeurs[champ] = ""
                if valeurs["DisplayName"] == NOM_APPLICATION:
                    trouvees.append({"code": nom, **valeurs})
    return trouvees


def marques_dans_le_registre() -> bool:
    """La clé où l'installeur inscrit ses marques de présence existe-t-elle ?"""
    import winreg

    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, liste_des_fichiers.CLE_DU_REGISTRE))
    except OSError:
        return False
    return True


def cible_du_raccourci(raccourci: pathlib.Path) -> str:
    resultat = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"(New-Object -ComObject WScript.Shell).CreateShortcut('{raccourci}').TargetPath"],
        capture_output=True, text=True, timeout=120, check=False)
    return resultat.stdout.strip()


def windows_installer(etape: str, action: str, installeur: pathlib.Path) -> None:
    """Installe (``/i``) ou désinstalle (``/x``) sans rien afficher, comme le ferait un double-clic sans écran."""
    journal = JOURNAUX / f"{etape}-msiexec.log"
    journal.unlink(missing_ok=True)
    try:
        lancer(etape, ["msiexec", action, installeur, "/qn", "/norestart", "/l*v", journal], delai=900)
    except Echec as echec:
        lignes = [ligne for ligne in lire_un_journal_de_windows(journal).splitlines()
                  if "value 3" in ligne or "Error " in ligne or "erreur" in ligne.lower() or "-- Error" in ligne]
        raise Echec(etape, f"Windows Installer : {echec}", fin_de("\n".join(lignes), 40)) from echec


def exiger_l_installation(etape: str, version: str, nombre_de_fichiers: int) -> dict[str, pathlib.Path]:
    lieux = emplacements()
    manquants = [nom for nom, chemin in lieux.items() if not chemin.exists()]
    if manquants:
        raise Echec(etape, "Après l'installation, il manque : " + ", ".join(manquants) + ".",
                    "\n".join(f"{nom} : {chemin}" for nom, chemin in lieux.items()))
    installes = len(fichiers_de(lieux["dossier"]))
    if installes != nombre_de_fichiers:
        raise Echec(etape, f"{installes} fichiers installés au lieu de {nombre_de_fichiers}.")
    for nom in ("raccourci du menu Démarrer", "raccourci du Bureau"):
        cible = cible_du_raccourci(lieux[nom])
        if pathlib.Path(cible) != lieux["programme"]:
            raise Echec(etape, f"Le {nom} n'ouvre pas le programme installé.",
                        f"cible : {cible!r}\nattendu : {lieux['programme']}")
    lignes = inscriptions()
    if len(lignes) != 1 or lignes[0]["DisplayVersion"] != version:
        raise Echec(etape, f"La liste des applications installées devrait contenir une seule ligne "
                           f"« {NOM_APPLICATION} », en version {version}.", json.dumps(lignes, ensure_ascii=False))
    return lieux


def exiger_la_desinstallation(etape: str) -> None:
    restes = [f"{nom} : {chemin}" for nom, chemin in emplacements().items() if chemin.exists()]
    restes += [f"ligne de la liste des applications installées : {ligne}" for ligne in inscriptions()]
    if marques_dans_le_registre():
        restes.append(f"clé du registre : {liste_des_fichiers.CLE_DU_REGISTRE}")
    if restes:
        raise Echec(etape, "La désinstallation a laissé quelque chose sur l'ordinateur.", "\n".join(restes))


def essayer_l_installation(wix: pathlib.Path, installeur: pathlib.Path, resume: Resume) -> None:
    titre("6. Essai de l'installeur sur cet ordinateur")
    nombre_de_fichiers = len(fichiers_de(DOSSIER_DE_L_APPLICATION))
    deja = [str(chemin) for chemin in emplacements().values() if chemin.exists()]
    deja += [str(ligne) for ligne in inscriptions()]
    if deja:
        raise Echec("6-essai", f"{NOM_APPLICATION} est déjà sur cet ordinateur : l'essai le désinstallerait. "
                               "Désinstallez-le d'abord, ou lancez le script sans --essayer-l-installation.",
                    "\n".join(deja))

    dire("  a) Première installation")
    windows_installer("6a-installation", "/i", installeur)
    lieux = exiger_l_installation("6a-installation", __version__, nombre_de_fichiers)
    resume.noter(f"Installation sans droits d'administrateur : {nombre_de_fichiers} fichiers dans "
                 f"« {lieux['dossier']} », une icône sur le Bureau et une dans le menu Démarrer (elles ouvrent le "
                 f"programme installé), une ligne « {NOM_APPLICATION} {__version__} » dans les applications installées")
    controler(lieux["programme"], "installe", resume, "Application installée")

    dire("  b) Désinstallation")
    windows_installer("6b-desinstallation", "/x", installeur)
    exiger_la_desinstallation("6b-desinstallation")
    resume.noter("Désinstallation : le dossier, les deux icônes, la ligne des applications installées et les "
                 "marques du registre sont retirés")

    dire(f"  c) Remplacement d'une ancienne version ({ANCIENNE_VERSION})")
    ancien = TRAVAIL / "essai" / f"ancienne-version-{ANCIENNE_VERSION}.msi"
    ancien.parent.mkdir(parents=True, exist_ok=True)
    fabriquer_l_installeur(wix, ANCIENNE_VERSION, ancien, "none", "ancienne-version")
    windows_installer("6c-ancienne-version", "/i", ancien)
    exiger_l_installation("6c-ancienne-version", ANCIENNE_VERSION, nombre_de_fichiers)
    windows_installer("6c-mise-a-jour", "/i", installeur)
    lieux = exiger_l_installation("6c-mise-a-jour", __version__, nombre_de_fichiers)
    controler(lieux["programme"], "mis-a-jour", resume, "Après une mise à jour")
    resume.noter(f"Mise à jour : installé par-dessus une version {ANCIENNE_VERSION}, l'installeur la remplace "
                 "(une seule ligne dans les applications installées)")
    windows_installer("6c-desinstallation", "/x", installeur)
    exiger_la_desinstallation("6c-desinstallation")


# ---------------------------------------------------------------------- programme principal
def construire(essai: bool) -> pathlib.Path:
    if sys.platform != "win32":
        raise Echec("0-depart", "L'installeur se fabrique sous Windows : ce script ne fonctionne pas sur ce système.")
    shutil.rmtree(TRAVAIL, ignore_errors=True)
    TRAVAIL.mkdir(parents=True)
    resume = Resume()
    installeur = TRAVAIL / NOM_DE_L_INSTALLEUR
    try:
        fabriquer_le_dossier(resume)

        titre("3. Contrôle du dossier de l'application")
        verifier_les_bibliotheques(resume)
        controler(DOSSIER_DE_L_APPLICATION / PROGRAMME, "dossier", resume, "Dossier de l'application")

        titre("4. Liste des fichiers à installer")
        nombre, dossiers = liste_des_fichiers.ecrire(DOSSIER_DE_L_APPLICATION, PROGRAMME, TRAVAIL / "fichiers.wxs")
        dire(f"  {nombre} fichiers dans {dossiers} dossiers")

        titre("5. Installeur (WiX Toolset 3)")
        wix = trouver_wix()
        dire(f"  WiX : {wix}")
        fabriquer_l_installeur(wix, __version__, installeur, "high", "installeur")
        resume.noter(f"Installeur : {installeur.name}, {taille(installeur.stat().st_size)}, "
                     f"SHA-256 {empreinte(installeur)}")

        if essai:
            essayer_l_installation(wix, installeur, resume)
        else:
            resume.noter("Installation non essayée (option --essayer-l-installation absente)")
    finally:
        resume.ecrire()
    annoter("notice", f"Installeur de {NOM_APPLICATION} {__version__}", resume.texte())
    titre(f"Terminé : {installeur}")
    return installeur


def main() -> int:
    for flux in (sys.stdout, sys.stderr):  # les accents s'affichent, même quand la sortie est redirigée
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    lecteur = argparse.ArgumentParser(description="Fabrique l'installeur de l'application pour Windows (.msi).")
    lecteur.add_argument("--essayer-l-installation", action="store_true",
                         help="installe, contrôle, désinstalle et met à jour l'application sur cet ordinateur")
    options = lecteur.parse_args()
    try:
        construire(options.essayer_l_installation)
    except Echec as echec:
        dire()
        dire(f"ÉCHEC — étape « {echec.etape} » : {echec}")
        if echec.details:
            dire(echec.details)
        annoter("error", f"Étape « {echec.etape} »", f"{echec}\n{echec.details}".strip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
