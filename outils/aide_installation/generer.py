#!/usr/bin/env python3
"""Dessine les images d'aide à l'installation sous Windows 10 (dossier docs/aide-installation).

Emploi, depuis le dossier du projet, avec Python 3.11 ou plus récent :

    python -m pip install -r outils/aide_installation/requirements.txt
    python outils/aide_installation/generer.py [dossier_de_sortie]

Ce script ne fait pas partie de l'application. Il sert quand Windows refuse d'ouvrir l'installeur avec le
message « L'application que vous tentez d'installer n'est pas une application vérifiée par Microsoft » : les
images montrent, en quatre étapes, le réglage de Windows à changer. Il écrit une image par étape et une
planche qui les réunit.

Ce sont des dessins et non des captures d'écran : les fenêtres de Windows sont redessinées dans
``ecrans.py``, les repères rouges et le texte avec ``dessin.py``. Les polices sont téléchargées la première
fois (voir ``polices.py``) : il faut alors une connexion à Internet.
"""
from __future__ import annotations

import pathlib
import re
import sys
from collections.abc import Callable
from typing import NamedTuple

DEPOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEPOT))

import ecrans  # noqa: E402
from dessin import ECHELLE, Toile, cadre, curseur, etiquette, pastille  # noqa: E402
from PIL import Image  # noqa: E402

from traducteur import __version__  # noqa: E402

#: Le fichier montré à l'étape 4. L'Explorateur n'écrit pas la fin du nom (« .msi »). La taille, en octets,
#: est celle de l'installeur 0.5.3 ; la date n'est qu'un exemple.
INSTALLEUR = f"Traducteur-juridique-{__version__}"
TAILLE_DE_L_INSTALLEUR = 23_507_045
DATE_D_EXEMPLE = "14/11/2026 10:24"

FOND = "#E9EEF4"
MARINE = "#1B3A5C"
ENCRE = "#111827"
LARGE, HAUT = 1280, 700  # place d'un écran, sous le bandeau de la consigne
BANDEAU = 100
NOTE = "Dessin d'après Windows 10 en français"


def _place(zone, x0, y0):
    """La zone d'un écran, une fois cet écran collé en (x0, y0)."""
    x, y, large, haut = zone
    return x0 + x, y0 + y, large, haut


# ---------------------------------------------------------------------- les quatre écrans
def ecran_1() -> Toile:
    toile = Toile(LARGE, HAUT, FOND)
    image, zones = ecrans.menu_demarrer()
    toile.coller(image, 20, 20)
    for nom, chiffre in (("demarrer", "1"), ("parametres", "2")):
        x, y, large, haut = _place(zones[nom], 20, 20)
        cadre(toile, x, y, large, haut)
        pastille(toile, x + large + 3, y - 1, chiffre, 13)
    return toile


def ecran_2() -> Toile:
    toile = Toile(LARGE, HAUT, FOND)
    image, zones = ecrans.accueil_des_parametres()
    toile.ombre(16, 46, 844, 606)
    toile.coller(image, 16, 46)
    x, y, large, haut = _place(zones["Applications"], 16, 46)
    cadre(toile, x, y, large, haut)
    pastille(toile, x + large, y, "1", 13)
    toile.icone(880, 350, "chevron_right", 26, "#8A96A6")
    image, zones = ecrans.menu_des_applications(FOND)
    toile.coller(image, 900, 90)
    x, y, large, haut = _place(zones["Applications et fonctionnalités"], 900, 90)
    cadre(toile, x, y, large, haut)
    pastille(toile, x + large, y, "2", 13)
    return toile


def ecran_3() -> Toile:
    toile = Toile(LARGE, HAUT, FOND)
    # en haut la liste fermée, en bas la même fenêtre une fois la liste ouverte
    image, zones = ecrans.page_des_applications(FOND, ouverte=False)
    toile.coller(image, 50, 22)
    x, y, large, haut = _place(zones["champ"], 50, 22)
    cadre(toile, x - 6, y - 6, large + 12, haut + 12)
    pastille(toile, x + large + 30, y + haut / 2, "1")
    image, zones = ecrans.page_des_applications(FOND, ouverte=True)
    toile.coller(image, 50, 362)
    x, y, large, haut = _place(zones["choix"], 50, 362)
    cadre(toile, x, y, large, haut)
    pastille(toile, x + large + 28, y + haut / 2, "2")
    curseur(toile, x + 190, y + 12)
    return toile


def ecran_4() -> Toile:
    toile = Toile(LARGE, HAUT, FOND)
    image, zones = ecrans.dossier_telechargements(INSTALLEUR, TAILLE_DE_L_INSTALLEUR, DATE_D_EXEMPLE)
    toile.ombre(120, 34, 1040, 420)
    toile.coller(image, 120, 34)
    x, y, large, haut = _place(zones["fichier"], 120, 34)
    cadre(toile, x - 3, y - 3, large + 6, haut + 6)
    x, y, large, haut = _place(zones["nom"], 120, 34)
    curseur(toile, x + large + 16, y + 12)
    etiquette(toile, x + large + 44, y + 36, "double-clic")
    # ce qui peut arriver ensuite : la fenêtre bleue de Windows
    x, y = 120, 506
    toile.rect(x, y, 1040, 150, fond="#FFFFFF", bord="#C9D3DF", ep=1.2, rayon=10)
    ecrans.fenetre_bleue(toile, x + 22, y + 22)
    toile.texte(x + 220, y + 40, "Si une fenêtre bleue « Windows a protégé votre ordinateur » apparaît :", "Bold", 18,
                ENCRE)
    toile.texte(x + 220, y + 78, "cliquer sur « Informations complémentaires »,", taille=18, couleur=ENCRE)
    toile.texte(x + 220, y + 108, "puis sur « Exécuter quand même ».", taille=18, couleur=ENCRE)
    return toile


class Etape(NamedTuple):
    ecran: Callable[[], Toile]
    consigne: str  # {1} et {2} sont les numéros rouges, les mêmes que sur l'écran
    detail: str
    fichier: str


ETAPES = (
    Etape(ecran_1, "Cliquer sur le bouton Démarrer {1}, puis sur la roue dentée {2}.",
          "La fenêtre « Paramètres » s'ouvre.", "etape-1-ouvrir-parametres.png"),
    Etape(ecran_2, "Cliquer sur « Applications » {1}, puis sur « Applications et fonctionnalités » {2}.",
          "Souvent, la page « Applications et fonctionnalités » est déjà ouverte : passer alors à l'étape 3.",
          "etape-2-applications.png"),
    Etape(ecran_3, "Tout en haut, cliquer sur la liste {1}, puis choisir « N'importe où » {2}.",
          "La liste est sous le titre « Choisir l'origine des applications ». Il n'y a rien à enregistrer.",
          "etape-3-n-importe-ou.png"),
    Etape(ecran_4, "Fermer la fenêtre « Paramètres », puis ouvrir de nouveau le fichier de l'installeur.",
          "Le fichier est souvent dans le dossier « Téléchargements ». Ensuite : Suivant, Installer, Terminer.",
          "etape-4-relancer-l-installeur.png"),
)


# ---------------------------------------------------------------------- consigne d'une étape
def _largeur_de_consigne(toile: Toile, morceaux: list[str], taille: float) -> float:
    """``morceaux`` alterne un texte et un numéro : les rangs impairs sont les numéros."""
    return sum(taille * 1.2 if rang % 2 else toile.largeur(morceau, "Semibold", taille)
               for rang, morceau in enumerate(morceaux))


def bandeau(toile: Toile, x, y, large, haut, numero: int, etape: Etape, k=1.0, note="") -> None:
    """Le numéro de l'étape, la consigne et sa précision. ``k`` réduit le tout pour la planche."""
    toile.rect(x, y, large, haut, fond="#FFFFFF")
    insigne_large, insigne_haut = 112 * k, 40 * k
    toile.rect(x + 26 * k, y + (haut - insigne_haut) / 2, insigne_large, insigne_haut, fond=MARINE,
               rayon=insigne_haut / 2)
    toile.texte(x + 26 * k + insigne_large / 2, y + haut / 2 - 1, f"Étape {numero}", "Bold", 19 * k, "#FFFFFF", "mm")
    droite = x + large - 24 * k
    if note:
        droite -= toile.texte(droite, y + haut / 2, note, taille=13 * k, couleur="#8A94A3", ancre="rm") + 20 * k
    gauche = x + 26 * k + insigne_large + 24 * k
    # le texte est réduit s'il ne tient pas sur une ligne
    morceaux = re.split(r"\{(\d)\}", etape.consigne)
    taille = 25 * k
    while _largeur_de_consigne(toile, morceaux, taille) > droite - gauche and taille > 15 * k:
        taille *= 0.97
    taille_du_detail = 17 * k
    while toile.largeur(etape.detail, taille=taille_du_detail) > droite - gauche and taille_du_detail > 11 * k:
        taille_du_detail *= 0.97
    cx, cy = gauche, y + haut * 0.36
    for rang, morceau in enumerate(morceaux):
        if rang % 2:
            pastille(toile, cx + taille * 0.56, cy + 0.5, morceau, taille / 2)
            cx += taille * 1.2
        else:
            cx += toile.texte(cx, cy, morceau, "Semibold", taille, ENCRE)
    toile.texte(gauche, y + haut * 0.71, etape.detail, taille=taille_du_detail, couleur="#4B5563")


def image_d_etape(numero: int) -> Image.Image:
    etape = ETAPES[numero - 1]
    toile = Toile(LARGE, BANDEAU + HAUT, FOND)
    toile.coller(etape.ecran().image, 0, BANDEAU)
    bandeau(toile, 0, 0, LARGE, BANDEAU, numero, etape, note=NOTE)
    toile.ligne([(0, BANDEAU), (LARGE, BANDEAU)], "#CBD3DD")
    return toile.sortie(1.5)


def planche() -> Image.Image:
    """Les quatre étapes sur une seule image, deux par rangée."""
    marge, case_large, bande = 40, 960, 92
    ecran_haut = round(HAUT * case_large / LARGE)
    case_haut = bande + ecran_haut
    tete, entre, pied = 150, 36, 84
    toile = Toile(2 * case_large + 3 * marge, tete + 2 * case_haut + entre + pied, "#F3F5F8")
    toile.texte(marge, 58, "Windows 10 : installer une application qui ne vient pas du Microsoft Store", "Bold", 36,
                ENCRE)
    toile.texte(marge, 108, "À faire une seule fois, quand Windows dit que l'application n'est pas "
                            "« vérifiée par Microsoft ».", taille=22, couleur="#4B5563")
    for rang, etape in enumerate(ETAPES):
        x, y = marge + (rang % 2) * (case_large + marge), tete + (rang // 2) * (case_haut + entre)
        toile.ombre(x, y, case_large, case_haut, flou=10, descente=4, force=40)
        ecran = etape.ecran().image.resize((case_large * ECHELLE, ecran_haut * ECHELLE), Image.Resampling.LANCZOS)
        toile.coller(ecran, x, y + bande)
        bandeau(toile, x, y, case_large, bande, rang + 1, etape, k=0.84)
        toile.ligne([(x, y + bande), (x + case_large, y + bande)], "#CBD3DD")
        toile.rect(x, y, case_large, case_haut, bord="#B9C3CF")
    toile.texte(marge, toile.haut - pied / 2, f"{NOTE}. Selon la version de Windows, certains mots peuvent changer "
                                              "un peu.", taille=19, couleur="#6B7280")
    return toile.sortie()


def generer(sortie: pathlib.Path) -> None:
    sortie.mkdir(parents=True, exist_ok=True)
    images = {etape.fichier: image_d_etape(numero) for numero, etape in enumerate(ETAPES, 1)}
    images["toutes-les-etapes.png"] = planche()
    for nom, image in images.items():
        image.save(sortie / nom, optimize=True)
        print("écrit :", sortie / nom)


if __name__ == "__main__":
    generer(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEPOT / "docs" / "aide-installation")
