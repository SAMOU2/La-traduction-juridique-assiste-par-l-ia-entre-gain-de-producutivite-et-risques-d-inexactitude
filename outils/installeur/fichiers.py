#!/usr/bin/env python3
"""Écrit la liste des fichiers à installer, dans le langage de WiX (fichier .wxs).

Emploi, depuis le dossier du projet :

    python outils/installeur/fichiers.py <dossier_de_l_application> <fichier_de_sortie.wxs>

Ce script ne fait pas partie de l'application : c'est une étape de ``construire.py``. Il parcourt le
dossier que PyInstaller a produit et décrit chaque sous-dossier et chaque fichier. ``traducteur.wxs``
décrit le reste de l'installeur (nom, écrans, raccourcis).

L'application s'installe dans le dossier de l'utilisateur (``AppData\\Local\\Programs``), sans droits
d'administrateur. Windows Installer impose alors deux règles, respectées ici pour chaque dossier :

* le « composant » qui contient les fichiers du dossier est repéré par une valeur du registre de
  l'utilisateur (``HKEY_CURRENT_USER``), et non par un fichier ;
* le dossier est explicitement retiré à la désinstallation.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import uuid
from xml.etree import ElementTree

ESPACE_WIX = "http://schemas.microsoft.com/wix/2006/wi"
#: Identifiant, dans l'installeur, du dossier où l'application s'installe (déclaré dans traducteur.wxs).
DOSSIER_D_INSTALLATION = "INSTALLFOLDER"
#: Identifiant du programme à lancer : traducteur.wxs s'en sert pour l'ouvrir à la fin de l'installation.
PROGRAMME_PRINCIPAL = "ProgrammePrincipal"
GROUPE = "FichiersDeLApplication"
#: Clé du registre de l'utilisateur où chaque composant inscrit sa marque de présence.
CLE_DU_REGISTRE = r"Software\TraducteurJuridique\Installation"
#: Les identifiants des composants sont calculés à partir de cette racine : ils ne changent pas d'une
#: fabrication à l'autre, ce que Windows Installer demande pour mettre à jour une installation.
RACINE_DES_IDENTIFIANTS = uuid.UUID("6d1f0c53-64a5-4d0a-9a8c-0e5f1b9c7a21")
#: Jeu de caractères de l'installeur (Europe de l'Ouest) : les noms de fichiers doivent s'y écrire.
JEU_DE_CARACTERES = "cp1252"


class ErreurFichiers(Exception):
    """Le dossier de l'application ne peut pas être décrit."""


def _empreinte(prefixe: str, chemin: str) -> str:
    """Identifiant court et stable d'un dossier ou d'un fichier, accepté par Windows Installer."""
    return f"{prefixe}_{hashlib.sha1(chemin.lower().encode('utf-8')).hexdigest()[:16]}"


def _guid(chemin: str) -> str:
    return "{" + str(uuid.uuid5(RACINE_DES_IDENTIFIANTS, "composant:" + chemin.lower())).upper() + "}"


def _verifier_le_nom(element: pathlib.Path, relatif: str) -> None:
    try:
        element.name.encode(JEU_DE_CARACTERES)
    except UnicodeEncodeError as erreur:
        raise ErreurFichiers(f"Le nom « {relatif} » contient un caractère que l'installeur ne sait pas écrire.") \
            from erreur


def fragment(dossier: pathlib.Path, programme: str) -> ElementTree.ElementTree:
    """Décrit le contenu de ``dossier`` ; ``programme`` est le nom du fichier .exe à lancer, à sa racine."""
    dossier = pathlib.Path(dossier)
    if not (dossier / programme).is_file():
        raise ErreurFichiers(f"Le programme « {programme} » est introuvable dans le dossier « {dossier} ».")

    ElementTree.register_namespace("", ESPACE_WIX)

    def balise(nom: str) -> str:
        return f"{{{ESPACE_WIX}}}{nom}"

    racine = ElementTree.Element(balise("Wix"))
    racine.append(ElementTree.Comment(
        " Fichier fabriqué par outils/installeur/fichiers.py : ne pas le modifier à la main. "))
    partie = ElementTree.SubElement(racine, balise("Fragment"))
    arbre = ElementTree.SubElement(partie, balise("DirectoryRef"), Id=DOSSIER_D_INSTALLATION)
    groupe = ElementTree.SubElement(partie, balise("ComponentGroup"), Id=GROUPE)

    def decrire(courant: pathlib.Path, relatif: str, identifiant: str, parent: ElementTree.Element) -> None:
        contenu = sorted(courant.iterdir(), key=lambda element: element.name.lower())
        fichiers = [element for element in contenu if element.is_file()]
        sous_dossiers = [element for element in contenu if element.is_dir()]
        if len(fichiers) + len(sous_dossiers) != len(contenu):
            inconnus = [element.name for element in contenu if element not in fichiers and element not in sous_dossiers]
            raise ErreurFichiers(f"Ni fichier ni dossier dans « {relatif or '.'} » : {', '.join(inconnus)}.")

        composant = ElementTree.SubElement(
            groupe, balise("Component"), Id=_empreinte("c", relatif), Directory=identifiant, Guid=_guid(relatif))
        ElementTree.SubElement(
            composant, balise("RegistryValue"), Root="HKCU", Key=CLE_DU_REGISTRE, Name=_empreinte("c", relatif),
            Type="integer", Value="1", KeyPath="yes")
        ElementTree.SubElement(composant, balise("RemoveFolder"), Id=_empreinte("r", relatif), On="uninstall")
        if not contenu:
            ElementTree.SubElement(composant, balise("CreateFolder"))  # un dossier vide est tout de même créé
        for fichier in fichiers:
            chemin = f"{relatif}/{fichier.name}" if relatif else fichier.name
            _verifier_le_nom(fichier, chemin)
            principal = not relatif and fichier.name.lower() == programme.lower()
            ElementTree.SubElement(
                composant, balise("File"), Id=PROGRAMME_PRINCIPAL if principal else _empreinte("f", chemin),
                Name=fichier.name, Source="$(var.Source)\\" + chemin.replace("/", "\\"))
        for sous_dossier in sous_dossiers:
            chemin = f"{relatif}/{sous_dossier.name}" if relatif else sous_dossier.name
            _verifier_le_nom(sous_dossier, chemin)
            fils = ElementTree.SubElement(
                parent, balise("Directory"), Id=_empreinte("d", chemin), Name=sous_dossier.name)
            decrire(sous_dossier, chemin, fils.get("Id"), fils)

    decrire(dossier, "", DOSSIER_D_INSTALLATION, arbre)
    ElementTree.indent(racine, space="  ")
    return ElementTree.ElementTree(racine)


def compter(document: ElementTree.ElementTree) -> tuple[int, int]:
    """Nombre de fichiers et de dossiers décrits (le dossier d'installation compris)."""
    fichiers = sum(1 for _ in document.iter(f"{{{ESPACE_WIX}}}File"))
    dossiers = sum(1 for _ in document.iter(f"{{{ESPACE_WIX}}}Component"))
    return fichiers, dossiers


def ecrire(dossier: pathlib.Path, programme: str, sortie: pathlib.Path) -> tuple[int, int]:
    """Écrit le fichier .wxs et renvoie le nombre de fichiers et de dossiers décrits."""
    document = fragment(dossier, programme)
    sortie = pathlib.Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    document.write(sortie, encoding="utf-8", xml_declaration=True)
    return compter(document)


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        return 2
    programme = sys.argv[3] if len(sys.argv) == 4 else "TraducteurJuridique.exe"
    try:
        fichiers, dossiers = ecrire(pathlib.Path(sys.argv[1]), programme, pathlib.Path(sys.argv[2]))
    except ErreurFichiers as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    print(f"{sys.argv[2]} : {fichiers} fichiers dans {dossiers} dossiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
