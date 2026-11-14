"""L'IA et l'application (tests exécutés sans écran).

Tant que l'IA est éteinte, l'application ne se connecte à rien : elle traduit avec le glossaire, et
avec lui seul. Pour l'instant, rien dans l'application ne permet de l'allumer.

Le réseau est « coupé » pendant ces tests : toute connexion tentée par Python est notée, puis
refusée. Seules les connexions faites par Python sont vues ; c'est par là que passe le connecteur
du service d'IA (``traducteur/ia/service.py``).
"""

import socket

import pytest

pytest.importorskip("PySide6")

from traducteur.ia import service as connecteur
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


def test_ia_eteinte_l_application_ne_se_connecte_a_rien(reseau_coupe, fenetre, application):
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


def test_le_reseau_coupe_voit_les_connexions_du_connecteur(reseau_coupe):
    """Le garde-fou n'est pas aveugle : une demande du connecteur est vue, et refusée avant de partir."""
    with pytest.raises(AssertionError, match="connexion tentée"):
        connecteur.lister_les_modeles("http://127.0.0.1:9/v1")
    with pytest.raises(AssertionError, match="connexion tentée"):
        connecteur.demander("https://service.example/v1", "cle-d-essai", "essai/modele",
                            [{"role": "user", "content": ARTICLE_106}])
    assert len(reseau_coupe) == 2
