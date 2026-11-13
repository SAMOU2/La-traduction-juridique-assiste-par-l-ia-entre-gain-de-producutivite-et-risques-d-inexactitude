"""Barre latérale, écrans d'information, allumage des étapes, écran de démarrage (tests exécutés sans écran).

* La barre latérale sombre, à gauche, donne accès aux cinq écrans : « Terme », « Texte »,
  « Paramètres », « Description de la plateforme » et « Centre d'aide ».
* « Paramètres » règle le glossaire, l'affichage et l'adresse du service informatique.
* Le « Centre d'aide » remplace le menu « Aide » : il prépare un message pour le service informatique.
* Les étapes de l'enchaînement s'allument l'une après l'autre quand un résultat s'affiche.
* L'écran de démarrage montre le logo entre deux rangées de tirets animés.
"""

import pytest

pytest.importorskip("PySide6")

from urllib.parse import parse_qs, unquote, urlsplit

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtTest import QTest
from test_interface import textes

from traducteur import __version__
from traducteur.interface import animation, demarrage, navigation, pages, theme
from traducteur.interface.animation import Allumage
from traducteur.interface.demarrage import PALETTE, EcranDemarrage, couleur_de_la_palette
from traducteur.interface.fenetre import (
    MODE_AIDE,
    MODE_DESCRIPTION,
    MODE_PARAMETRES,
    MODE_TERME,
    MODE_TEXTE,
    FenetrePrincipale,
)
from traducteur.interface.fiche import ETAPES as CHAMPS_DE_LA_FICHE
from traducteur.interface.pages import CLE_ADRESSE, CLE_ANIMATIONS, CLE_ECRAN_DE_DEMARRAGE, adresse_valide
from traducteur.interface.texte import ETAPES as ETAPES_DU_TRAITEMENT

ECRANS = [MODE_TERME, MODE_TEXTE, MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE]


class Horloge:
    """Horloge réglée à la main : les tests de l'allumage ne dépendent pas de la vitesse de la machine."""

    def __init__(self) -> None:
        self.temps = 0

    def start(self) -> None:
        self.temps = 0

    def elapsed(self) -> int:
        return self.temps


def allumage_a_la_main(nombre: int = 5) -> tuple[Allumage, Horloge]:
    allumage, horloge = Allumage(nombre), Horloge()
    allumage._horloge = horloge
    return allumage, horloge


# ------------------------------------------------------------------ barre latérale
def test_la_barre_laterale_donne_les_cinq_ecrans(fenetre, application):
    rail = fenetre.rail
    assert list(rail.boutons) == ECRANS == list(navigation.ECRANS)
    assert [bouton.accessibleName() for bouton in rail.boutons.values()] == [
        "Terme", "Texte", "Paramètres", "Description de la plateforme", "Centre d’aide"]
    # La barre occupe le bord gauche de la fenêtre, sur toute sa hauteur.
    assert rail.width() == navigation.LARGEUR == 64
    assert rail.mapTo(fenetre, QPoint(0, 0)) == QPoint(0, 0) and rail.height() == fenetre.height()
    # Les écrans se suivent de haut en bas ; le centre d'aide est tout en bas.
    hauteurs = [bouton.y() for bouton in rail.boutons.values()]
    assert hauteurs == sorted(hauteurs)
    aide = rail.boutons[MODE_AIDE]
    assert aide.y() + aide.height() > rail.height() - 24
    assert aide.y() - (rail.boutons[MODE_DESCRIPTION].y() + aide.height()) > 100
    # Chaque icône s'explique dans une infobulle : le nom de l'écran, son raccourci, ce qu'on y fait.
    assert "Terme (Ctrl+1)" in rail.boutons[MODE_TERME].toolTip()
    assert "Rechercher un terme dans le glossaire" in rail.boutons[MODE_TERME].toolTip()
    assert "Centre d’aide (F1)" in aide.toolTip()

    for mode in (MODE_TEXTE, MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE, MODE_TERME):
        rail.boutons[mode].click()
        application.processEvents()
        assert fenetre.mode == mode and fenetre.pile.currentWidget() is fenetre.pages[mode]
        # Un seul écran est marqué dans la barre, et dans le menu « Affichage ».
        assert [autre for autre, bouton in rail.boutons.items() if bouton.isChecked()] == [mode]
        assert [autre for autre, action in fenetre.actions_mode.items() if action.isChecked()] == [mode]


def test_la_barre_laterale_est_sombre_et_l_ecran_affiche_est_dore(fenetre, application):
    """Sur l'image de la fenêtre : le fond de la barre, puis le repère doré de l'écran affiché."""
    image = fenetre.grab().toImage()
    echelle = image.devicePixelRatio()

    def couleur(x: int, y: int) -> str:
        return QColor(image.pixel(int(x * echelle), int(y * echelle))).name().upper()

    rail = fenetre.rail
    assert couleur(rail.width() - 3, rail.height() // 2) == theme.RAIL
    bouton = rail.boutons[MODE_TERME]
    milieu = bouton.y() + bouton.height() // 2
    assert couleur(1, milieu) == theme.OR  # le trait doré, sur le bord gauche
    # L'écran qui n'est pas affiché n'a pas ce trait.
    autre = rail.boutons[MODE_TEXTE]
    assert couleur(1, autre.y() + autre.height() // 2) == theme.RAIL


def test_les_raccourcis_des_ecrans(fenetre):
    raccourcis = {mode: action.shortcut().toString() for mode, action in fenetre.actions_mode.items()}
    assert raccourcis == {MODE_TERME: "Ctrl+1", MODE_TEXTE: "Ctrl+2", MODE_PARAMETRES: "Ctrl+3",
                          MODE_DESCRIPTION: "Ctrl+4", MODE_AIDE: "F1"}
    for mode in (MODE_AIDE, MODE_DESCRIPTION, MODE_PARAMETRES, MODE_TEXTE, MODE_TERME):
        fenetre.actions_mode[mode].trigger()
        assert fenetre.mode == mode


def test_un_ecran_d_information_affiche_son_titre_a_la_place_des_outils(fenetre, application):
    assert fenetre.cadre_sens.isVisible() and fenetre.action_inverser.isEnabled()
    attendus = {
        MODE_PARAMETRES: ("Paramètres", "Glossaire, affichage, service informatique"),
        MODE_DESCRIPTION: ("Description de la plateforme", "Ce que fait l’application, et comment"),
        MODE_AIDE: ("Centre d’aide", "Contacter le service informatique, questions fréquentes"),
    }
    for mode, (titre, sous_titre) in attendus.items():
        fenetre.definir_mode(mode)
        application.processEvents()
        # Ni sens de traduction ni barre de recherche : le titre de l'écran les remplace.
        assert not fenetre.cadre_sens.isVisible() and not fenetre.page.barre.isVisible()
        assert fenetre.outils.currentWidget() is fenetre.titre_de_page and fenetre.titre_de_page.isVisible()
        assert fenetre.titre_de_page.titre.text() == titre
        assert fenetre.titre_de_page.sous_titre.texte_complet() == sous_titre
        assert not fenetre.action_inverser.isEnabled()
        assert fenetre.ecran_de_travail() is None and fenetre.barre_etat.etat() == ""
    fenetre.definir_mode(MODE_TEXTE)
    application.processEvents()
    assert fenetre.cadre_sens.isVisible() and fenetre.action_inverser.isEnabled()
    assert fenetre.ecran_de_travail() is fenetre.page_texte


def test_les_ecrans_d_information_tiennent_dans_une_petite_fenetre(fenetre, application):
    fenetre.resize(900, 560)
    for mode in (MODE_PARAMETRES, MODE_DESCRIPTION, MODE_AIDE):
        fenetre.definir_mode(mode)
        application.processEvents()
        page = fenetre.pages[mode]
        # La page défile de haut en bas, jamais de gauche à droite.
        assert page.defilement.horizontalScrollBar().maximum() == 0, mode
        place = page.defilement.viewport().width()
        for carte in page.cartes:
            assert 300 < carte.width() <= place - 2 * theme.MARGE, mode


# ------------------------------------------------------------------ paramètres
def test_les_parametres_presentent_le_glossaire_charge(fenetre):
    parametres = fenetre.page_parametres
    assert [carte.titre.text() for carte in parametres.cartes] == ["Glossaire", "Affichage", "Service informatique"]
    assert parametres.nom_du_glossaire.texte_complet() == "glossaire_essai.csv"
    assert parametres.dossier_du_glossaire.texte_complet() == "Glossaire fourni avec l’application"
    assert parametres.taille_du_glossaire.text() == "40 entrées"
    assert [bouton.text() for bouton in (parametres.bouton_choisir, parametres.bouton_recharger,
                                         parametres.bouton_fourni)] == [
        "Choisir un autre fichier…", "Recharger", "Revenir au glossaire fourni"]
    assert parametres.bouton_recharger.isEnabled() and not parametres.bouton_fourni.isEnabled()
    # Le glossaire se charge sans que l'utilisateur ait à le demander : la carte le dit.
    assert any(texte.startswith("Le glossaire est chargé automatiquement à l’ouverture de l’application.")
               for texte in textes(parametres.carte_glossaire))


def test_regler_les_etapes_animees(fenetre, reglages, application, avertissements):
    parametres = fenetre.page_parametres
    assert not parametres.interrupteur_animations.isChecked() and not animation.actives()  # réglage des tests
    parametres.interrupteur_animations.click()
    assert parametres.interrupteur_animations.isChecked()
    assert animation.actives() and reglages.value(CLE_ANIMATIONS, False, bool) is True
    parametres.interrupteur_animations.click()
    assert not animation.actives() and reglages.value(CLE_ANIMATIONS, True, bool) is False

    # Le réglage est repris à la prochaine ouverture ; sans réglage, les étapes sont animées.
    reglages.remove(CLE_ANIMATIONS)
    autre = FenetrePrincipale(reglages=reglages)
    assert animation.actives() and autre.page_parametres.interrupteur_animations.isChecked()
    autre.deleteLater()


def test_regler_l_ecran_de_demarrage(fenetre, reglages):
    parametres = fenetre.page_parametres
    assert parametres.interrupteur_demarrage.isChecked()  # affiché, sauf réglage contraire
    assert not reglages.contains(CLE_ECRAN_DE_DEMARRAGE)
    parametres.interrupteur_demarrage.click()
    assert not parametres.interrupteur_demarrage.isChecked()
    assert reglages.value(CLE_ECRAN_DE_DEMARRAGE, True, bool) is False
    parametres.interrupteur_demarrage.click()
    assert reglages.value(CLE_ECRAN_DE_DEMARRAGE, False, bool) is True


@pytest.mark.parametrize(("adresse", "valide"), [
    ("informatique@univ-alger.dz", True),
    ("  support.it@exemple.org ", True),
    ("prenom.nom+aide@service.gouv.dz", True),
    ("informatique", False),
    ("informatique@", False),
    ("@univ.dz", False),
    ("informatique@univ", False),
    ("deux mots@univ.dz", False),
    ("a@b@c.dz", False),
    ("", False),
])
def test_forme_d_une_adresse_electronique(adresse, valide):
    assert adresse_valide(adresse) is valide


def test_enregistrer_l_adresse_du_service_informatique(fenetre, reglages):
    parametres, aide = fenetre.page_parametres, fenetre.page_aide
    assert parametres.adresse() == "" and aide.adresse == "" and not parametres.retour_adresse.isVisibleTo(parametres)

    # Une adresse incomplète n'est pas enregistrée : un message dit ce qui manque.
    parametres.champ_adresse.setText("informatique@")
    parametres.bouton_enregistrer.click()
    assert not reglages.contains(CLE_ADRESSE) and aide.adresse == ""
    assert parametres.retour_adresse.isVisibleTo(parametres) and parametres.retour_adresse.property("erreur") is True
    assert parametres.retour_adresse.text() == (
        "Cette adresse n’est pas complète : il faut un nom, le signe @ et un domaine.")

    # Une adresse complète est enregistrée (la touche Entrée suffit) ; le centre d'aide la reçoit aussitôt.
    parametres.champ_adresse.setText("  informatique@univ-alger.dz ")
    QTest.keyClick(parametres.champ_adresse, Qt.Key.Key_Return)
    assert reglages.value(CLE_ADRESSE) == "informatique@univ-alger.dz" == parametres.adresse() == aide.adresse
    assert parametres.champ_adresse.text() == "informatique@univ-alger.dz"
    assert parametres.retour_adresse.text() == "Adresse enregistrée."
    assert parametres.retour_adresse.property("erreur") is False

    # Un champ vide efface l'adresse.
    parametres.champ_adresse.clear()
    parametres.bouton_enregistrer.click()
    assert parametres.adresse() == "" and aide.adresse == ""
    assert parametres.retour_adresse.text() == "Adresse effacée."


def test_l_adresse_enregistree_est_reprise_a_l_ouverture(application, reglages, avertissements):
    reglages.setValue(CLE_ADRESSE, "informatique@univ-alger.dz")
    fenetre = FenetrePrincipale(reglages=reglages)
    assert fenetre.page_parametres.champ_adresse.text() == "informatique@univ-alger.dz"
    assert fenetre.page_aide.adresse == "informatique@univ-alger.dz"
    fenetre.deleteLater()


# ------------------------------------------------------------------ centre d'aide
def test_le_centre_d_aide(fenetre, application):
    fenetre.rail.boutons[MODE_AIDE].click()
    application.processEvents()
    aide = fenetre.page_aide
    assert fenetre.pile.currentWidget() is aide
    assert [carte.titre.text() for carte in aide.cartes] == [
        "Contacter le service informatique", "Questions fréquentes", "Raccourcis du clavier"]
    # Les questions fréquentes, avec leur réponse.
    assert [question.text() for question in aide.questions] == [question for question, _ in pages.QUESTIONS] == [
        "Comment chercher un terme ?", "Comment traduire un texte ?",
        "Pourquoi des mots restent-ils dans la langue d’origine ?", "Que signifie la mention « À vérifier » ?",
        "Comment compléter le glossaire ?", "Comment utiliser un autre glossaire ?"]
    contenu = textes(aide.carte_questions)
    for _, reponse in pages.QUESTIONS:
        for paragraphe in reponse:
            assert paragraphe in contenu
    # Les raccourcis du clavier.
    contenu = textes(aide.carte_raccourcis)
    for _, action in pages.RACCOURCIS:
        assert action in contenu
    assert {"Ctrl+1", "Ctrl+F", "F1"} <= set(contenu)


def test_sans_adresse_le_centre_d_aide_renvoie_aux_parametres(fenetre, application):
    fenetre.definir_mode(MODE_AIDE)
    application.processEvents()
    aide = fenetre.page_aide
    assert aide.etat_adresse.text() == "L’adresse du service informatique n’est pas encore indiquée."
    assert aide.bouton_parametres.isVisible() and aide.bouton_parametres.text() == "Indiquer l’adresse dans Paramètres"
    assert not aide.bouton_ecrire.isVisible() and not aide.bouton_copier.isVisible()
    assert aide.ecrire() is False  # rien à ouvrir sans destinataire
    assert fenetre.mode == MODE_PARAMETRES
    fenetre.definir_mode(MODE_AIDE)
    aide.bouton_parametres.click()
    application.processEvents()
    # « Paramètres » s'ouvre sur le champ de l'adresse.
    assert fenetre.mode == MODE_PARAMETRES and fenetre.page_parametres.champ_adresse.hasFocus()


def test_ecrire_au_service_informatique(fenetre, application, monkeypatch):
    aide = fenetre.page_aide
    fenetre.page_parametres.champ_adresse.setText("informatique@univ-alger.dz")
    fenetre.page_parametres.enregistrer_l_adresse()
    fenetre.definir_mode(MODE_AIDE)
    application.processEvents()
    assert aide.etat_adresse.text() == "Adresse : informatique@univ-alger.dz"
    assert aide.bouton_ecrire.isVisible() and aide.bouton_copier.isVisible() and not aide.bouton_parametres.isVisible()
    assert aide.bouton_ecrire.text() == "Écrire au service informatique"

    # Le message est préparé : destinataire, objet, et ce que le service a besoin de savoir.
    lien = urlsplit(aide.lien_du_message())
    assert lien.scheme == "mailto" and lien.path == "informatique@univ-alger.dz"
    champs = parse_qs(lien.query)
    assert champs["subject"] == ["Traducteur juridique : demande d’aide"]
    corps = champs["body"][0].splitlines()
    assert corps[0] == "Bonjour," and "(Décrivez ici le problème rencontré.)" in corps
    assert f"Application : Traducteur juridique {__version__}" in corps
    assert "Glossaire : glossaire_essai.csv, 40 entrées" in corps
    assert any(ligne.startswith("Système : ") and "Python" in ligne and "PySide6" in ligne for ligne in corps)
    assert " " not in aide.lien_du_message() and unquote(aide.lien_du_message()) != aide.lien_du_message()

    # Le bouton ouvre le logiciel de messagerie sur ce message.
    ouverts = []
    monkeypatch.setattr(pages, "ouvrir_lien", lambda adresse: ouverts.append(adresse) or True)
    aide.bouton_ecrire.click()
    assert ouverts == [aide.lien_du_message()]
    assert fenetre.barre_etat.texte() == "Message préparé dans votre logiciel de messagerie."

    # Aucun logiciel de messagerie : l'adresse est copiée, pour écrire depuis une autre messagerie.
    QGuiApplication.clipboard().clear()
    monkeypatch.setattr(pages, "ouvrir_lien", lambda adresse: False)
    aide.bouton_ecrire.click()
    assert QGuiApplication.clipboard().text() == "informatique@univ-alger.dz"
    assert fenetre.barre_etat.texte() == (
        "Aucun logiciel de messagerie n’a répondu : l’adresse informatique@univ-alger.dz a été copiée.")

    QGuiApplication.clipboard().clear()
    aide.bouton_copier.click()
    assert QGuiApplication.clipboard().text() == "informatique@univ-alger.dz"
    assert fenetre.barre_etat.texte() == "Adresse copiée : informatique@univ-alger.dz"


def test_le_message_signale_l_absence_de_glossaire(application, reglages):
    aide = pages.PageAide(reglages)
    aide.definir_adresse("informatique@univ-alger.dz")
    assert aide.informations_techniques()[-1] == "Glossaire : aucun glossaire chargé"
    aide.deleteLater()


# ------------------------------------------------------------------ description de la plateforme
def test_la_description_de_la_plateforme(fenetre, application):
    fenetre.rail.boutons[MODE_DESCRIPTION].click()
    application.processEvents()
    description = fenetre.page_description
    assert fenetre.pile.currentWidget() is description
    assert [carte.titre.text() for carte in description.cartes] == [
        "Traducteur juridique", "L’enchaînement en cinq étapes", "Deux écrans de travail",
        "Comment un texte est traduit", "À savoir"]
    # Les cinq étapes de l'enchaînement portent les noms des cinq champs de la fiche.
    assert [ligne.titre.text() for ligne in description.etapes] == [titre for titre, _ in pages.CHAMPS] == [
        "Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
    assert [titre for titre, _ in pages.CHAMPS] == list(CHAMPS_DE_LA_FICHE)
    assert [ligne.numero.numero for ligne in description.etapes] == [1, 2, 3, 4, 5]
    assert all(ligne.numero.niveau == 1.0 for ligne in description.etapes)  # dessinées allumées
    # Les cinq étapes du traitement d'un texte portent les noms de la bande de l'écran « Texte ».
    assert [ligne.titre.text() for ligne in description.traitement] == [nom for nom, _, _ in ETAPES_DU_TRAITEMENT]
    # La présentation cite la taille du glossaire chargé ; la page n'affiche pas de numéro de version.
    contenu = textes(description)
    assert contenu[1] == ("Aide à la traduction juridique entre le français et l’arabe, à partir d’un glossaire "
                          "de 40 entrées.")
    assert any(texte.startswith("L’application ne remplace pas le traducteur.") for texte in contenu)
    assert not any(__version__ in texte or "ersion" in texte for texte in contenu)


def test_la_description_sans_glossaire(application):
    description = pages.PageDescription()
    assert textes(description)[1] == (
        "Aide à la traduction juridique entre le français et l’arabe, à partir d’un glossaire.")
    description.deleteLater()


# ------------------------------------------------------------------ allumage des étapes
def test_sans_animation_les_etapes_prennent_leur_etat_final(application):
    allumage = Allumage(5)
    assert allumage.allumees() == [False] * 5 and not allumage.en_cours()
    changements = []
    allumage.change.connect(lambda: changements.append(True))
    allumage.definir([True, False, True, True, False])
    assert allumage.allumees() == [True, False, True, True, False]
    assert not allumage.en_cours() and len(changements) == 1
    assert [allumage.niveau(rang) for rang in range(5)] == [1.0, 0.0, 1.0, 1.0, 0.0]
    assert [allumage.halo(rang) for rang in range(5)] == [0.0] * 5


def test_les_etapes_s_allument_l_une_apres_l_autre(application):
    animation.definir_actives(True)
    allumage, horloge = allumage_a_la_main()
    termine = []
    allumage.termine.connect(lambda: termine.append(True))
    allumage.definir([True] * 5)
    assert allumage.en_cours() and allumage.allumees() == [True] * 5
    assert [allumage.niveau(rang) for rang in range(5)] == [0.0] * 5  # tout est encore éteint

    # La première étape est allumée quand la deuxième commence ; les suivantes attendent leur tour.
    horloge.temps = Allumage.MONTEE
    niveaux = [allumage.niveau(rang) for rang in range(5)]
    assert niveaux[0] == 1.0 and 0.0 < niveaux[1] < 1.0 and niveaux[2:] == [0.0] * 3
    assert allumage.halo(0) > 0.0 and allumage.halo(4) == 0.0  # un halo entoure l'étape qui vient de s'allumer

    # À tout instant, une étape n'est jamais plus allumée que celle qui la précède.
    for temps in range(0, allumage.duree() + 50, 25):
        horloge.temps = temps
        niveaux = [allumage.niveau(rang) for rang in range(5)]
        assert niveaux == sorted(niveaux, reverse=True), temps
        assert all(0.0 <= allumage.halo(rang) <= 1.0 for rang in range(5)), temps

    # À la fin, toutes sont allumées et les halos sont éteints.
    assert allumage.duree() == 4 * Allumage.INTERVALLE + Allumage.HALO
    horloge.temps = allumage.duree()
    allumage._avancer()
    assert termine == [True] and not allumage.en_cours()
    assert [allumage.niveau(rang) for rang in range(5)] == [1.0] * 5
    assert [allumage.halo(rang) for rang in range(5)] == [0.0] * 5


def test_une_etape_non_renseignee_reste_eteinte(application):
    animation.definir_actives(True)
    allumage, horloge = allumage_a_la_main()
    allumage.definir([True, True, True, False, True])
    horloge.temps = allumage.duree() - 1
    assert allumage.niveau(3) == 0.0 and allumage.halo(3) == 0.0
    assert allumage.niveau(4) == 1.0  # l'étape suivante s'allume à son tour habituel
    allumage.terminer()
    assert not allumage.en_cours() and allumage.allumees() == [True, True, True, False, True]

    # Rien à allumer : pas d'animation.
    allumage.definir([False] * 5)
    assert not allumage.en_cours()


def test_l_allumage_reel_se_termine(application):
    """Avec la vraie horloge : l'animation s'arrête d'elle-même, toutes les étapes allumées."""
    animation.definir_actives(True)
    allumage = Allumage(3)
    termine = []
    allumage.termine.connect(lambda: termine.append(True))
    allumage.definir([True] * 3)
    assert allumage.en_cours()
    QTest.qWait(allumage.duree() + 400)
    assert termine == [True] and not allumage.en_cours()
    assert [allumage.niveau(rang) for rang in range(3)] == [1.0] * 3


def test_les_etapes_de_la_fiche_s_allument_selon_le_glossaire(fenetre):
    page = fenetre.page
    # À l'accueil, aucun terme n'est affiché : les cinq étapes sont éteintes.
    assert page.accueil.entete.etapes_allumees() == [False] * 5
    page.rechercher("contrat")
    assert page.fiche.etapes_renseignees() == [True] * 5
    assert page.fiche.entete.etapes_allumees() == [True] * 5
    # « contrat de travail » n'a pas de contexte dans le glossaire d'essai : l'étape 4 reste éteinte.
    page.rechercher("contrat de travail")
    assert page.fiche.colonne_contexte.emplois == []
    assert page.fiche.etapes_renseignees() == [True, True, True, False, True]
    assert page.fiche.entete.etapes_allumees() == [True, True, True, False, True]


def test_les_etapes_de_la_fiche_sont_animees_quand_le_reglage_le_demande(fenetre, application):
    fenetre.page_parametres.interrupteur_animations.click()
    assert animation.actives()
    page = fenetre.page
    page.rechercher("contrat")
    allumage = page.fiche.entete.allumage
    assert allumage.en_cours() and allumage.niveau(4) < 1.0  # la dernière étape n'est pas encore allumée
    QTest.qWait(allumage.duree() + 400)
    assert not allumage.en_cours() and [allumage.niveau(rang) for rang in range(5)] == [1.0] * 5
    assert page.fiche.entete.etapes_allumees() == [True] * 5


# ------------------------------------------------------------------ écran de démarrage
def test_la_palette_des_tirets_tourne_en_boucle():
    assert len(PALETTE) >= 5 and PALETTE[0] == theme.OR
    assert couleur_de_la_palette(0.0).name().upper() == PALETTE[0]
    assert couleur_de_la_palette(1.0) == couleur_de_la_palette(0.0) == couleur_de_la_palette(-3.0)
    assert couleur_de_la_palette(1 / len(PALETTE)).name().upper() == PALETTE[1]
    # Entre deux couleurs, la teinte passe de l'une à l'autre sans saut.
    milieu = couleur_de_la_palette(0.5 / len(PALETTE))
    premiere, deuxieme = QColor(PALETTE[0]), QColor(PALETTE[1])
    assert min(premiere.green(), deuxieme.green()) <= milieu.green() <= max(premiere.green(), deuxieme.green())


def test_l_ecran_de_demarrage_montre_le_logo_entre_deux_rangees_de_tirets(application):
    ecran = EcranDemarrage()
    assert (ecran.width(), ecran.height()) == (EcranDemarrage.LARGEUR, EcranDemarrage.HAUTEUR)
    assert ecran.windowFlags() & Qt.WindowType.FramelessWindowHint
    tirets = ecran.tirets(0.0)
    assert len(tirets) == 2 * EcranDemarrage.TIRETS
    milieu = ecran.width() / 2
    a_gauche = [tiret for tiret in tirets if tiret[0].x() < milieu]
    a_droite = [tiret for tiret in tirets if tiret[0].x() > milieu]
    assert len(a_gauche) == len(a_droite) == EcranDemarrage.TIRETS
    # Les tirets laissent la place du logo, au centre, et restent dans la fenêtre.
    bord_du_logo = EcranDemarrage.COTE_DU_LOGO / 2
    for centre, largeur, _, _ in tirets:
        assert abs(centre.x() - milieu) - largeur / 2 > bord_du_logo
        assert largeur / 2 < centre.x() < ecran.width() - largeur / 2
        assert abs(centre.y() - EcranDemarrage.MILIEU) < 14
    # Les deux rangées sont symétriques : même hauteur et même couleur de part et d'autre du logo.
    for (gauche, _, pente_gauche, couleur_gauche), (droite, _, pente_droite, couleur_droite) in zip(
            tirets[0::2], tirets[1::2], strict=True):
        assert gauche.x() + droite.x() == pytest.approx(2 * milieu)
        assert gauche.y() == droite.y() and pente_gauche == -pente_droite and couleur_gauche == couleur_droite
    ecran.deleteLater()


def test_les_tirets_bougent_et_changent_de_couleur(application):
    ecran = EcranDemarrage()
    avant, apres = ecran.tirets(0.0), ecran.tirets(0.4)
    # Les tirets restent à leur place de gauche à droite ; ils montent et descendent, et changent de couleur.
    assert [tiret[0].x() for tiret in avant] == [tiret[0].x() for tiret in apres]
    assert [tiret[0].y() for tiret in avant] != [tiret[0].y() for tiret in apres]
    assert all(ancien[3] != nouveau[3] for ancien, nouveau in zip(avant, apres, strict=True))
    # L'onde est plus ample au bout de la rangée que près du logo, comme une nageoire.
    def amplitude(rang: int) -> float:
        hauteurs = [ecran.tirets(instant / 20)[2 * rang][0].y() for instant in range(60)]
        return max(hauteurs) - min(hauteurs)

    assert amplitude(EcranDemarrage.TIRETS - 1) > 3 * amplitude(0) > 0
    # Le long d'une rangée, les couleurs diffèrent d'un tiret au suivant.
    couleurs = [tiret[3].name() for tiret in avant[0::2]]
    assert len(set(couleurs)) == EcranDemarrage.TIRETS
    # Le mouvement et les couleurs reprennent en boucle.
    periode = EcranDemarrage.PERIODE_DE_L_ONDE
    assert ecran.tirets(periode)[5][0].y() == pytest.approx(ecran.tirets(0.0)[5][0].y(), abs=1e-6)
    ecran.deleteLater()


def test_l_image_de_l_ecran_de_demarrage(application):
    ecran = EcranDemarrage()
    ecran.show()
    application.processEvents()
    image = ecran.grab().toImage()
    echelle = image.devicePixelRatio()

    def couleur(x: float, y: float) -> QColor:
        return QColor(image.pixel(int(x * echelle), int(y * echelle)))

    # Fond sombre ; au centre, la balance dorée du logo.
    assert couleur(20, 20).lightness() < 60
    milieu, hauteur = ecran.width() // 2, EcranDemarrage.MILIEU
    dores = [couleur(x, y) for x in range(milieu - 30, milieu + 30, 2) for y in range(hauteur - 30, hauteur + 30, 2)]
    assert any(teinte.red() > 200 and teinte.green() > 150 and teinte.blue() < 140 for teinte in dores)
    # De chaque côté du logo, des tirets de couleur vive.
    for cote in (-1, 1):
        vifs = [couleur(milieu + cote * distance, y) for distance in range(80, 300, 2)
                for y in range(hauteur - 14, hauteur + 14, 2)]
        assert sum(1 for teinte in vifs if teinte.saturation() > 120 and teinte.lightness() > 100) > 40
    ecran.close()
    ecran.deleteLater()


def test_l_ecran_de_demarrage_passe_la_main(application):
    ecran = EcranDemarrage()
    ecran.show()
    application.processEvents()
    assert ecran._images.isActive()  # l'animation tourne tant que l'écran est affiché
    termine = []
    ecran.termine.connect(lambda: termine.append(True))
    QTest.mouseClick(ecran, Qt.MouseButton.LeftButton)
    assert termine == [] and ecran.isVisible()  # la fenêtre principale n'est pas prête : le clic ne ferme rien
    # Une fois la fenêtre prête, l'écran reste affiché le temps prévu, puis se ferme.
    ecran.passer_la_main(duree_minimale=250)
    assert termine == [] and ecran.isVisible()
    QTest.qWait(500)
    assert termine == [True] and not ecran.isVisible() and not ecran._images.isActive()
    ecran.deleteLater()


def test_un_clic_ferme_l_ecran_de_demarrage_sans_attendre(application):
    ecran = EcranDemarrage()
    ecran.show()
    application.processEvents()
    termine = []
    ecran.termine.connect(lambda: termine.append(True))
    ecran.passer_la_main(duree_minimale=60_000)
    QTest.mouseClick(ecran, Qt.MouseButton.LeftButton)
    assert termine == [True] and not ecran.isVisible()
    QTest.mouseClick(ecran, Qt.MouseButton.LeftButton)  # un second clic ne signale rien de plus
    assert termine == [True]
    ecran.deleteLater()


def test_la_duree_minimale_laisse_voir_l_animation():
    assert 1500 <= demarrage.EcranDemarrage.DUREE_MINIMALE <= 3000
