"""Fichiers de Qt que PyInstaller ajoute au dossier de l'application et dont elle ne se sert pas.

``traducteur.spec`` les écarte : l'installeur est plus léger d'un tiers environ, et le téléchargement
plus court. L'application dessine ses fenêtres elle-même, sans carte graphique, et ne se connecte à
rien : elle n'a besoin ni du dessin en trois dimensions par logiciel, ni des bibliothèques de réseau,
ni des textes de Qt dans d'autres langues que le français.

Après ce tri, ``construire.py`` vérifie que le programme fonctionne encore (contrôle complet) et
qu'aucun fichier restant ne réclame une bibliothèque écartée.
"""
from __future__ import annotations

#: Bibliothèques écartées, par leur nom (en minuscules).
FICHIERS = frozenset({
    "opengl32sw.dll",  # dessin en trois dimensions par logiciel : 20 Mo
    "qt6network.dll",  # réseau
    "libcrypto-3-x64.dll", "libssl-3-x64.dll",  # chiffrement des connexions de Qt
})
#: Familles d'extensions de Qt écartées en entier : elles ont toutes besoin du réseau.
EXTENSIONS = frozenset({"generic", "networkinformation", "tls"})
#: Seul fichier de textes de Qt conservé : les menus « Copier », « Coller »… en français.
TEXTES_GARDES = "qtbase_fr.qm"


def est_superflu(destination: str) -> bool:
    """Vrai si ce fichier du dossier de l'application peut en être retiré. ``destination`` est son chemin."""
    morceaux = destination.replace("\\", "/").lower().split("/")
    nom = morceaux[-1]
    if nom in FICHIERS:
        return True
    if len(morceaux) >= 3 and morceaux[-3] == "plugins" and morceaux[-2] in EXTENSIONS:
        return True
    return "translations" in morceaux[:-1] and nom != TEXTES_GARDES


def trier(entrees: list) -> tuple[list, list]:
    """Sépare les entrées gardées des entrées écartées ; le chemin d'une entrée est son premier élément."""
    gardees = [entree for entree in entrees if not est_superflu(entree[0])]
    ecartees = [entree for entree in entrees if est_superflu(entree[0])]
    return gardees, ecartees
