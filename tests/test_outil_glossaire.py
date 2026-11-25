"""Outil qui construit le glossaire fourni (``outils/glossaire/construire.py``) : contrôle de ce qu'il assemble.

Le script assemble les lots de termes, les phrases d'exemple et les termes seuls dans
``donnees/glossaire_juridique.csv``. Depuis la version 0.11, un terme seul peut avoir sa phrase d'exemple ;
depuis la version 0.13, il peut avoir sa définition et des synonymes de plus, écrits dans ``definitions/``. Ces
tests travaillent sur des copies du fichier CSV et des dossiers ``exemples/``, ``termes/`` et ``definitions/`` :
ils ne modifient aucun fichier du projet.
"""

import csv
import importlib.util
import io
import shutil
import sys

import pytest
from conftest import (
    ENTREES_COMPLETES,
    NOMBRE_D_ENTREES,
    RACINE,
    TERMES_SEULS_AVEC_DEFINITION,
    TERMES_SEULS_AVEC_EXEMPLE,
)

from traducteur.glossaire import Glossaire, definition_a_verifier, equivalent_a_verifier
from traducteur.langues import AR, FR
from traducteur.surlignage import positions_du_terme

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
    """Le script, réglé pour lire et écrire des copies : le CSV, les exemples, les termes seuls, les définitions."""
    fichier, dossier, termes = tmp_path / "glossaire.csv", tmp_path / "exemples", tmp_path / "termes"
    definitions = tmp_path / "definitions"
    shutil.copy(script.CSV, fichier)
    shutil.copytree(script.EXEMPLES, dossier)
    shutil.copytree(script.TERMES, termes)
    shutil.copytree(script.DEFINITIONS, definitions)
    monkeypatch.setattr(script, "CSV", fichier)
    monkeypatch.setattr(script, "EXEMPLES", dossier)
    monkeypatch.setattr(script, "TERMES", termes)
    monkeypatch.setattr(script, "DEFINITIONS", definitions)
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


def test_les_lots_et_les_exemples_fournis_sont_acceptes(outil, glossaire_fourni, monkeypatch, capsys):
    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 0 and "ERREUR" not in sortie, sortie
    seuls = NOMBRE_D_ENTREES - ENTREES_COMPLETES
    assert f"40 entrées d'origine + 960 entrées des lots + {seuls} termes seuls = {NOMBRE_D_ENTREES}" in sortie
    # Chaque entrée d'un lot a sa phrase d'exemple ; les termes seuls ont reçu la leur par étapes (versions 0.11,
    # 0.12 et 0.14), et il n'en manque plus.
    pourvus = sum(1 for entree in glossaire_fourni.entrees[ENTREES_COMPLETES:] if entree.contextes)
    assert pourvus == seuls == TERMES_SEULS_AVEC_EXEMPLE
    assert f"phrases d'exemple : 960 sur 960 entrées des lots, {pourvus} sur {seuls} termes seuls" in sortie
    assert (f"il en manque {seuls - pourvus} (--manquants pour la liste)" in sortie) == (pourvus < seuls)
    # Chaque terme seul a aussi sa définition (version 0.13) : le script n'en signale aucun qui manque.
    definis = sum(1 for entree in glossaire_fourni.entrees[ENTREES_COMPLETES:] if entree.definition_fr)
    assert definis == seuls >= TERMES_SEULS_AVEC_DEFINITION
    assert f"définitions : {definis} sur {seuls} termes seuls" in sortie
    en_francais = sum(1 for entree in glossaire_fourni.entrees[ENTREES_COMPLETES:] if entree.synonymes_fr)
    en_arabe = sum(1 for entree in glossaire_fourni.entrees[ENTREES_COMPLETES:] if entree.synonymes_ar)
    assert f"termes seuls avec des synonymes : {en_francais} en français, {en_arabe} en arabe" in sortie
    # Version 0.16 : chaque entrée porte la mention de son équivalent, dans la colonne « source_equivalent ». Le
    # script l'écrit pour les entrées des lots et pour les termes seuls ; les 40 premières la portent déjà.
    assert glossaire_fourni.colonnes[:3] == ["terme_fr", "terme_ar", "source_equivalent"]
    assert {entree.source_equivalent for entree in glossaire_fourni.entrees} == {outil.SOURCE_EQUIVALENT}
    # Le fichier fourni est bien celui que donnent les lots, les exemples, les termes seuls et leurs définitions.
    assert "Le fichier CSV correspond aux lots, aux exemples et aux définitions." in sortie
    # Sans l'option --ecrire, le fichier CSV n'est pas touché.
    assert outil.CSV.read_bytes() == avant and "écrit :" not in sortie


def test_la_colonne_source_equivalent_est_exigee(outil, monkeypatch, capsys):
    """Version 0.16 : les 40 entrées d'origine, écrites à la main, doivent remplir « source_equivalent »."""
    lignes = outil.CSV.read_text(encoding="utf-8-sig").splitlines()
    debut = "contrat;عقد;à vérifier (équivalent d’exemple);"
    assert lignes[0].startswith("terme_fr;terme_ar;source_equivalent;") and lignes[1].startswith(debut)
    # Une cellule vide : le script la signale, avec la ligne du fichier CSV, et rend le code 1.
    vide = [lignes[0], lignes[1].replace(debut, "contrat;عقد;;", 1), *lignes[2:]]
    outil.CSV.write_text("\n".join(vide) + "\n", encoding="utf-8-sig")
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 1 and "1 ERREUR(S) :" in sortie
    assert ("glossaire.csv:2: « contrat » : la colonne « source_equivalent » est vide (écrire la source de "
            "l'équivalent, ou « à vérifier (équivalent d’exemple) »)") in sortie
    # Sans la colonne (un fichier d'avant la version 0.16), le script s'arrête tout de suite : l'application
    # n'afficherait la mention sous aucun équivalent.
    rangs = list(csv.reader(io.StringIO("\n".join(lignes) + "\n", newline=""), delimiter=";"))
    sans_colonne = io.StringIO()
    csv.writer(sans_colonne, delimiter=";", lineterminator="\n").writerows(rang[:2] + rang[3:] for rang in rangs)
    outil.CSV.write_text(sans_colonne.getvalue(), encoding="utf-8-sig")
    with pytest.raises(SystemExit, match="la colonne « source_equivalent » manque"):
        lancer(outil, monkeypatch, capsys)


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

    # Le CSV correspond maintenant aux lots, aux exemples et aux définitions ; une correction faite à la main est
    # signalée.
    outil.CSV.write_bytes(octets.replace("يسمح حق الانتفاع بمنزل بالسكن فيه.".encode(), "جملة مصححة باليد.".encode()))
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 0 and "Le fichier CSV diffère des lots, des exemples et des définitions : 1 ligne(s)." in sortie
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
    # 3. Une phrase trop longue pour la contextualisation.
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
def ecrire_les_termes(outil, *lignes: str, exemples: tuple[str, ...] = (),
                      definitions: tuple[str, ...] = ()) -> None:
    """Remplace les fichiers de termes seuls par un seul fichier, qui contient ``lignes``.

    Les phrases d'exemple et les définitions des fichiers retirés le sont aussi ; ``exemples`` et ``definitions``
    donnent celles du nouveau fichier.
    """
    for fichier in outil.TERMES.glob("*.txt"):
        (outil.EXEMPLES / fichier.name).unlink(missing_ok=True)
        (outil.DEFINITIONS / fichier.name).unlink(missing_ok=True)
        fichier.unlink()
    (outil.TERMES / "41_essai.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    if exemples:
        (outil.EXEMPLES / "41_essai.txt").write_text("\n".join(exemples) + "\n", encoding="utf-8")
    if definitions:
        (outil.DEFINITIONS / "41_essai.txt").write_text("\n".join(definitions) + "\n", encoding="utf-8")


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
    assert "phrases d'exemple : 960 sur 960 entrées des lots, 0 sur 6 termes seuls ; il en manque 6" in sortie
    assert "définitions : 0 sur 6 termes seuls ; il en manque 6 (--manquants pour la liste)" in sortie
    assert "termes seuls avec des synonymes : 1 en français, 1 en arabe" in sortie

    glossaire = Glossaire.charger(outil.CSV)
    assert len(glossaire) == 1006 and glossaire.lignes_ignorees == 0
    satellite, orbite, orbital, mettre, hors, au_dela = glossaire.entrees[ENTREES_COMPLETES:]
    assert (satellite.terme_ar, satellite.categorie_fr, satellite.categorie_ar) == (
        "قمر صناعي", "nom masculin", "مركب وصفي")
    assert (satellite.pluriel_fr, satellite.pluriel_ar) == ("satellites", "أقمار صناعية")
    assert satellite.domaines == ["Droit de l'espace", "Satellites"] and satellite.ressources
    assert (orbite.categorie_fr, orbite.synonymes_fr, orbite.synonymes_ar) == (
        "nom féminin", ["trajectoire orbitale"], ["فلك"])
    # Ni définition, ni exemple. La mention « à vérifier » de l'équivalent est écrite dans la colonne
    # « source_equivalent » (version 0.16) : la fiche l'affiche au pied de l'équivalent. Faute de définition, la
    # colonne « source_definition » reste vide.
    for entree in (satellite, orbite, orbital, mettre, hors, au_dela):
        assert not entree.definition_fr and not entree.definition_ar
        assert entree.source_equivalent == outil.SOURCE_EQUIVALENT == "à vérifier (équivalent d’exemple)"
        assert entree.source_definition == ""
        assert (equivalent_a_verifier(entree), definition_a_verifier(entree)) == ("équivalent d’exemple", None)
        assert entree.contextes == []
    # Les termes associés d'un terme seul sont ses voisins de groupe, comme dans un lot.
    assert satellite.termes_associes == ["orbite"] and orbite.termes_associes == ["satellite"]
    assert orbital.termes_associes == ["mettre en orbite", "hors atmosphère", "au-delà de"]
    # Un adjectif, un verbe, une locution : la catégorie dit ce qu'ils sont, dans les deux langues.
    assert [(entree.categorie_fr, entree.categorie_ar) for entree in (orbital, mettre, hors, au_dela)] == [
        ("adjectif", "صفة"), ("locution verbale", "عبارة فعلية"), ("locution adverbiale", "شبه جملة"),
        ("locution prépositive", "شبه جملة")]
    assert not any(entree.pluriel_fr or entree.pluriel_ar for entree in (orbital, mettre, hors, au_dela))


TERMES_DE_L_ESPACE = (
    "## Droit de l'espace | Satellites ## DIP",
    "satellite | قمر صناعي | ma | أقمار صناعية",
    "orbital | مداري | adj",
    "susceptible de lancement | قابل للإطلاق | adj",
    "lancer | أطلق | v",
    "mettre en orbite | وضع في المدار | v",
    "se désintégrer | تفكك | v",
    "au-delà de | فيما وراء | prep",
    "conformément à | طبقا ل | prep",
)


def test_la_phrase_d_exemple_d_un_terme_seul(outil, monkeypatch, capsys):
    """Version 0.11 : un terme seul reçoit sa phrase, écrite dans ``exemples/``, dans le fichier du même nom."""
    ecrire_les_termes(outil, *TERMES_DE_L_ESPACE, exemples=(
        "# terme | phrase française | phrase arabe",
        "satellite | L'État immatricule chaque satellite. | تسجل الدولة كل قمر صناعي.",
        # Un adjectif s'accorde avec son nom, dans les deux langues ; une locution adjectivale aussi.
        "orbital | La station orbitale relève de l'État d'immatriculation. | تخضع المحطة المدارية لدولة التسجيل.",
        "susceptible de lancement | Les fusées susceptibles de lancement sont déclarées. | "
        "يصرح بالصواريخ القابلة للإطلاق.",
        # Un verbe est au passé : le participe passé en français, le féminin en arabe (« أطلقت »).
        "lancer | L'agence a lancé un satellite. | أطلقت الوكالة قمرا صناعيا.",
        # Une locution verbale : quelques mots séparent le verbe de la suite, dans les deux langues.
        "mettre en orbite | L'agence a mis le satellite en orbite. | وضعت الوكالة القمر الصناعي في المدار.",
        "se désintégrer | Le satellite s'est désintégré dans l'atmosphère. | تفكك القمر الصناعي في الغلاف الجوي.",
        # Une locution se contracte avec le mot qui suit ; en arabe, la particule se colle à ce mot.
        "au-delà de | La loi ne s'applique pas au-delà des frontières. | لا يطبق القانون فيما وراء الحدود.",
        "conformément à | Le lancement est déclaré conformément au traité. | يصرح بالإطلاق طبقا للمعاهدة.",
    ))
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 0, sortie
    assert "phrases d'exemple : 960 sur 960 entrées des lots, 8 sur 8 termes seuls\n" in sortie  # il n'en manque pas

    glossaire = Glossaire.charger(outil.CSV)
    seuls = glossaire.entrees[ENTREES_COMPLETES:]
    assert len(seuls) == 8
    for entree in seuls:
        contexte, = entree.contextes
        # Pas de définition (aucun fichier de définitions ici) ; la phrase porte la même mention que celles des lots.
        assert not entree.definition_fr and contexte.source == outil.SOURCE_EXEMPLE and contexte.a_verifier
        # L'application repère le terme dans sa phrase, dans les deux langues.
        assert positions_du_terme(contexte.fr, entree, FR), entree.terme_fr
        assert positions_du_terme(contexte.ar, entree, AR), entree.terme_fr
    reperes = {entree.terme_fr: [[contexte.texte(langue)[debut:fin]
                                  for debut, fin in positions_du_terme(contexte.texte(langue), entree, langue)]
                                 for langue in (FR, AR)]
               for entree in seuls for contexte in entree.contextes}
    assert reperes["orbital"] == [["orbitale"], ["المدارية"]]
    assert reperes["susceptible de lancement"] == [["susceptibles de lancement"], ["القابلة للإطلاق"]]
    assert reperes["lancer"] == [["lancé"], ["أطلقت"]]
    assert reperes["mettre en orbite"] == [["mis", "en orbite"], ["وضعت", "في المدار"]]
    # Dans le CSV, l'apostrophe droite des fichiers d'exemples est devenue une apostrophe courbe.
    assert reperes["se désintégrer"] == [["s’est désintégré"], ["تفكك"]]
    assert reperes["au-delà de"] == [["au-delà des"], ["فيما وراء"]]
    assert reperes["conformément à"] == [["conformément au"], ["طبقا للمعاهدة"]]


def test_les_phrases_d_exemple_d_un_terme_seul_refusees(outil, monkeypatch, capsys):
    ecrire_les_termes(outil, *TERMES_DE_L_ESPACE, exemples=(
        # 1 : le verbe au présent n'est pas repéré, ni en français ni en arabe : il s'écrit au passé.
        "lancer | L'agence lance un satellite. | تطلق الوكالة قمرا صناعيا.",
        # 2 : l'adjectif est remplacé par un autre mot.
        "orbital | La station spatiale relève de l'État d'immatriculation. | تخضع المحطة الفضائية لدولة التسجيل.",
        # 3 : « contrat » est une entrée d'un lot, pas un terme de ce fichier.
        "contrat | Le contrat de lancement est écrit. | عقد الإطلاق مكتوب.",
        # 4 : le terme a déjà sa phrase, à la ligne 1.
        "lancer | L'agence a lancé une sonde. | أطلقت الوكالة مسبارا.",
    ))
    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 1 and outil.CSV.read_bytes() == avant and "écrit :" not in sortie
    erreurs = [ligne for ligne in sortie.splitlines() if ligne.startswith("41_essai.txt:")]
    for attendu in (
            "41_essai.txt:1: « lancer » : la phrase française ne contient pas « lancer »",
            "41_essai.txt:1: « lancer » : la phrase arabe ne contient pas « أطلق »",
            "41_essai.txt:2: « orbital » : la phrase française ne contient pas « orbital »",
            "41_essai.txt:2: « orbital » : la phrase arabe ne contient pas « مداري »",
            "41_essai.txt:3: exemple d'un terme absent de termes/41_essai.txt : contrat",
            "41_essai.txt:4: « lancer » a déjà un exemple",
    ):
        assert any(attendu in erreur for erreur in erreurs), (attendu, erreurs)
    assert len(erreurs) == 6

    # Un fichier d'exemples qui ne porte le nom d'aucun fichier de termes est lu comme celui d'un lot : ses
    # phrases ne vont pas aux termes seuls.
    (outil.EXEMPLES / "41_essai.txt").rename(outil.EXEMPLES / "99_autre_nom.txt")
    code, sortie = lancer(outil, monkeypatch, capsys)
    assert code == 1
    assert "99_autre_nom.txt:1: exemple d'un terme absent des lots : lancer" in sortie
    # « contrat » est une des 40 entrées d'origine : le script ne récrit pas ces entrées.
    assert "99_autre_nom.txt:3: exemple d'un terme absent des lots : contrat" in sortie


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


# ------------------------------------------------------------------ les définitions des termes seuls (version 0.13)
def test_la_definition_d_un_terme_seul(outil, monkeypatch, capsys):
    """Version 0.13 : un terme seul reçoit sa définition, écrite dans ``definitions/``, dans le fichier du même nom."""
    ecrire_les_termes(outil, *TERMES_DE_L_ESPACE, definitions=(
        "# terme | définition française | définition arabe | options",
        "",
        # Des synonymes peuvent suivre la définition : « sf= » en français, « sa= » en arabe.
        "satellite | Engin placé autour de la Terre pour l'observer. | مركبة توضع حول الأرض لرصدها. "
        "| sf=engin spatial | sa=ساتل",
        "orbital | Qui se rapporte à la trajectoire d'un engin autour d'un astre. | "
        "ما يتعلق بمسار مركبة حول جرم سماوي.",
        # « الإطلاق », le lancement, s'écrit comme le verbe « أطلق » à une lettre près : le script le distingue.
        "lancer | Envoyer un engin dans l'espace. | أرسل مركبة إلى الفضاء.",
        # Un mot de même écriture que le terme est permis s'il est annoncé : « طبقا » est aussi « des couches ».
        "conformément à | Mot qui introduit le texte que l'on suit. | لفظ يسبق النص المتبع، وقد تكون الأرض طبقا "
        "لذلك. | homographe=ar",
    ))
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 0, sortie
    assert "définitions : 4 sur 8 termes seuls ; il en manque 4 (--manquants pour la liste)" in sortie
    assert "termes seuls avec des synonymes : 1 en français, 1 en arabe" in sortie

    glossaire = Glossaire.charger(outil.CSV)
    seuls = {entree.terme_fr: entree for entree in glossaire.entrees[ENTREES_COMPLETES:]}
    satellite, lancer_ = seuls["satellite"], seuls["lancer"]
    # Dans le CSV, l'apostrophe droite du fichier de définitions est devenue une apostrophe courbe.
    assert satellite.definition_fr == "Engin placé autour de la Terre pour l’observer."
    assert satellite.definition_ar == "مركبة توضع حول الأرض لرصدها."
    assert (satellite.synonymes_fr, satellite.synonymes_ar) == (["engin spatial"], ["ساتل"])
    assert lancer_.definition_fr == "Envoyer un engin dans l’espace." and not lancer_.synonymes_fr
    for terme, entree in seuls.items():
        defini = terme in ("satellite", "orbital", "lancer", "conformément à")
        assert bool(entree.definition_fr) == bool(entree.definition_ar) == defini, terme
        # Chaque mention « à vérifier » a sa colonne : celle de l'équivalent, toujours ; celle de la définition,
        # quand le terme en a une. (Avant la version 0.16, une seule colonne portait les deux.)
        assert entree.source_equivalent == outil.SOURCE_EQUIVALENT, terme
        assert entree.source_definition == (outil.SOURCE if defini else ""), terme
        assert equivalent_a_verifier(entree) == "équivalent d’exemple", terme
        assert definition_a_verifier(entree) == ("définition d’exemple" if defini else None), terme
    assert outil.SOURCE == "à vérifier (définition d’exemple)"

    # Sans l'option --ecrire, le script dit seulement que le fichier correspond ; --manquants compte ce qui reste.
    code, sortie = lancer(outil, monkeypatch, capsys, "--manquants")
    assert code == 0 and "Le fichier CSV correspond aux lots, aux exemples et aux définitions." in sortie
    assert "termes seuls sans définition :\n   4  41_essai.txt" in sortie


def test_les_definitions_refusees(outil, monkeypatch, capsys):
    longue = "Engin " + "lancé depuis la Terre et " * 9 + "suivi."
    assert len(longue) > outil.LONGUEUR_DEFINITION == 200
    ecrire_les_termes(outil, *TERMES_DE_L_ESPACE, definitions=(
        # 1 : la définition reprend le terme, dans les deux langues (le pluriel compte aussi).
        "satellite | Un des satellites placés autour de la Terre. | قمر صناعي يوضع حول الأرض.",
        # 2 : sans majuscule ni point final en français ; des lettres latines en arabe.
        "orbital | qui tourne autour d'un astre | ما يدور حول جرم (astre).",
        # 3 : le verbe au participe passé est encore le terme ; la définition est aussi trop longue.
        f"lancer | {longue} | أرسل مركبة إلى الفضاء.",
        # 4 : « contrat » est une entrée d'un lot, pas un terme de ce fichier.
        "contrat | Accord de deux volontés. | اتفاق إرادتين.",
        # 5 : le terme a déjà sa définition, à la ligne 3.
        "lancer | Envoyer un engin dans l'espace. | أطلق مركبة.",
        # 6 : deux champs seulement.
        "au-delà de | Mot qui dit ce qui est plus loin.",
        # 7 : option inconnue ; 8 : un synonyme identique au terme.
        "mettre en orbite | Placer un engin sur sa trajectoire. | جعل مركبة في مسارها. | x=1",
        "se désintégrer | Se défaire en morceaux. | تحطم إلى أجزاء. | sf=se désintégrer",
        # 9 : la même définition française qu'à la ligne 8 ; 10 : l'option « homographe » ne sert à rien ici.
        "susceptible de lancement | Se défaire en morceaux. | ما يمكن إرساله إلى الفضاء.",
        "conformément à | Mot qui introduit le texte que l'on suit. | لفظ يسبق النص المتبع. | homographe=ar",
    ))
    (outil.DEFINITIONS / "99_autre_nom.txt").write_text("satellite | Engin. | مركبة.\n", encoding="utf-8")
    avant = outil.CSV.read_bytes()
    code, sortie = lancer(outil, monkeypatch, capsys, "--ecrire")
    assert code == 1 and outil.CSV.read_bytes() == avant and "écrit :" not in sortie
    # Chaque erreur nomme le fichier avec son dossier : « definitions/41_essai.txt » n'est pas « termes/41_essai.txt ».
    erreurs = [ligne for ligne in sortie.splitlines() if ligne.startswith("definitions/")]
    assert not any(ligne.startswith(("41_essai.txt:", "99_autre_nom.txt:")) for ligne in sortie.splitlines())
    for attendu in (
            "definitions/41_essai.txt:1: « satellite » : la définition française contient le terme « satellite »",
            "definitions/41_essai.txt:1: « satellite » : la définition arabe contient le terme « قمر صناعي »",
            "definitions/41_essai.txt:2: « orbital » : définition française : vide, arabe, sans majuscule ou sans",
            "definitions/41_essai.txt:2: « orbital » : définition arabe : vide, lettres latines, signe inattendu",
            f"definitions/41_essai.txt:3: « lancer » : définition française trop longue : {len(longue)} caractères",
            "definitions/41_essai.txt:3: « lancer » : la définition française contient le terme « lancer »",
            "definitions/41_essai.txt:4: définition d'un terme absent de termes/41_essai.txt : contrat",
            "definitions/41_essai.txt:5: « lancer » a déjà une définition",
            "definitions/41_essai.txt:6: 2 champs au lieu de 3 au moins",
            "definitions/41_essai.txt:7: option inconnue : x=1",
            "definitions/41_essai.txt:8: « se désintégrer » : synonyme répété, ou identique au terme : se désintégrer",
            # (signalée à la ligne du terme qui vient en second dans le fichier de termes)
            "definitions/41_essai.txt:8: même définition que « susceptible de lancement » : Se défaire en morceaux.",
            "definitions/41_essai.txt:10: « conformément à » : option homographe=ar inutile : la définition arabe ne",
            "definitions/99_autre_nom.txt:0: aucun fichier de termes seuls ne porte ce nom",
    ):
        assert any(attendu in erreur for erreur in erreurs), (attendu, erreurs)
    assert len(erreurs) == 14 and f"{len(erreurs)} ERREUR(S) :" in sortie, erreurs


def test_les_definitions_a_relire(outil, monkeypatch, capsys):
    """``--coherence-definitions`` : un terme du glossaire employé en français sans son équivalent en arabe."""
    ecrire_les_termes(outil, *TERMES_DE_L_ESPACE, definitions=(
        # « contrat » se dit « عقد » dans le glossaire : la définition arabe emploie un autre mot.
        "satellite | Engin dont le contrat règle le lancement. | مركبة ينظم الاتفاق إرسالها.",
        # Ici, le terme français et son équivalent sont tous les deux là : rien à relire.
        "orbital | Qui se rapporte au contrat d'un engin. | ما يتعلق بعقد مركبة.",
    ))
    code, sortie = lancer(outil, monkeypatch, capsys, "--coherence-definitions")
    assert code == 0, sortie
    assert "1 définition(s) à relire (terme français sans son équivalent arabe) :" in sortie
    a_relire = sortie.split("définition(s) à relire")[1]
    assert "satellite" in a_relire and "contrat" in a_relire and "orbital" not in a_relire


@pytest.mark.parametrize(
    ("verbe", "present", "autre"),
    [
        ("منح", "حماية يمنحها القانون", "المنحة التي يدفعها"),       # préfixe du présent, pronom à la fin
        ("أبرم", "عقد يبرمه الطرفان", "إبرام العقد"),               # le « أ » initial tombe
        ("ألغى", "قرار يلغي القانون", "إلغاء القانون"),              # la voyelle finale change
        ("أجاز", "نص يجيز ذلك", "الإجازة السنوية"),                 # la voyelle longue change
        ("وقع", "ما يقع من ضرر", "موقع العقار"),                    # le « و » initial tombe
        ("أنشأ", "عقد ينشئ التزاما", "إنشاء الشركة"),               # la hamza change de support
        ("صادق على", "ويصادق المجلس على النص", "المصادقة على النص"),  # locution : seul le verbe est cherché
    ],
)
def test_le_present_d_un_verbe_arabe(script, verbe, present, autre):
    """Le glossaire écrit les verbes au passé ; les définitions les emploient au présent."""
    motif = script.motif_du_present(verbe)
    assert motif.search(present) and not motif.search(autre)
    assert script.motif_du_present("") is None and script.motif_du_present("ب") is None
