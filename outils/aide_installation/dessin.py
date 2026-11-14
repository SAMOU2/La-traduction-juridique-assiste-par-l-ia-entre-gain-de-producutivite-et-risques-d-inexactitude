"""Outils de dessin des images d'aide : la toile, le texte, les icônes et les repères rouges.

Tout est dessiné ``ECHELLE`` fois plus grand que voulu, puis réduit à la fin : le texte et les bords sont
lisses. Les mesures données aux fonctions sont celles du dessin, avant cet agrandissement.
"""
from __future__ import annotations

import functools
import json

import polices
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

ECHELLE = 3

ROUGE = "#E81123"  # repères : cadres, numéros, étiquettes
ACCENT = "#0078D7"  # bleu de Windows 10
LIEN = "#0067C0"


def _px(valeur: float) -> int:
    return round(valeur * ECHELLE)


@functools.cache
def _police(graisse: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(polices.dossier() / f"Selawik-{graisse}.ttf"), taille,
                              layout_engine=ImageFont.Layout.BASIC)


@functools.cache
def _police_d_icones(style: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(polices.dossier() / f"FluentSystemIcons-{style}.ttf"), taille,
                              layout_engine=ImageFont.Layout.BASIC)


@functools.cache
def _codes(style: str) -> dict[str, int]:
    return json.loads((polices.dossier() / f"FluentSystemIcons-{style}.json").read_text(encoding="utf-8"))


def caractere_d_icone(nom: str, style: str = "Regular") -> str:
    """Le caractère de la police d'icônes qui dessine ``nom`` (« settings », « search »…)."""
    codes = _codes(style)
    for taille in (24, 20, 28, 32, 16, 48):  # l'icône n'existe pas toujours à toutes les tailles
        code = codes.get(f"ic_fluent_{nom}_{taille}_{style.lower()}")
        if code is not None:
            return chr(code)
    raise KeyError(f"icône inconnue : {nom} ({style})")


def _simple(texte: str) -> str:
    """Selawik n'a pas d'espace insécable : une espace ordinaire la remplace."""
    return texte.replace("\u00a0", " ").replace("\u202f", " ")


class Toile:
    """Une image en cours de dessin."""

    def __init__(self, large: float, haut: float, fond="#FFFFFF") -> None:
        self.large, self.haut = large, haut
        self.image = Image.new("RGBA", (_px(large), _px(haut)), fond)
        self.crayon = ImageDraw.Draw(self.image)

    # ------------------------------------------------------------------ formes
    def rect(self, x, y, large, haut, fond=None, bord=None, ep=1.0, rayon=0.0) -> None:
        boite = [_px(x), _px(y), _px(x + large) - 1, _px(y + haut) - 1]
        if rayon:
            self.crayon.rounded_rectangle(boite, radius=_px(rayon), fill=fond, outline=bord, width=max(1, _px(ep)))
        else:
            self.crayon.rectangle(boite, fill=fond, outline=bord, width=max(1, _px(ep)))

    def ligne(self, points, couleur, ep=1.0) -> None:
        self.crayon.line([(_px(x), _px(y)) for x, y in points], fill=couleur, width=max(1, _px(ep)), joint="curve")

    def polygone(self, points, fond=None, bord=None, ep=1.0) -> None:
        self.crayon.polygon([(_px(x), _px(y)) for x, y in points], fill=fond, outline=bord,
                            width=max(1, _px(ep)) if bord else 0)

    def disque(self, cx, cy, r, fond=None, bord=None, ep=1.0) -> None:
        self.crayon.ellipse([_px(cx - r), _px(cy - r), _px(cx + r), _px(cy + r)], fill=fond, outline=bord,
                            width=max(1, _px(ep)))

    # ------------------------------------------------------------------ texte et icônes
    def largeur(self, texte: str, graisse="Regular", taille=15.0) -> float:
        return self.crayon.textlength(_simple(texte), font=_police(graisse, _px(taille))) / ECHELLE

    def texte(self, x, y, texte: str, graisse="Regular", taille=15.0, couleur="#000000", ancre="lm") -> float:
        """Écrit une ligne et rend sa largeur. ``ancre`` : gauche, milieu ou droite (l, m, r), puis m = mi-hauteur."""
        police = _police(graisse, _px(taille))
        self.crayon.text((_px(x), _px(y)), _simple(texte), font=police, fill=couleur, anchor=ancre)
        return self.crayon.textlength(_simple(texte), font=police) / ECHELLE

    def couper(self, texte: str, largeur_max: float, graisse="Regular", taille=15.0) -> list[str]:
        lignes, courante = [], ""
        for mot in _simple(texte).split(" "):
            essai = f"{courante} {mot}".strip()
            if courante and self.largeur(essai, graisse, taille) > largeur_max:
                lignes.append(courante)
                courante = mot
            else:
                courante = essai
        return [*lignes, courante] if courante else lignes

    def paragraphe(self, x, y, texte: str, largeur_max: float, graisse="Regular", taille=15.0, couleur="#000000",
                   interligne=None) -> None:
        """Écrit un texte sur plusieurs lignes ; ``y`` est le haut de la première."""
        interligne = interligne or taille * 1.38
        for rang, ligne in enumerate(self.couper(texte, largeur_max, graisse, taille)):
            self.texte(x, y + (rang + 0.5) * interligne, ligne, graisse, taille, couleur)

    def icone(self, cx, cy, nom: str, taille=20.0, couleur="#000000", style="Regular") -> None:
        """Dessine une icône dont le centre est en (cx, cy)."""
        self.crayon.text((_px(cx), _px(cy)), caractere_d_icone(nom, style), font=_police_d_icones(style, _px(taille)),
                         fill=couleur, anchor="mm")

    # ------------------------------------------------------------------ calques
    def coller(self, image: Image.Image, x=0.0, y=0.0) -> None:
        self.image.alpha_composite(image.convert("RGBA"), (_px(x), _px(y)))
        self.crayon = ImageDraw.Draw(self.image)

    def calque(self) -> Toile:
        """Une toile transparente de la même taille, pour les formes à demi transparentes."""
        return Toile(self.large, self.haut, (0, 0, 0, 0))

    def flouter(self, rayon: float) -> None:
        self.image = self.image.filter(ImageFilter.GaussianBlur(_px(rayon)))
        self.crayon = ImageDraw.Draw(self.image)

    def ombre(self, x, y, large, haut, flou=14.0, descente=6.0, force=70) -> None:
        """L'ombre portée d'une fenêtre : à dessiner avant la fenêtre."""
        calque = self.calque()
        calque.rect(x, y + descente, large, haut, fond=(0, 0, 0, force))
        calque.flouter(flou)
        self.coller(calque.image)

    def fondu(self, x, y, large, haut, couleur: str, vers="bas") -> None:
        """Efface peu à peu le dessin vers le bas ou vers la droite : la fenêtre continue plus loin."""
        masque = Image.linear_gradient("L")  # noir en haut, blanc en bas
        if vers == "droite":
            masque = masque.rotate(90)
        masque = masque.resize((max(1, _px(large)), max(1, _px(haut))))
        bande = Image.new("RGBA", masque.size, ImageColor.getrgb(couleur))
        bande.putalpha(masque)
        self.coller(bande, x, y)

    def sortie(self, facteur: float = 1.0) -> Image.Image:
        """L'image finale, réduite : ``facteur`` points d'image par point du dessin."""
        taille = (round(self.large * facteur), round(self.haut * facteur))
        return self.image.resize(taille, Image.Resampling.LANCZOS).convert("RGB")


# ---------------------------------------------------------------------- repères
def cadre(toile: Toile, x, y, large, haut, rayon=5.0, ep=3.0) -> None:
    """Cadre rouge autour de l'endroit où cliquer ; son liseré blanc le détache des fonds sombres."""
    toile.rect(x - 1.5, y - 1.5, large + 3, haut + 3, bord="#FFFFFF", ep=ep + 3, rayon=rayon + 1.5)
    toile.rect(x, y, large, haut, bord=ROUGE, ep=ep, rayon=rayon)


def pastille(toile: Toile, cx, cy, chiffre: str, r=14.0) -> None:
    """Numéro blanc dans un rond rouge."""
    toile.disque(cx, cy, r + 2.5, fond="#FFFFFF")
    toile.disque(cx, cy, r, fond=ROUGE)
    toile.texte(cx, cy - r * 0.04, chiffre, "Bold", r * 1.25, "#FFFFFF", "mm")


def curseur(toile: Toile, x, y, k=1.7) -> None:
    """Flèche de la souris, la pointe en (x, y)."""
    forme = [(0, 0), (0, 16.2), (3.9, 12.6), (6.7, 18.9), (9.0, 17.9), (6.3, 11.8), (11.4, 11.8)]
    points = [(x + px * k, y + py * k) for px, py in forme]
    ombre = toile.calque()
    ombre.polygone([(px + 1.4, py + 2.2) for px, py in points], fond=(0, 0, 0, 80))
    ombre.flouter(1.2)
    toile.coller(ombre.image)
    toile.polygone(points, fond="#FFFFFF", bord="#000000", ep=1.3)


def etiquette(toile: Toile, x, y, texte: str, taille=15.0) -> None:
    """Mot d'explication en rouge dans un cartouche blanc ; (x, y) est son coin en haut à gauche."""
    large, haut = toile.largeur(texte, "Bold", taille) + 22, taille * 1.9
    toile.rect(x, y, large, haut, fond="#FFFFFF", bord=ROUGE, ep=2, rayon=haut / 2)
    toile.texte(x + large / 2, y + haut / 2 - 0.5, texte, "Bold", taille, ROUGE, "mm")
