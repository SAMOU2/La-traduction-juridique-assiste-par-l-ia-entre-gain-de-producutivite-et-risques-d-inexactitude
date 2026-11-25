"""Contrôle de l'installation : l'application s'essaie elle-même et écrit un rapport (option --controle)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import GLOSSAIRE_D_ESSAI, RACINE
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from traducteur import __version__, controle
from traducteur.interface.details import CLES, DETAILS


def _attendre_la_fin(suivi: controle.Controle, delai: int = 10_000) -> None:
    """Laisse tourner l'application jusqu'à la fin du contrôle."""
    attendu = 0
    while suivi.code is None and attendu < delai:
        QTest.qWait(50)
        attendu += 50
    assert suivi.code is not None, "le contrôle ne s'est pas terminé"


def _rapport(dossier: Path) -> dict:
    return json.loads((dossier / controle.NOM_DU_RAPPORT).read_text(encoding="utf-8"))


def _points_de_couleur(fichier: Path, couleur: str) -> int:
    """Nombre de points d'une image qui ont exactement cette couleur."""
    image = QImage(str(fichier)).convertToFormat(QImage.Format.Format_RGB32)
    assert not image.isNull(), fichier
    voulue = QColor(couleur)
    # Quatre octets par point, sans octet de remplissage : bleu, vert, rouge, puis 255.
    return bytes(image.constBits()).count(bytes([voulue.blue(), voulue.green(), voulue.red(), 255]))


@pytest.fixture
def demarrage_court(monkeypatch):
    """L'écran de démarrage ne reste que 0,2 seconde."""
    from traducteur.interface.demarrage import EcranDemarrage

    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 200)


@pytest.fixture
def textes_de_qt(application):
    """Les textes de Qt sont mis en français, comme au lancement de l'application, le temps d'un test."""
    from traducteur.application import installer_les_textes_de_qt

    textes = installer_les_textes_de_qt(application)
    if textes is None:
        pytest.skip("cette installation de Qt ne contient pas ses textes en français")
    yield
    application.removeTranslator(textes)
    textes.deleteLater()


def test_le_dossier_du_controle_est_lu_dans_les_arguments(tmp_path):
    assert controle.dossier_demande(["main.py"]) is None
    assert controle.dossier_demande(["main.py", "glossaire.csv"]) is None
    assert controle.dossier_demande(["main.py", "--controle="]) is None  # aucun dossier donné
    assert controle.dossier_demande(["main.py", f"--controle={tmp_path}"]) == tmp_path
    assert controle.dossier_demande(["main.py", "glossaire.csv", "--controle=un dossier"]) == Path("un dossier")
    # Le premier argument est le nom du programme : il n'est jamais lu comme une option.
    assert controle.dossier_demande(["--controle=x"]) is None


def test_le_controle_essaie_l_application_et_ecrit_son_rapport(application, tmp_path, demarrage_court, textes_de_qt):
    from traducteur.interface import boites

    afficher = boites.afficher
    suivi = controle.Controle(application, tmp_path / "rapport")
    codes = []
    suivi.termine.connect(codes.append)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    rapport = _rapport(tmp_path / "rapport")
    assert rapport["erreurs"] == []
    assert rapport["reussi"] is True and suivi.code == 0 and codes == [0]
    assert rapport["application"]["version"] == __version__ and rapport["application"]["installee"] is False
    assert rapport["demarrage"] == {"ecran_de_demarrage": True, "fond_transparent": True}
    assert rapport["glossaire"] == {"fichier": str(GLOSSAIRE_D_ESSAI), "fourni": True, "entrees": 40}
    assert rapport["recherche"]["entrees_trouvees"] >= 1
    # Le menu « Plus de détails » : la première information que le glossaire donne pour ce terme a été ouverte.
    informations = rapport["recherche"]["informations"]
    assert informations and set(informations) <= set(CLES)
    assert rapport["recherche"]["information_affichee"] == informations[0]
    assert rapport["traduction"]["termes_reconnus"] >= 1 and rapport["traduction"]["caracteres"] > 0
    # La fiche d'un terme du texte a été ouverte par un clic sur sa case, puis « Retour au texte » a ramené au texte.
    assert rapport["traduction"]["fiche_ouverte_depuis_le_texte"] == "contrat"
    # Le pointeur est venu sur le premier terme du texte : il s'est allumé à ses trois occurrences, aux trois
    # passages de la traduction qui le rendent et sur sa case, puis il s'est éteint.
    assert rapport["terme_allume"] == {"terme": "contrat", "dans_le_texte": 3, "dans_la_traduction": 3}
    assert rapport["ecrans"] == ["parametres", "description", "aide", "texte", "terme"]
    assert rapport["textes_de_qt"] == {"en_francais": True}
    # Les fichiers annoncés existent : le document Word de la traduction et l'image de la fenêtre.
    assert (tmp_path / "rapport" / rapport["document"]["fichier"]).stat().st_size == rapport["document"]["octets"]
    assert (tmp_path / "rapport" / rapport["image"]["fichier"]).read_bytes().startswith(b"\x89PNG")
    # Après le contrôle, la fenêtre est fermée et les boîtes de message fonctionnent de nouveau.
    assert not suivi.fenetre.isVisible() and boites.afficher is afficher
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_le_controle_ne_touche_pas_aux_reglages_de_l_utilisateur(application, tmp_path, demarrage_court):
    suivi = controle.Controle(application, tmp_path)
    assert Path(suivi.reglages.fileName()) == tmp_path / "reglages.ini"
    suivi.demarrer()
    assert suivi.fenetre.reglages is suivi.reglages
    _attendre_la_fin(suivi)
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_un_glossaire_fourni_introuvable_fait_echouer_le_controle(application, tmp_path, demarrage_court,
                                                                  monkeypatch):
    from traducteur.interface import fenetre

    monkeypatch.setattr(fenetre, "GLOSSAIRE_EXEMPLE", tmp_path / "donnees" / "glossaire_juridique.csv")
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    rapport = _rapport(tmp_path)
    assert rapport["reussi"] is False and suivi.code == 1
    assert "glossaire : aucun glossaire n'est chargé" in rapport["erreurs"]
    # La boîte « Glossaire non chargé » ne s'est pas ouverte (elle aurait attendu un clic) : elle est dans le rapport.
    assert any(erreur.startswith("message affiché : « Glossaire non chargé »") for erreur in rapport["erreurs"])
    # Les autres étapes ont tout de même été essayées : les écrans s'affichent sans glossaire.
    assert rapport["ecrans"] == ["parametres", "description", "aide", "texte", "terme"]
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_l_ecran_de_demarrage_est_photographie_sur_l_ecran_de_l_ordinateur(application, tmp_path, monkeypatch):
    """L'image montre ce qu'il y a derrière le logo : c'est elle qui dit si le fond est transparent."""
    from traducteur.interface.demarrage import EcranDemarrage

    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 600)
    monkeypatch.setattr(controle, "MOMENT_DE_L_IMAGE_DU_DEMARRAGE", 100)
    monkeypatch.setattr(controle, "AFFICHAGES_SANS_ECRAN", ())  # les tests n'ont pas d'écran : on fait comme si
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    demarrage = _rapport(tmp_path)["demarrage"]
    assert demarrage["image"] == controle.NOM_DE_L_IMAGE_DU_DEMARRAGE
    assert (tmp_path / demarrage["image"]).read_bytes().startswith(b"\x89PNG")
    assert len(demarrage["coins"]) == 4 and all(len(coin) == 9 and coin[0] == "#" for coin in demarrage["coins"])
    assert demarrage["logo"] == "#ff1e325c"  # le carré du logo est bien à cet endroit de l'image
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_sans_ecran_il_n_y_a_pas_d_image_de_l_ecran_de_demarrage(application, tmp_path, monkeypatch):
    from traducteur.interface.demarrage import EcranDemarrage

    if application.platformName() not in controle.AFFICHAGES_SANS_ECRAN:
        pytest.skip("ces tests sont lancés avec un écran")
    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 600)
    monkeypatch.setattr(controle, "MOMENT_DE_L_IMAGE_DU_DEMARRAGE", 100)
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    assert _rapport(tmp_path)["demarrage"] == {"ecran_de_demarrage": True, "fond_transparent": True}
    assert not (tmp_path / controle.NOM_DE_L_IMAGE_DU_DEMARRAGE).exists()
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_des_textes_de_qt_en_anglais_font_echouer_le_controle(application, tmp_path, demarrage_court):
    """Sans les textes français de Qt, les menus « Copier », « Coller »… s'affichent en anglais."""
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    rapport = _rapport(tmp_path)
    assert rapport["reussi"] is False and suivi.code == 1
    assert [erreur.split(" : ")[0] for erreur in rapport["erreurs"]] == ["textes_de_qt"]
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_un_terme_qui_ne_s_allume_pas_fait_echouer_le_controle(application, tmp_path, demarrage_court, textes_de_qt,
                                                               monkeypatch):
    from traducteur.interface.texte import PageTexte

    monkeypatch.setattr(PageTexte, "allumer", lambda self, entree: None)  # le pointeur n'allume plus rien
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    rapport = _rapport(tmp_path)
    assert rapport["reussi"] is False and suivi.code == 1
    assert rapport["erreurs"] == ["terme_allume : le terme placé sous le pointeur ne s'est pas allumé"]
    assert "terme_allume" not in rapport
    # Les autres étapes ont réussi : la traduction, le document, les écrans.
    assert rapport["traduction"]["fiche_ouverte_depuis_le_texte"] == "contrat"
    assert rapport["ecrans"] == ["parametres", "description", "aide", "texte", "terme"]
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_un_controle_trop_long_est_un_echec(application, tmp_path, monkeypatch):
    from traducteur.interface.demarrage import EcranDemarrage

    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 5_000)  # la fenêtre n'arrive pas à temps
    monkeypatch.setattr(controle, "DELAI", 300)
    suivi = controle.Controle(application, tmp_path)
    suivi.demarrer()
    _attendre_la_fin(suivi)

    rapport = _rapport(tmp_path)
    assert rapport["reussi"] is False and suivi.code == 1
    assert [erreur.split(" : ")[0] for erreur in rapport["erreurs"]] == ["délai"]
    assert "glossaire" not in rapport  # aucune étape n'a été essayée
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()


def test_un_rapport_precedent_est_efface_au_debut_du_controle(application, tmp_path):
    ancien = tmp_path / controle.NOM_DU_RAPPORT
    ancien.write_text('{"reussi": true}', encoding="utf-8")
    controle.Controle(application, tmp_path)
    assert not ancien.exists()


def test_le_programme_lance_avec_l_option_se_controle_et_se_ferme(tmp_path, glossaire_fourni):
    """L'application entière, lancée comme le fait l'installeur : python main.py --controle=<dossier>."""
    resultat = subprocess.run([sys.executable, str(RACINE / "main.py"), f"--controle={tmp_path}"],
                              capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert resultat.returncode == 0, resultat.stderr[-2000:]
    rapport = _rapport(tmp_path)
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    assert rapport["glossaire"]["fourni"] is True and rapport["glossaire"]["entrees"] == len(glossaire_fourni)
    assert Path(rapport["glossaire"]["fichier"]) == glossaire_fourni.chemin
    # L'image de la fenêtre montre l'écran « Terme » dans son état final. Le terme cherché a les six informations
    # du menu « Plus de détails » : les six cercles sont allumés, chacun dans sa couleur. Pendant l'allumage, qui
    # dure plus d'une seconde, les derniers cercles seraient encore gris.
    assert rapport["recherche"]["informations"] == list(CLES)
    for detail in DETAILS:
        assert _points_de_couleur(tmp_path / rapport["image"]["fichier"], detail.couleur) >= 20, detail.titre
