"""L'application ne se connecte à rien (tests exécutés sans écran).

Elle traduit avec le glossaire, et avec lui seul : elle n'a besoin ni d'Internet, ni d'un service
en ligne.

Le réseau est « coupé » pendant ces tests : toute connexion tentée par Python est notée, puis
refusée. Seules les connexions faites par Python sont vues. Celles que Qt pourrait faire passeraient
par son module de réseau : le premier test vérifie aussi que l'application ne le charge pas.
"""

import socket
import sys
import urllib.request

import pytest

pytest.importorskip("PySide6")

from traducteur.interface.navigation import MODE_AIDE, MODE_DESCRIPTION, MODE_PARAMETRES, MODE_TERME, MODE_TEXTE

ARTICLE_106 = "Le contrat fait la loi des parties."
ARTICLE_106_AR = "العقد شريعة المتعاقدين."


@pytest.fixture
def reseau_coupe(monkeypatch) -> list[str]:
    """Coupe le réseau et renvoie la liste des connexions tentées.

    Le refus est une ``AssertionError`` : rien ne peut le prendre pour une simple panne de réseau.
    Qt n'arrête pas un test pour une erreur survenue pendant un clic : c'est la liste qui fait foi.
    """
    tentatives: list[str] = []

    def refuser(nom: str):
        def tentative(*arguments, **options):
            tentatives.append(nom)
            raise AssertionError(f"connexion tentée ({nom}) : {arguments!r}")
        return tentative

    monkeypatch.setattr(socket.socket, "connect", refuser("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", refuser("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", refuser("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", refuser("getaddrinfo"))
    return tentatives


def test_l_application_ne_se_connecte_a_rien(reseau_coupe, fenetre, application):
    """Ouvrir l'application, chercher des termes, traduire des textes, visiter chaque écran : aucune connexion."""
    recherche = fenetre.page
    recherche.rechercher("contrat")
    assert recherche.entree.terme_fr == "contrat"
    recherche.rechercher("عقد")
    assert recherche.entree.terme_fr == "contrat"
    recherche.rechercher("rescision")  # terme absent du glossaire
    assert recherche.entree is None

    fenetre.definir_mode(MODE_TEXTE)
    texte = fenetre.page_texte
    for source, attendu in ((ARTICLE_106, ARTICLE_106_AR), (ARTICLE_106_AR, ARTICLE_106),
                            ("Le locataire inconnu signe le contrat.", "عقد")):
        texte.zone_source.setPlainText(source)
        texte.bouton_traduire.click()
        assert attendu in texte.zone_cible.toPlainText()
    texte.inserer_un_exemple()
    texte.bouton_traduire.click()
    texte.bouton_copier.click()

    for mode in (MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE, MODE_TERME):
        fenetre.definir_mode(mode)
        application.processEvents()

    assert reseau_coupe == []
    assert "PySide6.QtNetwork" not in sys.modules


def test_le_reseau_coupe_voit_les_connexions(reseau_coupe):
    """Le garde-fou n'est pas aveugle : une connexion tentée par Python est vue, et refusée avant de partir."""
    with pytest.raises(AssertionError, match="connexion tentée"):
        urllib.request.urlopen("http://127.0.0.1:9/", timeout=1)
    with pytest.raises(AssertionError, match="connexion tentée"):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    assert len(reseau_coupe) == 2
