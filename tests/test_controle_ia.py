"""Le contrôle de l'installation et l'IA (option --controle, voir ``traducteur/controle.py``).

Le contrôle vérifie que l'IA est éteinte tant que personne ne l'a allumée. Sur demande
(``--controle-connexion``), il essaie aussi une connexion au service d'IA proposé par défaut ; la
fabrication de l'installeur s'en sert sous Windows. Dans ces tests, ce service est le faux service
de ``test_ia_service.py`` : aucun test ne joint Internet.
"""

import json
import socket
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import RACINE
from PySide6.QtTest import QTest
from test_ia_service import (  # noqa: F401 (rien_ne_sort : aucune connexion vers une autre machine)
    LISTE_DES_MODELES,
    FauxService,
    rien_ne_sort,
)

from traducteur import controle
from traducteur.ia import service as connecteur
from traducteur.interface import ia

OUTILS = RACINE / "outils" / "installeur"
if str(OUTILS) not in sys.path:
    sys.path.insert(0, str(OUTILS))

import construire  # noqa: E402


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


@pytest.fixture
def faux():
    service = FauxService()
    yield service
    service.arreter()


def mener(suivi: controle.Controle, delai: int = 10_000) -> dict:
    """Lance le contrôle, attend sa fin et renvoie son rapport."""
    suivi.demarrer()
    attendu = 0
    while suivi.code is None and attendu < delai:
        QTest.qWait(50)
        attendu += 50
    assert suivi.code is not None, "le contrôle ne s'est pas terminé"
    rapport = json.loads((suivi.dossier / controle.NOM_DU_RAPPORT).read_text(encoding="utf-8"))
    suivi.fenetre.deleteLater()
    suivi.ecran.deleteLater()
    return rapport


# ------------------------------------------------------------------ le contrôle
def test_l_option_de_connexion_est_lue_dans_les_arguments(tmp_path):
    assert not controle.connexion_demandee(["main.py"])
    assert not controle.connexion_demandee(["main.py", f"--controle={tmp_path}"])
    assert controle.connexion_demandee(["main.py", f"--controle={tmp_path}", "--controle-connexion"])
    assert controle.connexion_demandee(["main.py", "--controle-connexion", f"--controle={tmp_path}"])
    # Le premier argument est le nom du programme : il n'est jamais lu comme une option.
    assert not controle.connexion_demandee(["--controle-connexion"])
    # Cette option ne demande pas le contrôle à elle seule, et n'est pas prise pour son dossier.
    assert controle.dossier_demande(["main.py", "--controle-connexion"]) is None
    assert controle.dossier_demande(["main.py", "--controle-connexion", f"--controle={tmp_path}"]) == tmp_path
    # La fabrication de l'installeur écrit la même option.
    assert construire.OPTION_DE_CONNEXION == controle.OPTION_DE_CONNEXION == "--controle-connexion"


def test_le_controle_verifie_que_l_ia_est_eteinte(application, tmp_path, demarrage_court, textes_de_qt):
    rapport = mener(controle.Controle(application, tmp_path))
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    assert rapport["ia"] == {"allumee": False, "adresse": "https://integrate.api.nvidia.com/v1",
                             "modele": "google/gemma-4-31b-it"}


def test_sans_l_option_le_controle_ne_se_connecte_a_rien(application, tmp_path, demarrage_court, textes_de_qt,
                                                         monkeypatch):
    tentatives: list[str] = []

    def refuser(nom: str):
        def tentative(*arguments, **options):
            tentatives.append(nom)
            raise AssertionError(f"connexion tentée ({nom})")
        return tentative

    monkeypatch.setattr(socket.socket, "connect", refuser("connect"))
    monkeypatch.setattr(socket, "create_connection", refuser("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", refuser("getaddrinfo"))
    rapport = mener(controle.Controle(application, tmp_path))
    assert rapport["reussi"] is True and "connexion" not in rapport["ia"]
    assert tentatives == []


def test_une_ia_allumee_d_avance_fait_echouer_le_controle(application, tmp_path, demarrage_court, textes_de_qt):
    """Un programme qui s'ouvrirait avec l'IA allumée, sans que personne l'ait demandé, serait un défaut."""
    suivi = controle.Controle(application, tmp_path)
    suivi.reglages.setValue(ia.CLE_ACTIVE, True)
    rapport = mener(suivi)
    assert rapport["reussi"] is False and suivi.code == 1
    assert rapport["erreurs"] == ["ia : l'IA est allumée sans que personne l'ait demandé"]


def test_une_cle_enregistree_d_avance_fait_echouer_le_controle(application, tmp_path, demarrage_court, textes_de_qt):
    suivi = controle.Controle(application, tmp_path)
    suivi.reglages.setValue(ia.CLE_CLE, "nvapi-cle-d-essai-123")
    rapport = mener(suivi)
    assert rapport["erreurs"] == ["ia : une clé d'accès est enregistrée dans des réglages neufs"]
    assert "nvapi-cle-d-essai-123" not in json.dumps(rapport)  # le rapport ne recopie jamais une clé


def test_sur_demande_le_controle_essaie_une_connexion(application, tmp_path, demarrage_court, textes_de_qt, faux,
                                                      monkeypatch):
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    rapport = mener(controle.Controle(application, tmp_path, connexion=True))
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    connexion = rapport["ia"]["connexion"]
    assert connexion["adresse"] == faux.adresse and connexion["modeles"] == 2
    assert connexion["etablie"] is True and connexion["reussie"] is True
    assert connexion["duree_en_secondes"] >= 0
    # Une seule demande est partie : la liste des modèles, sans clé et sans aucun texte.
    demande, = faux.recues
    assert (demande.methode, demande.chemin, demande.corps) == ("GET", "/v1/models", b"")
    assert "authorization" not in demande.en_tetes


def test_une_connexion_impossible_est_notee_sans_faire_echouer_le_controle(application, tmp_path, demarrage_court,
                                                                           textes_de_qt, faux, monkeypatch):
    """L'ordinateur peut ne pas avoir d'accès à Internet : le reste du contrôle garde sa valeur."""
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    faux.arreter()  # plus personne n'écoute à cette adresse
    rapport = mener(controle.Controle(application, tmp_path, connexion=True))
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    connexion = rapport["ia"]["connexion"]
    assert connexion["etablie"] is False and connexion["reussie"] is False
    assert connexion["genre"] == connecteur.CONNEXION and "code" not in connexion
    assert connexion["message"].startswith("Aucun service ne répond à cette adresse.")


@pytest.mark.parametrize("code, corps, genre, debut", [
    (401, {"detail": "Unauthorized"}, connecteur.CLE, "Ce service demande une clé d’accès."),
    (404, {"detail": "Not Found"}, connecteur.ADRESSE, "Cette adresse n’est pas celle d’un service d’IA"),
    (503, b"", connecteur.PANNE, "Le service est en panne ou surchargé (erreur 503)."),
])
def test_un_refus_du_service_montre_que_la_connexion_est_etablie(application, tmp_path, demarrage_court, textes_de_qt,
                                                                 faux, monkeypatch, code, corps, genre, debut):
    """L'essai cherche à savoir si le programme sait se connecter : un refus du service le montre aussi."""
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    faux.prevoir(code, corps)
    rapport = mener(controle.Controle(application, tmp_path, connexion=True))
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    connexion = rapport["ia"]["connexion"]
    assert connexion["etablie"] is True and connexion["reussie"] is False
    assert (connexion["code"], connexion["genre"]) == (code, genre) and connexion["message"].startswith(debut)
    assert len(faux.recues) == 1  # une seule demande : le contrôle n'insiste pas


def test_une_reponse_illisible_montre_aussi_que_la_connexion_est_etablie(application, tmp_path, demarrage_court,
                                                                         textes_de_qt, faux, monkeypatch):
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    faux.prevoir(200, b"<html>Bienvenue</html>")
    rapport = mener(controle.Controle(application, tmp_path, connexion=True))
    connexion = rapport["ia"]["connexion"]
    assert rapport["reussi"] is True and connexion["etablie"] is True and connexion["reussie"] is False
    assert connexion["genre"] == connecteur.REPONSE and "code" not in connexion


def attendre_le_fil_de_la_connexion(delai: float = 10.0) -> None:
    """Attend la fin de l'essai de connexion abandonné par le contrôle : il ne doit pas déborder sur un autre test."""
    for fil in threading.enumerate():
        if fil.name == "controle-de-la-connexion":
            fil.join(delai)
            assert not fil.is_alive(), "l'essai de connexion du contrôle ne s'est pas terminé"


def test_un_service_muet_ne_retient_pas_le_controle(application, tmp_path, demarrage_court, textes_de_qt, faux,
                                                    monkeypatch):
    """Le service tarde à répondre : l'essai est abandonné après sa durée maximale, et le contrôle réussit."""
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    monkeypatch.setattr(controle, "DUREE_MAXIMALE_DE_LA_CONNEXION", 0.3)
    faux.prevoir(200, LISTE_DES_MODELES, attente=1.5)
    rapport = mener(controle.Controle(application, tmp_path, connexion=True))
    assert rapport["reussi"] is True and rapport["erreurs"] == []
    # Le contrôle n'a pas attendu la réponse, qui aurait été une réussite : il a abandonné l'essai.
    assert rapport["ia"]["connexion"] == {
        "adresse": faux.adresse, "etablie": False, "reussie": False, "genre": connecteur.DELAI_DEPASSE,
        "message": "Le service n’a pas répondu en 0,3 secondes : l’essai a été abandonné."}
    attendre_le_fil_de_la_connexion()


def test_l_attente_du_service_ne_compte_pas_dans_le_delai_du_controle(application, tmp_path, faux, monkeypatch):
    """Sans cela, un réseau lent ferait échouer le contrôle : « le contrôle n'était pas fini après 60 secondes »."""
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    faux.prevoir(200, LISTE_DES_MODELES, attente=1.0)
    suivi = controle.Controle(application, tmp_path, connexion=True)
    suivi._limite.start(60_000)
    avant = suivi._limite.remainingTime()
    constat = suivi._connexion()
    assert constat["reussie"] is True and constat["modeles"] == 2 and constat["duree_en_secondes"] >= 1.0
    # La seconde passée à attendre le service n'a pas été retirée du délai.
    assert suivi._limite.isActive() and suivi._limite.remainingTime() > avant - 500
    suivi._limite.stop()


def test_un_delai_qui_ne_court_pas_n_est_pas_lance_par_l_essai_de_connexion(application, tmp_path, faux, monkeypatch):
    monkeypatch.setattr(connecteur, "ADRESSE_PAR_DEFAUT", faux.adresse)
    suivi = controle.Controle(application, tmp_path, connexion=True)
    assert suivi._connexion()["reussie"] is True
    assert not suivi._limite.isActive()


def test_une_erreur_du_programme_pendant_la_connexion_fait_echouer_le_controle(application, tmp_path, demarrage_court,
                                                                              textes_de_qt, monkeypatch):
    """Un service injoignable n'est pas un défaut du programme ; une erreur de son propre code en est un."""
    def tomber(*arguments, **options):
        raise ImportError("DLL load failed while importing _ssl")

    monkeypatch.setattr(connecteur, "lister_les_modeles", tomber)
    suivi = controle.Controle(application, tmp_path, connexion=True)
    rapport = mener(suivi)
    assert rapport["reussi"] is False and suivi.code == 1
    erreur, = rapport["erreurs"]
    assert erreur.startswith("ia : ") and "DLL load failed while importing _ssl" in erreur


# ------------------------------------------------------------------ la fabrication de l'installeur
REUSSIE = {"adresse": "https://integrate.api.nvidia.com/v1", "etablie": True, "reussie": True, "modeles": 84,
           "duree_en_secondes": 0.8}
ECHOUEE = {"adresse": "https://integrate.api.nvidia.com/v1", "etablie": False, "reussie": False, "genre": "connexion",
           "message": "La connexion sécurisée au service a été refusée : son certificat n’a pas pu être vérifié."}
REFUSEE = {"adresse": "https://integrate.api.nvidia.com/v1", "etablie": True, "reussie": False, "genre": "cle",
           "code": 401, "message": "Ce service demande une clé d’accès. Saisissez-la dans « Paramètres »."}


def test_le_resume_de_la_fabrication_dit_si_la_connexion_chiffree_marche():
    assert construire.ligne_de_la_connexion(REUSSIE) == (
        "Connexion chiffrée au service d'IA proposé par défaut (https://integrate.api.nvidia.com/v1) : le "
        "programme fabriqué l'établit et reçoit la liste de 84 modèles, sans clé, en 0,8 s")
    assert construire.ligne_de_la_connexion(ECHOUEE) == (
        "Connexion chiffrée au service d'IA proposé par défaut (https://integrate.api.nvidia.com/v1) : non "
        "établie depuis cette machine — La connexion sécurisée au service a été refusée : son certificat n’a "
        "pas pu être vérifié.")
    assert construire.ligne_de_la_connexion(REFUSEE) == (
        "Connexion chiffrée au service d'IA proposé par défaut (https://integrate.api.nvidia.com/v1) : le "
        "programme fabriqué l'établit. Le service a répondu sans donner la liste de ses modèles (code 401) — "
        "Ce service demande une clé d’accès. Saisissez-la dans « Paramètres ».")


def test_la_connexion_est_notee_dans_le_resume_pour_le_premier_controle(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    resume = construire.Resume()
    construire.noter_la_connexion({"ia": {"allumee": False, "connexion": REUSSIE}}, "dossier", resume)
    construire.noter_la_connexion({"ia": {"allumee": False, "connexion": REUSSIE}}, "installe", resume)
    assert resume.lignes == [construire.ligne_de_la_connexion(REUSSIE)]
    assert resume.details == ["installe : " + construire.ligne_de_la_connexion(REUSSIE)]
    assert "::warning" not in capsys.readouterr().out


def test_une_connexion_non_etablie_est_signalee_sans_arreter_la_fabrication(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    resume = construire.Resume()
    construire.noter_la_connexion({"ia": {"connexion": ECHOUEE}}, "dossier", resume)  # aucune erreur n'est levée
    assert resume.lignes == [construire.ligne_de_la_connexion(ECHOUEE)]
    assert "::warning title=Connexion au service d'IA (dossier)::" in capsys.readouterr().out


def test_un_refus_du_service_est_note_sans_signalement(monkeypatch, capsys):
    """La connexion chiffrée a fonctionné : c'est ce que l'essai cherche. Le refus est écrit dans le résumé."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    resume = construire.Resume()
    construire.noter_la_connexion({"ia": {"connexion": REFUSEE}}, "dossier", resume)
    assert resume.lignes == [construire.ligne_de_la_connexion(REFUSEE)]
    assert "::warning" not in capsys.readouterr().out


def test_un_rapport_sans_essai_de_connexion_n_ajoute_rien_au_resume():
    resume = construire.Resume()
    for rapport in ({}, {"ia": {"allumee": False}}):
        construire.noter_la_connexion(rapport, "dossier", resume)
    assert resume.lignes == [] and resume.details == []


def test_le_controle_du_programme_fabrique_demande_l_essai_de_connexion():
    """La fabrication lance le programme avec les deux options : le contrôle, et l'essai de connexion."""
    source = Path(construire.__file__).read_text(encoding="utf-8")
    assert '[programme, f"--controle={dossier}", OPTION_DE_CONNEXION]' in source
