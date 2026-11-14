"""Les écrans de Windows 10 en français, redessinés pour les images d'aide.

Ce ne sont pas des captures d'écran : les fenêtres sont dessinées d'après de vraies captures de Windows 10,
avec les mêmes mots. Chaque fonction rend l'image de l'écran et les zones où il faut cliquer. Une zone est
(x, y, largeur, hauteur), à partir du coin en haut à gauche de l'écran dessiné.
"""
from __future__ import annotations

import math

from dessin import ACCENT, ECHELLE, LIEN, Toile
from PIL import Image

GRIS_VOLET = "#F2F2F2"
TEXTE = "#000000"
TEXTE_DOUX = "#5F5F5F"
BORD_CHAMP = "#8E8E8E"
BORD_FENETRE = "#6B6B6B"

#: Les quatre choix de la liste « Choisir l'origine des applications », dans l'ordre de Windows.
CHOIX = (
    "N'importe où",
    "N'importe où, mais m'indiquer s'il existe une application comparable dans le Microsoft Store",
    "N'importe où, mais m'avertir avant d'installer une application qui ne provient pas du Microsoft Store",
    "Le Microsoft Store uniquement (recommandé)",
)

MENU_APPLICATIONS = (
    ("Applications et fonctionnalités", "text_bullet_list_ltr"),
    ("Applications par défaut", "apps_list_detail"),
    ("Cartes hors connexion", "map"),
    ("Applications pour les sites web", "open"),
    ("Lecture de vidéos", "video"),
    ("Démarrage", "desktop_arrow_right"),
)

RUBRIQUES = (
    ("Système", "Affichage, son, notifications, alimentation", "laptop"),
    ("Périphériques", "Bluetooth, imprimantes, souris", "keyboard"),
    ("Téléphone", "Associer votre téléphone Android ou votre iPhone", "phone"),
    ("Réseau et Internet", "Wi-Fi, mode Avion, VPN", "globe"),
    ("Personnalisation", "Arrière-plan, écran de verrouillage, couleurs", "paint_brush"),
    ("Applications", "Désinstaller, valeurs par défaut, fonctionnalités facultatives", "apps_list"),
    ("Comptes", "Comptes, adresse e-mail, sync., travail, famille", "person"),
    ("Heure et langue", "Voix, région, date", "local_language"),
    ("Jeux", "Xbox Game Bar, captures, Mode Jeu", "games"),
    ("Options d'ergonomie", "Narrateur, loupe, contraste élevé", "accessibility"),
    ("Rechercher", "Rechercher mes fichiers, autorisations", "search"),
    ("Confidentialité", "Emplacement, caméra, microphone", "lock_closed"),
    ("Mise à jour et sécurité", "Windows Update, récupération, sauvegarde", "arrow_sync"),
)

#: Menu Démarrer : les applications (une lettre seule est un intertitre) et les vignettes.
APPLICATIONS = (
    ("A", None), ("Accessoires Windows", "dossier"), ("Alarmes et horloge", "clock_alarm"),
    ("C", None), ("Calculatrice", "calculator"), ("Calendrier", "calendar_ltr"), ("Caméra", "camera"),
    ("Cartes", "map"), ("Courrier", "mail"),
    ("E", None), ("Enregistreur vocal", "mic"),
    ("F", None), ("Films et TV", "movies_and_tv"),
    ("G", None), ("Groove Musique", "music_note_2"),
)
VIGNETTES = (
    ("Productivité", (("Courrier", "mail"), ("Calendrier", "calendar_ltr"), ("Microsoft Edge", "globe"),
                      ("Photos", "image"), ("Microsoft Store", "store_microsoft"), ("Météo", "weather_sunny"))),
    ("Explorer", (("Cartes", "map"), ("Films et TV", "movies_and_tv"), ("Calculatrice", "calculator"))),
)


# ---------------------------------------------------------------------- éléments communs
def logo_windows(toile: Toile, x, y, cote, couleur="#FFFFFF") -> None:
    """Les quatre carreaux du logo de Windows 10, dans un carré de côté ``cote``."""
    carreaux = (
        ((0, 0.14), (0.41, 0.085), (0.41, 0.475), (0, 0.475)),
        ((0.455, 0.078), (1, 0), (1, 0.475), (0.455, 0.475)),
        ((0, 0.52), (0.41, 0.52), (0.41, 0.915), (0, 0.86)),
        ((0.455, 0.52), (1, 0.52), (1, 1), (0.455, 0.922)),
    )
    for carreau in carreaux:
        toile.polygone([(x + px * cote, y + py * cote) for px, py in carreau], fond=couleur)


def boutons_de_fenetre(toile: Toile, droite, y=0.0, haut=32.0, pas=46.0) -> None:
    """Les trois boutons en haut à droite d'une fenêtre : réduire, agrandir, fermer."""
    cy = y + haut / 2
    cx = droite - pas * 2.5
    toile.ligne([(cx - 5, cy), (cx + 5, cy)], TEXTE)
    cx = droite - pas * 1.5
    toile.rect(cx - 5, cy - 5, 10, 10, bord=TEXTE)
    cx = droite - pas * 0.5
    toile.ligne([(cx - 5, cy - 5), (cx + 5, cy + 5)], TEXTE)
    toile.ligne([(cx - 5, cy + 5), (cx + 5, cy - 5)], TEXTE)


def champ_de_recherche(toile: Toile, x, y, large, invite: str) -> None:
    toile.rect(x, y, large, 34, fond="#FFFFFF", bord=BORD_CHAMP, ep=1.4)
    toile.texte(x + 12, y + 17, invite, couleur=TEXTE_DOUX)
    toile.icone(x + large - 18, y + 17, "search", 17, TEXTE_DOUX)


# ---------------------------------------------------------------------- menu Démarrer
def fond_d_ecran(large: float, haut: float) -> Image.Image:
    """Un fond bleu, plus clair vers la droite, qui rappelle celui de Windows 10."""
    sombre, clair = (7, 62, 160), (4, 150, 236)
    petit = Image.new("RGB", (96, 54))
    for j in range(54):
        for i in range(96):
            distance = math.hypot(i / 95 - 0.64, (j / 53 - 0.46) * 0.62)
            part = max(0.0, min(1.0, 1.0 - distance * 1.55))
            part = part * part * (3 - 2 * part)
            petit.putpixel((i, j), tuple(round(a + (b - a) * part) for a, b in zip(sombre, clair, strict=True)))
    return petit.resize((round(large * ECHELLE), round(haut * ECHELLE)), Image.Resampling.BICUBIC)


def menu_demarrer(large=1240, haut=660):
    """Le bureau, menu Démarrer ouvert. Zones : « demarrer » (le bouton) et « parametres » (la roue dentée)."""
    toile = Toile(large, haut)
    toile.coller(fond_d_ecran(large, haut))
    lueur = toile.calque()
    logo_windows(lueur, large * 0.70, haut * 0.20, 250, couleur=(150, 215, 255, 70))
    toile.coller(lueur.image)

    barre, rail = 46, 54
    bas = haut - barre  # haut de la barre des tâches
    menu_large, menu_haut = 640, 588
    sommet = bas - menu_haut
    toile.rect(0, sommet, menu_large, menu_haut, fond="#1F2B36")

    # colonne de gauche : de bas en haut, Marche/Arrêt, Paramètres, Images, Documents, le compte
    toile.icone(rail / 2, sommet + 26, "navigation", 20, "#FFFFFF")
    boutons = {}
    for rang, icone in enumerate(("power", "settings", "image", "document", "person_circle")):
        cy = bas - 25 - 50 * rang
        toile.icone(rail / 2, cy, icone, 21, "#FFFFFF")
        boutons[icone] = (3, cy - 22, rail - 6, 44)

    # liste des applications
    cy = sommet + 32
    for nom, icone in APPLICATIONS:
        if icone is None:
            toile.texte(70, cy, nom, couleur="#FFFFFF")
        elif icone == "dossier":
            toile.icone(79, cy, "folder", 25, "#F6C445", "Filled")
            toile.icone(292, cy, "chevron_down", 13, "#FFFFFF")
        else:
            toile.rect(66, cy - 13, 26, 26, fond=ACCENT)
            toile.icone(79, cy, icone, 17, "#FFFFFF")
        if icone is not None:
            toile.texte(104, cy, nom, taille=14.5, couleur="#FFFFFF")
        cy += 36

    # vignettes
    y = sommet + 34
    for titre, vignettes in VIGNETTES:
        toile.texte(318, y, titre, taille=14, couleur="#E6E9EC")
        y += 22
        for rang, (nom, icone) in enumerate(vignettes):
            vx, vy = 318 + (rang % 3) * 102, y + (rang // 3) * 102
            toile.rect(vx, vy, 98, 98, fond="#374550")
            toile.icone(vx + 49, vy + 42, icone, 34, "#FFFFFF")
            toile.texte(vx + 8, vy + 85, nom, taille=12, couleur="#FFFFFF")
        y += math.ceil(len(vignettes) / 3) * 102 + 26

    # barre des tâches
    toile.rect(0, bas, large, barre, fond="#17212B")
    toile.rect(0, bas, rail, barre, fond="#2C3A46")
    logo_windows(toile, rail / 2 - 9.5, bas + barre / 2 - 9.5, 19)
    toile.rect(rail, bas + 5, 330, barre - 10, fond="#FFFFFF")
    toile.icone(rail + 20, bas + barre / 2, "search", 18, "#3B3B3B")
    toile.texte(rail + 42, bas + barre / 2, "Taper ici pour rechercher", couleur="#3B3B3B")
    epingles = (("globe", "#FFFFFF", "Regular"), ("folder", "#F6C445", "Filled"),
                ("store_microsoft", "#FFFFFF", "Regular"), ("mail", "#FFFFFF", "Regular"))
    for rang, (icone, couleur, style) in enumerate(epingles):
        toile.icone(rail + 370 + rang * 52, bas + barre / 2, icone, 23, couleur, style)

    return toile.image, {"demarrer": (3, bas + 3, rail - 6, barre - 6), "parametres": boutons["settings"]}


# ---------------------------------------------------------------------- Paramètres
def accueil_des_parametres(large=844, haut=606):
    """La fenêtre « Paramètres » quand elle s'ouvre. Zones : une par rubrique, à son nom."""
    toile = Toile(large, haut)
    toile.texte(14, 16, "Paramètres", taille=12.5)
    boutons_de_fenetre(toile, large)
    toile.texte(large / 2, 80, "Paramètres Windows", "Light", 26, ancre="mm")
    champ_de_recherche(toile, (large - 330) / 2, 114, 330, "Rechercher un paramètre")
    marge, colonnes, pas_y = 34, 4, 100
    pas_x = (large - 2 * marge) / colonnes
    zones = {}
    for rang, (nom, detail, icone) in enumerate(RUBRIQUES):
        x, y = marge + (rang % colonnes) * pas_x, 196 + (rang // colonnes) * pas_y
        toile.icone(x + 22, y + 22, icone, 31, ACCENT)
        toile.texte(x + 54, y + 11, nom)
        toile.paragraphe(x + 54, y + 22, detail, pas_x - 62, taille=12, couleur=TEXTE_DOUX, interligne=15.5)
        zones[nom] = (x + 2, y - 8, pas_x - 6, 84)
    toile.rect(0, 0, large, haut, bord=BORD_FENETRE)
    return toile.image, zones


def _volet_applications(toile: Toile, large, haut) -> dict:
    """Le menu de gauche de la rubrique « Applications ». Rend la zone de chaque ligne du menu."""
    toile.rect(0, 0, large, haut, fond=GRIS_VOLET)
    toile.icone(24, 16, "arrow_left", 17, TEXTE)
    toile.texte(58, 16, "Paramètres", taille=12.5)
    toile.icone(30, 76, "home", 19, TEXTE)
    toile.texte(56, 76, "Accueil")
    champ_de_recherche(toile, 16, 100, large - 32, "Rechercher un paramètre")
    toile.texte(20, 171, "Applications", "Bold")
    zones = {}
    for rang, (nom, icone) in enumerate(MENU_APPLICATIONS):
        cy = 222 + 48 * rang
        if cy + 24 > haut:  # pas de ligne coupée en bas d'une fenêtre montrée en partie
            break
        if rang == 0:  # la page ouverte
            toile.rect(0, cy - 12, 5, 24, fond=ACCENT)
        toile.icone(30, cy, icone, 19, TEXTE)
        toile.texte(56, cy, nom)
        zones[nom] = (10, cy - 20, large - 20, 40)
    return zones


def menu_des_applications(fond: str, large=380, haut=520):
    """Le côté gauche de la rubrique « Applications » ; la fenêtre continue à droite. Zones : les lignes du menu."""
    toile = Toile(large, haut)
    zones = _volet_applications(toile, 320, haut)
    toile.texte(344, 82, "Applications et fonctionnalités", "Light", 28)
    toile.texte(344, 130, "Choisir l'origine des applications", taille=20)
    toile.ligne([(large, 0.5), (0.5, 0.5), (0.5, haut - 0.5), (large, haut - 0.5)], BORD_FENETRE)
    toile.fondu(326, 0, large - 326, haut, fond, vers="droite")
    return toile.image, zones


def page_des_applications(fond: str, ouverte: bool, large=1180, haut=318):
    """Le haut de la page « Applications et fonctionnalités » ; la fenêtre continue en bas.

    Zones : « champ » (la liste fermée) et, si ``ouverte``, « choix » (la ligne « N'importe où »).
    """
    toile = Toile(large, haut)
    volet = 320
    _volet_applications(toile, volet, haut)
    boutons_de_fenetre(toile, large)
    x = volet + 24
    toile.texte(x, 82, "Applications et fonctionnalités", "Light", 28)
    toile.texte(x, 130, "Choisir l'origine des applications", taille=20)
    toile.texte(x, 173, "L'installation d'applications uniquement à partir du Microsoft Store")
    toile.texte(x, 193, "contribue à protéger votre appareil.")
    # la liste fermée montre le choix en vigueur : le Microsoft Store uniquement
    cy, pas = 232, 32
    champ = (x, cy - 16, toile.largeur(CHOIX[3]) + 52, 32)
    toile.rect(*champ, fond="#FFFFFF", bord=BORD_CHAMP, ep=1.6)
    toile.texte(x + 11, cy, CHOIX[3])
    toile.icone(x + champ[2] - 19, cy + 1, "chevron_down", 15, TEXTE)
    toile.texte(x, 298, "Applications et fonctionnalités", taille=20)
    toile.texte(x, 351, "Fonctionnalités facultatives", couleur=LIEN)
    zones = {"champ": champ}
    if ouverte:
        # la liste s'ouvre par-dessus la page, sa ligne en vigueur à la place du champ
        gauche, liste_large = x - 12, max(toile.largeur(choix) for choix in CHOIX) + 24
        sommet, liste_haut = cy - pas / 2 - 3 * pas - 4, 4 * pas + 8
        toile.ombre(gauche, sommet, liste_large, liste_haut, flou=7, descente=3, force=60)
        toile.rect(gauche, sommet, liste_large, liste_haut, fond="#F2F2F2", bord="#C6C6C6")
        for rang, choix in enumerate(CHOIX):
            y = sommet + 4 + rang * pas
            if rang == 3:  # le choix en vigueur
                toile.rect(gauche + 1, y, liste_large - 2, pas, fond="#A9D1EF")
            if rang == 0:  # la ligne sous la souris
                toile.rect(gauche + 1, y, liste_large - 2, pas, fond="#DADADA")
            toile.texte(gauche + 12, y + pas / 2, choix)
        zones["choix"] = (gauche + 4, sommet + 6, liste_large - 8, pas - 4)
    toile.ligne([(0.5, haut), (0.5, 0.5), (large - 0.5, 0.5), (large - 0.5, haut)], BORD_FENETRE)
    toile.fondu(0, haut - 34, large, 34, fond)
    return toile.image, zones


# ---------------------------------------------------------------------- Explorateur de fichiers
def _icone_d_installeur(toile: Toile, x, y) -> None:
    """La petite icône d'un fichier .msi : une boîte et un disque."""
    toile.rect(x + 1, y + 5, 15, 13, fond="#D9B37A", bord="#9C7A45")
    toile.polygone([(x + 1, y + 5), (x + 4, y + 1.5), (x + 13, y + 1.5), (x + 16, y + 5)], fond="#EBCB98",
                   bord="#9C7A45")
    toile.disque(x + 14, y + 14, 5.6, fond="#DDE6EE", bord="#5D7386")
    toile.disque(x + 14, y + 14, 1.5, fond="#5D7386")


def _taille_en_ko(octets: int) -> str:
    """La taille comme l'écrit l'Explorateur : en Ko, arrondie au-dessus, les milliers séparés."""
    return f"{math.ceil(octets / 1024):,} Ko".replace(",", " ")


def _taille_en_mo(octets: int) -> str:
    return f"{math.floor(octets / 1024 / 1024 * 10) / 10:.1f} Mo".replace(".", ",")


def dossier_telechargements(fichier: str, octets: int, date: str, large=1040, haut=420):
    """Le dossier « Téléchargements » avec le fichier de l'installeur. Zones : « fichier » (la ligne), « nom »."""
    toile = Toile(large, haut)
    gris = "#6D6D6D"
    # barre de titre et onglets
    toile.icone(18, 16, "folder", 18, "#F6C445", "Filled")
    toile.ligne([(34, 8), (34, 24)], "#C9C9C9")
    toile.texte(44, 16, "Téléchargements", taille=12.5)
    boutons_de_fenetre(toile, large)
    toile.rect(1, 32, 64, 26, fond="#1979CA")
    toile.texte(33, 45, "Fichier", taille=13, couleur="#FFFFFF", ancre="mm")
    for rang, nom in enumerate(("Accueil", "Partage", "Affichage")):
        toile.texte(98 + rang * 74, 45, nom, taille=13, ancre="mm")
    toile.ligne([(0, 58.5), (large, 58.5)], "#DADADA")
    # flèches, adresse et recherche
    toile.icone(22, 79, "arrow_left", 17, "#9A9A9A")
    toile.icone(52, 79, "arrow_right", 17, "#9A9A9A")
    toile.icone(86, 79, "arrow_up", 16, "#4A4A4A")
    adresse, adresse_large = 106, large - 408
    toile.rect(adresse, 66, adresse_large, 26, fond="#FFFFFF", bord="#D9D9D9")
    toile.icone(adresse + 16, 79, "arrow_download", 16, "#2C82D8", "Filled")
    x = adresse + 32
    for morceau in ("Ce PC", "Téléchargements"):
        toile.icone(x + 5, 79.5, "chevron_right", 10, gris)
        x += 14 + toile.texte(x + 14, 79, morceau, taille=13) + 6
    toile.icone(adresse + adresse_large - 14, 79.5, "chevron_down", 11, gris)
    toile.rect(adresse + adresse_large + 1, 66, 28, 26, fond="#FFFFFF", bord="#D9D9D9")
    toile.icone(adresse + adresse_large + 15, 79, "arrow_clockwise", 14, gris)
    recherche = adresse + adresse_large + 40
    toile.rect(recherche, 66, large - recherche - 12, 26, fond="#FFFFFF", bord="#D9D9D9")
    toile.texte(recherche + 10, 79, "Rechercher dans : Téléchargements", taille=12.5, couleur="#7A7A7A")
    toile.icone(large - 26, 79, "search", 14, gris)
    # volet de gauche
    volet = 196
    emplacements = (
        ("Accès rapide", "star", "#3A8EE6", "Filled", 0, 120), ("Bureau", "desktop", "#2C82D8", "Filled", 1, 147),
        ("Téléchargements", "arrow_download", "#2C82D8", "Filled", 1, 174),
        ("Documents", "document", "#5B6B7B", "Regular", 1, 201), ("Images", "image", "#5B6B7B", "Regular", 1, 228),
        ("Ce PC", "desktop", "#4A4A4A", "Regular", 0, 268),
    )
    for nom, icone, couleur, style, retrait, cy in emplacements:
        if nom == "Téléchargements":
            toile.rect(0, cy - 13, volet, 26, fond="#CCE8FF")
        toile.icone(22 + retrait * 18, cy, icone, 17, couleur, style)
        toile.texte(38 + retrait * 18, cy, nom, taille=13.5)
    toile.ligne([(volet + 0.5, 100), (volet + 0.5, haut - 26)], "#E5E5E5")
    # colonnes
    colonnes = (("Nom", volet + 24), ("Modifié le", volet + 392), ("Type", volet + 546), ("Taille", large - 78))
    for rang, (nom, cx) in enumerate(colonnes):
        toile.texte(cx, 112, nom, taille=13, couleur="#4C607A")
        if rang:
            toile.ligne([(cx - 10.5, 102), (cx - 10.5, 123)], "#E5E5E5")
    # le groupe « Aujourd'hui » et le fichier, sélectionné
    toile.icone(volet + 22, 143.5, "chevron_down", 11, gris)
    fin = volet + 34 + toile.texte(volet + 34, 143, "Aujourd'hui (1)", taille=13.5, couleur="#1E3287")
    toile.ligne([(fin + 10, 143.5), (large - 16, 143.5)], "#E2E2E2")
    ligne = (volet + 12, 158, large - volet - 24, 26)
    cy = ligne[1] + 13
    toile.rect(*ligne, fond="#CCE8FF", bord="#99D1FF")
    _icone_d_installeur(toile, volet + 20, ligne[1] + 3)
    nom_large = toile.texte(volet + 46, cy, fichier, taille=13.5)
    toile.texte(volet + 392, cy, date, taille=13.5, couleur="#4A4A4A")
    toile.texte(volet + 546, cy, "Package Windows Installer", taille=13.5, couleur="#4A4A4A")
    toile.texte(large - 22, cy, _taille_en_ko(octets), taille=13.5, couleur="#4A4A4A", ancre="rm")
    # barre d'état
    toile.ligne([(0, haut - 26.5), (large, haut - 26.5)], "#EDEDED")
    toile.texte(12, haut - 13, "1 élément", taille=12.5, couleur="#4A4A4A")
    toile.texte(86, haut - 13, f"1 élément sélectionné  {_taille_en_mo(octets)}", taille=12.5, couleur="#4A4A4A")
    toile.rect(0, 0, large, haut, bord=BORD_FENETRE)
    return toile.image, {"fichier": ligne, "nom": (volet + 46, ligne[1], nom_large, 26)}


def fenetre_bleue(toile: Toile, x, y, large=172, haut=106) -> None:
    """Une vignette de la fenêtre « Windows a protégé votre ordinateur », pour la reconnaître."""
    toile.rect(x, y, large, haut, fond="#0B63C5")
    toile.texte(x + 12, y + 22, "Windows a protégé", taille=13.5, couleur="#FFFFFF")
    toile.texte(x + 12, y + 39, "votre ordinateur", taille=13.5, couleur="#FFFFFF")
    lien_large = toile.texte(x + 12, y + 57, "Informations complémentaires", taille=9, couleur="#FFFFFF")
    toile.ligne([(x + 12, y + 63.5), (x + 12 + lien_large, y + 63.5)], "#FFFFFF", 0.6)
    toile.rect(x + large - 72, y + haut - 26, 60, 16, fond="#FFFFFF")
