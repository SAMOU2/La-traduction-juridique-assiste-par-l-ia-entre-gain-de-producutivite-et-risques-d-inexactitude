"""Outil qui construit le glossaire fourni (``outils/glossaire/construire.py``) : contrôle de ce qu'il assemble.

Le script assemble les lots de termes, les phrases d'exemple et les termes seuls dans
``donnees/glossaire_juridique.csv``. Ces tests travaillent sur des copies du fichier CSV et des dossiers
``exemples/`` et ``termes/`` : ils ne modifient aucun fichier du projet. Ils ne vérifient pas que le fichier CSV
fourni correspond encore aux lots : il peut avoir été corrigé à la main.
"""

import importlib.util
import shutil
import sys

import pytest
from conftest import ENTREES_COMPLETES, NOMBRE_D_ENTREES, RACINE

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
    """Le script, réglé pour lire et écrire des copies : le CSV, les phrases d'exemple et les termes seuls."""
    fichier, dossier, termes = tmp_path / "glossaire.csv", tmp_path / "exemples", tmp_path / "termes"
    shutil.copy(script.CSV, fichier)
    shutil.copytree(script.EXEMPLES, dossier)
    shutil.copytree(script.TERMES, termes)
    monkeypatch.setattr(script, "CSV", fichier)
    monkeypatch.setattr(script, "EXEMPLES", dossier)
    monkeypatch.setattr(script, "TERMES", termes)
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
    seuls = NOMBRE_D_ENTREES - ENTREES_COMPLETES
    assert f"40 entrées d'origine + 960 entrées des lots + {seuls} termes seuls = {NOMBRE_D_ENTREES}" in sortie
    # Chaque entrée d'un lot a sa phrase d'exemple.
    assert "phrases d'exemple : 960 sur 960 entrées des lots" in sortie and "il en manque" not in sortie
    # Le fichier fourni est bien celui que donnent les lots, les exemples et les termes seuls.
    assert "Le fichier CSV correspond aux lots et aux exemples." in sortie
    # Sans l'option --ecrire, le fichier CSV n'est pas touché.
    assert outil.CSV.read_bytes() == avant and "écrit :" not in sortie


def test_une_phrase_corrigee_est_ecrite_dans_le_csv(outil, monkeypatch, capsys):
    """Une phrase corrigée dans ``exemples/`` passe dans le CSV avec ``--ecrire``, sous la source « à vérifier »."""
    origine = outil.CSV.read_text(encoding="utf-8-sig").splitlines()[:41]
    remplacer_la_ligne(outil.EXEMPLES / "12_biens.txt", "usufruit", "L'usufruit d'une maison permet de l'habiter.",
                       "يسمح حق الانتفاع بمنزل بالسكن فيه.")
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 0 and f"écrit : {outil.CSV}" in sortie

    # Le fichier garde sa forme : marque d'ordre des octets, fin de ligne « \n », même nombre d'entrées.
    octets = outil.CSV.read_bytes()
    assert octets.startswith(b"\xef\xbb\xbf") and b"\r" not in octets and octets.endswith(b"\n")
    lignes = octets.decode("utf-8-sig").splitlines()
    assert len(lignes) == NOMBRE_D_ENTREES + 1
    assert lignes[:41] == origine  # les 40 premières entrées ne sont pas récrites
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


# ------------------------------------------------------------------ les termes seuls (version 0.8)
def ecrire_les_termes(outil, *lignes: str) -> None:
    """Remplace les fichiers de termes seuls par un seul fichier, qui contient ``lignes``."""
    for fichier in outil.TERMES.glob("*.txt"):
        fichier.unlink()
    (outil.TERMES / "41_essai.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def test_un_terme_seul_est_ecrit_sans_definition_ni_exemple(outil, monkeypatch, capsys):
    ecrire_les_termes(
        outil,
        "## Droit de l'espace | Satellites ## DIP",
        "satellite | قمر صناعي | ma | أقمار صناعية",
        "orbite | مدار | fm | مدارات | sf=trajectoire orbitale | sa=فلك",
        "",
        "orbital | مداري | adj",
        "mettre en orbite | وضع في المدار | v",
        "hors atmosphère | خارج الغلاف الجوي | adv",
        "au-delà de | فيما وراء | prep",
    )
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 0, sortie
    assert "40 entrées d'origine + 960 entrées des lots + 6 termes seuls = 1006 (objectif 5000, reste 3994)" in sortie

    glossaire = Glossaire.charger(outil.CSV)
    assert len(glossaire) == 1006 and glossaire.lignes_ignorees == 0
    satellite, orbite, orbital, mettre, hors, au_dela = glossaire.entrees[ENTREES_COMPLETES:]
    assert (satellite.terme_ar, satellite.categorie_fr, satellite.categorie_ar) == (
        "قمر صناعي", "nom masculin", "مركب وصفي")
    assert (satellite.pluriel_fr, satellite.pluriel_ar) == ("satellites", "أقمار صناعية")
    assert satellite.domaines == ["Droit de l'espace", "Satellites"] and satellite.ressources
    assert (orbite.categorie_fr, orbite.synonymes_fr, orbite.synonymes_ar) == (
        "nom féminin", ["trajectoire orbitale"], ["فلك"])
    # Ni définition, ni exemple. Faute de définition, la mention « à vérifier » porte sur l'équivalent : la fiche
    # l'affiche au pied du champ ②.
    for entree in (satellite, orbite, orbital, mettre, hors, au_dela):
        assert not entree.definition_fr and not entree.definition_ar
        assert entree.source_definition == "à vérifier (équivalent d’exemple)"
        assert entree.contextes == []
    # Les termes associés d'un terme seul sont ses voisins de groupe, comme dans un lot.
    assert satellite.termes_associes == ["orbite"] and orbite.termes_associes == ["satellite"]
    assert orbital.termes_associes == ["mettre en orbite", "hors atmosphère", "au-delà de"]
    # Un adjectif, un verbe, une locution : la catégorie dit ce qu'ils sont, dans les deux langues.
    assert [(entree.categorie_fr, entree.categorie_ar) for entree in (orbital, mettre, hors, au_dela)] == [
        ("adjectif", "صفة"), ("locution verbale", "عبارة فعلية"), ("locution adverbiale", "شبه جملة"),
        ("locution prépositive", "شبه جملة")]
    assert not any(entree.pluriel_fr or entree.pluriel_ar for entree in (orbital, mettre, hors, au_dela))


def test_les_termes_seuls_refuses(outil, monkeypatch, capsys):
    ecrire_les_termes(
        outil,
        "## Droit civil ## CIVIL",
        "contrat | عقد | mm | عقود",                  # 2 : déjà dans le glossaire
        "pacte | عقد | mm",                           # 3 : l'équivalent arabe désigne déjà « contrat »
        "convention écrite | اتفاق مكتوب | fa | sf=contrat",   # 4 : le synonyme est une autre entrée
        "nouveau terme | مصطلح جديد | ma | عقود",     # 5 : le pluriel arabe est celui de « contrat »
        "or | ذهب | mm",                              # 6 : la conjonction « or »
        "antériorité | قبل | fm",                     # 7 : « قبل », « avant », est un mot courant de l'arabe
        "terme sans codes | مصطلح",                   # 8 : deux champs
        "valable | صحيح | adj | صحاح",                # 9 : un adjectif n'a pas de pluriel
        "résilier | فسخ عقد | x",                     # 10 : code inconnu
        "immeuble bâti | عقار مبني | mm",             # 11 : deux mots arabes, noté comme un seul
        "chose jugée | الشيء المقضي به | fa",         # 12 : nom et adjectif écrits avec l'article
    )
    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 1 and outil.CSV.read_bytes() == avant and "écrit :" not in sortie
    erreurs = {int(ligne.split(":")[1]): ligne for ligne in sortie.splitlines() if ligne.startswith("41_essai.txt:")}
    for numero, attendu in (
            (3, "« pacte » : la forme « عقد » désigne aussi « contrat / عقد »"),
            (4, "« convention écrite » : la forme « contrat » désigne aussi « contrat / عقد »"),
            (5, "« nouveau terme » : la forme « عقود » désigne aussi « contrat / عقد »"),
            (6, "« or » est aussi un mot courant"),
            (7, "« قبل » est aussi un mot courant"),
            (8, "2 champs au lieu de 3 au moins"),
            (9, "un adjectif, un verbe ou une locution n'a pas de pluriel dans le glossaire"),
            (10, "codes invalides : x"),
            (11, "nature arabe « m » incompatible avec 2 mot(s)"),
            (12, "nom + adjectif : aucun mot ne doit porter l'article")):
        assert attendu in erreurs[numero], (numero, erreurs.get(numero))
    assert "doublon de « contrat / عقد » (origine)" in sortie
    assert f"{sortie.count('41_essai.txt:')} ERREUR(S)" in sortie
