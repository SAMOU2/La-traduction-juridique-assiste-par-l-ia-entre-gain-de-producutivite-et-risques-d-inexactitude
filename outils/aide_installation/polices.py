"""Polices dont le dessin des images d'aide a besoin. Elles ne sont pas dans le dépôt.

Elles sont prises sur GitHub la première fois, puis gardées dans ``build/aide_installation`` :

* Selawik (Microsoft, licence SIL OFL 1.1) pour le texte. Sa forme est proche de celle de Segoe UI, la
  police de Windows, qui n'est pas libre. Elle est fabriquée à partir de ses sources avec ``fontmake`` ;
* Fluent System Icons (Microsoft, licence MIT) pour les icônes.
"""
from __future__ import annotations

import functools
import io
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

DEPOT = pathlib.Path(__file__).resolve().parents[2]

#: Dépôt et numéro de commit de chaque police : le dessin ne change pas si ces projets changent.
SELAWIK = ("microsoft/Selawik", "89362e84731d1f5777fa078fd4d5ebbd339e4378")
ICONES = ("microsoft/fluentui-system-icons", "67e6dec1ee956af3ab4c746a2b3bb6a2e5520a44")

DOSSIER = DEPOT / "build" / "aide_installation" / f"polices-{SELAWIK[1][:7]}-{ICONES[1][:7]}"

FICHIERS_SELAWIK = tuple(f"Selawik-{graisse}.ttf" for graisse in ("Light", "Regular", "Semibold", "Bold"))
FICHIERS_ICONES = tuple(f"FluentSystemIcons-{style}.{suffixe}"
                        for style in ("Regular", "Filled") for suffixe in ("ttf", "json"))


def _telecharger(url: str, brut: bool = False) -> bytes:
    entetes = {"User-Agent": "aide-installation"}
    if brut:  # demande à GitHub le fichier lui-même, et non sa description
        entetes["Accept"] = "application/vnd.github.raw"
    print("téléchargement :", url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=entetes), timeout=120) as reponse:
            return reponse.read()
    except OSError as erreur:  # pas de connexion, adresse refusée ou délai dépassé
        raise SystemExit(f"Téléchargement impossible ({erreur}). Les polices sont prises sur GitHub la première "
                         "fois : il faut une connexion à Internet.") from erreur


def _ecrire(nom: str, contenu: bytes) -> None:
    """Écrit le fichier en une fois : un téléchargement interrompu ne laisse pas de fichier incomplet."""
    provisoire = DOSSIER / (nom + ".partiel")
    provisoire.write_bytes(contenu)
    provisoire.replace(DOSSIER / nom)


def _fabriquer_selawik() -> None:
    depot, version = SELAWIK
    archive = _telecharger(f"https://codeload.github.com/{depot}/tar.gz/{version}")
    with tempfile.TemporaryDirectory() as nom_du_dossier:
        travail = pathlib.Path(nom_du_dossier)
        with tarfile.open(fileobj=io.BytesIO(archive)) as contenu:
            source = next(membre for membre in contenu.getmembers() if membre.name.endswith("/Glyphs/selawik.glyphs"))
            (travail / "selawik.glyphs").write_bytes(contenu.extractfile(source).read())
        print("fabrication de la police Selawik (fontmake)")
        commande = [sys.executable, "-m", "fontmake", "-g", "selawik.glyphs", "-i", "-o", "ttf", "--no-autohint",
                    "--output-dir", "ttf"]
        resultat = subprocess.run(commande, cwd=travail, capture_output=True, text=True, check=False)
        if resultat.returncode:
            raise SystemExit("La police Selawik n'a pas pu être fabriquée. Les outils sont-ils installés ?\n"
                             "    python -m pip install -r outils/aide_installation/requirements.txt\n\n"
                             + resultat.stderr[-1500:])
        for nom in FICHIERS_SELAWIK:
            _ecrire(nom, (travail / "ttf" / nom).read_bytes())


@functools.cache
def dossier() -> pathlib.Path:
    """Le dossier où sont les polices. Celles qui manquent sont d'abord téléchargées ou fabriquées."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    if not all((DOSSIER / nom).is_file() for nom in FICHIERS_SELAWIK):
        _fabriquer_selawik()
    depot, version = ICONES
    for nom in FICHIERS_ICONES:
        if not (DOSSIER / nom).is_file():
            _ecrire(nom, _telecharger(f"https://api.github.com/repos/{depot}/contents/fonts/{nom}?ref={version}",
                                      brut=True))
    return DOSSIER
