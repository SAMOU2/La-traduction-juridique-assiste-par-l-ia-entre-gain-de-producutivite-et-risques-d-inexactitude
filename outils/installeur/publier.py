#!/usr/bin/env python3
"""Publie l'installeur sur la page « Releases » du dépôt GitHub.

Lancé par la fabrication automatique (``.github/workflows/installeur.yml``), après ``construire.py`` :

    python outils/installeur/publier.py

* Depuis la branche principale (``main``), l'installeur est publié comme version ``v<version>`` :
  c'est celle que montre la page ``…/releases/latest`` du dépôt.
* Depuis une autre branche, il est publié comme « version d'essai » (étiquette ``installeur-essai``),
  remplacée à chaque fabrication : elle sert à essayer un travail qui n'est pas encore fusionné.

Une publication qui porte déjà la même étiquette est d'abord supprimée. Le script se sert de la
commande ``gh`` de GitHub et lit les variables que GitHub Actions lui donne.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))

from traducteur import NOM_APPLICATION, __version__  # noqa: E402

TRAVAIL = RACINE / "build" / "installeur"
BRANCHE_PRINCIPALE = "main"
ETIQUETTE_D_ESSAI = "installeur-essai"


def publication(branche: str, version: str = __version__) -> tuple[str, str, bool]:
    """L'étiquette, le titre de la publication, et « version d'essai » ou non."""
    if branche == BRANCHE_PRINCIPALE:
        return f"v{version}", f"{NOM_APPLICATION} {version}", False
    return ETIQUETTE_D_ESSAI, f"{NOM_APPLICATION} {version} — version d’essai", True


def notes(fichier: str, version: str, essai: bool, branche: str, commit: str, verifications: str,
          adresse_de_la_fabrication: str = "") -> str:
    """Le texte de la page de téléchargement : comment installer, puis ce qui a été vérifié."""
    lignes = []
    if essai:
        lignes += [
            f"**Version d’essai.** Elle est fabriquée à partir de la branche `{branche}`, qui n’est pas encore "
            f"fusionnée dans `{BRANCHE_PRINCIPALE}`. Elle est remplacée à chaque nouvelle fabrication.",
            "",
        ]
    lignes += [
        f"## Installer {NOM_APPLICATION} {version} sous Windows",
        "",
        f"1. Téléchargez le fichier **{fichier}** (plus bas, dans « Assets »).",
        "2. Double-cliquez sur le fichier téléchargé.",
        "3. Cliquez sur **Suivant**, puis sur **Installer**, puis sur **Terminer**. L’application s’ouvre.",
        "",
        f"Les fois suivantes, ouvrez l’application avec l’icône « {NOM_APPLICATION} » du Bureau.",
        "",
        "- L’installeur est fait pour Windows 10 et Windows 11 (64 bits).",
        "- Il n’y a rien d’autre à installer : Python est dans l’installeur.",
        "- Si Windows affiche « Windows a protégé votre ordinateur », cliquez sur « Informations "
        "complémentaires », puis sur « Exécuter quand même ». Ce message apparaît parce que l’installeur "
        "n’est pas signé.",
        f"- Pour désinstaller : Paramètres de Windows → Applications → {NOM_APPLICATION} → Désinstaller.",
        "",
        "## Vérifications faites pendant la fabrication",
        "",
        "Elles sont faites automatiquement, sur une machine Windows de GitHub, sans personne devant l’écran.",
        "",
        verifications.strip() or "- Aucune vérification n’a été notée.",
        "",
        f"Fabriqué à partir du commit `{commit[:7]}` (branche `{branche}`)."
        + (f" [Journal de la fabrication]({adresse_de_la_fabrication})." if adresse_de_la_fabrication else ""),
    ]
    return "\n".join(lignes) + "\n"


def gh(*arguments: str, verifier: bool = True) -> subprocess.CompletedProcess:
    resultat = subprocess.run(["gh", *arguments], capture_output=True, text=True, encoding="utf-8", check=False)
    if verifier and resultat.returncode != 0:
        raise SystemExit(f"Échec de « gh {' '.join(arguments[:3])} … » :\n{resultat.stdout}{resultat.stderr}")
    return resultat


def publier() -> str:
    """Publie l'installeur fabriqué et renvoie l'adresse de la page de téléchargement."""
    depot = os.environ["GITHUB_REPOSITORY"]
    branche = os.environ["GITHUB_REF_NAME"]
    commit = os.environ["GITHUB_SHA"]
    installeurs = sorted(TRAVAIL.glob("*.msi"))
    if len(installeurs) != 1:
        raise SystemExit(f"Un seul installeur est attendu dans {TRAVAIL} ; trouvé : {[f.name for f in installeurs]}")
    installeur = installeurs[0]
    etiquette, titre, essai = publication(branche)
    resume = TRAVAIL / "resume.md"
    fabrication = ""
    if os.environ.get("GITHUB_RUN_ID"):
        fabrication = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{depot}/actions/runs/" \
                      f"{os.environ['GITHUB_RUN_ID']}"
    texte = notes(installeur.name, __version__, essai, branche, commit,
                  resume.read_text(encoding="utf-8") if resume.is_file() else "", fabrication)
    fichier_des_notes = TRAVAIL / "notes-de-publication.md"
    fichier_des_notes.write_text(texte, encoding="utf-8")

    # Une publication de même étiquette est retirée, avec son étiquette : la nouvelle désigne ce commit.
    gh("release", "delete", etiquette, "--repo", depot, "--yes", "--cleanup-tag", verifier=False)
    gh("api", "--method", "DELETE", f"repos/{depot}/git/refs/tags/{etiquette}", verifier=False)
    arguments = ["release", "create", etiquette, str(installeur), "--repo", depot, "--target", commit,
                 "--title", titre, "--notes-file", str(fichier_des_notes)]
    arguments += ["--prerelease"] if essai else ["--latest"]
    return gh(*arguments).stdout.strip().splitlines()[-1]


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    adresse = publier()
    print(f"Installeur publié : {adresse}")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::notice title=Page de téléchargement::{adresse}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
