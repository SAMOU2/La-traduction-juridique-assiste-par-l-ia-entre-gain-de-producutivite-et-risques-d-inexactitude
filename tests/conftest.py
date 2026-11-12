"""Réglages communs aux tests."""

import os
import sys
from pathlib import Path

import pytest

# Les tests de l'interface s'exécutent sans ouvrir de fenêtre à l'écran.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RACINE = Path(__file__).resolve().parents[1]
# Le paquet « traducteur » est à la racine du projet ; certains tests reprennent aussi des
# données d'un autre fichier de tests (« from test_segmentation import … »).
for dossier in (RACINE, RACINE / "tests"):
    if str(dossier) not in sys.path:
        sys.path.insert(0, str(dossier))

from traducteur.glossaire import Glossaire  # noqa: E402

GLOSSAIRE_EXEMPLE = RACINE / "donnees" / "glossaire_juridique.csv"


@pytest.fixture(scope="session")
def glossaire() -> Glossaire:
    """Le glossaire d'exemple fourni avec le projet."""
    return Glossaire.charger(GLOSSAIRE_EXEMPLE)


# ------------------------------------------------------------------ interface (tests sans écran)
@pytest.fixture(scope="session")
def application():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


@pytest.fixture
def reglages(tmp_path):
    """Réglages de l'application rangés dans un fichier temporaire."""
    coeur = pytest.importorskip("PySide6.QtCore")
    return coeur.QSettings(str(tmp_path / "reglages.ini"), coeur.QSettings.Format.IniFormat)


@pytest.fixture
def avertissements(monkeypatch):
    """Remplace les boîtes de dialogue par une simple liste de messages : (titre, texte)."""
    pytest.importorskip("PySide6")
    from traducteur.interface.fenetre import FenetrePrincipale
    from traducteur.interface.texte import PageTexte

    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(FenetrePrincipale, "_boite", lambda self, icone, titre, texte: messages.append((titre, texte)))
    monkeypatch.setattr(PageTexte, "_avertir", lambda self, titre, texte: messages.append((titre, texte)))
    return messages


@pytest.fixture
def fenetre(application, reglages, avertissements):
    """La fenêtre de l'application, ouverte avec le glossaire d'exemple."""
    from traducteur.interface.fenetre import FenetrePrincipale

    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.resize(1440, 860)
    fenetre.show()
    application.processEvents()
    yield fenetre
    fenetre.close()
    fenetre.deleteLater()
    application.processEvents()
