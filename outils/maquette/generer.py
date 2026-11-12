#!/usr/bin/env python3
"""Dessine les fichiers SVG de la proposition d'interface (dossier maquette/proposition).

Emploi, depuis le dossier du projet :

    python outils/maquette/generer.py [dossier_de_sortie]

Ce script ne fait pas partie de l'application. Il lit le glossaire fourni, pour que la maquette montre
le vrai contenu d'une fiche et la vraie traduction du texte d'exemple, puis il écrit cinq fichiers SVG.
Les couleurs, les tailles et les éléments communs sont dans ``kit.py`` ; chaque écran a son module.
"""
from __future__ import annotations

import pathlib
import sys

DEPOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEPOT))

import ecran_terme  # noqa: E402
import ecran_texte  # noqa: E402

from traducteur.glossaire import Glossaire  # noqa: E402


def generer(sortie: pathlib.Path) -> None:
    glossaire = Glossaire.charger(DEPOT / "donnees" / "glossaire_juridique.csv")
    fichiers = {
        "01-terme.svg": ecran_terme.dessiner(glossaire, "contrat"),
        "02-texte.svg": ecran_texte.dessiner(glossaire),
        "03-terme-deux-sens.svg": ecran_terme.dessiner(glossaire, "action"),
        "04-terme-accueil.svg": ecran_terme.dessiner_sans_fiche(
            glossaire, exemples=("contrat", "soumissionnaire", "offre", "livret foncier", "dividende")),
        "05-terme-introuvable.svg": ecran_terme.dessiner_sans_fiche(glossaire, "contart"),
    }
    sortie.mkdir(parents=True, exist_ok=True)
    for nom, contenu in fichiers.items():
        (sortie / nom).write_text(contenu, encoding="utf-8", newline="\n")
        print("écrit :", sortie / nom)


if __name__ == "__main__":
    generer(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEPOT / "maquette" / "proposition")
