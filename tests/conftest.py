"""Réglages communs aux tests."""

import os
import sys
from pathlib import Path

import pytest

# Les tests de l'interface s'exécutent sans ouvrir de fenêtre à l'écran.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from traducteur.glossaire import Glossaire  # noqa: E402

GLOSSAIRE_EXEMPLE = RACINE / "donnees" / "glossaire_juridique.csv"


@pytest.fixture(scope="session")
def glossaire() -> Glossaire:
    """Le glossaire d'exemple fourni avec le projet."""
    return Glossaire.charger(GLOSSAIRE_EXEMPLE)
