"""Outils qui fabriquent l'installeur Windows (dossier outils/installeur).

L'installeur lui-même ne se fabrique que sous Windows : ces tests portent sur ce qui se vérifie partout,
c'est-à-dire la liste des fichiers, l'icône, le texte de la page de téléchargement et l'accord entre
les fichiers de l'installeur.
"""

import struct
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest
from conftest import RACINE

OUTILS = RACINE / "outils" / "installeur"
if str(OUTILS) not in sys.path:
    sys.path.insert(0, str(OUTILS))

import construire  # noqa: E402
import fichiers  # noqa: E402
import publier  # noqa: E402

from traducteur import NOM_APPLICATION, __version__  # noqa: E402

WIX = "{http://schemas.microsoft.com/wix/2006/wi}"


@pytest.fixture
def dossier(tmp_path):
    """Un petit dossier rangé comme celui que PyInstaller produit."""
    racine = tmp_path / "TraducteurJuridique"
    for chemin in ("TraducteurJuridique.exe", "_internal/python313.dll", "_internal/donnees/glossaire_juridique.csv",
                   "_internal/PySide6/Qt6Core.dll", "_internal/PySide6/plugins/platforms/qwindows.dll"):
        fichier = racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_bytes(b"x")
    return racine


def _elements(document, nom):
    return list(document.iter(WIX + nom))


# ---------------------------------------------------------------------- liste des fichiers
def test_chaque_fichier_et_chaque_dossier_est_decrit(dossier):
    document = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    sources = sorted(element.get("Source") for element in _elements(document, "File"))
    assert sources == sorted([
        "$(var.Source)\\TraducteurJuridique.exe",
        "$(var.Source)\\_internal\\python313.dll",
        "$(var.Source)\\_internal\\donnees\\glossaire_juridique.csv",
        "$(var.Source)\\_internal\\PySide6\\Qt6Core.dll",
        "$(var.Source)\\_internal\\PySide6\\plugins\\platforms\\qwindows.dll",
    ])
    # Six dossiers : la racine, _internal, donnees, PySide6, plugins et platforms.
    assert fichiers.compter(document) == (5, 6)
    noms = sorted(element.get("Name") for element in _elements(document, "Directory"))
    assert noms == ["PySide6", "_internal", "donnees", "platforms", "plugins"]
    # Les dossiers sont emboîtés comme sur le disque.
    racine = _elements(document, "DirectoryRef")[0]
    assert racine.get("Id") == fichiers.DOSSIER_D_INSTALLATION
    interne = racine.find(WIX + "Directory")
    assert interne.get("Name") == "_internal"
    assert sorted(fils.get("Name") for fils in interne.findall(WIX + "Directory")) == ["PySide6", "donnees"]


def test_le_programme_a_un_identifiant_connu_de_l_installeur(dossier):
    document = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    noms = [element.get("Name") for element in _elements(document, "File")
            if element.get("Id") == fichiers.PROGRAMME_PRINCIPAL]
    assert noms == ["TraducteurJuridique.exe"]


def test_chaque_dossier_suit_les_regles_d_une_installation_sans_administrateur(dossier):
    """Un composant par dossier, repéré par une valeur du registre de l'utilisateur, et retiré à la désinstallation."""
    document = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    composants = _elements(document, "Component")
    repertoires = {element.get("Id") for element in _elements(document, "Directory")}
    assert {composant.get("Directory") for composant in composants} == repertoires | {fichiers.DOSSIER_D_INSTALLATION}
    for composant in composants:
        marque = composant.findall(WIX + "RegistryValue")
        assert len(marque) == 1
        assert (marque[0].get("Root"), marque[0].get("Key"), marque[0].get("KeyPath")) == (
            "HKCU", fichiers.CLE_DU_REGISTRE, "yes")
        assert [retrait.get("On") for retrait in composant.findall(WIX + "RemoveFolder")] == ["uninstall"]
        assert composant.get("Guid").startswith("{") and len(composant.get("Guid")) == 38
    groupe = _elements(document, "ComponentGroup")
    assert [element.get("Id") for element in groupe] == [fichiers.GROUPE]
    assert len(groupe[0].findall(WIX + "Component")) == len(composants)


def test_les_identifiants_sont_uniques_et_ne_changent_pas_d_une_fabrication_a_l_autre(dossier):
    premier = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    second = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    identifiants = [element.get("Id") for nom in ("File", "Directory", "Component", "RemoveFolder")
                    for element in _elements(premier, nom)]
    assert len(identifiants) == len(set(identifiants))
    assert all(len(identifiant) <= 72 and identifiant[0].isalpha() for identifiant in identifiants)
    guids = [composant.get("Guid") for composant in _elements(premier, "Component")]
    assert len(guids) == len(set(guids))
    assert ElementTree.tostring(premier.getroot()) == ElementTree.tostring(second.getroot())
    # Un fichier ajouté ne change pas l'identifiant des autres : Windows Installer s'y fie pour une mise à jour.
    (dossier / "_internal" / "nouveau.dll").write_bytes(b"x")
    apres = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    assert set(guids) == {composant.get("Guid") for composant in _elements(apres, "Component")}
    assert set(identifiants) < {element.get("Id") for nom in ("File", "Directory", "Component", "RemoveFolder")
                                for element in _elements(apres, nom)}


def test_un_dossier_vide_est_tout_de_meme_cree(dossier):
    (dossier / "_internal" / "vide").mkdir()
    document = fichiers.fragment(dossier, "TraducteurJuridique.exe")
    vide = next(element for element in _elements(document, "Directory") if element.get("Name") == "vide")
    composant = next(element for element in _elements(document, "Component")
                     if element.get("Directory") == vide.get("Id"))
    assert composant.find(WIX + "CreateFolder") is not None and composant.find(WIX + "File") is None
    autres = [element for element in _elements(document, "Component") if element is not composant]
    assert all(element.find(WIX + "CreateFolder") is None for element in autres)


def test_un_dossier_sans_le_programme_est_refuse(dossier):
    (dossier / "TraducteurJuridique.exe").unlink()
    with pytest.raises(fichiers.ErreurFichiers, match=r"TraducteurJuridique\.exe"):
        fichiers.fragment(dossier, "TraducteurJuridique.exe")


def test_un_nom_que_l_installeur_ne_sait_pas_ecrire_est_refuse(dossier):
    """L'installeur écrit ses textes dans le jeu de caractères d'Europe de l'Ouest : pas de lettres arabes."""
    (dossier / "_internal" / "قاموس.csv").write_bytes(b"x")
    with pytest.raises(fichiers.ErreurFichiers, match="قاموس"):
        fichiers.fragment(dossier, "TraducteurJuridique.exe")
    (dossier / "_internal" / "قاموس.csv").unlink()
    (dossier / "_internal" / "données.csv").write_bytes(b"x")  # les lettres accentuées, elles, s'écrivent
    assert fichiers.compter(fichiers.fragment(dossier, "TraducteurJuridique.exe"))[0] == 6


def test_la_liste_est_ecrite_dans_un_fichier_lisible(dossier, tmp_path):
    sortie = tmp_path / "sortie" / "fichiers.wxs"
    assert fichiers.ecrire(dossier, "TraducteurJuridique.exe", sortie) == (5, 6)
    relu = ElementTree.parse(sortie)
    assert relu.getroot().tag == WIX + "Wix" and len(_elements(relu, "File")) == 5


# ---------------------------------------------------------------------- accord entre les fichiers de l'installeur
@pytest.fixture(scope="module")
def description():
    """« traducteur.wxs », la partie de l'installeur écrite à la main."""
    return ElementTree.parse(OUTILS / "traducteur.wxs")


def test_la_description_de_l_installeur_et_la_liste_des_fichiers_s_accordent(description):
    assert [element.get("Id") for element in _elements(description, "ComponentGroupRef")] == [fichiers.GROUPE]
    assert fichiers.DOSSIER_D_INSTALLATION in {element.get("Id") for element in _elements(description, "Directory")}
    # « Ouvrir l'application » à la fin de l'installation lance le programme décrit par la liste des fichiers.
    actions = _elements(description, "CustomAction")
    assert [element.get("FileKey") for element in actions] == [fichiers.PROGRAMME_PRINCIPAL]
    assert {element.get("Key") for element in _elements(description, "RegistryValue")} == {fichiers.CLE_DU_REGISTRE}


def test_l_installeur_ne_demande_pas_de_droits_d_administrateur(description):
    assert [element.get("InstallScope") for element in _elements(description, "Package")] == ["perUser"]
    assert {element.get("Root") for element in _elements(description, "RegistryValue")} == {"HKCU"}


def test_l_installeur_cree_deux_raccourcis_vers_le_programme(description):
    raccourcis = _elements(description, "Shortcut")
    assert len(raccourcis) == 2
    assert {raccourci.get("Target") for raccourci in raccourcis} == {"[INSTALLFOLDER]$(var.Programme)"}
    texte = (OUTILS / "traducteur.wxs").read_text(encoding="utf-8")
    assert f'<?define Programme = "{construire.PROGRAMME}" ?>' in texte
    assert f'<?define Nom = "{NOM_APPLICATION}" ?>' in texte


def test_les_textes_de_l_installeur_s_ecrivent_dans_son_jeu_de_caracteres(description):
    """Une flèche ou une lettre arabe dans un texte affiché ferait échouer la fabrication."""
    for element in description.iter():
        for texte in (*element.attrib.values(), element.text or ""):
            texte.encode(fichiers.JEU_DE_CARACTERES)


def test_la_recette_de_pyinstaller_est_du_python_correct():
    compile((OUTILS / "traducteur.spec").read_text(encoding="utf-8"), "traducteur.spec", "exec")


# ---------------------------------------------------------------------- icône
def test_l_icone_contient_toutes_ses_tailles(application, tmp_path):
    import icone

    sortie = tmp_path / "traducteur.ico"
    icone.ecrire(sortie)
    donnees = sortie.read_bytes()
    reserve, genre, nombre = struct.unpack_from("<HHH", donnees, 0)
    assert (reserve, genre, nombre) == (0, 1, len(icone.TAILLES))
    fin = 6 + 16 * nombre
    for rang, cote in enumerate(icone.TAILLES):
        largeur, hauteur, _, _, plans, bits, longueur, debut = struct.unpack_from("<BBBBHHII", donnees, 6 + 16 * rang)
        assert (largeur or 256, hauteur or 256, plans, bits) == (cote, cote, 1, 32)
        assert debut == fin  # les images se suivent sans trou
        image = donnees[debut:debut + longueur]
        if cote >= 256:
            assert image.startswith(b"\x89PNG\r\n\x1a\n")
        else:
            # Hauteur doublée dans l'en-tête : l'image, puis son masque de transparence.
            assert struct.unpack_from("<Iii", image, 0) == (40, cote, 2 * cote)
            assert longueur == 40 + cote * cote * 4 + cote * ((cote + 31) // 32 * 4)
        fin = debut + longueur
    assert fin == len(donnees)


def test_l_icone_est_transparente_dans_les_coins_et_opaque_au_centre(application):
    import icone

    image = icone.dessin(48)
    assert (image.width(), image.height()) == (48, 48)
    assert image.pixelColor(0, 0).alpha() == 0 and image.pixelColor(47, 47).alpha() == 0
    assert image.pixelColor(24, 8).alpha() == 255


# ---------------------------------------------------------------------- publication
def test_la_branche_principale_publie_une_version_les_autres_une_version_d_essai():
    assert publier.publication("main", "1.2.3") == ("v1.2.3", f"{NOM_APPLICATION} 1.2.3", False)
    etiquette, titre, essai = publier.publication("arena/travail-en-cours", "1.2.3")
    assert (etiquette, essai) == (publier.ETIQUETTE_D_ESSAI, True) and "essai" in titre and "1.2.3" in titre


def test_la_page_de_telechargement_explique_l_installation():
    texte = publier.notes("Traducteur-juridique-1.2.3.msi", "1.2.3", False, "main", "0123456789abcdef",
                          "- Installeur : 30 Mo\n", "https://exemple.org/fabrication/1")
    assert "Téléchargez le fichier **Traducteur-juridique-1.2.3.msi**" in texte
    assert "**Suivant**, puis sur **Installer**, puis sur **Terminer**" in texte
    assert "Exécuter quand même" in texte and "Python est dans l’installeur" in texte
    assert "- Installeur : 30 Mo" in texte and "commit `0123456`" in texte
    assert "[Journal de la fabrication](https://exemple.org/fabrication/1)" in texte
    assert "essai" not in texte


def test_une_version_d_essai_s_annonce_comme_telle():
    texte = publier.notes("Traducteur-juridique-1.2.3.msi", "1.2.3", True, "arena/travail", "0123456789abcdef", "")
    assert texte.startswith("**Version d’essai.**") and "`arena/travail`" in texte
    assert "Aucune vérification n’a été notée." in texte


# ---------------------------------------------------------------------- fabrication
def test_le_nom_de_l_installeur_porte_le_numero_de_version():
    assert f"Traducteur-juridique-{__version__}.msi" == construire.NOM_DE_L_INSTALLEUR


def test_la_fin_d_un_journal_garde_les_dernieres_lignes():
    journal = "\n".join(f"ligne {numero}" for numero in range(1, 201))
    assert construire.fin_de(journal, lignes=3) == "ligne 198\nligne 199\nligne 200"
    assert construire.fin_de("x" * 10_000, caracteres=100) == "x" * 100
    assert construire.fin_de("") == ""


def test_une_erreur_de_fabrication_s_affiche_sur_la_page_de_github(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    construire.annoter("error", "Étape « 5-light », essai", "ligne 1\nligne 2 : 100 %")
    assert capsys.readouterr().out == "::error title=Étape « 5-light »%2C essai::ligne 1%0Aligne 2 : 100 %25\n"
    monkeypatch.delenv("GITHUB_ACTIONS")
    construire.annoter("error", "Étape", "message")
    assert capsys.readouterr().out == ""


def test_la_fabrication_refuse_de_demarrer_ailleurs_que_sous_windows(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", ["construire.py"])
    assert construire.main() == 1
    assert "sous Windows" in capsys.readouterr().out
    assert not (Path(construire.TRAVAIL) / "resume.md").exists()
