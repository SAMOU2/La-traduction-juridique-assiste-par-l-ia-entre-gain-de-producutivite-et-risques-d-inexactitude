"""Démarrage de l'application : contrôle de l'installation."""

import sys

import pytest

pytest.importorskip("PySide6")

import PySide6
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from traducteur import application
from traducteur.application import installer_les_textes_de_qt

mesure_possible = pytest.mark.skipif(not hasattr(sys, "getrefcount"), reason="sys.getrefcount n'existe pas ici")


def test_python_recent_n_est_jamais_concerne(monkeypatch):
    monkeypatch.setattr(sys, "getrefcount", lambda objet: pytest.fail("aucune mesure n'est nécessaire"), raising=False)
    assert application.liaison_qt_instable((3, 12)) is False
    assert application.liaison_qt_instable((3, 15)) is False


@mesure_possible
@pytest.mark.parametrize(
    ("avant", "apres", "attendu"),
    [
        (5000, 4936, True),  # une référence à None perdue à chaque appel : défaut présent
        (5000, 5000, False),
        (5000, 5003, False),
        (5000, 4990, False),  # petite variation sans rapport avec les appels
    ],
)
def test_le_defaut_est_reconnu_a_la_baisse_des_references(monkeypatch, avant, apres, attendu):
    mesures = iter((avant, apres))
    monkeypatch.setattr(sys, "getrefcount", lambda objet: next(mesures))
    assert application.liaison_qt_instable((3, 11)) is attendu


def test_cette_installation_n_a_pas_le_defaut():
    """Échoue si les tests sont lancés avec des versions de Python et de PySide6 qui ne vont pas ensemble."""
    assert not application.liaison_qt_instable(), (
        f"PySide6 {PySide6.__version__} ne convient pas à Python {sys.version.split()[0]} : "
        "lancez « python -m pip install -r requirements.txt » pour installer une version qui convient.")


def test_le_message_d_avertissement_donne_les_versions_et_la_commande():
    message = application.AVERTISSEMENT_LIAISON.format(python="3.11", pyside="6.12.0")
    assert "Python 3.11 et PySide6 6.12.0" in message
    assert "python -m pip install -r requirements.txt" in message


def test_les_textes_de_qt_sont_mis_en_francais(request):
    """Le menu contextuel des zones de saisie (« Copier », « Coller »…) est fourni par Qt, en anglais par défaut."""
    qt = request.getfixturevalue("application")  # l'application Qt ; ici, « application » désigne le module testé
    textes = installer_les_textes_de_qt(qt)
    if textes is None:
        pytest.skip("cette installation de Qt ne contient pas ses textes en français")
    try:
        assert QCoreApplication.translate("QShortcut", "Shift") == "Maj"
        champ = QLineEdit()
        menu = champ.createStandardContextMenu()
        libelles = [action.text().replace("&", "").split("\t")[0] for action in menu.actions()]
        assert {"Annuler", "Couper", "Copier", "Coller", "Tout sélectionner"} <= set(libelles)
        menu.deleteLater()
        champ.deleteLater()
    finally:
        # Les autres tests gardent les textes d'origine de Qt.
        qt.removeTranslator(textes)
        textes.deleteLater()


# ------------------------------------------------------------------ ouverture de l'application
def test_l_application_s_ouvre_sur_l_ecran_de_demarrage(request, reglages, avertissements, monkeypatch):
    from traducteur.interface.demarrage import EcranDemarrage

    qt = request.getfixturevalue("application")
    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 300)
    fenetre, ecran = application.ouvrir(qt, reglages=reglages)
    # Le logo animé est affiché ; la fenêtre, déjà construite avec son glossaire, attend derrière lui.
    assert isinstance(ecran, EcranDemarrage) and ecran.isVisible()
    assert not fenetre.isVisible() and len(fenetre.glossaire) == 40
    QTest.qWait(700)
    # Puis l'écran de démarrage laisse la place à la fenêtre.
    assert fenetre.isVisible() and not ecran.isVisible()
    assert avertissements == []
    fenetre.close()
    fenetre.deleteLater()
    ecran.deleteLater()


def test_un_glossaire_introuvable_est_signale_apres_l_ecran_de_demarrage(request, reglages, avertissements,
                                                                         monkeypatch, tmp_path):
    from traducteur.interface.demarrage import EcranDemarrage

    qt = request.getfixturevalue("application")
    monkeypatch.setattr(EcranDemarrage, "DUREE_MINIMALE", 300)
    reglages.setValue("glossaire/chemin", str(tmp_path / "disparu.csv"))
    fenetre, ecran = application.ouvrir(qt, reglages=reglages)
    qt.processEvents()
    assert ecran.isVisible() and avertissements == []  # rien ne passe devant le logo animé
    QTest.qWait(700)
    assert fenetre.isVisible() and [titre for titre, _ in avertissements] == ["Glossaire non chargé"]
    assert "disparu.csv" in avertissements[0][1] and len(fenetre.glossaire) == 40  # le glossaire fourni est repris
    fenetre.close()
    fenetre.deleteLater()
    ecran.deleteLater()


def test_l_ecran_de_demarrage_peut_etre_desactive(request, reglages, avertissements):
    qt = request.getfixturevalue("application")
    reglages.setValue("affichage/ecran_de_demarrage", False)
    fenetre, ecran = application.ouvrir(qt, reglages=reglages)
    assert ecran is None and fenetre.isVisible()
    fenetre.close()
    fenetre.deleteLater()


def test_le_glossaire_demande_au_lancement_est_charge(request, reglages, avertissements, tmp_path):
    qt = request.getfixturevalue("application")
    reglages.setValue("affichage/ecran_de_demarrage", False)
    fichier = tmp_path / "choisi.csv"
    fichier.write_text("terme_fr;terme_ar\ntribunal;محكمة\n", encoding="utf-8")
    fenetre, _ = application.ouvrir(qt, str(fichier), reglages)
    assert fenetre.glossaire.nom == "choisi.csv" and len(fenetre.glossaire) == 1
    fenetre.close()
    fenetre.deleteLater()


def test_l_installation_a_corriger_est_signalee_a_l_ouverture(request, reglages, avertissements, monkeypatch):
    qt = request.getfixturevalue("application")
    reglages.setValue("affichage/ecran_de_demarrage", False)
    monkeypatch.setattr(application, "liaison_qt_instable", lambda: True)
    fenetre, _ = application.ouvrir(qt, reglages=reglages)
    assert [titre for titre, _ in avertissements] == ["Installation à corriger"]
    assert "python -m pip install -r requirements.txt" in avertissements[0][1]
    fenetre.close()
    fenetre.deleteLater()
