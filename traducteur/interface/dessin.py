"""Outils de dessin du texte, pour les composants peints à la main (tableau des termes, listes).

Ces composants écrivent beaucoup de lignes courtes. Les dessiner directement évite de créer
une étiquette par texte, et permet d'abréger chaque ligne à la largeur exacte de sa case.
"""

from __future__ import annotations

from collections.abc import Sequence

import regex
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QTextCharFormat, QTextLayout, QTextOption

from ..langues import AR, FR
from . import theme

_MOT = regex.compile(r"\S+")
#: Ce qui ne peut pas rester tel quel dans un texte écrit sur une ligne.
_ESPACES_A_REDUIRE = regex.compile(r"\s{2,}|[\t\n\r\f\v]|^\s|\s$")
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


def sur_une_ligne(texte: str, evidences: Sequence[tuple[int, int]] = ()) -> tuple[str, list[tuple[int, int]]]:
    """Prépare un texte à être écrit sur une seule ligne.

    Les tabulations, les retours à la ligne et les suites d'espaces deviennent une espace ; les
    espaces du début et de la fin sont retirées. Renvoie le texte et les positions (début, fin)
    des passages en évidence, reportées dans ce nouveau texte.
    """
    if not _ESPACES_A_REDUIRE.search(texte):
        return texte, list(evidences)
    positions, caracteres, espace_en_attente = [], [], ""
    for caractere in texte:
        if caractere.isspace():
            positions.append(len(caracteres) + (1 if espace_en_attente else 0))
            if caracteres:
                # Une espace seule est gardée telle quelle (espace insécable comprise).
                espace_en_attente = " " if espace_en_attente or caractere in "\t\n\r\f\v" else caractere
            continue
        if espace_en_attente:
            caracteres.append(espace_en_attente)
            espace_en_attente = ""
        positions.append(len(caracteres))
        caracteres.append(caractere)
    limite = len(caracteres)
    positions.append(limite)
    reportees = [(min(positions[debut], limite), min(positions[fin], limite)) for debut, fin in evidences]
    return "".join(caracteres), [(debut, fin) for debut, fin in reportees if fin > debut]


def extrait_autour(texte: str, evidences: Sequence[tuple[int, int]], police_du_texte: QFont, largeur: float,
                   repere: float = 0.0) -> tuple[str, list[tuple[int, int]]]:
    """Passage d'une phrase qui tient sur une ligne, pris autour de son premier passage en évidence.

    Le passage est étendu mot par mot, à droite puis à gauche, tant qu'il tient dans ``largeur``
    pixels ; « … » marque chaque côté coupé. Sans passage en évidence, le passage est pris autour
    du mot situé à la proportion ``repere`` de la phrase (0 : début, 1 : fin).

    Renvoie le passage et la position des passages en évidence dans ce passage.
    """
    texte, evidences = sur_une_ligne(texte, evidences)
    normale = QFontMetricsF(police_du_texte)
    grasse = QFontMetricsF(police(police_du_texte, police_du_texte.pixelSize(), gras=True))

    def largeur_de(chaine: str, locales: Sequence[tuple[int, int]]) -> float:
        total = normale.horizontalAdvance(chaine)
        for debut, fin in locales:
            total += grasse.horizontalAdvance(chaine[debut:fin]) - normale.horizontalAdvance(chaine[debut:fin])
        return total + 1.0

    if largeur_de(texte, evidences) <= largeur:
        return texte, list(evidences)
    mots = [(trouve.start(), trouve.end()) for trouve in _MOT.finditer(texte)]
    if not mots:
        return texte, list(evidences)
    if evidences:
        debut_foyer, fin_foyer = evidences[0]
    else:
        debut_foyer = fin_foyer = min(int(len(texte) * min(max(repere, 0.0), 1.0)), len(texte) - 1)
    premier = next((rang for rang, (_, fin) in enumerate(mots) if fin > debut_foyer), len(mots) - 1)
    dernier = max((rang for rang, (debut, _) in enumerate(mots) if debut < fin_foyer), default=premier)
    dernier = max(dernier, premier)

    def construire(rang_debut: int, rang_fin: int) -> tuple[str, list[tuple[int, int]]]:
        debut, fin = mots[rang_debut][0], mots[rang_fin][1]
        prefixe = "… " if rang_debut > 0 else ""
        corps = texte[debut:fin]
        if rang_fin < len(mots) - 1:
            corps = corps.rstrip(_FIN_DE_COUPE) + "…"
        decalage = len(prefixe) - debut
        limite = len(prefixe) + fin - debut
        locales = [(max(a, debut) + decalage, min(min(b, fin) + decalage, limite))
                   for a, b in evidences if b > debut and a < fin]
        return prefixe + corps, locales

    def tient(rang_debut: int, rang_fin: int) -> bool:
        return largeur_de(*construire(rang_debut, rang_fin)) <= largeur

    while True:
        etendu = False
        if dernier < len(mots) - 1 and tient(premier, dernier + 1):
            dernier += 1
            etendu = True
        if premier > 0 and tient(premier - 1, dernier):
            premier -= 1
            etendu = True
        if not etendu:
            break
    return construire(premier, dernier)
