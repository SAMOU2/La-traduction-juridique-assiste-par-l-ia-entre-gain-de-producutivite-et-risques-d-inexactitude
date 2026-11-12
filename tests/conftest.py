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

#: Glossaire fourni avec l'application : celui qu'elle ouvre au démarrage.
GLOSSAIRE_FOURNI = RACINE / "donnees" / "glossaire_juridique.csv"
#: Petit glossaire réservé aux tests : 40 entrées de droit civil. La plupart des tests l'utilisent,
#: pour que leurs résultats ne changent pas quand le glossaire fourni est enrichi ou remplacé.
GLOSSAIRE_D_ESSAI = RACINE / "tests" / "donnees" / "glossaire_essai.csv"


@pytest.fixture(scope="session")
def glossaire() -> Glossaire:
    """Le glossaire d'essai (40 entrées)."""
    return Glossaire.charger(GLOSSAIRE_D_ESSAI)


@pytest.fixture(scope="session")
def glossaire_fourni() -> Glossaire:
    """Le glossaire fourni avec l'application."""
    return Glossaire.charger(GLOSSAIRE_FOURNI)


@pytest.fixture(autouse=True)
def glossaire_de_demarrage(monkeypatch):
    """Pendant les tests, l'application démarre avec le glossaire d'essai.

    Un test qui porte sur le glossaire fourni le demande par son chemin :
    ``FenetrePrincipale(GLOSSAIRE_FOURNI, reglages)``.
    """
    try:
        from traducteur.interface import fenetre
    except ImportError:  # PySide6 n'est pas installé : les tests de l'interface sont ignorés
        return
    monkeypatch.setattr(fenetre, "GLOSSAIRE_EXEMPLE", GLOSSAIRE_D_ESSAI)


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
    """La fenêtre de l'application, ouverte avec le glossaire d'essai."""
    from traducteur.interface.fenetre import FenetrePrincipale

    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.resize(1440, 860)
    fenetre.show()
    application.processEvents()
    yield fenetre
    fenetre.close()
    fenetre.deleteLater()
    application.processEvents()
