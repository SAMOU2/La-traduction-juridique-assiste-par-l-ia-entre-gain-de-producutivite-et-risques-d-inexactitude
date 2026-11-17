"""Outils de dessin du texte, pour les composants peints à la main (tableau des termes, listes).

Ces composants écrivent beaucoup de lignes courtes. Les dessiner directement évite de créer
une étiquette par texte, et permet d'abréger chaque ligne à la largeur exacte de sa case.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QTextCharFormat, QTextLayout, QTextOption

from ..langues import AR, FR
from . import theme

#: Signes retirés de la fin d'un texte abrégé, avant « … ».
_FIN_DE_COUPE = " ,;:،؛"


def police(base: QFont, taille: int, *, gras: bool = False, italique: bool = False,
           espacement: float = 0.0) -> QFont:
    """Police d'un texte dessiné : celle de ``base``, à une taille donnée en pixels."""
    resultat = QFont(base)
    resultat.setPixelSize(taille)
    resultat.setWeight(QFont.Weight.DemiBold if gras else QFont.Weight.Normal)
    resultat.setItalic(italique)
    if espacement:
        resultat.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espacement)
    return resultat


def largeur_du_texte(texte: str, police_du_texte: QFont) -> float:
    return QFontMetricsF(police_du_texte).horizontalAdvance(texte)


def melanger(depart: str, arrivee: str, part: float) -> QColor:
    """Couleur située entre deux couleurs : ``part`` vaut 0 pour la première, 1 pour la seconde."""
    part = min(max(part, 0.0), 1.0)
    debut, fin = QColor(depart), QColor(arrivee)
    return QColor(round(debut.red() + (fin.red() - debut.red()) * part),
                  round(debut.green() + (fin.green() - debut.green()) * part),
                  round(debut.blue() + (fin.blue() - debut.blue()) * part))


def dessiner_numero(peintre: QPainter, centre: QPointF, rayon: float, texte: str, police_du_numero: QFont,
                    niveau: float, halo: float = 0.0, *, carre: bool = False) -> None:
    """Dessine le numéro d'une étape, plus ou moins allumé.

    ``niveau`` va de 0 (étape éteinte : cercle gris) à 1 (étape allumée : disque doré) ;
    ``halo`` (0 à 1) ajoute un anneau lumineux autour du numéro, au moment où il s'allume.
    Avec ``carre``, le numéro est dans un carré aux angles arrondis.
    """
    peintre.save()
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
    arrondi = rayon * 0.6 if carre else rayon

    def forme(marge: float) -> None:
        cadre = QRectF(centre.x() - rayon - marge, centre.y() - rayon - marge,
                       2 * (rayon + marge), 2 * (rayon + marge))
        peintre.drawRoundedRect(cadre, arrondi + marge, arrondi + marge)

    if halo > 0.0:
        peintre.setPen(Qt.PenStyle.NoPen)
        for marge, opacite in ((2.0 + 7.0 * halo, 0.20), (1.0 + 3.5 * halo, 0.34)):
            lueur = QColor(theme.OR)
            lueur.setAlphaF(opacite * halo)
            peintre.setBrush(lueur)
            forme(marge)
    bord = melanger(theme.GRIS_300, theme.OR_FONCE, niveau)
    peintre.setPen(QPen(bord, 1.25))
    peintre.setBrush(melanger(theme.SURFACE, theme.OR, niveau))
    forme(-0.625)
    peintre.setFont(police_du_numero)
    peintre.setPen(melanger(theme.TEXTE_4, theme.MARINE, niveau))
    peintre.drawText(QRectF(centre.x() - rayon, centre.y() - rayon, 2 * rayon, 2 * rayon),
                     Qt.AlignmentFlag.AlignCenter, texte)
    peintre.restore()


def abreger(texte: str, police_du_texte: QFont, largeur: float, *, par_le_debut: bool = False) -> str:
    """Raccourcit un texte, mot par mot, pour qu'il tienne dans ``largeur`` pixels.

    « … » marque la coupure : à la fin du texte, ou au début si ``par_le_debut`` est vrai
    (on garde alors la fin du texte, par exemple les numéros d'articles d'une référence).
    """
    metrique = QFontMetricsF(police_du_texte)
    if metrique.horizontalAdvance(texte) <= largeur:
        return texte
    mots = texte.split()
    while len(mots) > 1:
        if par_le_debut:
            mots.pop(0)
            essai = "… " + " ".join(mots)
        else:
            mots.pop()
            essai = " ".join(mots).rstrip(_FIN_DE_COUPE) + "…"
        if metrique.horizontalAdvance(essai) <= largeur:
            return essai
    # Il ne reste qu'un mot, encore trop large : il est coupé lettre par lettre.
    mode = Qt.TextElideMode.ElideLeft if par_le_debut else Qt.TextElideMode.ElideRight
    return metrique.elidedText(texte, mode, max(largeur, 0))


def _utf16(texte: str, indice: int) -> int:
    """Position dans le texte comptée en unités UTF-16, comme le fait Qt."""
    return indice + sum(1 for caractere in texte[:indice] if ord(caractere) > 0xFFFF)


def dessiner_ligne(peintre: QPainter, rectangle: QRectF, texte: str, police_du_texte: QFont, couleur: str, *,
                   langue: str = FR, alignement: Qt.AlignmentFlag | None = None, base: float | None = None,
                   evidences: Sequence[tuple[int, int]] = (), couleur_evidence: str = theme.BLEU_FONCE) -> None:
    """Écrit une ligne de texte dans un rectangle.

    ``langue`` fixe le sens d'écriture et, par défaut, l'alignement (à droite pour l'arabe).
    ``base`` est la distance entre le haut du rectangle et la ligne de base du texte ; sans
    elle, le texte est centré en hauteur. ``evidences`` donne les passages (début, fin) à
    écrire en demi-gras et en couleur.
    """
    if not texte or rectangle.width() <= 0:
        return
    disposition = QTextLayout(texte, police_du_texte)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.NoWrap)
    option.setTextDirection(Qt.LayoutDirection.RightToLeft if langue == AR else Qt.LayoutDirection.LeftToRight)
    if alignement is None:
        alignement = Qt.AlignmentFlag.AlignRight if langue == AR else Qt.AlignmentFlag.AlignLeft
    option.setAlignment(alignement | Qt.AlignmentFlag.AlignAbsolute)
    disposition.setTextOption(option)
    if evidences:
        formats = []
        for debut, fin in evidences:
            forme = QTextCharFormat()
            forme.setFontWeight(QFont.Weight.DemiBold)
            forme.setForeground(QColor(couleur_evidence))
            plage = QTextLayout.FormatRange()
            plage.start = _utf16(texte, debut)
            plage.length = _utf16(texte, fin) - plage.start
            plage.format = forme
            formats.append(plage)
        disposition.setFormats(formats)
    disposition.beginLayout()
    ligne = disposition.createLine()
    ligne.setLineWidth(rectangle.width())
    disposition.endLayout()
    haut = base - ligne.ascent() if base is not None else (rectangle.height() - ligne.height()) / 2
    peintre.setPen(QColor(couleur))
    disposition.draw(peintre, QPointF(rectangle.x(), rectangle.y() + haut))


def couper_en_lignes(texte: str, police_du_texte: QFont, largeur: float, lignes: int) -> tuple[list[str], bool]:
    """Coupe un texte en lignes de ``largeur`` pixels, sans dépasser ``lignes`` lignes.

    La dernière ligne est abrégée par « … » si le texte ne tient pas. Renvoie les lignes et
    un indicateur : vrai si le texte a été abrégé.
    """
    if largeur <= 0 or not texte:
        return [], bool(texte)
    # Qt compte les positions en unités UTF-16 : on découpe le texte dans ce codage.
    unites = texte.encode("utf-16-le")

    def tranche(debut: int, fin: int | None = None) -> str:
        return unites[2 * debut:None if fin is None else 2 * fin].decode("utf-16-le").strip()

    disposition = QTextLayout(texte, police_du_texte)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WordWrap)
    disposition.setTextOption(option)
    resultat: list[str] = []
    abrege = False
    disposition.beginLayout()
    while True:
        ligne = disposition.createLine()
        if not ligne.isValid():
            break
        ligne.setLineWidth(largeur)
        debut, fin = ligne.textStart(), ligne.textStart() + ligne.textLength()
        if len(resultat) == lignes - 1 and fin < len(unites) // 2:
            # Dernière ligne permise et il reste du texte : toute la fin est abrégée sur cette ligne.
            resultat.append(abreger(tranche(debut), police_du_texte, largeur))
            abrege = True
            break
        resultat.append(tranche(debut, fin))
    disposition.endLayout()
    return resultat, abrege
