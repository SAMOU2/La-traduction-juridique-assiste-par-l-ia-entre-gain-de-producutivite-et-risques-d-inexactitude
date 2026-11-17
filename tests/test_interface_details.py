"""Menu « Plus de détails » de l'écran « Terme » (tests exécutés sans écran).

La fiche n'affiche que le terme et son équivalent. Le reste de l'entrée est rangé dans un menu
en forme de roue : le terme au centre, six cercles autour de lui (trois à gauche, trois à
droite). Un clic sur un cercle affiche son information à droite de la roue.

La place des cercles dépend de la taille de la fenêtre et de la police du système. Les tests
vérifient donc leur disposition (aucun cercle n'en recouvre un autre, tous restent dans le
panneau), et non des coordonnées exactes.
"""

import math

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel
from test_interface import points_de_couleur, puces, textes

from traducteur.interface import theme
from traducteur.interface.details import CLES, DETAILS, PAR_CLE, PanneauDetails, RoueDesDetails, medaillon
from traducteur.langues import AR, FR

#: Tailles de fenêtre essayées : un grand écran, la fenêtre de référence, un portable, la plus petite fenêtre.
TAILLES = ((1900, 1000), (1440, 860), (1080, 620), (900, 600))
NOMS = [detail.titre for detail in DETAILS]
NOMS_COURTS = [detail.titre_court for detail in DETAILS]


@pytest.fixture
def details(fenetre, application):
    """Le menu « Plus de détails » de la fiche de « contrat »."""
    fenetre.page.rechercher("contrat")
    application.processEvents()
    return fenetre.page.details


def cercles(roue) -> dict[str, tuple[float, float, float]]:
    """Pour chaque information : le centre de son cercle (x, y) et son rayon, dans les coordonnées de la roue."""
    return {cle: (bouton.x() + bouton.centre.x(), bouton.y() + bouton.centre.y(), bouton.rayon)
            for cle, bouton in roue.boutons.items()}


# ------------------------------------------------------------------ les six informations
def test_les_six_informations_du_menu():
    assert CLES == ("definition", "contexte", "ressources", "expressions", "associes", "synonymes")
    assert list(PAR_CLE) == list(CLES) and PAR_CLE["contexte"] is DETAILS[1]
    assert NOMS == ["Définition", "Contextualisation", "Ressources", "Expressions", "Termes associés", "Synonymes"]
    # Les noms longs ont une forme courte : elle sert quand la roue est étroite.
    assert NOMS_COURTS == ["Définition", "Contexte", "Ressources", "Expressions", "Associés", "Synonymes"]
    assert all(len(court) <= len(long) for court, long in zip(NOMS_COURTS, NOMS, strict=True))
    # Chaque information a sa couleur et son icône. Ses deux infobulles disent ce qu'elle contient, ou ce qui manque.
    assert len({detail.couleur for detail in DETAILS}) == len({detail.icone for detail in DETAILS}) == 6
    assert all(detail.info and detail.info_vide and detail.info != detail.info_vide for detail in DETAILS)


def test_le_cercle_d_une_information_dans_un_titre(application):
    """Le petit cercle placé devant le titre d'une information : de sa couleur, ou gris."""
    definition = DETAILS[0]
    colore, gris = medaillon(definition, 24), medaillon(definition, 24, False)
    assert colore.deviceIndependentSize().toSize().width() == 24 == gris.deviceIndependentSize().toSize().height()
    etiquette_coloree, etiquette_grise = QLabel(), QLabel()
    etiquette_coloree.setPixmap(colore)
    etiquette_grise.setPixmap(gris)
    for etiquette in (etiquette_coloree, etiquette_grise):
        etiquette.setFixedSize(24, 24)
    assert points_de_couleur(etiquette_coloree, definition.couleur) > 20
    assert points_de_couleur(etiquette_grise, definition.couleur) == 0


# ------------------------------------------------------------------ le menu d'un terme
def test_le_menu_d_un_terme_que_le_glossaire_renseigne_en_entier(details):
    roue = details.roue
    assert details.titre.text() == "Plus de détails" and details.titre.isVisible()
    assert list(roue.boutons) == list(CLES)
    # Le terme est écrit au centre ; chaque cercle porte le nom de son information.
    assert (roue.terme, roue.langue) == ("contrat", FR)
    assert roue.lignes_du_centre()[0] == ["contrat"]
    assert roue.libelles_affiches() == NOMS
    # Les six cercles sont colorés. Une pastille donne le nombre d'éléments ; la définition ne se compte pas.
    assert details.etats() == {
        "definition": (True, 0), "contexte": (True, 2), "ressources": (True, 4), "expressions": (True, 5),
        "associes": (True, 4), "synonymes": (True, 2)}
    assert details.renseignes() == list(CLES) and roue.etats() == dict.fromkeys(CLES, True)
    assert [(bouton.disponible, bouton.nombre) for bouton in roue.boutons.values()] == list(details.etats().values())
    assert roue.allumage.allumees() == [True] * 6
    # Rien n'est ouvert : à droite de la roue, une invitation nomme les informations disponibles.
    assert details.detail == "" and details.pile.currentWidget() is details.invite
    assert not any(bouton.isChecked() for bouton in roue.boutons.values())
    assert details.invite.titre.text() == "Plus de détails sur ce terme"
    assert details.invite.texte.text() == (
        "Cliquez sur un cercle coloré : définition, contextualisation, ressources, expressions, "
        "termes associés, synonymes.")
    # Chaque cercle s'explique dans une infobulle, et se nomme pour un lecteur d'écran.
    for cle, bouton in roue.boutons.items():
        assert bouton.accessibleName() == PAR_CLE[cle].titre
        assert bouton.accessibleDescription() == PAR_CLE[cle].info
        assert bouton.toolTip() == f"<qt>{PAR_CLE[cle].info}</qt>"


def test_un_clic_sur_un_cercle_affiche_son_information(details):
    roue = details.roue

    def ouvrir(cle: str, titre: str, nombre: str):
        roue.boutons[cle].click()
        assert details.detail == cle and details.pile.currentWidget() is details.vue
        assert [autre for autre, bouton in roue.boutons.items() if bouton.isChecked()] == [cle]
        assert details.colonnes[cle].corps.isVisible()
        assert details.titre_du_detail.texte_complet() == titre
        assert (details.nombre.text() if details.nombre.isVisible() else "") == nombre
        return details.colonnes[cle]

    # Définition : dans les deux langues, puis sa source.
    definition = ouvrir("definition", "Définition", "")
    contenu = textes(definition.corps)
    assert contenu[0] == "FRANÇAIS" and contenu[1].startswith("Convention par laquelle")
    assert contenu[2] == "العربية" and contenu[3].startswith("اتفاق يلتزم بموجبه")
    assert textes(definition.pied) == ["Source :", "Code civil, art. 54"]

    # Contextualisation : des phrases avec leur source ; le terme y est en évidence dans les deux langues.
    contexte = ouvrir("contexte", "Contextualisation", "2")
    assert textes(contexte.corps) == [
        "Code civil, art. 106", "Le contrat fait la loi des parties.", "العقد شريعة المتعاقدين.",
        "Code civil, art. 107", "Le contrat doit être exécuté conformément à son contenu, et de bonne foi.",
        "يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية."]
    assert textes(contexte.pied) == ["2 exemples dans le glossaire"]
    assert [emploi.origine for emploi in contexte.emplois] == ["propre", "propre"]
    riches = [label.text() for label in contexte.corps.findChildren(QLabel) if "<span" in label.text()]
    assert len(riches) == 4
    assert any('font-weight: 600;">contrat</span>' in texte for texte in riches)
    assert any('font-weight: 600;">العقد</span>' in texte for texte in riches)

    # Ressources : chaque référence est écrite en entier ; l'adresse d'un site est un lien.
    ressources = ouvrir("ressources", "Ressources", "4")
    assert textes(ressources.corps) == [
        "Code civil algérien\nordonnance n° 75-58 du 26 septembre 1975, art. 54, 106 et 107",
        "القانون المدني\nالأمر رقم 75-58 المؤرخ في 26 سبتمبر 1975، المواد 54 و106 و107",
        "Journal officiel (JORADP) n° 78 du 30 septembre 1975\nwww.joradp.dz\u00a0↗",
        "G. Cornu (dir.)\nVocabulaire juridique, Association Henri Capitant, PUF"]
    liens = [label.text() for label in ressources.corps.findChildren(QLabel) if "<a href" in label.text()]
    assert len(liens) == 1 and 'href="https://www.joradp.dz"' in liens[0]
    assert ressources.bouton_copier.isVisible() and ressources.bouton_copier.text() == "Copier les références"

    # Expressions : les autres entrées trouvées par la recherche, à ouvrir d'un clic.
    expressions = ouvrir("expressions", "Expressions avec « contrat »", "5")
    assert [entree.terme_fr for entree in expressions.entrees()] == [
        "contrat de bail", "contrat de vente", "contrat de travail", "exécution du contrat", "conclusion du contrat"]
    assert expressions.grille.cellules[0].text() == "contrat de bail — عقد الإيجار"
    assert textes(expressions.pied) == ["Cliquez sur une ligne pour ouvrir sa fiche"]

    # Termes associés : en bleu et cliquables, ceux qui ont leur entrée dans le glossaire.
    associes = ouvrir("associes", "Termes associés", "4")
    assert [puce.text() for puce in associes.puces] == ["contractant", "cocontractant", "clause", "obligation"]
    assert puces(associes.corps) == ["contractant", "obligation"]
    assert textes(associes.pied) == [
        "En bleu : une entrée du glossaire, à ouvrir d’un clic · en gris : un terme sans entrée"]

    # Synonymes : dans la langue du terme.
    synonymes = ouvrir("synonymes", "Synonymes", "2")
    assert textes(synonymes.corps) == ["convention", "accord"]
    assert textes(synonymes.pied) == ["Ces termes n’ont pas encore d’entrée dans le glossaire"]


def test_un_second_clic_la_croix_ou_le_centre_referment_l_information(details):
    roue = details.roue
    changements = []
    details.detail_change.connect(changements.append)
    roue.boutons["definition"].click()
    roue.boutons["definition"].click()  # un second clic sur le même cercle
    assert details.detail == "" and details.pile.currentWidget() is details.invite
    assert not roue.boutons["definition"].isChecked()
    # La croix, à droite du titre de l'information.
    roue.boutons["ressources"].click()
    assert details.bouton_fermer.isVisible() and details.bouton_fermer.toolTip() == "Refermer cette information"
    details.bouton_fermer.click()
    assert details.detail == "" and not details.bouton_fermer.isVisible()
    # Le centre de la roue : il referme l'information affichée, et ne fait rien quand il n'y en a pas.
    roue.boutons["synonymes"].click()
    assert roue.info_du_centre() == "Refermer l’information affichée"
    QTest.mouseClick(roue, Qt.MouseButton.LeftButton, pos=roue.centre.toPoint())
    assert details.detail == "" and roue.info_du_centre() == ""
    QTest.mouseClick(roue, Qt.MouseButton.LeftButton, pos=roue.centre.toPoint())
    assert details.detail == ""
    assert changements == ["definition", "", "ressources", "", "synonymes", ""]


def test_le_cercle_et_son_nom_repondent_au_clic(details):
    bouton = details.roue.boutons["ressources"]
    QTest.mouseClick(bouton, Qt.MouseButton.LeftButton, pos=bouton.centre.toPoint())
    assert details.detail == "ressources"
    # Le nom répond comme le cercle : ce second clic referme l'information.
    QTest.mouseClick(bouton, Qt.MouseButton.LeftButton, pos=bouton.cadre_du_libelle.center().toPoint())
    assert details.detail == ""
    # Le coin du rectangle du bouton n'est ni le cercle ni son nom : il ne répond pas.
    assert not bouton.hitButton(QPoint(1, 1))
    QTest.mouseClick(bouton, Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
    assert details.detail == ""


def test_le_clavier_atteint_les_cercles(details):
    assert all(bouton.focusPolicy() == Qt.FocusPolicy.TabFocus for bouton in details.roue.boutons.values())
    bouton = details.roue.boutons["contexte"]
    bouton.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(bouton, Qt.Key.Key_Space)
    assert details.detail == "contexte"
    QTest.keyClick(bouton, Qt.Key.Key_Space)
    assert details.detail == ""


def test_l_information_choisie_reste_affichee_d_un_terme_a_l_autre(fenetre, details):
    page = fenetre.page

    def definition_affichee() -> bool:
        return (details.detail == "definition" and details.roue.boutons["definition"].isChecked()
                and page.entree.definition_fr in textes(details.colonne_definition.corps))

    details.roue.boutons["definition"].click()
    # Une autre recherche, les flèches de la fiche, l'onglet d'un autre sens : la définition reste ouverte.
    page.rechercher("loi")
    assert page.entree.terme_fr == "loi" and definition_affichee()
    page.fiche.colonne_terme.bouton_suivant.click()
    assert page.entree.terme_fr != "loi" and definition_affichee()
    page.rechercher("droit")
    page.fiche.onglets.onglets[1].click()
    assert page.entree.terme_ar == "قانون" and definition_affichee()
    # Sans fiche (recherche effacée), rien n'est affiché ; le choix revient avec la fiche suivante.
    page.barre.effacer.click()
    assert page.entree is None and details.detail == ""
    page.rechercher("contrat")
    assert definition_affichee()
    # Refermée par l'utilisateur, l'information reste fermée.
    details.bouton_fermer.click()
    page.rechercher("loi")
    assert details.detail == "" and details.pile.currentWidget() is details.invite


def test_un_cercle_reste_gris_quand_le_glossaire_n_a_rien(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat de travail")
    application.processEvents()
    details, roue = page.details, page.details.roue
    # Dans le glossaire d'essai, ce terme n'a ni exemple, ni expression, ni terme associé, ni synonyme.
    assert details.renseignes() == ["definition", "ressources"]
    assert roue.etats() == {"definition": True, "contexte": False, "ressources": True, "expressions": False,
                            "associes": False, "synonymes": False}
    assert roue.allumage.allumees() == [True, False, True, False, False, False]
    # L'invitation ne nomme que ce que le glossaire renseigne.
    assert details.invite.texte.text() == "Cliquez sur un cercle coloré : définition, ressources."
    gris, colore = roue.boutons["contexte"], roue.boutons["ressources"]
    assert (gris.disponible, gris.nombre) == (False, 0) and (colore.disponible, colore.nombre) == (True, 3)
    assert gris.toolTip() == "<qt>Aucune phrase du glossaire n’emploie ce terme</qt>"
    assert gris.accessibleDescription() == "Aucune phrase du glossaire n’emploie ce terme"
    # Sur l'image : le cercle renseigné a la couleur de son information, l'autre n'en a pas un point.
    assert colore.couleur().name().upper() == PAR_CLE["ressources"].couleur
    assert gris.couleur().name().upper() == theme.DETAIL_ETEINT
    assert points_de_couleur(colore, PAR_CLE["ressources"].couleur) > 100
    assert points_de_couleur(gris, PAR_CLE["contexte"].couleur) == 0
    # Un cercle gris s'ouvre quand même : sa page dit ce qui manque.
    gris.click()
    assert details.detail == "contexte" and not details.nombre.isVisible()
    assert textes(details.colonne_contexte.corps) == [
        "Aucun exemple pour ce terme", "Aucune phrase du glossaire n’emploie encore ce terme."]


def test_le_cercle_des_autres_entrees_change_de_nom(fenetre, application):
    page = fenetre.page
    details = page.details
    bouton = details.roue.boutons["expressions"]
    # Le terme saisi a son entrée, et les autres résultats le contiennent : « Expressions ».
    page.rechercher("contrat")
    assert bouton.libelle == "Expressions"
    assert details.colonne_expressions.titre == "Expressions avec « contrat »"
    # D'autres résultats ne contiennent pas le terme (un terme de même équivalent, par exemple) : « Termes proches ».
    page.rechercher("usage")
    assert page.barre.texte_du_resume() == "1 terme · 1 résultat proche"
    assert bouton.libelle in ("Termes proches", "Proches")
    assert details.colonne_expressions.titre == "Expressions et termes proches"
    assert "termes proches" in details.invite.texte.text() and details.detail == ""
    # Le terme saisi n'a pas d'entrée : la première trouvée est affichée, et la liste des « Autres résultats »
    # s'ouvre d'office.
    page.rechercher("contra")
    assert page.entree.terme_fr == "contrat" and page.barre.texte_du_resume() == "5 résultats"
    assert bouton.libelle in ("Autres résultats", "Résultats")
    assert details.detail == "expressions" and details.nombre.text() == "4"
    assert details.titre_du_detail.texte_complet() == "Autres résultats pour « contra »"
    assert "contrat" not in [entree.terme_fr for entree in details.colonne_expressions.entrees()]
    # Le nom d'origine revient avec une recherche exacte.
    details.bouton_fermer.click()
    page.rechercher("contrat")
    assert bouton.libelle == "Expressions" and details.detail == ""


def test_le_menu_d_un_terme_arabe(fenetre, application):
    page = fenetre.page
    page.rechercher("العقد")
    application.processEvents()
    details, roue = page.details, page.details.roue
    assert page.source == AR and (roue.terme, roue.langue) == ("عقد", AR)
    assert roue.lignes_du_centre()[0] == ["عقد"]
    # Les noms des cercles restent en français, la langue de l'interface. Les contenus suivent le sens de traduction.
    assert roue.libelles_affiches() == NOMS
    details.choisir("definition")
    contenu = textes(details.colonne_definition.corps)
    assert contenu[0] == "العربية" and contenu[1].startswith("اتفاق يلتزم بموجبه") and contenu[2] == "FRANÇAIS"
    details.choisir("synonymes")
    assert textes(details.colonne_synonymes.corps) == ["اتفاق"]
    assert details.colonne_synonymes.corps.layoutDirection() == Qt.LayoutDirection.RightToLeft
    details.choisir("expressions")
    assert details.titre_du_detail.texte_complet() == "Expressions avec « عقد »"
    assert details.etats()["expressions"] == (True, 5)


# ------------------------------------------------------------------ disposition de la roue
def test_les_cercles_sont_ranges_dans_le_sens_des_aiguilles_d_une_montre():
    directions = RoueDesDetails.directions()
    assert len(directions) == 6
    angles = [math.degrees(math.atan2(dx, -dy)) % 360 for dx, dy in directions]  # 0° : en haut ; 90° : à droite
    # Le premier cercle est en haut à gauche ; les suivants tournent à droite, de 60° en 60°.
    assert angles == pytest.approx([330, 30, 90, 150, 210, 270])
    # Trois cercles à gauche, trois à droite : aucun au-dessus ni au-dessous du terme.
    assert [dx < 0 for dx, _ in directions] == [True, False, False, False, True, True]
    assert all(abs(dx) >= 0.49 for dx, _ in directions)


@pytest.mark.parametrize("taille", TAILLES)
def test_les_cercles_entourent_le_terme_sans_se_recouvrir(fenetre, details, application, taille):
    fenetre.resize(*taille)
    application.processEvents()
    roue = details.roue
    centre, echelle = roue.centre, roue.echelle
    assert RoueDesDetails.ECHELLE_MINIMALE <= echelle <= RoueDesDetails.ECHELLE_MAXIMALE
    places = cercles(roue)
    cadres = {cle: roue.cadre_du_libelle(cle) for cle in CLES}
    assert [cle for cle, (x, _, _) in places.items() if x < centre.x()] == ["definition", "associes", "synonymes"]
    assert [cle for cle, (x, _, _) in places.items() if x > centre.x()] == ["contexte", "ressources", "expressions"]
    for cle, (x, y, rayon) in places.items():
        # Tous à la même distance du terme, hors du disque central.
        distance = math.hypot(x - centre.x(), y - centre.y())
        assert distance == pytest.approx(RoueDesDetails.RAYON_DE_L_ORBITE * echelle, abs=1.0), cle
        assert distance - rayon > RoueDesDetails.RAYON_DU_CENTRE * echelle, cle
        # Le cercle et son nom sont dans la roue.
        cadre = cadres[cle]
        assert rayon <= x <= roue.width() - rayon and rayon <= y <= roue.height() - rayon, cle
        assert cadre.left() >= 0 and cadre.right() <= roue.width(), cle
        assert cadre.top() >= 0 and cadre.bottom() <= roue.height(), cle
        # Le nom est écrit à la hauteur du cercle, du côté opposé au terme.
        assert cadre.top() < y < cadre.bottom(), cle
        assert cadre.right() < x - rayon if x < centre.x() else cadre.left() > x + rayon, cle
    # Aucun cercle n'en recouvre un autre.
    for rang, premiere in enumerate(CLES):
        for seconde in CLES[rang + 1:]:
            (x1, y1, r1), (x2, y2, r2) = places[premiere], places[seconde]
            assert math.hypot(x1 - x2, y1 - y2) > r1 + r2, (premiere, seconde)
            assert not cadres[premiere].intersects(cadres[seconde]), (premiere, seconde)
    # Aucun nom ne recouvre un cercle, ni le disque central.
    disques = [QRectF(x - rayon, y - rayon, 2 * rayon, 2 * rayon) for x, y, rayon in places.values()]
    rayon_du_centre = RoueDesDetails.RAYON_DU_CENTRE * echelle
    disques.append(QRectF(centre.x() - rayon_du_centre, centre.y() - rayon_du_centre,
                          2 * rayon_du_centre, 2 * rayon_du_centre))
    for cle, cadre in cadres.items():
        assert not any(cadre.intersects(disque) for disque in disques), cle
    # Le titre « Plus de détails » est posé sur le coin de la roue : ni cercle ni nom ne passe dessous.
    assert details.titre.parentWidget() is roue.parentWidget()
    titre = QRectF(details.titre.geometry()).translated(-roue.x(), -roue.y())
    assert titre.width() >= details.titre.fontMetrics().horizontalAdvance("Plus de détails")  # écrit en entier
    assert not any(zone.intersects(titre) for zone in (*disques, *cadres.values()))


@pytest.mark.parametrize("taille", TAILLES)
def test_la_roue_est_a_gauche_l_information_a_droite(fenetre, details, application, taille):
    fenetre.resize(*taille)
    details.roue.boutons["definition"].click()
    application.processEvents()
    roue, droite = details.roue, details.pile
    # La roue occupe toute la hauteur du panneau ; sa largeur est une part de celle du panneau, entre deux limites.
    assert roue.height() == details.height()
    menu = droite.x()
    assert PanneauDetails.LARGEUR_MINIMALE_DU_MENU <= menu <= PanneauDetails.LARGEUR_MAXIMALE_DU_MENU
    assert roue.mapTo(details, QPoint(0, 0)).x() + roue.width() <= menu
    # L'information prend le reste : plus de place que la roue.
    assert droite.x() + droite.width() == details.width() and droite.width() > menu
    assert details.colonne_definition.corps.isVisible()
    assert details.colonne_definition.corps.mapTo(details, QPoint(0, 0)).x() >= menu
    # Jusque dans la plus petite fenêtre, la roue reste assez large pour écrire un terme court en son centre.
    assert roue.lignes_du_centre()[0] == ["contrat"]


def test_les_noms_des_cercles_raccourcissent_dans_une_roue_etroite(application):
    roue = RoueDesDetails()
    roue.definir(dict.fromkeys(CLES, (True, 3)), "contrat", FR)
    roue.resize(700, 330)
    roue.show()
    application.processEvents()
    assert roue.libelles_affiches() == NOMS
    grande = roue.echelle
    roue.resize(roue.minimumSizeHint())
    application.processEvents()
    assert roue.libelles_affiches() == NOMS_COURTS and roue.echelle < grande
    # Les six noms sont longs, ou les six sont courts : aucun n'est coupé par « … ».
    for largeur in range(260, 720, 20):
        roue.resize(largeur, 240)
        application.processEvents()
        assert roue.libelles_affiches() in (NOMS, NOMS_COURTS), largeur
    # Un nom donné par l'écran (« Autres résultats ») suit la même règle.
    roue.definir(dict.fromkeys(CLES, (True, 3)), "contrat", FR, {"expressions": ("Autres résultats", "Résultats")})
    roue.resize(700, 330)
    application.processEvents()
    assert roue.boutons["expressions"].libelle == "Autres résultats"
    roue.resize(roue.minimumSizeHint())
    application.processEvents()
    assert roue.boutons["expressions"].libelle == "Résultats"
    roue.close()
    roue.deleteLater()


def test_le_terme_est_ecrit_au_centre_de_la_roue(application):
    roue = RoueDesDetails()
    etats = dict.fromkeys(CLES, (True, 1))
    roue.resize(700, 330)
    roue.show()
    application.processEvents()
    roue.definir(etats, "contrat", FR)
    lignes, taille = roue.lignes_du_centre()
    assert lignes == ["contrat"] and roue.info_du_centre() == ""
    # L'arabe est écrit un peu plus grand que le français.
    roue.definir(etats, "عقد", AR)
    lignes, taille_arabe = roue.lignes_du_centre()
    assert lignes == ["عقد"] and taille_arabe > taille
    # Un terme de plusieurs mots passe sur plusieurs lignes, en caractères plus petits s'il le faut.
    roue.definir(etats, "contrat de vente", FR)
    lignes, petite = roue.lignes_du_centre()
    assert " ".join(lignes) == "contrat de vente" and 1 <= len(lignes) <= 3 and petite <= taille
    # Un terme qui ne tient pas n'est pas abrégé : le centre porte le mot « TERME », l'infobulle donne le terme.
    long = "responsabilité contractuelle du fait d’autrui"
    roue.definir(etats, long, FR)
    assert roue.lignes_du_centre()[0] == [] and roue.info_du_centre() == f"<qt>{long}</qt>"
    assert RoueDesDetails.REPERE_DU_CENTRE == "TERME"
    # Dans une petite roue, un terme court finit lui aussi par ne plus tenir.
    roue.definir(etats, "consentement", FR)
    assert roue.lignes_du_centre()[0] == ["consentement"]
    roue.resize(roue.minimumSizeHint())
    application.processEvents()
    assert roue.lignes_du_centre()[0] == [] and roue.info_du_centre() == "<qt>consentement</qt>"
    # Sans terme (aucune fiche affichée), le centre reste vide.
    roue.definir(dict.fromkeys(CLES, (False, 0)), "", FR)
    assert not "".join(roue.lignes_du_centre()[0]) and roue.info_du_centre() == ""
    roue.close()
    roue.deleteLater()
