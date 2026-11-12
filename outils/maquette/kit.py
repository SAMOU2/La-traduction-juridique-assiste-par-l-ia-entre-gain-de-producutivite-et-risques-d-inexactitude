"""Outils de dessin de la maquette : écriture du SVG, icônes, éléments communs aux écrans."""
from __future__ import annotations

import contextlib
import re
from xml.sax.saxutils import escape

from mesure import est_arabe, largeur

POLICE = ("'Segoe UI', 'Selawik', 'Helvetica Neue', Helvetica, 'Noto Sans Arabic', 'Geeza Pro', Arial, "
          "'Liberation Sans', 'Noto Sans', sans-serif")

# ------------------------------------------------------------------ couleurs
FOND = "#F4F6F9"
SURFACE = "#FFFFFF"
FILET = "#E1E6EE"
FILET_DOUX = "#EDF0F5"
T1 = "#101828"  # texte principal
T2 = "#344054"  # texte courant secondaire
T3 = "#667085"  # légendes
T4 = "#98A2B3"  # texte estompé
BLEU = "#2251CC"
BLEU_FONCE = "#1A3FA6"
BLEU_50 = "#F1F5FF"
BLEU_100 = "#DFE8FF"
BLEU_200 = "#C2D3FF"
AMBRE = "#B54708"
AMBRE_50 = "#FFFAEB"
AMBRE_200 = "#FEDF89"
VERT = "#067647"
VERT_50 = "#ECFDF3"
VERT_200 = "#ABEFC6"
MARINE = "#0F1F3D"
GRIS_50 = "#F7F9FB"
GRIS_100 = "#F0F3F7"

# ------------------------------------------------------------------ géométrie commune
L, H = 1520, 972  # dessin
FX, FY, FL, FH = 40, 36, 1440, 892  # fenêtre (barre de titre comprise)
CY = FY + 32  # haut de la zone de l'application
X0, X1 = FX + 24, FX + FL - 24  # bords du contenu
BAS = FY + FH  # bas de la fenêtre

ICONES = {
    "loupe": '<circle cx="7" cy="7" r="4.25"/><path d="M10.2 10.2 13.5 13.5"/>',
    "echange": '<path d="M2.5 5.5H13M10.5 3 13 5.5 10.5 8M13.5 10.5H3M5.5 8 3 10.5 5.5 13"/>',
    "fleche": '<path d="M3 8h10M9.5 4.5 13 8l-3.5 3.5"/>',
    "chevron-d": '<path d="M6 3.5 10.5 8 6 12.5"/>',
    "chevron-g": '<path d="M10 3.5 5.5 8 10 12.5"/>',
    "chevron-b": '<path d="M3.5 6 8 10.5 12.5 6"/>',
    "croix": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
    "copier": ('<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
               '<path d="M10.5 5.5V4A1.5 1.5 0 0 0 9 2.5H4A1.5 1.5 0 0 0 2.5 4v5A1.5 1.5 0 0 0 4 10.5h1.5"/>'),
    "document": ('<path d="M9.5 2.5h-5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1v-7z"/>'
                 '<path d="M9.5 2.5v3h3M6 8.5h4M6 11h4"/>'),
    "importer": '<path d="M8 2.5v8M4.8 7.4 8 10.6l3.2-3.2M3 13.5h10"/>',
    "exporter": '<path d="M8 10.5v-8M4.8 5.7 8 2.5l3.2 3.2M3 13.5h10"/>',
    "alerte": '<circle cx="8" cy="8" r="5.75"/><path d="M8 5v3.4M8 10.9v.1"/>',
    "lien": ('<path d="M9.5 3H13v3.5M13 3 7.5 8.5M11 9.5V12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2.5"/>'),
    "texte": '<path d="M3 4.5h10M3 8h10M3 11.5h6"/>',
    "fiche": '<rect x="3" y="2.5" width="10" height="11" rx="1.5"/><path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3"/>',
    "balance": ('<path d="M8 2.8v10.4M5.5 13.2h5M3.4 4.6h9.2M3.4 4.6 1.8 8.6h3.2zM12.6 4.6 11 8.6h3.2z'
                'M1.8 8.6a1.6 1.6 0 0 0 3.2 0M11 8.6a1.6 1.6 0 0 0 3.2 0"/>'),
}

_RLE, _PDF = "&#x202B;", "&#x202C;"
_ATTRIBUTS = {"taille": "font-size", "poids": "font-weight", "couleur": "fill", "ancre": "text-anchor",
              "espacement": "letter-spacing", "style": "font-style", "opacite": "opacity", "trait": "stroke",
              "epaisseur": "stroke-width", "rayon": "rx", "decoration": "text-decoration"}


def n(valeur: float) -> str:
    """Nombre écrit sans zéros inutiles."""
    texte = f"{valeur:.2f}".rstrip("0").rstrip(".")
    return "0" if texte in ("-0", "") else texte


def _attributs(valeurs: dict) -> str:
    morceaux = []
    for cle, valeur in valeurs.items():
        if valeur is None:
            continue
        nom = _ATTRIBUTS.get(cle, cle.replace("_", "-"))
        if isinstance(valeur, (int, float)):
            valeur = n(valeur)
        morceaux.append(f'{nom}="{valeur}"')
    return (" " + " ".join(morceaux)) if morceaux else ""


class Dessin:
    """Accumule les lignes d'un fichier SVG, avec indentation."""

    def __init__(self) -> None:
        self.lignes: list[str] = []
        self.niveau = 1
        self.icones: list[str] = []  # icônes employées, dans l'ordre de leur premier emploi

    def brut(self, texte: str) -> None:
        self.lignes.append("  " * self.niveau + texte)

    def vide(self) -> None:
        self.lignes.append("")

    def c(self, texte: str) -> None:
        self.brut(f"<!-- {texte} -->")

    def titre(self, texte: str) -> None:
        self.vide()
        self.brut(f"<!-- ═══ {texte} ═══ -->")

    @contextlib.contextmanager
    def g(self, **attributs):
        self.brut(f"<g{_attributs(attributs)}>")
        self.niveau += 1
        yield
        self.niveau -= 1
        self.brut("</g>")

    def rect(self, x, y, large, h, r=None, **a) -> None:
        self.brut(f'<rect x="{n(x)}" y="{n(y)}" width="{n(large)}" height="{n(h)}"'
                  + (f' rx="{n(r)}"' if r else "") + _attributs(a) + "/>")

    def ligne(self, x1, y1, x2, y2, **a) -> None:
        a.setdefault("trait", FILET_DOUX)
        self.brut(f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}"' + _attributs(a) + "/>")

    def cercle(self, cx, cy, r, **a) -> None:
        self.brut(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}"' + _attributs(a) + "/>")

    def chemin(self, d, **a) -> None:
        self.brut(f'<path d="{d}"' + _attributs(a) + "/>")

    def icone(self, nom, x, y, t=16, couleur=T3, e=1.5) -> None:
        if nom not in self.icones:
            self.icones.append(nom)
        self.brut(f'<use xlink:href="#i-{nom}" x="{n(x)}" y="{n(y)}" width="{n(t)}" height="{n(t)}" '
                  f'stroke="{couleur}" stroke-width="{n(e)}"/>')

    def texte(self, x, y, contenu, arabe=None, **a) -> None:
        """Écrit une ligne de texte. ``contenu`` : chaîne, ou liste de chaînes et de couples (chaîne, style)."""
        parties = [contenu] if isinstance(contenu, (str, tuple)) else list(contenu)
        brut = "".join(p if isinstance(p, str) else p[0] for p in parties)
        if arabe is None:
            arabe = est_arabe(brut)
        interieur = ""
        for partie in parties:
            if isinstance(partie, str):
                interieur += escape(partie)
            else:
                interieur += f"<tspan{_attributs(partie[1])}>{escape(partie[0])}</tspan>"
        if arabe:
            interieur = _RLE + interieur + _PDF
        self.brut(f'<text x="{n(x)}" y="{n(y)}"' + _attributs(a) + f">{interieur}</text>")


# ------------------------------------------------------------------ texte : coupe des lignes
#: Signes qui ne commencent jamais une ligne en français : ils restent collés au mot qui précède.
_COLLES_AU_PRECEDENT = {";", ":", "?", "!", "»"}


def _mots(texte: str) -> list[str]:
    """Mots d'un texte ; un signe double (« ; », « : »…) reste avec son mot."""
    mots: list[str] = []
    for mot in texte.split():
        if mots and (mot in _COLLES_AU_PRECEDENT or mots[-1].endswith("«")):
            mots[-1] += " " + mot
        else:
            mots.append(mot)
    return mots


def couper(texte: str, largeur_max: float, taille: float, poids: int = 400) -> list[str]:
    """Coupe un texte en lignes qui tiennent dans ``largeur_max`` pixels."""
    lignes, courante = [], ""
    for mot in _mots(texte):
        essai = f"{courante} {mot}".strip()
        if courante and largeur(essai, taille, poids) > largeur_max:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    if courante:
        lignes.append(courante)
    return lignes


def couper_riche(segments: list[tuple[str, dict]], largeur_max: float, taille: float) -> list[list]:
    """Coupe un texte fait de segments stylés. Rend, pour chaque ligne, une liste de chaînes et de couples."""
    mots: list[list[tuple[str, dict]]] = []
    courant: list[tuple[str, dict]] = []
    for texte, style in segments:
        for morceau in re.split(r"(\s+)", texte):
            if not morceau:
                continue
            if morceau.isspace():
                if courant:
                    mots.append(courant)
                    courant = []
            else:
                courant.append((morceau, style))
    if courant:
        mots.append(courant)
    # Un signe double (« ; », « : »…) reste sur la ligne du mot qui précède.
    colles: list[list[tuple[str, dict]]] = []
    for mot in mots:
        seul = "".join(texte for texte, _ in mot)
        if colles and (seul in _COLLES_AU_PRECEDENT or colles[-1][-1][0].endswith("«")):
            colles[-1] = [*colles[-1], (" ", {}), *mot]
        else:
            colles.append(mot)
    mots = colles

    espace = largeur(" ", taille)
    lignes: list[list[list[tuple[str, dict]]]] = []
    ligne: list[list[tuple[str, dict]]] = []
    occupe = 0.0
    for mot in mots:
        large = sum(largeur(texte, taille, style.get("poids", 400)) for texte, style in mot)
        if ligne and occupe + espace + large > largeur_max:
            lignes.append(ligne)
            ligne, occupe = [], 0.0
        occupe += (espace if ligne else 0) + large
        ligne.append(mot)
    if ligne:
        lignes.append(ligne)

    resultat = []
    for ligne in lignes:
        suite: list[tuple[str, dict]] = []
        for rang, mot in enumerate(ligne):
            if rang:
                # L'espace prend le style des deux mots voisins s'ils ont le même (expression de plusieurs mots).
                avant, apres = ligne[rang - 1][-1][1], mot[0][1]
                suite.append((" ", avant if avant is apres else {}))
            suite.extend(mot)
        fusion: list[tuple[str, dict]] = []
        for texte, style in suite:
            if fusion and fusion[-1][1] is style:
                fusion[-1] = (fusion[-1][0] + texte, style)
            elif fusion and not fusion[-1][1] and not style:
                fusion[-1] = (fusion[-1][0] + texte, fusion[-1][1])
            else:
                fusion.append((texte, style))
        resultat.append([texte if not style else (texte, style) for texte, style in fusion])
    return resultat


def _nombre_de_mots(ligne) -> int:
    if isinstance(ligne, str):
        return len(ligne.split())
    return len("".join(partie if isinstance(partie, str) else partie[0] for partie in ligne).split())


def equilibrer(coupe, largeur_max: float):
    """Évite un mot isolé sur la dernière ligne : la coupe est refaite avec des lignes de longueurs voisines."""
    lignes = coupe(largeur_max)
    if len(lignes) < 2 or _nombre_de_mots(lignes[-1]) > 1:
        return lignes
    bas, haut = 0.0, largeur_max
    for _ in range(16):
        milieu = (bas + haut) / 2
        if len(coupe(milieu)) <= len(lignes):
            haut = milieu
        else:
            bas = milieu
    return coupe(haut)


def couper_net(texte: str, largeur_max: float, taille: float, poids: int = 400) -> list[str]:
    """Comme ``couper``, avec des lignes de longueurs voisines."""
    return equilibrer(lambda limite: couper(texte, limite, taille, poids), largeur_max)


def couper_riche_net(segments: list[tuple[str, dict]], largeur_max: float, taille: float) -> list[list]:
    return equilibrer(lambda limite: couper_riche(segments, limite, taille), largeur_max)


def abreger_debut(texte: str, largeur_max: float, taille: float, poids: int = 400) -> str:
    """Raccourcit un texte par le début (« …1975, art. 54 ») s'il dépasse ``largeur_max``."""
    if largeur(texte, taille, poids) <= largeur_max:
        return texte
    mots = texte.split()
    while mots and largeur("… " + " ".join(mots), taille, poids) > largeur_max:
        mots.pop(0)
    return "… " + " ".join(mots)


def abreger_lettres(texte: str, largeur_max: float, taille: float, poids: int = 400) -> str:
    """Raccourcit un terme lettre par lettre (« prescription de l'action pub… »)."""
    if largeur(texte, taille, poids) <= largeur_max:
        return texte
    while texte and largeur(texte.rstrip() + "…", taille, poids) > largeur_max:
        texte = texte[:-1]
    return texte.rstrip() + "…"


def abreger(texte: str, largeur_max: float, taille: float, poids: int = 400) -> str:
    """Raccourcit un texte par des points de suspension s'il dépasse ``largeur_max``."""
    if largeur(texte, taille, poids) <= largeur_max:
        return texte
    mots = texte.split()
    while mots and largeur(" ".join(mots) + "…", taille, poids) > largeur_max:
        mots.pop()
    return " ".join(mots).rstrip(" ,;:") + "…"


# ------------------------------------------------------------------ composants
def capitales(d: Dessin, x, y, texte, ancre="start", couleur=T3, taille=10.5) -> None:
    d.texte(x, y, texte.upper(), taille=taille, poids=600, couleur=couleur, espacement=0.7,
            ancre=None if ancre == "start" else ancre)


def bouton(d: Dessin, x, y, large, h, libelle, genre="contour", icone=None, taille=13) -> None:
    """Bouton : « primaire » (plein), « contour » ou « discret » (texte seul)."""
    fond, trait, couleur = {"primaire": (BLEU, None, "#FFFFFF"), "contour": (SURFACE, FILET, T2),
                            "discret": (None, None, BLEU), "desactive": (GRIS_100, None, T4)}[genre]
    if fond:
        d.rect(x, y, large, h, 8, fill=fond, trait=trait)
    base = y + h / 2 + taille * 0.35
    if icone:
        depart = x + (large - (16 + 7 + largeur(libelle, taille, 600))) / 2
        d.icone(icone, depart, y + h / 2 - 8, 16, couleur, 1.6)
        d.texte(depart + 23, base, libelle, taille=taille, poids=600, couleur=couleur)
    else:
        d.texte(x + large / 2, base, libelle, taille=taille, poids=600, couleur=couleur, ancre="middle")


def puce(d: Dessin, x, y, libelle, genre="lien", h=24, taille=12.5) -> float:
    """Petite étiquette cliquable. Rend sa largeur."""
    arabe = est_arabe(libelle)
    taille_texte = taille + 1.5 if arabe else taille
    large = round(largeur(libelle, taille_texte, 400) + 20)
    fond, trait, couleur = {"lien": (BLEU_50, BLEU_100, BLEU_FONCE), "neutre": (GRIS_50, FILET, T3),
                            "source": (GRIS_100, None, T2)}[genre]
    d.rect(x, y, large, h, 6, fill=fond, trait=trait)
    d.texte(x + large / 2, y + h / 2 + taille_texte * (0.30 if arabe else 0.35), libelle, taille=taille_texte,
            couleur=couleur, ancre="middle")
    return large


def pastille(d: Dessin, x, y, texte, fond=GRIS_100, couleur=T2, h=18, taille=11) -> float:
    """Petit compteur arrondi. Rend sa largeur."""
    large = max(round(largeur(texte, taille, 600) + 12), h + 4)
    d.rect(x, y, large, h, h / 2, fill=fond)
    d.texte(x + large / 2, y + h / 2 + taille * 0.36, texte, taille=taille, poids=600, couleur=couleur, ancre="middle")
    return large


def numero(d: Dessin, cx, cy, chiffre, plein=False, r=11, taille=12) -> None:
    """Numéro d'une étape de l'enchaînement, dans un cercle."""
    if plein:
        d.cercle(cx, cy, r, fill=BLEU)
        d.texte(cx, cy + taille * 0.36, str(chiffre), taille=taille, poids=600, couleur="#FFFFFF", ancre="middle")
    else:
        d.cercle(cx, cy, r - 0.75, fill=SURFACE, trait=BLEU_200, epaisseur=1.5)
        d.texte(cx, cy + taille * 0.36, str(chiffre), taille=taille, poids=600, couleur=BLEU, ancre="middle")


# ------------------------------------------------------------------ fenêtre et éléments communs
def entete(titre: str, description: str, notes: str, icones_employees: list[str]) -> list[str]:
    """Début du fichier : notes, balise <svg>, définitions (dégradé, ombres, icônes employées)."""
    icones = "\n".join(
        f'    <symbol id="i-{nom}" viewBox="0 0 16 16"><g fill="none" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICONES[nom]}</g></symbol>" for nom in icones_employees)
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!--",
        notes.strip("\n"),
        "-->",
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{L}" height="{H}" viewBox="0 0 {L} {H}" xml:lang="fr" role="img"',
        '     aria-labelledby="titre description"',
        f'     font-family="{POLICE}"',
        f'     font-size="13" fill="{T1}">',
        f'  <title id="titre">{escape(titre)}</title>',
        f'  <desc id="description">{escape(description)}</desc>',
        "",
        "  <defs>",
        '    <linearGradient id="g-fond" x1="0" y1="0" x2="0" y2="1">',
        '      <stop offset="0" stop-color="#EDF0F5"/>',
        '      <stop offset="1" stop-color="#DFE4EC"/>',
        "    </linearGradient>",
        '    <filter id="ombre-fenetre" x="-10%" y="-10%" width="120%" height="130%"',
        '            color-interpolation-filters="sRGB">',
        '      <feGaussianBlur in="SourceAlpha" stdDeviation="18"/>',
        '      <feOffset dy="14" result="flou"/>',
        '      <feFlood flood-color="#0F1F3D" flood-opacity="0.20"/>',
        '      <feComposite in2="flou" operator="in"/>',
        "    </filter>",
        '    <filter id="ombre-bouton" x="-20%" y="-30%" width="140%" height="180%"',
        '            color-interpolation-filters="sRGB">',
        '      <feGaussianBlur in="SourceAlpha" stdDeviation="1.2"/>',
        '      <feOffset dy="1" result="flou"/>',
        '      <feFlood flood-color="#101828" flood-opacity="0.14"/>',
        '      <feComposite in2="flou" operator="in"/>',
        "      <feMerge><feMergeNode/><feMergeNode in=\"SourceGraphic\"/></feMerge>",
        "    </filter>",
        f'    <clipPath id="c-fenetre"><rect x="{FX}" y="{FY}" width="{FL}" height="{FH}" rx="10"/></clipPath>',
        "    <!-- Icônes : traits de 1,5 px sur une grille de 16 px. La couleur est donnée à chaque emploi. -->",
        icones,
        "  </defs>",
    ]


def fenetre(d: Dessin, glossaire="glossaire_juridique.csv", entrees="1 000 entrées") -> None:
    """Fond, fenêtre, barre de titre, barre de menus."""
    d.titre("Fond et fenêtre")
    d.rect(0, 0, L, H, fill="url(#g-fond)")
    d.rect(FX, FY, FL, FH, 10, fill="#0F1F3D", filter="url(#ombre-fenetre)")
    d.rect(FX, FY, FL, FH, 10, fill=FOND)
    d.brut('<g clip-path="url(#c-fenetre)">')
    d.niveau += 1

    d.titre("Barre de titre (dessinée par Windows)")
    d.rect(FX, FY, FL, 32, fill=SURFACE)
    d.rect(FX + 12, FY + 8, 16, 16, 4, fill=MARINE)
    d.icone("balance", FX + 14.5, FY + 10.5, 11, "#F4C95D", 1.7)
    d.texte(FX + 36, FY + 20.5, "Traducteur juridique", taille=12, couleur=T1)
    with d.g(trait=T2, epaisseur=1, fill="none"):
        d.chemin(f"M{FX + FL - 120} {FY + 16.5}h10")
        d.rect(FX + FL - 74, FY + 11.5, 10, 10, 1.5)
        d.chemin(f"M{FX + FL - 28} {FY + 11.5}l10 10M{FX + FL - 18} {FY + 11.5}l-10 10")

    d.titre("Barre de menus ; à droite, le glossaire chargé")
    d.rect(FX, CY, FL, 34, fill=SURFACE)
    x = FX + 16
    with d.g(taille=13, couleur=T2):
        for menu in ("Fichier", "Affichage", "Recherche", "Traduction", "Aide"):
            d.texte(x, CY + 21.5, menu)
            x += largeur(menu, 13) + 22
    large = 12 + 8 + 10 + largeur(glossaire, 12, 600) + largeur(" · " + entrees, 12) + 8 + 14 + 10
    gx = X1 - large
    d.rect(gx, CY + 5, large, 24, 12, fill=GRIS_50, trait=FILET)
    d.cercle(gx + 14, CY + 17, 3.5, fill="#12B76A")
    d.texte(gx + 24, CY + 21.2, [(glossaire, {"poids": 600, "couleur": T1}), (" · " + entrees, {"couleur": T3})],
            taille=12)
    d.icone("chevron-b", gx + large - 22, CY + 11, 12, T3, 1.6)
    d.ligne(FX, CY + 34, FX + FL, CY + 34, trait=FILET)


def barre_d_etat(d: Dessin, gauche, droite="Sens : français → arabe") -> None:
    d.titre("Barre d'état")
    d.rect(FX, BAS - 26, FL, 26, fill=SURFACE)
    d.ligne(FX, BAS - 26, FX + FL, BAS - 26, trait=FILET)
    with d.g(taille=11.5, couleur=T3):
        d.texte(X0, BAS - 8.5, gauche)
        d.texte(X1, BAS - 8.5, "Version 0.3", ancre="end")
        d.ligne(X1 - 76, BAS - 19, X1 - 76, BAS - 7, trait=FILET)
        # « français → arabe » : la flèche est dessinée (elle manque dans certaines polices)
        d.texte(X1 - 88, BAS - 8.5, "arabe", ancre="end")
        d.icone("fleche", X1 - 88 - largeur("arabe", 11.5) - 17, BAS - 18.5, 12, T3, 1.4)
        d.texte(X1 - 88 - largeur("arabe", 11.5) - 22, BAS - 8.5, "Sens : français", ancre="end")


def fin_fenetre(d: Dessin) -> None:
    d.niveau -= 1
    d.brut("</g>")
    d.c("Contour de la fenêtre")
    d.rect(FX + 0.5, FY + 0.5, FL - 1, FH - 1, 10, fill="none", trait="#C5CCD8")


def barre_d_outils(d: Dessin, mode: str) -> float:
    """Sélecteur Terme / Texte et sens de traduction. Rend l'abscisse où commence la suite de la barre."""
    y = CY + 48  # haut des commandes (hauteur 44)
    d.titre("Barre d'outils : sélecteur d'écran et sens de traduction")
    d.rect(X0, y, 200, 44, 10, fill="#E6EAF0")
    actif = X0 + 4 if mode == "terme" else X0 + 100
    d.rect(actif, y + 4, 96, 36, 7, fill=SURFACE, filter="url(#ombre-bouton)")
    for nom, icone, x in (("Terme", "fiche", X0 + 52), ("Texte", "texte", X0 + 148)):
        choisi = nom.lower() == mode
        couleur = BLEU_FONCE if choisi else T3
        large = 16 + 7 + largeur(nom, 13.5, 600)
        d.icone(icone, x - large / 2, y + 14, 16, couleur, 1.6)
        d.texte(x - large / 2 + 23, y + 26.8, nom, taille=13.5, poids=600, couleur=couleur)

    x = X0 + 216
    francais, arabe = largeur("Français", 13.5, 600), largeur("العربية", 15.5, 600)
    large = 16 + francais + 12 + 16 + 12 + arabe + 16 + 44
    d.rect(x, y, large, 44, 10, fill=SURFACE, trait=FILET)
    d.texte(x + 16, y + 26.8, "Français", taille=13.5, poids=600)
    d.icone("fleche", x + 16 + francais + 12, y + 14, 16, T4, 1.6)
    d.texte(x + 16 + francais + 40, y + 27.2, "العربية", taille=15.5, poids=600)
    d.ligne(x + large - 44, y + 10, x + large - 44, y + 34, trait=FILET)
    d.icone("echange", x + large - 31, y + 13, 18, BLEU, 1.6)
    return x + large + 16
