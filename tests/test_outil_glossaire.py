"""Outil qui construit le glossaire fourni (``outils/glossaire/construire.py``) : contrôle des phrases d'exemple.

Le script assemble les lots de termes et les phrases d'exemple dans ``donnees/glossaire_juridique.csv``.
Ces tests travaillent sur des copies du fichier CSV et du dossier ``exemples/`` : ils ne modifient aucun
fichier du projet. Ils ne vérifient pas que le fichier CSV fourni correspond encore aux lots : il peut avoir
été corrigé à la main.
"""

import importlib.util
import shutil
import sys

import pytest
from conftest import RACINE

from traducteur.glossaire import Glossaire

SCRIPT = RACINE / "outils" / "glossaire" / "construire.py"


@pytest.fixture(scope="module")
def script():
    """Le script, chargé comme un module."""
    specification = importlib.util.spec_from_file_location("construire_le_glossaire", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    yield module
    del sys.modules[specification.name]


@pytest.fixture
def outil(script, monkeypatch, tmp_path):
    """Le script, réglé pour lire et écrire des copies : le fichier CSV et les phrases d'exemple du projet."""
    fichier, dossier = tmp_path / "glossaire.csv", tmp_path / "exemples"
    shutil.copy(script.CSV, fichier)
    shutil.copytree(script.EXEMPLES, dossier)
    monkeypatch.setattr(script, "CSV", fichier)
    monkeypatch.setattr(script, "EXEMPLES", dossier)
    return script


def lancer(outil, monkeypatch, capsys, *options: str) -> tuple[int, str]:
    """Lance le script ; renvoie le code de sortie et ce qu'il a écrit à l'écran."""
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *options])
    code = outil.construire()
    return code, capsys.readouterr().out


def phrases_de(fichier, terme: str) -> tuple[str, str]:
    """Les deux phrases écrites pour un terme dans un fichier d'exemples."""
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(f"{terme} | "):
            _, phrase_fr, phrase_ar = ligne.split(" | ")
            return phrase_fr, phrase_ar
    raise AssertionError(terme)


def remplacer_la_ligne(fichier, terme: str, phrase_fr: str, phrase_ar: str) -> None:
    """Remplace, dans un fichier d'exemples, la ligne d'un terme."""
    lignes = fichier.read_text(encoding="utf-8").splitlines()
    rangs = [rang for rang, ligne in enumerate(lignes) if ligne.startswith(f"{terme} | ")]
    assert len(rangs) == 1, terme
    lignes[rangs[0]] = f"{terme} | {phrase_fr} | {phrase_ar}"
    fichier.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def test_les_lots_et_les_exemples_fournis_sont_acceptes(outil, monkeypatch, capsys):
    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 0 and "ERREUR" not in sortie, sortie
    assert "40 entrées d'origine + 960 nouvelles = 1000" in sortie
    # Chaque entrée nouvelle a sa phrase d'exemple.
    assert "phrases d'exemple : 960 sur 960 entrées nouvelles" in sortie and "il en manque" not in sortie
    # Sans l'option --ecrire, le fichier CSV n'est pas touché.
    assert outil.CSV.read_bytes() == avant and "écrit :" not in sortie


def test_une_phrase_corrigee_est_ecrite_dans_le_csv(outil, monkeypatch, capsys):
    """Une phrase corrigée dans ``exemples/`` passe dans le CSV avec ``--ecrire``, sous la source « à vérifier »."""
    origine = outil.CSV.read_text(encoding="utf-8-sig").splitlines()[:41]
    remplacer_la_ligne(outil.EXEMPLES / "12_biens.txt", "usufruit", "L'usufruit d'une maison permet de l'habiter.",
                       "يسمح حق الانتفاع بمنزل بالسكن فيه.")
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 0 and f"écrit : {outil.CSV}" in sortie

    # Le fichier garde sa forme : marque d'ordre des octets, fin de ligne « \n », 1 000 entrées.
    octets = outil.CSV.read_bytes()
    assert octets.startswith(b"\xef\xbb\xbf") and b"\r" not in octets and octets.endswith(b"\n")
    lignes = octets.decode("utf-8-sig").splitlines()
    assert len(lignes) == 1001 and lignes[:41] == origine  # les 40 premières entrées ne sont pas récrites
    glossaire = Glossaire.charger(outil.CSV)
    contexte, = next(entree for entree in glossaire.entrees if entree.terme_fr == "usufruit").contextes
    # L'apostrophe droite du fichier d'exemples devient une apostrophe courbe.
    assert (contexte.fr, contexte.ar) == ("L’usufruit d’une maison permet de l’habiter.",
                                          "يسمح حق الانتفاع بمنزل بالسكن فيه.")
    assert contexte.source == outil.SOURCE_EXEMPLE == "à vérifier (phrase d’exemple)" and contexte.a_verifier

    # Le CSV correspond maintenant aux lots et aux exemples ; une correction faite à la main est signalée.
    outil.CSV.write_bytes(octets.replace("يسمح حق الانتفاع بمنزل بالسكن فيه.".encode(), "جملة مصححة باليد.".encode()))
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 0 and "Le fichier CSV diffère des lots et des exemples : 1 ligne(s)." in sortie
    assert "serait alors perdue" in sortie and "écrit :" not in sortie


def test_les_phrases_d_exemple_refusees(outil, glossaire_fourni, monkeypatch, capsys):
    biens = outil.EXEMPLES / "12_biens.txt"
    # 1. La phrase d'une autre entrée, recopiée : le terme n'y figure pas, et la phrase sert déjà.
    meuble_fr, meuble_ar = phrases_de(biens, "bien meuble")
    remplacer_la_ligne(biens, "chose fongible", meuble_fr, meuble_ar)
    # 2. Une phrase arabe identique à l'exemple d'une des 40 premières entrées (ici, un article du Code civil).
    debiteur = next(entree for entree in glossaire_fourni.entrees if entree.terme_fr == "débiteur")
    officielle = debiteur.contextes[0].ar
    assert "أموال" in officielle and not debiteur.contextes[0].a_verifier
    remplacer_la_ligne(biens, "biens", "Les créanciers peuvent saisir tous les biens du débiteur.", officielle)
    # 3. Une phrase trop longue pour le champ ④.
    longue = "Le propriétaire " + "peut vendre sa maison et " * 7 + "la louer."
    assert len(longue) > outil.LONGUEUR_EXEMPLE
    remplacer_la_ligne(biens, "propriétaire", longue, phrases_de(biens, "propriétaire")[1])
    # 4. Une phrase sans point final, et une phrase arabe qui contient des lettres latines.
    remplacer_la_ligne(biens, "fruits", "Les fruits de la chose appartiennent à son propriétaire",
                       "ثمار الشيء ملك لمالكه (fruits).")
    # 5. Trois lignes mal formées, à la fin du fichier.
    with biens.open("a", encoding="utf-8") as flux:
        flux.write("terme inconnu | Phrase sans entrée. | جملة بلا مدخل.\n")
        flux.write("partage | Une seconde phrase pour le partage. | جملة ثانية عن القسمة.\n")
        flux.write("usufruit | Deux champs seulement.\n")
    nombre = len(biens.read_text(encoding="utf-8").splitlines())

    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 1
    erreurs = [ligne for ligne in sortie.splitlines() if ligne.startswith("12_biens.txt:")]
    for attendu in (
            "« chose fongible » : la phrase française ne contient pas « chose fongible »",
            "« chose fongible » : la phrase arabe ne contient pas",
            f"même phrase que « bien meuble » : {meuble_fr}",
            f"même phrase que « bien meuble » : {meuble_ar}",
            f"même phrase que « débiteur » : {officielle}",
            f"« propriétaire » : phrase française trop longue : {len(longue)} caractères (maximum 170)",
            "« fruits » : phrase française : vide, avec de l'arabe, sans majuscule ou sans point final",
            "« fruits » : phrase arabe : vide, lettres latines, signe inattendu ou sans point final",
            f"12_biens.txt:{nombre - 2}: exemple d'un terme absent des lots : terme inconnu",
            f"12_biens.txt:{nombre - 1}: « partage » a déjà un exemple",
            f"12_biens.txt:{nombre}: 2 champs au lieu de 3",
    ):
        assert any(attendu in erreur for erreur in erreurs), (attendu, erreurs)
    # Seules ces sept lignes sont refusées, et rien n'est écrit tant qu'il reste une erreur.
    assert len({erreur.split(":")[1] for erreur in erreurs}) == 7
    assert f"{len(erreurs)} ERREUR(S) :" in sortie
    assert outil.CSV.read_bytes() == avant and "écrit :" not in sortie
