"""Démarrage de l'application : contrôle de l'installation."""

import sys

import pytest

pytest.importorskip("PySide6")

import PySide6
from PySide6.QtCore import QCoreApplication
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
