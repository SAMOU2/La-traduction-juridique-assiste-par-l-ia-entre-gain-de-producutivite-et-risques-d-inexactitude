"""L'IA et l'application (tests exécutés sans écran).

L'IA est éteinte au départ. Éteinte, l'application ne se connecte à rien : elle traduit avec le
glossaire, et avec lui seul. Elle s'allume dans « Paramètres », partie « Intelligence
artificielle » ; allumée, elle ne se connecte que sur un clic : « Tester la connexion ».

Aucun test ne joint Internet. Pour les tests qui vérifient que rien ne part, le réseau est
« coupé » : toute connexion tentée par Python est notée, puis refusée. Seules les connexions faites
par Python sont vues ; c'est par là que passe le connecteur du service d'IA
(``traducteur/ia/service.py``). Pour les autres, le faux service de ``test_ia_service.py`` répond
sur l'ordinateur lui-même.
"""

import socket
import threading
import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QDialog, QLineEdit
from test_ia_service import (  # noqa: F401 (« rien_ne_sort » interdit toute connexion vers une autre machine)
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
from traducteur.interface import ia, theme
from traducteur.interface.fenetre import FenetrePrincipale
from traducteur.interface.navigation import MODE_AIDE, MODE_DESCRIPTION, MODE_PARAMETRES, MODE_TERME, MODE_TEXTE

ARTICLE_106 = "Le contrat fait la loi des parties."
ARTICLE_106_AR = "العقد شريعة المتعاقدين."
CLES_DE_L_IA = (ia.CLE_ACTIVE, ia.CLE_ADRESSE_DU_SERVICE, ia.CLE_CLE, ia.CLE_MODELE, ia.CLE_AVERTISSEMENT)


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


@pytest.fixture
def faux():
    """Le faux service d'IA, sur l'ordinateur lui-même."""
    service = FauxService()
    yield service
    service.arreter()


@pytest.fixture
def partie(fenetre, application, monkeypatch):
    """La partie « Intelligence artificielle », écran « Paramètres » affiché.

    L'avertissement du premier allumage est accepté d'office : une vraie boîte attendrait un clic.
    """
    monkeypatch.setattr(ia, "confirmer_l_allumage", lambda parent: True)
    fenetre.definir_mode(MODE_PARAMETRES)
    application.processEvents()
    return fenetre.page_parametres.ia


def saisir(champ: QLineEdit, texte: str) -> None:
    """Écrit dans un champ, puis le quitte : c'est le moment où il est enregistré."""
    champ.setText(texte)
    champ.editingFinished.emit()


def allumer(partie: ia.PartieIA, service: FauxService | None = None, modele: str = MODELE, cle: str = CLE) -> None:
    """Allume l'IA et, si un faux service est donné, saisit son adresse, la clé et le modèle."""
    if not partie.active():
        partie.interrupteur.click()
    if service is not None:
        saisir(partie.champ_adresse, service.adresse)
        saisir(partie.champ_cle, cle)
        saisir(partie.champ_modele, modele)


def laisser_passer(duree: float) -> None:
    """Laisse tourner l'application, et les fils d'exécution de Python, pendant ``duree`` secondes.

    ``QTest.qWait`` ne convient pas ici : pendant son attente, il retient l'interpréteur Python, et le
    fil de l'essai n'avance pas. Une boucle d'événements de Qt, elle, le laisse avancer : c'est ce que
    fait l'application quand elle tourne.
    """
    boucle = QEventLoop()
    QTimer.singleShot(round(duree * 1000), boucle.quit)
    boucle.exec()


def fils_de_l_essai() -> list[threading.Thread]:
    """Les fils d'exécution des essais de connexion qui ne sont pas finis."""
    return [fil for fil in threading.enumerate() if fil.name == "essai-de-l-ia"]


def attendre_les_fils(delai: float = 5.0) -> None:
    """Attend la fin de tous les essais lancés, puis laisse leurs résultats arriver jusqu'à la fenêtre."""
    limite = time.monotonic() + delai
    while fils_de_l_essai() and time.monotonic() < limite:
        laisser_passer(0.01)
    assert not fils_de_l_essai(), "un essai de connexion ne s'est pas terminé"
    laisser_passer(0.05)


@pytest.fixture(autouse=True)
def aucun_essai_ne_reste():
    """Un essai lancé par un test est fini avant le test suivant."""
    yield
    limite = time.monotonic() + 5.0
    while fils_de_l_essai() and time.monotonic() < limite:
        time.sleep(0.01)
    assert not fils_de_l_essai(), "un essai de connexion est resté en cours après le test"


def attendre_la_fin(partie: ia.PartieIA, delai: float = 5.0) -> None:
    """Laisse tourner l'application jusqu'à la fin de l'essai de connexion."""
    limite = time.monotonic() + delai
    while partie.essai_en_cours() and time.monotonic() < limite:
        laisser_passer(0.01)
    assert not partie.essai_en_cours(), "l'essai de connexion ne s'est pas terminé"


def phrases(partie: ia.PartieIA) -> list[tuple[str, str]]:
    """Les deux lignes du résultat de l'essai : (état, phrase)."""
    return [(ligne.etat, ligne.phrase) for ligne in (partie.constat_du_service, partie.constat_du_modele)]


# ====================================================================== IA éteinte : rien ne part
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


def test_ia_eteinte_le_bouton_d_essai_ne_fait_rien(reseau_coupe, fenetre, application):
    partie = fenetre.page_parametres.ia
    fenetre.definir_mode(MODE_PARAMETRES)
    application.processEvents()
    assert not partie.active() and not partie.bouton_tester.isEnabled()
    partie.bouton_tester.click()  # un bouton grisé ne répond pas au clic
    partie.tester()  # et la demande elle-même est refusée tant que l'IA est éteinte
    application.processEvents()
    assert not partie.essai_en_cours() and not partie.cadre_essai.isVisible()
    assert reseau_coupe == []


def test_ia_allumee_rien_ne_part_sans_clic(reseau_coupe, application, reglages, avertissements):
    """Avec l'IA allumée et une clé enregistrée, ouvrir, chercher et traduire ne joint toujours personne."""
    reglages.setValue(ia.CLE_ACTIVE, True)
    reglages.setValue(ia.CLE_AVERTISSEMENT, True)
    reglages.setValue(ia.CLE_CLE, CLE)
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    application.processEvents()
    assert fenetre.page_parametres.ia.active()
    fenetre.page.rechercher("contrat")
    fenetre.definir_mode(MODE_TEXTE)
    fenetre.page_texte.zone_source.setPlainText(ARTICLE_106)
    fenetre.page_texte.bouton_traduire.click()
    assert ARTICLE_106_AR in fenetre.page_texte.zone_cible.toPlainText()
    for mode in (MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE, MODE_TERME):
        fenetre.definir_mode(mode)
        application.processEvents()
    assert reseau_coupe == []
    fenetre.close()
    fenetre.deleteLater()


# ====================================================================== la partie « Intelligence artificielle »
def test_la_partie_ia_est_eteinte_au_depart(fenetre, reglages, application):
    parametres = fenetre.page_parametres
    partie = parametres.ia
    fenetre.definir_mode(MODE_PARAMETRES)
    application.processEvents()
    assert parametres.carte_ia.titre.text() == "Intelligence artificielle" and parametres.carte_ia.isVisible()
    assert not partie.active() and not partie.interrupteur.isChecked()
    assert ia.IA_ETEINTE in partie.reglage.texte.text()
    # L'adresse de NVIDIA et le modèle proposé sont déjà là ; il n'y a pas de clé.
    assert partie.champ_adresse.text() == connecteur.ADRESSE_PAR_DEFAUT == "https://integrate.api.nvidia.com/v1"
    assert partie.champ_modele.text() == ia.MODELE_PAR_DEFAUT == "google/gemma-4-31b-it"
    assert partie.champ_cle.text() == ""
    # Éteinte, la partie est grisée : rien ne s'y saisit, rien ne s'y essaie.
    for element in (partie.champ_adresse, partie.champ_cle, partie.champ_modele, partie.bouton_afficher,
                    partie.bouton_tester, partie.bouton_effacer):
        assert not element.isEnabled()
    assert not partie.cadre_essai.isVisible()
    # La carte dit ce que fait l'IA aujourd'hui, et où la clé est rangée.
    assert "la traduction se fait toujours avec le glossaire, et avec lui seul" in ia.PRESENTATION
    assert partie.note.isVisible() and "sans chiffrement" in ia.NOTE_SUR_LA_CLE
    # Rien n'est enregistré tant que l'utilisateur n'a rien changé.
    assert not any(reglages.contains(nom) for nom in CLES_DE_L_IA)
    assert ia.lire(reglages) == ia.ReglagesIA(False, connecteur.ADRESSE_PAR_DEFAUT, "", ia.MODELE_PAR_DEFAUT)


def test_le_premier_allumage_demande_une_confirmation(fenetre, reglages, application, monkeypatch):
    partie = fenetre.page_parametres.ia
    fenetre.definir_mode(MODE_PARAMETRES)
    reponses, demandes = [False, True], []

    def confirmer(parent) -> bool:
        demandes.append(parent)
        return reponses.pop(0)

    monkeypatch.setattr(ia, "confirmer_l_allumage", confirmer)
    bascules = []
    partie.basculee.connect(bascules.append)

    # « Annuler » : l'interrupteur revient à sa place et rien n'est enregistré.
    partie.interrupteur.click()
    assert demandes == [fenetre] and not partie.active() and not partie.interrupteur.isChecked()
    assert bascules == [] and not any(reglages.contains(nom) for nom in CLES_DE_L_IA)
    assert not partie.champ_cle.isEnabled()

    # « Allumer l'IA » : l'IA est allumée, et l'avertissement ne reviendra plus.
    partie.interrupteur.click()
    assert len(demandes) == 2 and partie.active() and bascules == [True]
    assert reglages.value(ia.CLE_ACTIVE, False, bool) and reglages.value(ia.CLE_AVERTISSEMENT, False, bool)
    assert fenetre.barre_etat.texte() == "IA allumée."
    partie.interrupteur.click()
    partie.interrupteur.click()
    assert len(demandes) == 2 and partie.active() and bascules == [True, False, True]


def test_l_avertissement_laisse_le_choix(application):
    boite = ia.BoiteAllumage()
    assert boite.titre.text() == "Avant d’allumer l’IA"
    assert "N’envoyez jamais de texte confidentiel" in boite.texte.text()
    assert "Rien n’est envoyé sans un clic de votre part." in boite.texte.text()
    assert (boite.bouton_annuler.text(), boite.bouton.text()) == ("Annuler", "Allumer l’IA")
    # La touche Entrée ne doit pas allumer l'IA par mégarde.
    assert boite.bouton_annuler.isDefault() and not boite.bouton.isDefault()
    boite.bouton.click()
    assert boite.result() == QDialog.DialogCode.Accepted
    boite.deleteLater()

    autre = ia.BoiteAllumage()
    autre.bouton_annuler.click()
    assert autre.result() == QDialog.DialogCode.Rejected
    autre.deleteLater()


@pytest.mark.parametrize("bouton, attendu", [("bouton", True), ("bouton_annuler", False)])
def test_la_confirmation_attend_le_choix_de_l_utilisateur(application, bouton, attendu):
    def choisir() -> None:
        boite = application.activeModalWidget()
        assert isinstance(boite, ia.BoiteAllumage)
        getattr(boite, bouton).click()

    QTimer.singleShot(50, choisir)
    assert ia.confirmer_l_allumage(None) is attendu


def test_allumer_puis_eteindre(partie, reglages, fenetre):
    partie.interrupteur.click()
    assert partie.active() and ia.IA_ALLUMEE in partie.reglage.texte.text().replace("&nbsp;", " ")
    for element in (partie.champ_adresse, partie.champ_cle, partie.champ_modele, partie.bouton_afficher,
                    partie.bouton_tester):
        assert element.isEnabled()
    assert not partie.bouton_effacer.isEnabled()  # il n'y a pas encore de clé à effacer
    partie.champ_cle.setText("n")  # dès la première lettre, la clé peut être effacée
    assert partie.bouton_effacer.isEnabled()

    partie.interrupteur.click()
    assert not partie.active() and not reglages.value(ia.CLE_ACTIVE, True, bool)
    assert ia.IA_ETEINTE in partie.reglage.texte.text()
    assert not partie.champ_cle.isEnabled() and not partie.bouton_tester.isEnabled()
    assert fenetre.barre_etat.texte() == "IA éteinte : l’application ne se connecte à aucun service."


# ====================================================================== réglages saisis
def test_les_reglages_saisis_sont_enregistres(partie, reglages):
    allumer(partie)
    saisir(partie.champ_adresse, "  https://autre.example/v1  ")
    saisir(partie.champ_cle, f"  {CLE}  ")
    saisir(partie.champ_modele, " mistralai/mistral-large-4-1t-a52b ")
    assert ia.lire(reglages) == ia.ReglagesIA(True, "https://autre.example/v1", CLE,
                                              "mistralai/mistral-large-4-1t-a52b")
    # Les champs montrent ce qui est enregistré : sans les espaces autour.
    assert partie.champ_adresse.text() == "https://autre.example/v1" and partie.champ_cle.text() == CLE
    assert partie.champ_modele.text() == "mistralai/mistral-large-4-1t-a52b"

    # Une adresse ou un modèle effacé reprend sa valeur de départ, qui n'a pas besoin d'être enregistrée.
    saisir(partie.champ_adresse, "")
    saisir(partie.champ_modele, "   ")
    assert partie.champ_adresse.text() == connecteur.ADRESSE_PAR_DEFAUT
    assert partie.champ_modele.text() == ia.MODELE_PAR_DEFAUT
    assert not reglages.contains(ia.CLE_ADRESSE_DU_SERVICE) and not reglages.contains(ia.CLE_MODELE)
    assert ia.lire(reglages) == ia.ReglagesIA(True, connecteur.ADRESSE_PAR_DEFAUT, CLE, ia.MODELE_PAR_DEFAUT)


def test_la_saisie_est_enregistree_sans_attendre_que_le_champ_soit_quitte(partie, reglages):
    """Fermer l'application juste après avoir collé la clé ne la fait pas perdre."""
    allumer(partie)
    partie.champ_cle.setText(f'"{CLE}"')  # collée avec ses guillemets, sans quitter le champ
    partie.champ_modele.setText("essai/modele-2 ")
    partie.champ_adresse.setText(" http://127.0.0.1:8000/v1")
    assert ia.lire(reglages) == ia.ReglagesIA(True, "http://127.0.0.1:8000/v1", CLE, "essai/modele-2")
    # Pendant la saisie, le champ n'est pas réécrit : le curseur ne bouge pas sous les doigts.
    assert partie.champ_cle.text() == f'"{CLE}"' and partie.champ_modele.text() == "essai/modele-2 "
    partie.champ_adresse.clear()  # l'adresse effacée pour en écrire une autre : celle de départ, en attendant
    assert partie.champ_adresse.text() == "" and ia.lire(reglages).adresse == connecteur.ADRESSE_PAR_DEFAUT
    assert not reglages.contains(ia.CLE_ADRESSE_DU_SERVICE)


@pytest.mark.parametrize("saisie", [
    CLE, f"  {CLE}\n", f'"{CLE}"', f"'{CLE}'", f"Bearer {CLE}", f'"Bearer {CLE}"', f"bearer   {CLE} ", f"« {CLE} »"])
def test_une_cle_copiee_d_un_exemple_de_code_est_nettoyee(saisie):
    assert ia.nettoyer_la_cle(saisie) == CLE


def test_une_cle_vide_reste_vide():
    assert ia.nettoyer_la_cle("") == ia.nettoyer_la_cle('  ""  ') == ia.nettoyer_la_cle("Bearer ") == ""


def test_la_cle_collee_avec_bearer_est_enregistree_sans_lui(partie, reglages):
    allumer(partie)
    saisir(partie.champ_cle, f'"Bearer {CLE}"')
    assert partie.champ_cle.text() == CLE and reglages.value(ia.CLE_CLE, "", str) == CLE


def test_les_reglages_sont_relus_a_l_ouverture(application, reglages, avertissements):
    reglages.setValue(ia.CLE_ACTIVE, True)
    reglages.setValue(ia.CLE_AVERTISSEMENT, True)
    reglages.setValue(ia.CLE_ADRESSE_DU_SERVICE, "http://127.0.0.1:8000/v1")
    reglages.setValue(ia.CLE_CLE, CLE)
    reglages.setValue(ia.CLE_MODELE, "essai/modele-2")
    fenetre = FenetrePrincipale(reglages=reglages)
    partie = fenetre.page_parametres.ia
    assert partie.active() and partie.champ_adresse.text() == "http://127.0.0.1:8000/v1"
    assert partie.champ_cle.text() == CLE and partie.champ_modele.text() == "essai/modele-2"
    assert partie.champ_cle.isEnabled() and partie.bouton_tester.isEnabled() and partie.bouton_effacer.isEnabled()
    fenetre.deleteLater()


def test_la_cle_est_masquee_a_l_ecran(partie):
    allumer(partie)
    saisir(partie.champ_cle, CLE)
    assert partie.champ_cle.echoMode() == QLineEdit.EchoMode.Password
    assert partie.champ_cle.displayText() != CLE and CLE not in partie.champ_cle.displayText()
    partie.bouton_afficher.click()
    assert partie.champ_cle.echoMode() == QLineEdit.EchoMode.Normal and partie.champ_cle.displayText() == CLE
    assert partie.bouton_afficher.text() == "Masquer"
    partie.bouton_afficher.click()
    assert partie.champ_cle.echoMode() == QLineEdit.EchoMode.Password and partie.bouton_afficher.text() == "Afficher"


def test_effacer_la_cle(partie, reglages, fenetre):
    allumer(partie)
    saisir(partie.champ_cle, CLE)
    assert reglages.value(ia.CLE_CLE, "", str) == CLE and partie.bouton_effacer.isEnabled()
    partie.bouton_effacer.click()
    assert partie.champ_cle.text() == "" and not reglages.contains(ia.CLE_CLE)
    assert ia.lire(reglages).cle == "" and not partie.bouton_effacer.isEnabled()
    assert fenetre.barre_etat.texte() == "Clé effacée des réglages de l’application."
    reglages.sync()
    assert CLE not in open(reglages.fileName(), encoding="utf-8").read()  # noqa: SIM115, PTH123


def test_la_cle_n_est_ecrite_que_dans_les_reglages(partie, reglages, fenetre, tmp_path):
    """Ni le message préparé pour le service informatique, ni la traduction exportée ne contiennent la clé."""
    allumer(partie)
    saisir(partie.champ_cle, CLE)
    aide = fenetre.page_aide
    aide.definir_adresse("informatique@univ-alger.dz")
    assert CLE not in "\n".join(aide.informations_techniques()) and CLE not in aide.lien_du_message()
    assert "nvapi" not in aide.lien_du_message()
    fenetre.page_texte.zone_source.setPlainText(ARTICLE_106)
    fenetre.page_texte.traduire()
    fichier = tmp_path / "traduction.txt"
    assert fenetre.page_texte.exporter(fichier)
    assert CLE not in fichier.read_text(encoding="utf-8")


# ====================================================================== essai de la connexion
def test_tester_la_connexion(partie, faux, fenetre, application):
    allumer(partie, faux)
    fins = []
    partie.essai_fini.connect(fins.append)
    partie.bouton_tester.click()
    attendre_la_fin(partie)

    assert partie.cadre_essai.isVisible() and fins == [True]
    assert phrases(partie)[0] == (
        ia.REUSSI, "1. Le service répond : il propose 2 modèles. « essai/modele-1 » est dans sa liste.")
    etat, phrase = phrases(partie)[1]
    assert etat == ia.REUSSI and phrase.startswith("2. Le modèle a répondu en ")
    assert phrase.endswith(f" s. Sa réponse : {TRADUCTION}")
    assert [constat.reussi for constat in partie.constats] == [True, True]
    assert fenetre.barre_etat.texte() == "La connexion au service d’IA fonctionne."
    assert partie.bouton_tester.isEnabled() and partie.bouton_tester.text() == "Tester la connexion"
    # Deux demandes sont parties, avec la clé saisie : la liste des modèles, puis le mot à traduire.
    assert [(demande.methode, demande.chemin) for demande in faux.recues] == [
        ("GET", "/v1/models"), ("POST", "/v1/chat/completions")]
    assert faux.recues[1].json["messages"] == [{"role": "user", "content": essai.DEMANDE}]
    assert all(demande.en_tetes["authorization"] == f"Bearer {CLE}" for demande in faux.recues)


def test_pendant_l_essai_la_fenetre_repond_et_le_bouton_attend(partie, faux, application):
    allumer(partie, faux)
    faux.prevoir(200, LISTE_DES_MODELES, attente=0.4)
    partie.bouton_tester.click()
    application.processEvents()
    # L'essai se fait à part : la main est rendue tout de suite, avant la réponse du service.
    assert partie.essai_en_cours() and not partie.bouton_tester.isEnabled()
    assert partie.bouton_tester.text() == "Essai en cours…"
    assert phrases(partie) == [
        (ia.ATTENTE, "1. Le service répond-il ? La liste de ses modèles est demandée…"),
        (ia.ATTENTE, "2. Le modèle répond-il ?")]
    partie.tester()  # un second essai ne démarre pas pendant le premier
    attendre_la_fin(partie)
    assert len(faux.recues) == 2 and [etat for etat, _ in phrases(partie)] == [ia.REUSSI, ia.REUSSI]


def test_les_reglages_saisis_juste_avant_le_clic_sont_ceux_de_l_essai(partie, faux):
    """Le clic enregistre d'abord ce qui est à l'écran : l'essai porte sur ce que l'utilisateur voit."""
    allumer(partie, faux)
    partie.champ_modele.setText("essai/modele-2")  # saisi, sans avoir quitté le champ
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    assert faux.recues[1].json["model"] == "essai/modele-2"
    assert "« essai/modele-2 » est dans sa liste." in phrases(partie)[0][1]


@pytest.mark.parametrize("code, debut", [
    (401, "2. Le service a refusé la clé d’accès."),
    (402, "2. Le service refuse la demande : le crédit du compte est épuisé"),
    (404, "2. Le service ne connaît pas le modèle « essai/modele-1 »"),
    (429, "2. Le service reçoit trop de demandes."),
])
def test_un_refus_du_service_est_dit_en_clair(partie, faux, fenetre, code, debut):
    allumer(partie, faux)
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(code, {"detail": f"refus, clé {CLE}"})
    fins = []
    partie.essai_fini.connect(fins.append)
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    (etat_1, _), (etat_2, phrase) = phrases(partie)
    assert (etat_1, etat_2) == (ia.REUSSI, ia.ECHEC) and phrase.startswith(debut)
    assert CLE not in phrase and CLE not in partie.constat_du_modele.texte.text()
    assert fins == [False] and fenetre.barre_etat.texte() == "La connexion au service d’IA n’a pas fonctionné."
    assert partie.bouton_tester.isEnabled()  # l'utilisateur corrige, puis essaie de nouveau


def test_un_modele_mal_ecrit_recoit_des_noms_proches(partie, faux):
    allumer(partie, faux, modele="essai/modele")
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(404, {"detail": "Not Found"})
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    assert phrases(partie)[0] == (
        ia.REUSSI, "1. Le service répond : il propose 2 modèles. « essai/modele » n’est pas dans sa liste. "
                   "Noms proches : essai/modele-1, essai/modele-2.")
    assert phrases(partie)[1][0] == ia.ECHEC


def test_un_service_absent_est_dit_au_premier_temps(partie, faux, fenetre):
    allumer(partie, faux)
    faux.arreter()  # plus personne n'écoute à cette adresse
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    assert phrases(partie) == [
        (ia.ECHEC, "1. Aucun service ne répond à cette adresse. Vérifiez l’adresse du service dans « Paramètres »."),
        (ia.ATTENTE, "2. Le modèle n’a pas été essayé.")]
    assert len(partie.constats) == 1


def test_la_reponse_du_service_est_affichee_telle_quelle(partie, faux):
    """Ce que le service écrit est du texte, jamais de la mise en forme : « < » et « & » restent visibles."""
    allumer(partie, faux)
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(200, reponse_du_modele("<b>عقد</b> & <i>اتفاق</i>"))
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    assert phrases(partie)[1][1].endswith("Sa réponse : <b>عقد</b> & <i>اتفاق</i>")
    assert "&lt;b&gt;عقد&lt;/b&gt; &amp; &lt;i&gt;" in partie.constat_du_modele.texte.text()


def test_eteindre_l_ia_abandonne_l_essai_en_cours(partie, faux, application):
    allumer(partie, faux)
    faux.prevoir(200, LISTE_DES_MODELES, attente=0.3)
    fins = []
    partie.essai_fini.connect(fins.append)
    partie.bouton_tester.click()
    application.processEvents()
    assert partie.essai_en_cours()
    partie.interrupteur.click()  # l'utilisateur éteint l'IA pendant l'essai
    assert not partie.active() and not partie.essai_en_cours() and not partie.cadre_essai.isVisible()
    assert fils_de_l_essai()  # la première demande est partie : sa réponse est encore attendue
    attendre_les_fils()  # la réponse du service arrive ensuite : elle n'intéresse plus personne
    assert not partie.cadre_essai.isVisible() and partie.constats == [] and fins == []
    assert len(faux.recues) == 1  # la seconde demande n'est jamais partie
    assert not partie.bouton_tester.isEnabled() and partie.bouton_tester.text() == "Tester la connexion"


def test_effacer_la_cle_retire_le_resultat_de_l_essai(partie, faux):
    allumer(partie, faux)
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    assert partie.cadre_essai.isVisible()
    partie.bouton_effacer.click()
    assert not partie.cadre_essai.isVisible() and partie.constats == []


def test_une_erreur_inattendue_pendant_l_essai_est_montree(partie, faux, monkeypatch):
    def casser(*arguments, **options):
        raise ZeroDivisionError("division par zéro")

    monkeypatch.setattr(connecteur, "demander", casser)
    allumer(partie, faux)
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    (etat_1, _), (etat_2, phrase) = phrases(partie)
    assert (etat_1, etat_2) == (ia.REUSSI, ia.ECHEC)
    assert phrase.startswith("2. L’essai s’est arrêté sur une erreur inattendue : ZeroDivisionError")
    assert partie.bouton_tester.isEnabled()  # la partie reste utilisable


def test_la_fenetre_fermee_pendant_l_essai_ne_fait_rien_tomber(application, reglages, avertissements, faux,
                                                              monkeypatch):
    erreurs = []  # les erreurs qui s'échapperaient du fil de l'essai
    monkeypatch.setattr(threading, "excepthook", erreurs.append)
    monkeypatch.setattr(ia, "confirmer_l_allumage", lambda parent: True)
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    partie = fenetre.page_parametres.ia
    allumer(partie, faux)
    faux.prevoir(200, LISTE_DES_MODELES, attente=0.3)
    partie.bouton_tester.click()
    application.processEvents()
    assert partie.essai_en_cours()
    fenetre.close()
    fenetre.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # la fenêtre est détruite maintenant
    with pytest.raises(RuntimeError):
        partie.active()  # la partie « Intelligence artificielle » n'existe plus
    assert fils_de_l_essai()  # l'essai, lui, attend encore la réponse du service
    attendre_les_fils()  # il se termine après la fermeture : son résultat est abandonné, sans erreur
    assert erreurs == []
    assert len(faux.recues) == 1  # et la seconde demande n'est pas partie


# ====================================================================== mise en page
@pytest.mark.parametrize("taille", [(1440, 860), (900, 560)])
def test_la_partie_ia_tient_dans_la_fenetre(partie, faux, fenetre, application, taille):
    fenetre.resize(*taille)
    allumer(partie, faux, modele="un-modele/au-nom-tres-long-pour-voir-si-la-ligne-passe-bien-a-la-ligne-suivante")
    faux.prevoir(200, LISTE_DES_MODELES)
    faux.prevoir(404, {"detail": "The model does not exist or you do not have access to it. " * 3})
    partie.bouton_tester.click()
    attendre_la_fin(partie)
    application.processEvents()
    page = fenetre.page_parametres
    # La page défile de haut en bas, jamais de gauche à droite.
    assert page.defilement.horizontalScrollBar().maximum() == 0
    carte = page.carte_ia
    assert 300 < carte.width() <= page.defilement.viewport().width() - 2 * theme.MARGE
    for element in (partie.ligne_adresse, partie.ligne_cle, partie.ligne_modele, partie.cadre_essai, partie.note,
                    partie.bouton_tester, partie.bouton_effacer, partie.bouton_afficher):
        droite = element.mapTo(carte, element.rect().topRight()).x()
        assert droite <= carte.width() - theme.MARGE + 1, element
    # Les trois champs commencent au même endroit, et aucun bouton n'est plus étroit que son texte.
    assert len({champ.mapTo(carte, champ.rect().topLeft()).x()
                for champ in (partie.champ_adresse, partie.champ_cle, partie.champ_modele)}) == 1
    for bouton in (partie.bouton_tester, partie.bouton_effacer, partie.bouton_afficher):
        assert bouton.width() >= bouton.sizeHint().width()
