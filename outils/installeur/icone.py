#!/usr/bin/env python3
"""Écrit l'icône de l'application au format de Windows (fichier .ico).

Emploi, depuis le dossier du projet :

    python outils/installeur/icone.py [fichier_de_sortie.ico]

Ce script ne fait pas partie de l'application. Il sert à fabriquer l'installeur pour Windows :
l'icône est celle de la fenêtre (une balance dorée sur fond bleu marine), dessinée aux tailles
dont Windows se sert pour le bureau, le menu Démarrer et la barre des tâches. Sans argument, le
fichier est écrit dans ``build/installeur/traducteur.ico``.
"""
from __future__ import annotations

import os
import pathlib
import struct
import sys

DEPOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEPOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # aucune fenêtre n'est ouverte

from PySide6.QtCore import QBuffer, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

from traducteur.interface import icones  # noqa: E402

#: Tailles de l'icône, en pixels : petites icônes (16 à 24), bureau (32 à 64), grandes vignettes.
TAILLES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
SORTIE = DEPOT / "build" / "installeur" / "traducteur.ico"


def dessin(taille: int) -> QImage:
    """Le logo dessiné à la taille demandée, avec sa transparence."""
    image = icones.logo(taille).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    if image.width() != taille:  # écran à haute densité : le logo est dessiné plus grand
        image = image.scaled(taille, taille, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    image.setDevicePixelRatio(1.0)
    return image


def en_png(image: QImage) -> bytes:
    tampon = QBuffer()
    tampon.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(tampon, "PNG"):
        raise RuntimeError("Qt n'a pas pu écrire l'image au format PNG.")
    return bytes(tampon.data())


def en_bitmap(image: QImage) -> bytes:
    """L'image au format « bitmap » d'une icône : les couleurs, de bas en haut, puis le masque de transparence."""
    cote = image.width()
    points = bytes(image.constBits())  # 4 octets par point : bleu, vert, rouge, opacité
    largeur_de_ligne = image.bytesPerLine()
    lignes = [points[y * largeur_de_ligne: y * largeur_de_ligne + cote * 4] for y in range(cote - 1, -1, -1)]
    # Le masque marque d'un bit à 1 chaque point entièrement transparent ; ses lignes font un multiple de 4 octets.
    octets_par_ligne = (cote + 31) // 32 * 4
    masque = bytearray()
    for ligne in lignes:
        bits = bytearray(octets_par_ligne)
        for x in range(cote):
            if ligne[x * 4 + 3] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        masque += bits
    entete = struct.pack("<IiiHHIIiiII", 40, cote, cote * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    return entete + b"".join(lignes) + bytes(masque)


def ecrire(sortie: pathlib.Path) -> None:
    """Écrit le fichier .ico : un répertoire, puis une image par taille."""
    images = []
    for taille in TAILLES:
        image = dessin(taille)
        # Windows lit la grande taille au format PNG ; les autres restent en « bitmap », lu partout.
        images.append((taille, en_png(image) if taille >= 256 else en_bitmap(image)))
    debut = 6 + 16 * len(images)
    repertoire = struct.pack("<HHH", 0, 1, len(images))
    for taille, donnees in images:
        cote = taille % 256  # 0 signifie 256
        repertoire += struct.pack("<BBBBHHII", cote, cote, 0, 0, 1, 32, len(donnees), debut)
        debut += len(donnees)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_bytes(repertoire + b"".join(donnees for _, donnees in images))


def main() -> int:
    sortie = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else SORTIE
    application = QGuiApplication.instance() or QGuiApplication([])
    ecrire(sortie)
    print(f"{sortie} : {len(TAILLES)} tailles ({', '.join(map(str, TAILLES))} pixels), {sortie.stat().st_size} octets")
    del application
    return 0


if __name__ == "__main__":
    sys.exit(main())
