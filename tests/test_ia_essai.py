"""Essai de la connexion au service d'IA (``traducteur/ia/essai.py``) et lecture des réponses (``lecture.py``).

Aucun test ne joint Internet : le faux service de ``test_ia_service.py`` joue chaque cas, et une
connexion vers une autre machine fait échouer le test.
"""

import pytest
from test_ia_service import (  # noqa: F401 (« rien_ne_sort » interdit toute connexion vers une autre machine)
    AILLEURS,
    CLE,
    LISTE_DES_MODELES,
    MODELE,
    TRADUCTION,
    FauxService,
    reponse_du_modele,
    rien_ne_sort,
)

from traducteur.ia import essai
from traducteur.ia import service as connecteur
from traducteur.ia.essai import MODELE as TEMPS_DU_MODELE
from traducteur.ia.essai import SERVICE as TEMPS_DU_SERVICE
from traducteur.ia.lecture import sans_reflexion


@pytest.fixture
def faux():
    service = FauxService()
    yield service
    service.arreter()


def constats(faux_service: FauxService, modele: str = MODELE, cle: str = CLE, **options) -> list[essai.Constat]:
    return list(essai.essayer(faux_service.adresse, cle, modele, **options))


def liste(*noms: str) -> dict:
    return {"object": "list", "data": [{"id": nom, "object": "model"} for nom in noms]}


# ------------------------------------------------------------------ l'essai réussit
def test_l_essai_reussit_en_deux_temps(faux):
    service, modele = constats(faux)
    assert (service.temps, service.reussi, service.genre) == (TEMPS_DU_SERVICE, True, "")
    assert service.message == "Le service répond : il propose 2 modèles. « essai/modele-1 » est dans sa liste."
    assert (modele.temps, modele.reussi, modele.genre) == (TEMPS_DU_MODELE, True, "")
    assert modele.message.startswith("Le modèle a répondu en ")
    assert modele.message.endswith(f" s. Sa réponse : {TRADUCTION}")


def test_l_essai_n_envoie_que_sa_propre_demande(faux):
    """Deux demandes partent : la liste des modèles, puis un mot à traduire. Aucun texte de l'utilisateur."""
    constats(faux)
    premiere, seconde = faux.recues
    assert (premiere.methode, premiere.chemin, premiere.corps) == ("GET", "/v1/models", b"")
    assert (seconde.methode, seconde.chemin) == ("POST", "/v1/chat/completions")
    # La demande la plus simple : le modèle, la phrase, la longueur maximale. Aucun autre réglage.
    assert seconde.json == {"model": MODELE, "messages": [{"role": "user", "content": essai.DEMANDE}],
                            "stream": False, "max_tokens": essai.LONGUEUR_MAXIMALE}
    assert premiere.en_tetes["authorization"] == seconde.en_tetes["authorization"] == f"Bearer {CLE}"
    assert "contrat" in essai.DEMANDE and "arabe" in essai.DEMANDE


def test_un_modele_absent_de_la_liste_est_tout_de_meme_essaye(faux):
    """La liste d'un service n'est pas toujours complète : c'est la réponse du modèle qui tranche."""
    faux.prevoir(200, liste("essai/modele-2", "essai/modele-3"))
    service, modele = constats(faux)
    assert service.reussi and "« essai/modele-1 » n’est pas dans sa liste." in service.message
    assert "Noms proches : essai/modele-2, essai/modele-3." in service.message
    assert modele.reussi


def test_un_service_sans_liste_de_modeles(faux):
    faux.prevoir(200, liste())
    service, modele = constats(faux)
    assert service.reussi and service.message == "Le service répond. Il ne donne pas la liste de ses modèles."
    assert modele.reussi


def test_un_seul_modele_s_ecrit_au_singulier(faux):
    faux.prevoir(200, liste(MODELE))
    assert constats(faux)[0].message == "Le service répond : il propose 1 modèle. « essai/modele-1 » est dans sa liste."


# ------------------------------------------------------------------ la réponse montrée
@pytest.mark.parametrize("ecrit, montre", [
    ("عقد", "عقد"),
    ("  عقد \n", "عقد"),
    ("<|channel>thought\n<channel|>عقد", "عقد"),  # bloc de réflexion vide de Gemma 4
    ("<think>Le mot « contrat » se dit…</think>\n\nعقد", "عقد"),
    ("Le mot\nest :\n\nعقد", "Le mot est : عقد"),  # la réponse est montrée sur une ligne
])
def test_la_reponse_est_montree_sans_reflexion_et_sur_une_ligne(faux, ecrit, montre):
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(200, reponse_du_modele(ecrit))
    assert constats(faux)[1].message.endswith(f"Sa réponse : {montre}")


def test_une_longue_reponse_est_abregee(faux):
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(200, reponse_du_modele("mot " * 100))
    message = constats(faux)[1].message
    reponse = message.split("Sa réponse : ")[1]
    assert reponse.endswith("…") and len(reponse) <= essai.LONGUEUR_MONTREE + 1


def test_une_reponse_faite_de_la_seule_reflexion_est_un_echec(faux):
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(200, reponse_du_modele("<think>Je réfléchis.</think>"))
    modele = constats(faux)[1]
    assert not modele.reussi and modele.genre == connecteur.REPONSE
    assert modele.message.startswith("Le modèle a répondu, mais sans texte utilisable.")


# ------------------------------------------------------------------ l'essai échoue
def test_un_service_absent_arrete_l_essai_au_premier_temps(faux):
    faux.arreter()  # plus personne n'écoute à cette adresse
    resultat = constats(faux)
    assert len(resultat) == 1
    assert (resultat[0].temps, resultat[0].reussi, resultat[0].genre) == (TEMPS_DU_SERVICE, False, connecteur.CONNEXION)
    assert resultat[0].message.startswith("Aucun service ne répond à cette adresse.")


def test_une_adresse_mal_ecrite_arrete_l_essai_sans_rien_envoyer():
    resultat = list(essai.essayer("integrate.api.nvidia.com", CLE, MODELE))
    assert [(constat.temps, constat.reussi, constat.genre) for constat in resultat] == [
        (TEMPS_DU_SERVICE, False, connecteur.ADRESSE)]


@pytest.mark.parametrize("code, genre, debut", [
    (401, connecteur.CLE, "Le service a refusé la clé d’accès."),
    (402, connecteur.ACCES, "Le service refuse la demande : le crédit du compte est épuisé"),
    (404, connecteur.MODELE, "Le service ne connaît pas le modèle « essai/modele-1 »"),
    (429, connecteur.DEBIT, "Le service reçoit trop de demandes."),
    (500, connecteur.PANNE, "Le service est en panne ou surchargé (erreur 500)."),
])
def test_un_refus_du_modele_est_dit_au_second_temps(faux, code, genre, debut):
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(code, {"detail": f"refus avec la clé {CLE}"})
    service, modele = constats(faux)
    assert service.reussi
    assert (modele.temps, modele.reussi, modele.genre) == (TEMPS_DU_MODELE, False, genre)
    assert modele.message.startswith(debut)
    assert CLE not in modele.message  # la clé n'est jamais recopiée dans un message
    assert len(faux.recues) == 2  # l'essai ne renvoie pas la demande : il dit tout de suite ce qui ne va pas


def test_une_cle_refusee_des_la_liste_arrete_l_essai(faux):
    faux.prevoir(401, {"detail": "Unauthorized"})
    resultat = constats(faux)
    assert [(constat.temps, constat.reussi, constat.genre) for constat in resultat] == [
        (TEMPS_DU_SERVICE, False, connecteur.CLE)]
    assert len(faux.recues) == 1


def test_sans_cle_le_second_temps_dit_qu_il_en_faut_une(monkeypatch):
    """NVIDIA donne la liste de ses modèles sans clé : le premier temps réussit, le second réclame la clé."""
    monkeypatch.setattr(connecteur, "lister_les_modeles", lambda *arguments, **options: [MODELE])
    service, modele = essai.essayer(AILLEURS, "", MODELE)
    assert service.reussi
    assert (modele.reussi, modele.genre) == (False, connecteur.CLE)
    assert modele.message == "Aucune clé d’accès n’est saisie. Saisissez-la dans « Paramètres »."


def test_sans_modele_le_second_temps_dit_qu_il_en_faut_un(faux):
    service, modele = constats(faux, modele="  ")
    assert service.message == "Le service répond : il propose 2 modèles."
    assert (modele.reussi, modele.genre) == (False, connecteur.MODELE)


def test_un_service_trop_lent_est_un_echec(faux):
    faux.prevoir(200, LISTE_DES_MODELES, attente=1.0)
    resultat = constats(faux, delai_du_service=0.2)
    assert [(constat.reussi, constat.genre) for constat in resultat] == [(False, connecteur.DELAI_DEPASSE)]
    assert resultat[0].message == ("Le service n’a pas répondu à temps. Vérifiez la connexion à Internet, puis "
                                   "réessayez dans un moment.")


def test_un_modele_trop_lent_est_un_echec_du_second_temps(faux):
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(200, reponse_du_modele(), attente=1.0)
    service, modele = constats(faux, delai_du_modele=0.2)
    assert service.reussi
    assert (modele.temps, modele.reussi, modele.genre) == (TEMPS_DU_MODELE, False, connecteur.DELAI_DEPASSE)
    assert modele.message == ("Le modèle n’a pas répondu à temps. Il est peut-être très demandé : réessayez dans un "
                              "moment, ou choisissez un autre modèle.")


@pytest.mark.parametrize("code", [408, 504, 524])
def test_un_service_qui_dit_avoir_tarde_ne_conseille_pas_un_texte_plus_court(faux, code):
    """L'essai n'envoie aucun texte de l'utilisateur : le conseil du connecteur ne lui servirait à rien."""
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(code, {"detail": "Gateway Timeout"})
    _service, modele = constats(faux)
    assert (modele.reussi, modele.genre) == (False, connecteur.DELAI_DEPASSE)
    assert "texte plus court" not in modele.message and modele.message.startswith("Le modèle n’a pas répondu à temps.")


# ------------------------------------------------------------------ l'arrêt
def test_un_arret_demande_avant_l_essai_n_envoie_rien(faux):
    resultat = constats(faux, arret=lambda: True)
    assert [(constat.temps, constat.reussi, constat.genre) for constat in resultat] == [
        (TEMPS_DU_SERVICE, False, connecteur.ARRET)]
    assert faux.recues == []


def test_un_arret_demande_entre_les_deux_temps_n_envoie_pas_la_seconde_demande(faux):
    reponses = iter([False, True])
    service, modele = constats(faux, arret=lambda: next(reponses))
    assert service.reussi
    assert (modele.temps, modele.reussi, modele.genre) == (TEMPS_DU_MODELE, False, connecteur.ARRET)
    assert len(faux.recues) == 1


# ------------------------------------------------------------------ noms proches
def test_les_noms_proches_ignorent_les_majuscules():
    modeles = ["google/gemma-3-12b-it", "google/gemma-4-31b-it", "mistralai/mistral-large-4-1t-a52b",
               "nvidia/riva-translate-4b-instruct-v2"]
    assert essai.noms_proches("google/gemma-4-31b", modeles)[0] == "google/gemma-4-31b-it"
    assert essai.noms_proches("Google/Gemma-4-31B-IT", modeles)[0] == "google/gemma-4-31b-it"
    assert essai.noms_proches("mistral-large-4", modeles) == ["mistralai/mistral-large-4-1t-a52b"]
    assert essai.noms_proches("tout autre chose", modeles) == []
    assert len(essai.noms_proches("google/gemma", [*modeles, "google/gemma-2", "google/gemma-5"])) == essai.NOMS_PROCHES


# ------------------------------------------------------------------ lecture des réponses
@pytest.mark.parametrize("ecrit, lu", [
    ("عقد", "عقد"),
    ("\n  عقد  \n", "عقد"),
    ("<|channel>thought\n<channel|>عقد", "عقد"),
    ("<|channel>thought\nLe mot se traduit par…\n<channel|>\nعقد", "عقد"),
    ("<think>\nplusieurs\nlignes\n</think>\nعقد", "عقد"),
    ("<THINK>x</THINK> عقد", "عقد"),
    ("", ""),
    ("<think>seulement la réflexion</think>", ""),
])
def test_la_reflexion_qui_precede_la_reponse_est_retiree(ecrit, lu):
    assert sans_reflexion(ecrit) == lu


@pytest.mark.parametrize("ecrit", [
    "عقد <think>ce bloc n'ouvre pas la réponse</think>",
    "<think>bloc jamais refermé : عقد",
    "<|channel>thought jamais refermé : عقد",
    "Le mot <channel|> n'est pas une marque ici.",
])
def test_un_texte_qui_n_est_pas_une_reflexion_est_garde(ecrit):
    assert sans_reflexion(ecrit) == ecrit
