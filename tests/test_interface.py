"""Interface de bureau : fenêtre, barre de menus, écran « Terme », fiche (tests exécutés sans écran).

La fiche d'un terme a deux colonnes : le terme et son équivalent. Le reste de l'entrée (définition,
phrases d'exemple, ressources…) est dans le menu « Plus de détails », sous la fiche : ce menu est
testé dans ``test_interface_details.py``. La barre latérale, les écrans « Paramètres »,
« Description de la plateforme » et « Centre d'aide », l'allumage et l'écran de démarrage sont
testés dans ``test_interface_ecrans.py``.

La largeur d'un texte dépend de la police du système. Les tests ne comparent donc pas les textes
abrégés ou raccourcis à une valeur exacte : ils vérifient leur forme (une des formes prévues,
abrégée ou non), et les contenus complets.
"""

import re
from html import unescape

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QGuiApplication, QTextLayout
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QPushButton

from traducteur.interface import boites, theme
from traducteur.interface import fenetre as module_fenetre
from traducteur.interface.boites import BoiteMessage
from traducteur.interface.composants import (
    ESPACE_INVISIBLE,
    MARQUE_LTR,
    MARQUE_RTL,
    EtiquetteCourte,
    TermeAjuste,
    message_en_francais,
)
from traducteur.interface.details import CLES
from traducteur.interface.fenetre import MODE_PARAMETRES, MODE_TERME, MODE_TEXTE, BarreEtat, FenetrePrincipale
from traducteur.interface.fiche import LARGEUR_MINIMALE, LienCourt, LigneDeProvenance
from traducteur.interface.navigation import LARGEUR as LARGEUR_DU_RAIL
from traducteur.langues import AR, FR

_BALISE = re.compile(r"<[^>]+>")
_FIN_DE_PARAGRAPHE = re.compile(r"</p>\s*<p[^>]*>|<br\s*/?>")


def textes(widget) -> list[str]:
    """Textes des étiquettes d'un widget : sans balises, sans marque de direction, non abrégés."""
    resultat = []
    for label in widget.findChildren(QLabel):
        texte = label.texte_complet() if isinstance(label, EtiquetteCourte) else label.text()
        if label.textFormat() == Qt.TextFormat.RichText:
            texte = unescape(_BALISE.sub("", _FIN_DE_PARAGRAPHE.sub("\n", texte)))
        texte = texte.replace(MARQUE_RTL, "").replace(ESPACE_INVISIBLE, "").strip()
        if texte:
            resultat.append(texte)
    return resultat


def points_de_couleur(widget, couleur: str, tolerance: int = 40) -> int:
    """Nombre de points de l'image d'un widget dont la couleur est proche de ``couleur``."""
    image = widget.grab().toImage()
    cible = QColor(couleur)
    total = 0
    for x in range(image.width()):
        for y in range(image.height()):
            point = image.pixelColor(x, y)
            if (point.alpha() > 200 and abs(point.red() - cible.red()) <= tolerance
                    and abs(point.green() - cible.green()) <= tolerance
                    and abs(point.blue() - cible.blue()) <= tolerance):
                total += 1
    return total


def puces(widget) -> list[str]:
    """Libellés des puces cliquables d'un widget."""
    return [bouton.text() for bouton in widget.findChildren(QPushButton)
            if bouton.property("classe") in ("puce", "puceExemple")]


def grand_terme(colonne) -> str:
    """Le terme affiché en grand dans une colonne de la fiche."""
    return colonne.terme.terme


def onglets(page) -> list[str]:
    """Les onglets des sens, en haut de la fiche."""
    return [onglet.text() for onglet in page.fiche.onglets.onglets]


def ecrire(chemin, texte):
    chemin.write_text(texte, encoding="utf-8")
    return chemin


# ------------------------------------------------------------------ démarrage
def test_la_fenetre_s_ouvre_avec_le_glossaire_d_exemple(fenetre, avertissements):
    """Le glossaire est chargé à l'ouverture, sans aucune commande."""
    assert avertissements == []
    assert fenetre.windowTitle() == "Traducteur juridique"
    assert (fenetre.minimumWidth(), fenetre.minimumHeight()) == (900, 600)
    assert fenetre.glossaire.nom == "glossaire_essai.csv" and len(fenetre.glossaire) == 40
    assert fenetre.glossaire_fourni()
    # Barre d'outils : le sens de traduction, puis la barre de recherche de l'écran « Terme ».
    assert fenetre.mode == MODE_TERME and fenetre.rail.boutons[MODE_TERME].isChecked()
    assert fenetre.cadre_sens.isVisible()
    assert fenetre.sens.source.text() == "Français" and fenetre.sens.cible.text() == "العربية"
    assert fenetre.outils.currentWidget() is fenetre.page.barre
    assert fenetre.page.champ.hasFocus()
    # La barre d'état n'affiche que des messages : rien à signaler à l'ouverture.
    assert fenetre.barre_etat.texte() == ""


def test_la_fenetre_n_a_pas_de_libelle_technique(fenetre):
    """Ni version, ni nom du glossaire, ni encodage, ni bouton de chargement dans la fenêtre de travail."""
    for page in (fenetre.page, fenetre.page_texte):
        visibles = textes(page) + [bouton.text() for bouton in page.findChildren(QPushButton)]
        for texte in visibles:
            assert "UTF-8" not in texte and "Version" not in texte and "version" not in texte, texte
            assert "glossaire_essai" not in texte and "Ouvrir un glossaire" not in texte, texte
    for nom in ("indicateur", "boutons_mode", "action_exemple"):
        assert not hasattr(fenetre, nom)
    assert not hasattr(fenetre.barre_etat, "version") and not hasattr(fenetre.barre_etat, "sens")


def test_le_style_de_l_application(application, fenetre):
    """« Fusion » et une palette claire : le même rendu sur tous les systèmes, même en mode sombre."""
    assert application.style().objectName().lower() == "fusion"
    assert fenetre.palette().window().color().name().upper() == theme.FOND
    assert fenetre.palette().windowText().color().name().upper() == theme.TEXTE


def test_ecran_d_accueil(fenetre):
    page = fenetre.page
    accueil = page.accueil
    assert page.entree is None and page.pile.currentWidget() is accueil
    assert accueil.titre.text() == "Recherchez un terme juridique"
    assert "Saisissez un terme en français ou en arabe, puis appuyez sur Entrée." in textes(accueil)[1]
    # L'accueil ne décrit pas la fiche : il invite à chercher un terme, sans autre explication.
    assert not {"Définition", "Équivalent", "Contextualisation", "Ressources"} & set(textes(accueil))
    # Cinq termes du glossaire en exemple, puis les raccourcis.
    assert accueil.etiquette_puces.text() == "PAR EXEMPLE"
    exemples = [bouton.text() for bouton in accueil.puces]
    assert exemples == puces(accueil)
    assert len(exemples) == 5 and exemples[0] == "contrat" and len(set(exemples)) == 5
    assert accueil.raccourcis.isVisible() and not accueil.conseil.isVisible()
    assert not accueil.bouton_glossaire.isVisible()
    assert len(accueil.raccourcis.elements) == 4 and accueil.raccourcis.elements[0].isVisible()
    assert page.champ.placeholderText() == "Saisir un terme juridique, en français ou en arabe…"
    assert page.barre.texte_du_resume() == "" and not page.barre.effacer.isVisible()


def test_un_exemple_de_l_accueil_ouvre_sa_fiche(fenetre):
    page = fenetre.page
    page.accueil.puces[1].click()
    assert page.entree.terme_fr == "loi" and page.champ.text() == "loi"
    assert page.pile.currentWidget() is page.vue_fiche


# ------------------------------------------------------------------ recherche
def test_recherche_d_un_terme_francais(fenetre, application):
    """La fiche a deux colonnes : le terme et son équivalent. Le reste est dans le menu « Plus de détails »."""
    page = fenetre.page
    page.rechercher("contrat")
    application.processEvents()
    fiche, details = page.fiche, page.details
    assert page.entree.terme_fr == "contrat"
    assert page.pile.currentWidget() is page.vue_fiche
    assert page.barre.texte_du_resume() == "1 terme · 5 expressions"
    assert page.barre.resume.isVisible() and page.barre.effacer.isVisible()
    assert fenetre.barre_etat.texte() == "« contrat » : 6 entrées trouvées dans le glossaire."
    assert fiche.colonnes == [fiche.colonne_terme, fiche.colonne_equivalent]
    assert not fiche.onglets.isVisible()  # un seul sens : pas d'onglets

    # À gauche, le terme : sa catégorie et son domaine. Au pied : son rang dans le glossaire, les entrées voisines.
    assert grand_terme(fiche.colonne_terme) == "contrat"
    assert textes(fiche.colonne_terme.corps) == [
        "FRANÇAIS · SOURCE", "contrat", "nom masculin · pl. contrats", "Droit civil › Obligations"]
    assert fiche.colonne_terme.rang.texte_complet() == "Entrée 1 sur 40"
    assert not fiche.colonne_terme.bouton_precedent.isEnabled() and fiche.colonne_terme.bouton_suivant.isEnabled()

    # À droite, l'équivalent : sa grammaire, ses autres équivalents. Au pied : le lien qui le copie.
    assert grand_terme(fiche.colonne_equivalent) == "عقد"
    assert textes(fiche.colonne_equivalent.corps) == [
        "ARABE · CIBLE", "عقد", "اسم مذكر، ج. عقود", "AUTRE ÉQUIVALENT", "اتفاق"]
    assert fiche.colonne_equivalent.mention is None  # rien à vérifier : la définition de « contrat » cite sa source
    assert textes(fiche.colonne_equivalent.pied) == []
    assert fiche.colonne_equivalent.bouton_copier.text() == "Copier l’équivalent"

    # Les deux colonnes se partagent la largeur de la fiche ; le terme et son équivalent sont à la même hauteur.
    terme, equivalent = fiche.colonne_terme.terme, fiche.colonne_equivalent.terme
    assert abs(fiche.colonne_terme.corps.width() - fiche.colonne_equivalent.corps.width()) <= 1
    assert fiche.colonne_terme.corps.width() + fiche.colonne_equivalent.corps.width() == fiche.width()
    assert terme.mapTo(fiche, QPoint(0, 0)).x() < equivalent.mapTo(fiche, QPoint(0, 0)).x()
    assert abs(terme.mapTo(fiche, terme.rect().center()).y()
               - equivalent.mapTo(fiche, equivalent.rect().center()).y()) <= 1

    # Ni définition, ni phrase d'exemple, ni référence dans la fiche : le menu les donne à la demande.
    contenu = textes(fiche)
    assert not any(texte.startswith("Convention par laquelle") for texte in contenu)
    assert "Le contrat fait la loi des parties." not in contenu and "Code civil, art. 54" not in contenu
    assert details.isVisible() and details.titre.text() == "Plus de détails"
    assert fiche.geometry().bottom() < details.geometry().top()  # le menu est sous la fiche
    # Aucune information n'est ouverte d'office : une invitation nomme celles que le glossaire renseigne.
    assert details.detail == "" and details.pile.currentWidget() is details.invite
    assert details.renseignes() == list(CLES)


def test_la_saisie_au_clavier_lance_la_recherche(fenetre, application):
    page = fenetre.page
    page.champ.setFocus()
    QTest.keyClicks(page.champ, "bonne foi")
    QTest.keyClick(page.champ, Qt.Key.Key_Return)
    application.processEvents()
    assert page.entree.terme_fr == "bonne foi"
    assert grand_terme(page.fiche.colonne_equivalent) == "حسن النية"


def test_le_bouton_rechercher(fenetre):
    page = fenetre.page
    page.champ.setText("  Équité ")
    page.bouton.click()
    assert page.entree.terme_fr == "équité"
    assert page.champ.text() == "Équité"


def test_choisir_une_autre_entree_trouvee(fenetre):
    page = fenetre.page
    details = page.details
    page.rechercher("contrat")
    details.roue.boutons["expressions"].click()
    details.colonne_expressions.grille.cellules[1].click()
    assert page.entree.terme_fr == "contrat de vente"
    assert grand_terme(page.fiche.colonne_equivalent) == "عقد البيع"
    assert page.champ.text() == "contrat"  # la recherche saisie est conservée
    # La liste reste ouverte : elle présente alors les autres résultats de cette recherche, « contrat » compris.
    assert details.detail == "expressions"
    assert details.titre_du_detail.texte_complet() == "Autres résultats pour « contrat »"
    assert [entree.terme_fr for entree in details.colonne_expressions.entrees()] == [
        "contrat", "contrat de bail", "contrat de travail", "exécution du contrat", "conclusion du contrat"]


def test_un_terme_arabe_inverse_le_sens(fenetre):
    page = fenetre.page
    page.rechercher("العقد")
    assert page.source == AR
    assert page.entree.terme_fr == "contrat"
    assert grand_terme(page.fiche.colonne_terme) == "عقد"
    assert grand_terme(page.fiche.colonne_equivalent) == "contrat"
    assert textes(page.fiche.colonne_terme.corps)[0] == "ARABE · SOURCE"
    assert textes(page.fiche.colonne_equivalent.corps)[0] == "FRANÇAIS · CIBLE"
    # Le terme et son équivalent sont centrés dans leur colonne ; le terme arabe s'écrit de droite à gauche.
    assert page.fiche.colonne_terme.terme.alignment() == Qt.AlignmentFlag.AlignCenter
    assert page.fiche.colonne_equivalent.terme.alignment() == Qt.AlignmentFlag.AlignCenter
    assert page.fiche.colonne_terme.terme.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert page.fiche.colonne_equivalent.terme.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert fenetre.sens.source.text() == "العربية" and fenetre.sens.cible.text() == "Français"
    assert page.champ.placeholderText() == "أدخل مصطلحا قانونيا، بالعربية أو بالفرنسية..."
    assert page.champ.layoutDirection() == Qt.LayoutDirection.RightToLeft
    # Un message passager l'annonce ; l'état de l'écran reste le résultat de la recherche.
    assert fenetre.barre_etat.texte() == "Terme saisi en arabe : le sens de traduction a été inversé."
    assert fenetre.barre_etat.etat() == "« العقد » : 6 entrées trouvées dans le glossaire."


def test_un_message_qui_cite_un_terme_arabe_se_lit_de_gauche_a_droite(fenetre, application):
    """La barre d'état écrit en français : un terme arabe ne doit ni inverser la ligne, ni déplacer un nombre."""

    def abscisses(texte: str) -> list[float]:
        """Où Qt écrit chaque partie du message, de la première à la dernière."""
        disposition = QTextLayout(texte, barre.message.font())
        disposition.beginLayout()
        ligne = disposition.createLine()
        ligne.setLineWidth(100_000)
        disposition.endLayout()
        return [ligne.cursorToX(texte.index(partie))[0] for partie in ("«", "العقد", "»", ":", "6", "entrées", "dans")]

    barre = fenetre.barre_etat
    fenetre.page.rechercher("العقد")
    barre._oublier_le_message()  # le message passager « Terme saisi en arabe… » laisse la place à l'état
    message = "« العقد » : 6 entrées trouvées dans le glossaire."
    assert barre.texte() == barre.etat() == message
    # Des marques invisibles gardent au message son sens de lecture : ses parties se suivent de gauche à droite.
    affiche = barre.message.text()
    assert affiche == message_en_francais(message)
    assert affiche == f"{MARQUE_LTR}« \u2067العقد\u2069 » : 6 entrées trouvées dans le glossaire."
    positions = abscisses(affiche)
    assert positions == sorted(positions) and len(set(positions)) == len(positions)
    # Sans elles, Qt écrit la ligne de droite à gauche. Avec la seule marque de début de ligne, le terme arabe
    # entraîne le nombre qui le suit : « 6 » passerait devant lui.
    positions = abscisses(message)
    assert positions == sorted(positions, reverse=True)
    positions = abscisses(MARQUE_LTR + message)
    assert positions != sorted(positions) and positions[4] < positions[2]
    # À l'écran : le message part du bord gauche de la barre, rien n'est écrit dans sa moitié droite.
    application.processEvents()
    image = barre.grab().toImage()
    fond = image.pixelColor(image.width() - 3, image.height() // 2)
    assert all(image.pixelColor(x, y) == fond
               for x in range(image.width() // 2, image.width() - 3) for y in range(4, image.height() - 2))
    # Un message sans terme arabe ne reçoit que la marque de début ; une barre vide reste vide.
    assert message_en_francais("Glossaire chargé : g.csv.") == MARQUE_LTR + "Glossaire chargé : g.csv."
    assert message_en_francais("Copié : عقد البيع") == f"{MARQUE_LTR}Copié : \u2067عقد البيع\u2069"
    fenetre.definir_mode(MODE_TEXTE)
    assert barre.texte() == "" and barre.message.text() == "" and message_en_francais("") == ""


def test_inverser_le_sens_garde_l_entree_affichee(fenetre):
    page = fenetre.page
    page.rechercher("usage")
    assert page.entree.terme_fr == "usage"
    fenetre.bouton_inverser.click()
    assert page.source == AR
    assert page.entree.terme_fr == "usage"  # et non « coutume », qui a le même équivalent arabe
    assert page.champ.text() == "عرف"
    # « عرف » a deux sens dans le glossaire : un onglet chacun, celui de « usage » est choisi.
    assert onglets(page) == ["Sens 1 : coutume", "Sens 2 : usage"]
    assert [onglet.isChecked() for onglet in page.fiche.onglets.onglets] == [False, True]
    fenetre.action_inverser.trigger()  # menu Affichage → Inverser le sens de traduction (Ctrl+I)
    assert page.source == FR and page.entree.terme_fr == "usage" and page.champ.text() == "usage"
    assert onglets(page) == []


def test_inverser_le_sens_sans_entree_affichee(fenetre):
    page = fenetre.page
    page.champ.setText("bail")  # texte saisi, pas encore recherché : il est conservé
    page.inverser()
    assert page.source == AR and page.entree is None
    assert page.accueil.puces[0].text() == "عقد"  # exemples proposés dans la nouvelle langue source
    assert page.champ.text() == "bail"

    page.rechercher("xyz")  # recherche sans résultat : elle est effacée quand on inverse le sens
    assert page.source == FR and page.entree is None
    page.inverser()
    assert page.source == AR and page.champ.text() == "" and page.requete == ""
    assert len(page.accueil.puces) == 5


def test_un_terme_qui_a_plusieurs_sens(fenetre, application):
    page = fenetre.page
    page.rechercher("droit")
    assert page.barre.texte_du_resume() == "2 sens"
    bande = page.fiche.onglets
    assert bande.isVisible()
    assert onglets(page) == ["Sens 1 : حق", "Sens 2 : قانون"]
    assert [onglet.isChecked() for onglet in bande.onglets] == [True, False]
    assert bande.avertissement.texte_complet() == (
        "« droit » a 2 sens dans le glossaire : choisissez celui qui convient au texte.")
    assert grand_terme(page.fiche.colonne_equivalent) == "حق"
    assert page.details.etats()["expressions"] == (False, 0)  # aucune autre entrée trouvée

    bande.onglets[1].click()
    assert page.entree.terme_ar == "قانون"
    assert grand_terme(page.fiche.colonne_equivalent) == "قانون"
    assert [onglet.isChecked() for onglet in page.fiche.onglets.onglets] == [False, True]
    assert page.champ.text() == "droit"

    # Les onglets sont au-dessus des deux colonnes. Le signe orange précède l'avertissement, écrit à droite :
    # dans une fenêtre étroite, où le texte raccourcit, il ne recouvre jamais un onglet.
    for taille in ((1440, 860), (1080, 620), (900, 600)):
        fenetre.resize(*taille)
        application.processEvents()
        bande = page.fiche.onglets
        assert bande.geometry().bottom() < page.fiche.defilement.geometry().top(), taille
        assert bande.avertissement.text() in (
            "« droit » a 2 sens dans le glossaire : choisissez celui qui convient au texte.",
            "2 sens dans le glossaire : choisissez celui qui convient.", "2 sens", ""), taille
        if bande.avertissement.text():
            assert bande._signe.isVisible(), taille
            assert bande.onglets[-1].geometry().right() < bande._signe.geometry().left(), taille
            assert bande._signe.geometry().right() < bande.avertissement.geometry().right(), taille
        else:
            assert not bande._signe.isVisible(), taille


def test_aucun_resultat_propose_les_termes_proches(fenetre):
    page = fenetre.page
    accueil = page.accueil
    page.rechercher("contrat")
    page.rechercher("contart")
    assert page.entree is None and page.pile.currentWidget() is accueil
    assert accueil.titre.text() == "Aucune entrée pour « contart »"
    assert textes(accueil)[1] == (
        "Ce terme n’est pas dans le glossaire. Vérifiez son orthographe, ou ouvrez un terme proche.")
    assert accueil.etiquette_puces.text() == "TERME PROCHE" and puces(accueil) == ["contrat"]
    assert page.barre.texte_du_resume() == "Aucun résultat"
    assert fenetre.barre_etat.texte() == "Aucune entrée du glossaire ne correspond à « contart »."
    # Au pied du panneau, un conseil remplace les raccourcis : les fiches viennent du glossaire.
    assert accueil.conseil.isVisible() and not accueil.raccourcis.isVisible()
    assert accueil.conseil.texte_complet() == (
        "Les fiches viennent du glossaire. Le centre d’aide explique comment le compléter.")
    accueil.puces[0].click()
    assert page.entree.terme_fr == "contrat" and page.champ.text() == "contrat"

    # Ni entrée ni terme proche.
    page.rechercher("xyz")
    assert accueil.titre.text() == "Aucune entrée pour « xyz »"
    assert textes(accueil)[1] == "Ce terme n’est pas dans le glossaire. Vérifiez son orthographe."
    assert puces(accueil) == [] and not accueil.etiquette_puces.isVisible()


def test_effacer_la_recherche_revient_a_l_accueil(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    page.barre.effacer.click()
    assert page.entree is None and page.requete == "" and page.champ.text() == ""
    assert page.pile.currentWidget() is page.accueil and len(page.accueil.puces) == 5
    assert page.barre.texte_du_resume() == "" and not page.barre.effacer.isVisible()
    assert fenetre.barre_etat.texte() == ""


def test_les_puces_et_les_fleches_ouvrent_une_autre_entree(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    # Dans « Termes associés », un terme qui a son entrée dans le glossaire est une puce cliquable.
    page.details.choisir("associes")
    associes = page.details.colonne_associes
    assert puces(associes.corps) == ["contractant", "obligation"]
    associes.corps.findChild(QPushButton).click()  # puce « contractant »
    assert page.entree.terme_fr == "contractant" and page.champ.text() == "contractant"

    # Au pied de la colonne du terme : l'entrée précédente et l'entrée suivante du glossaire.
    numero = page.entree.numero
    page.fiche.colonne_terme.bouton_suivant.click()
    assert page.entree.numero == numero + 1 and page.champ.text() == page.entree.terme_fr
    page.fiche.colonne_terme.bouton_precedent.click()
    assert page.entree.terme_fr == "contractant"

    page.ouvrir(fenetre.glossaire.entrees[-1])
    assert page.fiche.colonne_terme.rang.texte_complet() == "Entrée 40 sur 40"
    assert not page.fiche.colonne_terme.bouton_suivant.isEnabled()


def test_entree_sans_definition_ni_exemple_ni_ressource(fenetre, tmp_path):
    """Un glossaire réduit aux deux colonnes de termes : la fiche est complète, le menu dit ce qui manque."""
    assert fenetre.charger_glossaire(ecrire(tmp_path / "deux_colonnes.csv", "terme_fr;terme_ar\ncapacité;أهلية\n"))
    page = fenetre.page
    page.rechercher("capacité")
    fiche, details = page.fiche, page.details
    assert textes(fiche.colonne_terme.corps) == ["FRANÇAIS · SOURCE", "capacité"]
    assert grand_terme(fiche.colonne_equivalent) == "أهلية"
    assert textes(fiche.colonne_equivalent.corps) == ["ARABE · CIBLE", "أهلية"]
    assert fiche.colonne_terme.rang.texte_complet() == "Entrée 1 sur 1"
    # Les six cercles du menu sont gris ; l'invitation dit que le glossaire ne donne que l'équivalent.
    assert details.renseignes() == [] and details.roue.etats() == dict.fromkeys(CLES, False)
    assert (details.invite.titre.text(), details.invite.texte.text()) == (
        "Le glossaire ne donne que l’équivalent de ce terme",
        "Il n’a pour lui ni définition, ni phrase d’exemple, ni référence.")
    # Un cercle gris s'ouvre quand même : son message dit ce qui manque, sans nom de colonne ni de fichier.
    attendus = {
        "definition": ["Aucune définition pour ce terme", "Le glossaire n’en donne pas encore."],
        "contexte": ["Aucun exemple pour ce terme", "Aucune phrase du glossaire n’emploie encore ce terme."],
        "ressources": ["Aucune ressource pour ce terme", "Le glossaire ne cite pas encore de référence."],
        "expressions": ["Aucune expression avec ce terme", "Aucune autre entrée du glossaire ne contient ce terme."],
        "associes": ["Aucun terme associé", "Le glossaire n’en cite pas pour ce terme."],
        "synonymes": ["Aucun synonyme pour ce terme", "Le glossaire n’en donne pas."],
    }
    assert list(attendus) == list(CLES)
    for cle, message in attendus.items():
        details.roue.boutons[cle].click()
        assert details.detail == cle and details.pile.currentWidget() is details.vue
        assert textes(details.colonnes[cle].corps) == message
        assert textes(details.colonnes[cle].pied) == [] and not details.nombre.isVisible()


def test_une_definition_sans_source_est_a_verifier(fenetre, tmp_path):
    fenetre.charger_glossaire(ecrire(tmp_path / "sources.csv", (
        "terme_fr;terme_ar;definition_fr;source_definition\n"
        "bail;إيجار;Contrat de location.;à vérifier (définition d’exemple)\n"
        "vente;بيع;Contrat de vente.;à vérifier\n"
        "prêt;قرض;Contrat de prêt.;\n")))
    page = fenetre.page
    page.rechercher("bail")
    definition = page.details.colonne_definition
    assert textes(definition.pied) == ["À vérifier", "· définition d’exemple"]
    assert textes(definition.corps)[-1] == "Pas de définition en arabe dans le glossaire."
    # La mention porte sur la définition : rien n'est signalé au pied de l'équivalent.
    assert page.fiche.colonne_equivalent.mention is None
    page.rechercher("vente")
    assert textes(definition.pied) == ["À vérifier"]
    # Sans source dans le glossaire, la définition est aussi à vérifier.
    page.rechercher("prêt")
    assert textes(definition.pied) == ["À vérifier", "· source non indiquée"]


def test_la_mention_peut_porter_sur_l_equivalent_et_sur_la_definition(fenetre, application, tmp_path):
    """« à vérifier (équivalent et définition d'exemple) » : chaque champ affiche sa part de la mention."""
    fenetre.charger_glossaire(ecrire(tmp_path / "definis.csv", (
        "terme_fr;terme_ar;categorie_fr;definition_fr;definition_ar;source_definition\n"
        "protégé;محمي;adjectif;Qui bénéficie d’une protection.;الذي يستفيد من حماية.;"
        "à vérifier (équivalent et définition d’exemple)\n")))
    page = fenetre.page
    page.rechercher("protégé")
    application.processEvents()
    colonne = page.fiche.colonne_equivalent
    assert colonne.mention is not None and colonne.mention.isVisible()
    assert textes(colonne.pied) == ["À vérifier", "· équivalent d’exemple"]
    definition = page.details.colonne_definition
    assert page.details.etats()["definition"] == (True, 0)
    page.details.roue.boutons["definition"].click()
    assert textes(definition.corps) == [
        "FRANÇAIS", "Qui bénéficie d’une protection.", "العربية", "الذي يستفيد من حماية."]
    assert textes(definition.pied) == ["À vérifier", "· définition d’exemple"]
    mention, = (label for label in definition.pied.findChildren(QLabel) if label.text() == "À vérifier")
    assert "Cette définition n’est pas reprise d’un texte officiel" in mention.toolTip()


def test_un_terme_sans_definition_peut_etre_a_verifier(fenetre, application, tmp_path):
    """Sans définition, la mention « à vérifier » de la colonne « source_definition » porte sur l'équivalent."""
    fenetre.charger_glossaire(ecrire(tmp_path / "seuls.csv", (
        "terme_fr;terme_ar;categorie_fr;source_definition\n"
        "protégé;محمي;adjectif;à vérifier (équivalent d’exemple)\n"
        "bail;إيجار;nom masculin;\n")))
    page = fenetre.page
    page.rechercher("protégé")
    application.processEvents()
    # La mention est écrite au pied de la colonne de l'équivalent : elle se voit sans ouvrir le menu.
    colonne = page.fiche.colonne_equivalent
    assert colonne.mention is not None and colonne.mention.isVisible()
    assert textes(colonne.pied) == ["À vérifier", "· équivalent d’exemple"]
    mention, = (label for label in colonne.pied.findChildren(QLabel) if label.text() == "À vérifier")
    assert "Cet équivalent n’est repris d’aucun texte officiel" in mention.toolTip()
    assert colonne.bouton_copier.isVisible()  # le lien « Copier l'équivalent » reste à côté d'elle
    # La définition, elle, manque : son cercle est gris, et sa page ne répète pas la mention.
    definition = page.details.colonne_definition
    assert page.details.etats()["definition"] == (False, 0)
    assert textes(definition.corps) == ["Aucune définition pour ce terme", "Le glossaire n’en donne pas encore."]
    assert textes(definition.pied) == []
    # Un terme sans définition et sans mention : le glossaire ne dit rien de lui, rien n'est signalé.
    page.rechercher("bail")
    assert page.fiche.colonne_equivalent.mention is None and textes(page.fiche.colonne_equivalent.pied) == []


def test_une_phrase_d_exemple_a_verifier_est_signalee(fenetre, application, tmp_path):
    """Contextualisation : la mention « À vérifier » précède une phrase que le glossaire ne reprend d'aucun texte."""
    fenetre.charger_glossaire(ecrire(tmp_path / "exemples.csv", (
        "terme_fr;terme_ar;definition_fr;definition_ar;source_definition;contexte_fr;contexte_ar;source_contexte\n"
        "bail;إيجار;;;;Le bail est écrit.;الإيجار مكتوب.;à vérifier (phrase d’exemple)\n"
        "loyer;بدل الإيجار;;;;Le loyer est payé chaque mois.;يدفع بدل الإيجار كل شهر.;Code civil, art. 498\n"
        "preneur;مستأجر;;;;Le preneur signe le bail.;يوقع المستأجر الإيجار.;À vérifier\n"
        "caution;كفيل;;;;La caution paie la dette.;يوفي الكفيل الدين.;\n")))
    page = fenetre.page
    page.details.choisir("contexte")  # la contextualisation s'ouvre par son cercle, et reste ouverte ensuite
    colonne = page.details.colonne_contexte

    # L'exemple de l'entrée, puis celui d'une autre entrée : tous deux sont à vérifier.
    page.rechercher("bail")
    application.processEvents()
    assert [(emploi.origine, emploi.a_verifier) for emploi in colonne.emplois] == [("propre", True), ("exemple", True)]
    assert textes(colonne.corps) == [
        "À vérifier", "· phrase d’exemple", "Le bail est écrit.", "الإيجار مكتوب.",
        "À vérifier", "Le preneur signe le bail.", "يوقع المستأجر الإيجار."]
    assert textes(colonne.pied) == ["1 exemple · 1 autre emploi dans le glossaire"]
    # La mention « à vérifier » n'est jamais écrite comme une source.
    assert not any("phrase d’exemple)" in texte for texte in textes(colonne.corps))
    explications = {label.toolTip() for label in colonne.corps.findChildren(QLabel) if label.text() == "À vérifier"}
    assert len(explications) == 1 and "vérifiez-la avant de la citer" in explications.pop()
    # La phrase de l'autre entrée garde son lien : il nomme l'entrée et l'ouvre.
    provenance, = colonne.corps.findChildren(LigneDeProvenance)
    assert provenance.a_verifier() and provenance.lien.texte_complet == "Exemple de « preneur »"
    assert provenance.icone.isVisible() and provenance.lien.width() >= provenance.lien.minimumSizeHint().width()
    provenance.lien.click()
    assert grand_terme(page.fiche.colonne_terme) == "preneur" and page.details.detail == "contexte"
    # Ici la mention est seule, sans précision : rien ne la suit.
    assert textes(colonne.corps)[:3] == ["À vérifier", "Le preneur signe le bail.", "يوقع المستأجر الإيجار."]

    # Une phrase qui cite sa source affiche cette source, sans mention.
    page.rechercher("loyer")
    assert textes(colonne.corps) == [
        "Code civil, art. 498", "Le loyer est payé chaque mois.", "يدفع بدل الإيجار كل شهر."]
    # Une phrase sans source reste sans étiquette, comme avant.
    page.rechercher("caution")
    assert textes(colonne.corps) == ["La caution paie la dette.", "يوفي الكفيل الدين."]


def test_une_definition_prise_pour_contexte_porte_la_mention_de_sa_fiche(fenetre, tmp_path):
    """Contextualisation : la définition d'une autre entrée est « À vérifier » si elle ne cite pas de source."""
    fenetre.charger_glossaire(ecrire(tmp_path / "definitions.csv", (
        "terme_fr;terme_ar;definition_fr;definition_ar;source_definition\n"
        "vente;بيع;;;\n"
        "vendeur;بائع;Partie à la vente.;طرف في البيع.;Code civil, art. 351\n"
        "acheteur;مشترٍ;Autre partie à la vente.;الطرف الآخر في البيع.;\n")))
    page = fenetre.page
    page.rechercher("vente")
    colonne = page.details.colonne_contexte
    lignes = colonne.corps.findChildren(LigneDeProvenance)
    assert [(ligne.lien.texte_complet, ligne.a_verifier()) for ligne in lignes] == [
        ("Définition de « vendeur »", False), ("Définition de « acheteur »", True)]
    assert textes(colonne.corps) == ["Partie à la vente.", "طرف في البيع.",
                                     "À vérifier", "Autre partie à la vente.", "الطرف الآخر في البيع."]
    assert textes(colonne.pied) == ["2 contextes trouvés dans le glossaire"]


def test_la_ligne_de_provenance_garde_le_lien_lisible(application):
    """Dans une colonne étroite, la mention se réduit à son icône avant que le lien ne soit abrégé."""
    def ligne(largeur: int) -> LigneDeProvenance:
        ligne = LigneDeProvenance(LienCourt("Exemple de « bail »", "sourceLien"), "Phrase à vérifier.")
        ligne.resize(largeur, ligne.sizeHint().height())
        ligne.show()
        application.processEvents()
        return ligne

    large = ligne(600)
    complet = large.lien.sizeHint().width()
    assert large.sizeHint().width() > complet and large.minimumSizeHint().width() < complet
    assert large.mots.isVisible() and large.lien.width() == complet and large.lien.text() == "Exemple de « bail »"
    assert large.icone.x() >= large.lien.width() and large.mots.x() > large.icone.x()
    assert large.icone.toolTip() == large.mots.toolTip() != ""
    # Juste assez de place pour le lien et l'icône : les deux mots disparaissent, le lien reste entier.
    juste = ligne(complet + LigneDeProvenance.ECART + LigneDeProvenance.ICONE)
    assert not juste.mots.isVisible() and juste.icone.isVisible()
    assert juste.lien.width() == complet and juste.lien.text() == "Exemple de « bail »"
    # Plus étroit encore : le lien est abrégé, l'icône reste dans la ligne.
    etroit = ligne(90)
    assert etroit.lien.text().endswith("…") and etroit.lien.texte_complet == "Exemple de « bail »"
    assert etroit.icone.x() + etroit.icone.width() <= etroit.width()
    # Sans mention : le lien seul.
    seul = LigneDeProvenance(LienCourt("Code civil, art. 107", "sourceLien"))
    assert not seul.a_verifier() and seul.icone is None and seul.mots is None
    assert seul.sizeHint().width() == seul.lien.sizeHint().width()
    for widget in (large, juste, etroit, seul):
        widget.deleteLater()


def test_chaque_entree_de_l_exemple_a_une_definition_et_des_ressources(glossaire):
    for entree in glossaire.entrees:
        assert entree.definition_fr and entree.definition_ar and entree.source_definition, entree.terme_fr
        assert entree.ressources, entree.terme_fr


def test_copier_l_equivalent_et_les_references(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    QGuiApplication.clipboard().clear()
    page.fiche.colonne_equivalent.bouton_copier.click()
    assert QGuiApplication.clipboard().text() == "عقد"
    assert page.fiche.colonne_equivalent.bouton_copier.text() == "Équivalent copié"
    assert fenetre.barre_etat.texte() == "Équivalent copié : عقد"
    # Les références se copient depuis le menu « Plus de détails » : cercle « Ressources ».
    page.details.roue.boutons["ressources"].click()
    lien = page.details.colonne_ressources.bouton_copier
    assert lien.isVisible() and lien.text() == "Copier les références"
    lien.click()
    assert QGuiApplication.clipboard().text().splitlines() == page.entree.ressources
    assert lien.text() == "Références copiées"
    assert fenetre.barre_etat.texte() == "Références copiées dans le presse-papiers"


def test_suggestions_pendant_la_saisie(fenetre):
    page = fenetre.page
    modele = page.suggestions.model()
    francais = [modele.data(modele.index(rang, 0)) for rang in range(modele.rowCount())]
    assert "contrat" in francais and "équité" in francais
    assert len(francais) == 39  # 40 entrées, « droit » une seule fois
    page.definir_sens(AR)
    arabe = [modele.data(modele.index(rang, 0)) for rang in range(modele.rowCount())]
    assert "عقد" in arabe and "contrat" not in arabe
    page.suggestions.setCompletionPrefix("إيج")
    assert page.suggestions.completionCount() == 3  # إيجار، عقد الإيجار، بدل الإيجار


def test_toutes_les_entrees_trouvees_sont_dans_la_liste(fenetre, application, tmp_path):
    lignes = "".join(f"contrat type {lettre};عقد {arabe}\n" for lettre, arabe in zip("abcdefghij", "ابتثجحخدذر",
                                                                                     strict=True))
    fenetre.charger_glossaire(ecrire(tmp_path / "long.csv", "terme_fr;terme_ar\n" + lignes))
    page = fenetre.page
    details = page.details
    page.rechercher("contrat")
    application.processEvents()
    # Aucune entrée ne s'appelle « contrat » : la première trouvée est affichée. La liste des autres s'ouvre
    # d'office : l'utilisateur voit que le terme affiché n'est pas celui qu'il a saisi.
    assert len(page.resultats) == 10 and page.entree.terme_fr == "contrat type a"
    assert page.barre.texte_du_resume() == "10 résultats"
    assert details.detail == "expressions" and details.roue.boutons["expressions"].isChecked()
    assert details.titre_du_detail.texte_complet() == "Autres résultats pour « contrat »"
    assert details.nombre.isVisible() and details.nombre.text() == "9"
    liste = details.colonne_expressions
    assert [entree.terme_fr[-1] for entree in liste.entrees()] == list("bcdefghij")
    # Le cercle porte alors le nom « Autres résultats » (« Résultats » quand la roue est étroite).
    assert details.roue.boutons["expressions"].libelle in ("Autres résultats", "Résultats")
    # À droite de la roue : trois colonnes dans la fenêtre de référence, une seule dans la plus petite fenêtre.
    grille = liste.grille
    assert (grille.colonnes(), grille.rangees()) == (3, 3) and grille.cases_abregees() == 0
    fenetre.resize(900, 600)
    application.processEvents()
    assert (grille.colonnes(), grille.rangees()) == (1, 9) and grille.cases_abregees() == 0
    # La fiche garde tout son contenu, le menu sa hauteur minimale : c'est la liste qui défile.
    assert page.fiche.height() >= page.fiche.hauteur_du_contenu(page.fiche.width())
    assert details.height() >= details.HAUTEUR_MINIMALE

    grille.cellules[-1].click()
    assert page.entree.terme_fr == "contrat type j" and len(liste.entrees()) == 9
    assert details.detail == "expressions"

    # Refermée, la liste ne se rouvre pas pour un terme trouvé tel quel ; elle se rouvre à la prochaine
    # recherche dont le premier résultat n'est pas le terme saisi.
    details.bouton_fermer.click()
    page.rechercher("contrat type b")
    assert page.entree.terme_fr == "contrat type b" and details.detail == ""
    page.rechercher("contrat")
    assert details.detail == "expressions"


def test_de_longues_expressions_sont_rangees_sur_moins_de_colonnes(fenetre, application, tmp_path):
    """Le nombre de colonnes d'une liste dépend de ses termes : ils doivent, presque tous, être écrits en entier."""
    lettres = list(zip("abcdefghij", "ابتثجحخدذر", strict=True))
    courtes = "".join(f"bail {lettre};إيجار {arabe}\n" for lettre, arabe in lettres)
    longues = "".join(
        f"responsabilité du fait des choses inanimées {lettre};المسؤولية عن فعل الأشياء غير الحية {arabe}\n"
        for lettre, arabe in lettres)
    page = fenetre.page

    def lister(requete: str):
        """Cherche ``requete`` et ouvre la liste des autres résultats : la grille, et les colonnes possibles."""
        page.rechercher(requete)
        page.details.choisir("expressions")
        application.processEvents()
        grille = page.details.colonne_expressions.grille
        return grille, min(4, grille.width() // grille.LARGEUR_DE_CASE)

    def entiere(cellule) -> bool:
        return cellule.textes_affiches() == (cellule.entree.terme_fr, cellule.entree.terme_ar)

    fenetre.charger_glossaire(ecrire(tmp_path / "longueurs.csv", "terme_fr;terme_ar\n" + courtes + longues))
    # Des termes courts : autant de colonnes que la largeur le permet.
    grille, possibles = lister("bail")
    assert len(grille.cellules) == 9 and grille.colonnes() == possibles == 3 and grille.cases_abregees() == 0
    # De longues expressions, dans la même largeur : une seule colonne, et chacune est écrite en entier.
    grille, possibles = lister("responsabilité")
    assert len(grille.cellules) == 9 and (possibles, grille.colonnes()) == (3, 1) and grille.cases_abregees() == 0
    assert grille.rangees() == 9 and grille.height() == 9 * grille.HAUTEUR_DE_LIGNE
    assert {cellule.width() for cellule in grille.cellules} == {grille.width()}
    assert grille.width() // 2 < max(cellule.largeur_necessaire() for cellule in grille.cellules) <= grille.width()
    # La largeur nécessaire d'une case est juste : à cette largeur, les deux termes sont écrits en entier ;
    # quelques points de moins, et l'un d'eux est abrégé (l'infobulle donne alors les termes entiers).
    cellule = grille.cellules[0]
    cellule.marge_gauche = cellule.marge_droite = theme.MARGE
    necessaire = cellule.largeur_necessaire()
    cellule.resize(necessaire, cellule.height())
    assert entiere(cellule) and cellule.toolTip() == ""
    cellule.resize(necessaire - 6, cellule.height())
    assert not entiere(cellule) and cellule.entree.terme_fr in unescape(cellule.toolTip())

    # Un seul terme long parmi des courts ne change pas la grille : il est abrégé, les autres restent en colonnes.
    long = "bail et responsabilité du fait des choses inanimées;إيجار والمسؤولية عن فعل الأشياء غير الحية\n"
    fenetre.charger_glossaire(ecrire(tmp_path / "melange.csv", "terme_fr;terme_ar\n" + courtes + long))
    grille, possibles = lister("bail")
    assert len(grille.cellules) == 10 and grille.colonnes() == possibles == 3
    assert [entiere(cellule) for cellule in grille.cellules] == [True] * 9 + [False]


def test_la_fiche_et_le_menu_tiennent_dans_la_plus_petite_fenetre(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat")
    fiche, details = page.fiche, page.details

    def place(largeur: int) -> int:
        """Largeur laissée à la fiche : la fenêtre, moins la barre latérale et les marges."""
        return largeur - LARGEUR_DU_RAIL - 2 * theme.MARGE

    for taille in ((1900, 1000), (1440, 860), (1080, 620), (900, 600)):
        fenetre.resize(*taille)
        application.processEvents()
        # La fiche et le menu occupent toute la largeur : rien ne défile de gauche à droite.
        assert fiche.width() == details.width() == place(taille[0]) >= LARGEUR_MINIMALE, taille
        # La fiche montre tout son contenu, sans défilement ; le menu garde au moins sa hauteur minimale.
        assert fiche.defilement.verticalScrollBar().maximum() == 0, taille
        assert fiche.height() >= fiche.hauteur_du_contenu(fiche.width()), taille
        assert details.height() >= details.HAUTEUR_MINIMALE == 170, taille
        # Le menu est sous la fiche, et se termine dans l'écran.
        assert fiche.geometry().bottom() < details.geometry().top(), taille
        assert details.geometry().bottom() < page.vue_fiche.height(), taille
        # Le résumé de la recherche laisse sa place au champ de saisie quand elle manque ; il reste connu.
        assert page.barre.texte_du_resume() == "1 terme · 5 expressions", taille
    # Quand la hauteur ne manque pas, la fiche a sa hauteur de référence : le menu reçoit tout le reste.
    fenetre.resize(1440, 860)
    application.processEvents()
    assert fiche.height() == fiche.hauteur_de_reference() and details.height() > details.HAUTEUR_CONFORTABLE


def test_les_signes_speciaux_du_glossaire_sont_affiches_tels_quels(fenetre, tmp_path):
    """« < » et « & » ne sont pas pris pour des balises ou des raccourcis clavier."""
    fichier = ecrire(tmp_path / "a&b.csv", (
        "terme_fr;terme_ar;domaine;termes_associes;definition_fr;source_definition;contexte_fr;ressources\n"
        "dommages & intérêts;تعويض <1>;Droit <civil>;<b>gras</b> | droits & devoirs;Somme <b>due</b> & payée.;"
        "Source <x> & y;Les dommages & intérêts <dus>.;Titre <b>x</b>, suite & fin\n"
        "droits & devoirs;حقوق وواجبات;;;;;;\n"))
    assert fenetre.charger_glossaire(fichier)
    nom = fenetre.page_parametres.nom_du_glossaire
    assert nom.texte_complet() == "a&b.csv" and nom.textFormat() == Qt.TextFormat.PlainText
    page = fenetre.page
    page.rechercher("dommages & intérêts")
    fiche, details = page.fiche, page.details
    assert fenetre.barre_etat.etat() == "« dommages & intérêts » : 1 entrée trouvée dans le glossaire."
    assert fenetre.barre_etat.message.textFormat() == Qt.TextFormat.PlainText
    assert grand_terme(fiche.colonne_terme) == "dommages & intérêts"
    assert grand_terme(fiche.colonne_equivalent) == "تعويض <1>"
    simples = {label.text(): label for label in fiche.colonne_terme.corps.findChildren(QLabel)}
    assert "Droit <civil>" in simples and simples["Droit <civil>"].textFormat() == Qt.TextFormat.PlainText
    # Dans le menu « Plus de détails » : les termes associés, la définition et sa source, l'exemple, la ressource.
    associes = details.colonne_associes
    simples = {label.text(): label for label in associes.corps.findChildren(QLabel)}
    assert "<b>gras</b>" in simples and simples["<b>gras</b>"].textFormat() == Qt.TextFormat.PlainText
    assert [bouton.text() for bouton in associes.corps.findChildren(QPushButton)] == ["droits && devoirs"]
    assert "Somme <b>due</b> & payée." in textes(details.colonne_definition.corps)
    assert textes(details.colonne_definition.pied) == ["Source :", "Source <x> & y"]
    exemple = next(label.text() for label in details.colonne_contexte.corps.findChildren(QLabel)
                   if "<span" in label.text())
    assert '600;">dommages &amp; intérêts</span> &lt;dus&gt;.' in exemple
    ressource = next(label.text() for label in details.colonne_ressources.corps.findChildren(QLabel)
                     if "<span" in label.text())
    assert "Titre &lt;b&gt;x&lt;/b&gt;</span>" in ressource and "suite &amp; fin" in ressource
    # Au centre de la roue, le terme est dessiné tel quel.
    assert details.roue.terme == "dommages & intérêts"

    associes.corps.findChild(QPushButton).click()
    assert page.entree.terme_fr == "droits & devoirs" and page.champ.text() == "droits & devoirs"


# ------------------------------------------------------------------ textes ajustés à la largeur
def test_un_texte_trop_long_est_abrege(application):
    label = EtiquetteCourte("Source : Code <civil> & autres textes de référence")
    label.show()
    label.resize(120, 20)
    application.processEvents()
    assert label.text().endswith("…") and label.text().startswith("Source")
    assert label.texte_complet() == "Source : Code <civil> & autres textes de référence"
    # Le texte complet reste lisible dans l'infobulle, signes « < » et « & » compris.
    assert label.toolTip() == "<qt>Source : Code &lt;civil&gt; &amp; autres textes de référence</qt>"
    label.resize(900, 20)
    application.processEvents()
    assert label.text() == label.texte_complet() and label.toolTip() == ""
    label.close()
    label.deleteLater()


def test_un_texte_prend_sa_forme_courte_quand_la_place_manque(application):
    label = EtiquetteCourte()
    label.definir_texte("5 phrases · 54 mots · 321 caractères", "5 phrases · 54 mots", "54 mots")
    label.show()
    largeurs = [label.fontMetrics().horizontalAdvance(forme) for forme in
                ("5 phrases · 54 mots · 321 caractères", "5 phrases · 54 mots", "54 mots")]
    for largeur, attendu in ((largeurs[0] + 2, "5 phrases · 54 mots · 321 caractères"),
                             (largeurs[0] - 2, "5 phrases · 54 mots"), (largeurs[1] - 2, "54 mots")):
        label.resize(largeur, 20)
        application.processEvents()
        assert label.text() == attendu
    assert label.texte_complet() == "5 phrases · 54 mots · 321 caractères"
    assert label.toolTip() == "<qt>5 phrases · 54 mots · 321 caractères</qt>"
    label.resize(largeurs[2] - 6, 20)  # même la forme la plus courte ne tient pas : elle est abrégée
    application.processEvents()
    assert label.text().endswith("…")

    # Une dernière forme vide : le texte disparaît plutôt que d'être abrégé.
    label.definir_texte("Cliquez sur un terme pour ouvrir sa fiche", "")
    label.resize(60, 20)
    application.processEvents()
    assert label.text() == "" and label.minimumSizeHint().width() == 0
    label.close()
    label.deleteLater()


def test_la_forme_la_plus_courte_peut_fixer_la_largeur_minimale(application):
    label = EtiquetteCourte("", forme_minimale=True)
    label.definir_texte("5 phrases · 54 mots · 321 caractères", "54 mots")
    assert label.minimumSizeHint().width() >= label.fontMetrics().horizontalAdvance("54 mots")
    assert label.minimumSizeHint().width() < label.fontMetrics().horizontalAdvance("5 phrases · 54 mots")
    label.deleteLater()


def test_un_mot_plus_large_que_la_colonne_est_coupe(fenetre, application, tmp_path):
    mot = "anticonstitutionnellement" * 3  # 75 lettres : plus large qu'une colonne, même en petits caractères
    fenetre.charger_glossaire(ecrire(tmp_path / "long.csv",
                                     f"terme_fr;terme_ar\nrecours {mot};على نحو مخالف للدستور\n"))
    page = fenetre.page
    fenetre.resize(900, 600)
    page.rechercher(mot)
    application.processEvents()
    terme = page.fiche.colonne_terme.terme
    # Même écrit à la plus petite taille, le mot dépasse : il passe à la ligne au lieu d'être rogné.
    assert terme.taille == 14 and terme.fontMetrics().horizontalAdvance(mot) > terme.contentsRect().width()
    assert terme.text() == "recours " + ESPACE_INVISIBLE.join(mot)
    assert terme.height() >= 2 * terme.fontMetrics().height()  # le terme occupe plusieurs lignes…
    assert terme.height() >= terme.heightForWidth(terme.width())  # … et toutes sont visibles
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction
    assert terme.terme == f"recours {mot}"
    # La fiche montre le terme en entier, sans défilement ; le menu garde sa hauteur minimale.
    assert page.fiche.defilement.verticalScrollBar().maximum() == 0
    assert page.details.height() >= page.details.HAUTEUR_MINIMALE
    # Le centre de la roue ne peut pas l'écrire : il porte le mot « TERME », et son infobulle donne le terme.
    assert page.details.roue.lignes_du_centre()[0] == []
    assert page.details.roue.info_du_centre() == f"<qt>recours {mot}</qt>"

    fenetre.resize(1900, 860)  # avec plus de place, le mot redevient entier (et sélectionnable)
    application.processEvents()
    assert terme.text() == f"recours {mot}" and terme.taille > 14
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.TextSelectableByMouse
    assert terme.fontMetrics().horizontalAdvance(mot) <= terme.contentsRect().width()


def test_le_terme_trop_long_est_ecrit_plus_petit(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat")
    application.processEvents()
    assert page.fiche.colonne_terme.terme.taille == 40 and page.fiche.colonne_equivalent.terme.taille == 58
    # Un terme plus long est écrit plus petit, dès la fenêtre de référence.
    page.rechercher("responsabilité")
    application.processEvents()
    assert page.fiche.colonne_terme.terme.taille == 30
    # Dans la plus petite fenêtre, il ne dépasse pas de sa colonne.
    fenetre.resize(900, 600)
    application.processEvents()
    terme = page.fiche.colonne_terme.terme
    assert 14 <= terme.taille <= 30
    assert terme.fontMetrics().horizontalAdvance("responsabilité") <= terme.contentsRect().width()
    assert terme.geometry().right() < page.fiche.colonne_terme.corps.width()


def test_les_caracteres_du_terme_diminuent_quand_la_largeur_manque(application):
    terme = TermeAjuste("responsabilité", "terme", FR, 40, 14, centre=True)
    terme.resize(900, 80)
    terme.show()
    application.processEvents()
    assert terme.taille == 40
    largeur = terme.fontMetrics().horizontalAdvance("responsabilité")
    terme.resize(largeur * 2 // 3, 80)  # moins de place que le mot n'en demande
    application.processEvents()
    assert 14 <= terme.taille < 40
    assert terme.fontMetrics().horizontalAdvance("responsabilité") <= terme.contentsRect().width()
    assert terme.text() == "responsabilité"
    terme.resize(900, 80)  # la place revenue, le terme reprend sa taille
    application.processEvents()
    assert terme.taille == 40
    terme.close()
    terme.deleteLater()


def test_les_termes_trop_longs_de_la_liste_sont_abreges(fenetre, application, tmp_path):
    longue = "responsabilité civile du fait des choses inanimées dont on a la garde et des animaux"
    fenetre.charger_glossaire(ecrire(tmp_path / "expressions.csv", (
        "terme_fr;terme_ar\nfaute;خطأ\nfaute lourde;خطأ جسيم\n"
        f"faute et {longue};خطأ والمسؤولية المدنية عن فعل الأشياء غير الحية التي تكون تحت الحراسة وعن الحيوانات\n")))
    page = fenetre.page
    page.rechercher("faute")
    page.details.choisir("expressions")
    application.processEvents()
    courte, etendue = page.details.colonne_expressions.grille.cellules
    assert courte.textes_affiches() == ("faute lourde", "خطأ جسيم") and courte.toolTip() == ""
    francais, arabe = etendue.textes_affiches()
    assert francais.endswith("…") and francais.startswith("faute et") and arabe.endswith("…")
    # Les termes entiers restent lisibles dans l'infobulle.
    assert longue in etendue.toolTip() and "الحيوانات" in etendue.toolTip()


# ------------------------------------------------------------------ glossaire
def test_ouvrir_un_autre_glossaire(fenetre, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "mon_glossaire.csv",
                     "Français,Arabe,Remarque\ntribunal,محكمة,\nappel,استئناف,voie de recours\n")
    fenetre.page.rechercher("contrat")
    assert fenetre.charger_glossaire(fichier, bilan=True)
    assert len(fenetre.glossaire) == 2 and not fenetre.glossaire_fourni()
    assert reglages.value("glossaire/chemin") == str(fichier.resolve())
    # L'écran « Paramètres » décrit le glossaire chargé.
    parametres = fenetre.page_parametres
    assert parametres.nom_du_glossaire.texte_complet() == "mon_glossaire.csv"
    assert parametres.dossier_du_glossaire.texte_complet() == str(tmp_path)
    assert parametres.taille_du_glossaire.text() == "2 entrées"
    assert parametres.bouton_fourni.isEnabled() and parametres.bouton_recharger.isEnabled()
    titre, bilan = avertissements[-1]
    assert titre == "Glossaire chargé"
    assert bilan.splitlines()[0] == "mon_glossaire.csv : 2 entrées."
    assert "Colonnes reconnues : terme_fr, terme_ar." in bilan
    assert "Colonnes ignorées (nom inconnu) : Remarque." in bilan
    # La recherche en cours est relancée dans le nouveau glossaire.
    assert fenetre.page.entree is None
    assert fenetre.page.accueil.titre.text() == "Aucune entrée pour « contrat »"
    assert fenetre.barre_etat.etat() == "Aucune entrée du glossaire ne correspond à « contrat »."
    fenetre.page.rechercher("tribunal")
    assert grand_terme(fenetre.page.fiche.colonne_equivalent) == "محكمة"


def test_choisir_un_glossaire_dans_les_parametres(fenetre, avertissements, monkeypatch, tmp_path):
    fichier = ecrire(tmp_path / "choisi.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    demandes = []

    def choisir(parent, titre, dossier, filtre):
        demandes.append((titre, dossier, filtre))
        return str(fichier), filtre

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(choisir))
    dossier_du_glossaire = str(fenetre.glossaire.chemin.parent)
    fenetre.definir_mode(MODE_PARAMETRES)
    fenetre.page_parametres.bouton_choisir.click()  # Paramètres → Choisir un autre fichier…
    titre, dossier, filtre = demandes[0]
    assert titre == "Choisir un glossaire" and "*.csv" in filtre
    assert dossier == dossier_du_glossaire  # la fenêtre s'ouvre sur le dossier du glossaire chargé
    assert fenetre.glossaire.nom == "choisi.csv"
    assert avertissements[-1][0] == "Glossaire chargé"  # le bilan de lecture est affiché

    # Fenêtre fermée sans choisir de fichier : le glossaire ne change pas.
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *arguments: ("", "")))
    fenetre.action_ouvrir.trigger()  # le raccourci Ctrl+O ouvre la même fenêtre de choix
    assert fenetre.glossaire.nom == "choisi.csv" and len(avertissements) == 1


def test_un_fichier_invalide_ne_remplace_pas_le_glossaire(fenetre, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "casse.csv", "terme_fr;terme_ar\ncontrat;???\n")
    assert not fenetre.charger_glossaire(fichier)
    assert len(fenetre.glossaire) == 40
    assert avertissements[-1][0] == "Glossaire non chargé" and "CSV UTF-8" in avertissements[-1][1]
    assert avertissements[-1][1].startswith("casse.csv\n\n")
    assert not reglages.contains("glossaire/chemin")
    assert fenetre.page_parametres.nom_du_glossaire.texte_complet() == "Glossaire juridique"  # le glossaire fourni


def test_recharger_le_glossaire_garde_l_entree_affichee(fenetre, tmp_path):
    fichier = ecrire(tmp_path / "g.csv", "terme_fr;terme_ar\ndroit;حق\ndroit;قانون\n")
    fenetre.charger_glossaire(fichier)
    fenetre.page.rechercher("droit")
    fenetre.page.fiche.onglets.onglets[1].click()
    ecrire(fichier, "terme_fr;terme_ar;definition_fr\ndroit;حق;\ndroit;قانون;Ensemble de règles\nloi;قانون;\n")
    fenetre.page_parametres.bouton_recharger.click()  # Paramètres → Recharger (ou F5)
    assert len(fenetre.glossaire) == 3
    assert fenetre.page.entree.terme_ar == "قانون"
    assert "Ensemble de règles" in textes(fenetre.page.details.colonne_definition.corps)
    assert fenetre.page_parametres.taille_du_glossaire.text() == "3 entrées"
    assert fenetre.barre_etat.texte() == "Glossaire chargé : g.csv, 3 entrées."  # message passager


def test_le_dernier_glossaire_ouvert_est_repris_au_demarrage(application, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "dernier.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    reglages.setValue("glossaire/chemin", str(fichier))
    fenetre = FenetrePrincipale(reglages=reglages)
    assert fenetre.glossaire.nom == "dernier.csv"
    fenetre.deleteLater()

    fichier.unlink()  # le fichier a disparu : retour au glossaire d'exemple, avec un avertissement
    fenetre = FenetrePrincipale(reglages=reglages)
    application.processEvents()
    assert fenetre.glossaire.nom == "glossaire_essai.csv"
    assert not reglages.contains("glossaire/chemin")
    # L'avertissement attend que la fenêtre soit affichée : il ne passe pas devant l'écran de démarrage.
    assert avertissements == []
    fenetre.show()
    application.processEvents()
    assert len(avertissements) == 1 and "dernier.csv" in avertissements[0][1]
    assert avertissements[0][0] == "Glossaire non chargé"
    # Il n'est affiché qu'une fois.
    fenetre.hide()
    fenetre.show()
    application.processEvents()
    assert len(avertissements) == 1
    fenetre.close()
    fenetre.deleteLater()


def test_glossaire_donne_au_lancement(application, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "choisi.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    fenetre = FenetrePrincipale(fichier, reglages)
    assert fenetre.glossaire.nom == "choisi.csv"
    assert reglages.value("glossaire/chemin") == str(fichier.resolve())
    fenetre.deleteLater()


def test_revenir_au_glossaire_fourni(fenetre, reglages, tmp_path):
    parametres = fenetre.page_parametres
    assert not parametres.bouton_fourni.isEnabled()  # le glossaire fourni est déjà chargé
    assert parametres.nom_du_glossaire.texte_complet() == "Glossaire juridique"
    assert parametres.dossier_du_glossaire.texte_complet() == "Fourni avec l’application"
    fichier = ecrire(tmp_path / "autre.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    fenetre.charger_glossaire(fichier)
    assert reglages.contains("glossaire/chemin") and parametres.bouton_fourni.isEnabled()
    assert parametres.nom_du_glossaire.texte_complet() == "autre.csv"  # un fichier choisi garde son nom
    assert fenetre.barre_etat.texte() == "Glossaire chargé : autre.csv, 1 entrée."
    parametres.bouton_fourni.click()
    assert fenetre.glossaire.nom == "glossaire_essai.csv" and len(fenetre.glossaire) == 40
    assert parametres.nom_du_glossaire.texte_complet() == "Glossaire juridique"
    assert fenetre.barre_etat.texte() == "Glossaire chargé : glossaire fourni, 40 entrées."
    assert not reglages.contains("glossaire/chemin")  # le glossaire fourni est le glossaire par défaut
    assert not parametres.bouton_fourni.isEnabled()


def test_sans_aucun_glossaire(application, reglages, avertissements, tmp_path, monkeypatch):
    monkeypatch.setattr(module_fenetre, "GLOSSAIRE_EXEMPLE", tmp_path / "absent.csv")
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    application.processEvents()
    page = fenetre.page
    assert fenetre.glossaire is None and not fenetre.glossaire_fourni()
    assert not fenetre.action_recharger.isEnabled()
    assert len(avertissements) == 1 and avertissements[0][0] == "Glossaire non chargé"
    # L'accueil renvoie à l'écran « Paramètres ».
    assert page.accueil.titre.text() == "Aucun glossaire n’est chargé"
    assert page.accueil.bouton_glossaire.isVisible() and page.accueil.puces == []
    assert page.accueil.bouton_glossaire.text() == "Ouvrir les paramètres"
    page.rechercher("contrat")
    assert page.entree is None and page.accueil.titre.text() == "Aucun glossaire n’est chargé"
    assert fenetre.barre_etat.etat() == (
        "Aucun glossaire n’est chargé : choisissez un fichier CSV dans « Paramètres ».")
    page.accueil.bouton_glossaire.click()
    assert fenetre.mode == MODE_PARAMETRES
    parametres = fenetre.page_parametres
    assert parametres.nom_du_glossaire.texte_complet() == "Aucun glossaire chargé"
    assert parametres.taille_du_glossaire.text() == "" and not parametres.bouton_recharger.isEnabled()
    assert parametres.bouton_choisir.text() == "Choisir un fichier…"

    # Un fichier choisi dans « Paramètres » est chargé ; la recherche en attente est relancée.
    fichier = ecrire(tmp_path / "nouveau.csv", "terme_fr;terme_ar\ncontrat;عقد\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *arguments: (str(fichier), "")))
    parametres.bouton_choisir.click()
    assert fenetre.glossaire.nom == "nouveau.csv" and page.entree.terme_fr == "contrat"
    assert fenetre.action_recharger.isEnabled() and parametres.bouton_recharger.isEnabled()
    assert parametres.bouton_choisir.text() == "Choisir un autre fichier…"
    fenetre.close()
    fenetre.deleteLater()


def test_bilan_de_lecture(glossaire):
    bilan = FenetrePrincipale.bilan_de_lecture(glossaire)
    assert bilan.splitlines()[0] == "glossaire_essai.csv : 40 entrées."
    assert "Colonnes reconnues : terme_fr, terme_ar" in bilan
    assert "ignorée" not in bilan and "UTF-8" not in bilan and "Encodage" not in bilan


# ------------------------------------------------------------------ menus
def test_la_barre_de_menus(fenetre):
    def libelles(menu) -> list[str]:
        return [action.text().replace("&", "").split("\t")[0] for action in menu.actions() if not action.isSeparator()]

    # Les titres ne contiennent pas de « & » : aucune lettre n'y est soulignée. Il n'y a pas de menu « Aide ».
    assert [action.text() for action in fenetre.menus.actions()] == ["Fichier", "Affichage", "Recherche", "Traduction"]
    menus = fenetre.menus_par_titre
    assert list(menus) == ["Fichier", "Affichage", "Recherche", "Traduction"]
    # Le glossaire est chargé à l'ouverture : le menu « Fichier » n'a aucune commande pour le charger.
    assert libelles(menus["Fichier"]) == ["Importer un texte…", "Exporter la traduction…", "Quitter"]
    assert libelles(menus["Affichage"]) == [
        "Recherche d’un terme", "Traduction d’un texte", "Paramètres", "Description de la plateforme",
        "Centre d’aide", "Inverser le sens de traduction"]
    assert libelles(menus["Recherche"]) == ["Aller à la barre de recherche", "Effacer la recherche"]
    # « Étapes du traitement… » ouvre le détail du traitement, qui n'est plus affiché en permanence.
    assert libelles(menus["Traduction"]) == [
        "Traduire le texte", "Copier la traduction", "Étapes du traitement…", "Insérer un texte d’exemple",
        "Effacer le texte"]
    # Hors des menus, deux raccourcis restent : choisir un autre glossaire, relire le fichier.
    assert fenetre.action_ouvrir.shortcut().toString() == "Ctrl+O"
    assert fenetre.action_recharger.shortcut().toString() == "F5"
    assert fenetre.action_ouvrir in fenetre.actions() and fenetre.action_recharger in fenetre.actions()


def test_alt_et_une_lettre_ouvrent_un_menu(fenetre, application):
    fenetre.activateWindow()
    if not QTest.qWaitForWindowActive(fenetre, 1000):
        pytest.skip("la fenêtre ne peut pas être activée dans cet environnement")
    for lettre, titre in ((Qt.Key.Key_F, "Fichier"), (Qt.Key.Key_I, "Affichage"), (Qt.Key.Key_T, "Traduction")):
        QTest.keyClick(application.focusWidget() or fenetre, lettre, Qt.KeyboardModifier.AltModifier)
        application.processEvents()
        assert [nom for nom, menu in fenetre.menus_par_titre.items() if menu.isVisible()] == [titre]
        for menu in fenetre.menus_par_titre.values():
            menu.close()
        application.processEvents()


def test_le_menu_recherche(fenetre):
    fenetre.definir_mode(MODE_TEXTE)
    fenetre.page.champ.setText("contrat")
    fenetre._aller_a_la_recherche()  # Recherche → Aller à la barre de recherche (Ctrl+F)
    assert fenetre.mode == MODE_TERME and fenetre.page.champ.hasFocus()
    assert fenetre.page.champ.selectedText() == "contrat"

    fenetre.page.rechercher("contrat")
    fenetre.definir_mode(MODE_TEXTE)
    fenetre._effacer_la_recherche()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree is None and fenetre.page.champ.text() == ""


# ------------------------------------------------------------------ barre d'état
def test_la_barre_d_etat_affiche_l_etat_ou_un_message_passager(application):
    barre = BarreEtat()
    barre.definir_etat("Glossaire chargé : 40 entrées.")
    assert barre.texte() == barre.etat() == "Glossaire chargé : 40 entrées."

    barre.afficher_message("Équivalent copié : عقد")
    assert barre.texte() == "Équivalent copié : عقد" and barre.etat() == "Glossaire chargé : 40 entrées."
    # Un changement d'état qui suit aussitôt le message ne l'efface pas…
    barre.definir_etat("« contrat » : 6 entrées trouvées dans le glossaire.")
    assert barre.texte() == "Équivalent copié : عقد"
    # … mais un changement d'état plus tardif le remplace : le message ne décrit plus l'écran.
    barre.DELAI_DE_GARDE = -1
    barre.definir_etat("« loi » : 1 entrée trouvée dans le glossaire.")
    assert barre.texte() == "« loi » : 1 entrée trouvée dans le glossaire."

    # Sans nouveau changement, le message s'efface de lui-même au bout de quelques secondes.
    barre.afficher_message("Références copiées")
    assert barre.texte() == "Références copiées"
    barre._retour.timeout.emit()
    assert barre.texte() == "« loi » : 1 entrée trouvée dans le glossaire."
    barre.deleteLater()


def test_la_barre_d_etat_suit_l_ecran_affiche(fenetre):
    fenetre.page.rechercher("contrat")
    assert fenetre.barre_etat.etat() == "« contrat » : 6 entrées trouvées dans le glossaire."
    fenetre.definir_mode(MODE_TEXTE)
    assert fenetre.barre_etat.etat() == ""  # l'écran « Texte » n'a rien à signaler
    fenetre.definir_mode(MODE_PARAMETRES)
    assert fenetre.barre_etat.etat() == ""
    fenetre.definir_mode(MODE_TERME)
    assert fenetre.barre_etat.etat() == "« contrat » : 6 entrées trouvées dans le glossaire."


# ------------------------------------------------------------------ boîtes de message
def test_une_boite_de_message(application):
    boite = BoiteMessage(None, boites.ALERTE, "Glossaire non chargé", "mon glossaire & <essai>.csv\n\nColonne absente.")
    assert boite.windowTitle() == "Traducteur juridique" and boite.isModal()
    assert boite.titre.text() == "Glossaire non chargé"
    # Le texte est affiché tel quel : « & » et « < » ne sont pas interprétés.
    assert boite.texte.text() == "mon glossaire & <essai>.csv\n\nColonne absente."
    assert boite.texte.textFormat() == Qt.TextFormat.PlainText
    assert boite.genre == boites.ALERTE and boite.signe.property("alerte") is True
    assert boite.defilement is None
    assert boite.sizeHint().width() == boites.LARGEUR
    assert boite.bouton.text() == "OK" and boite.bouton.isDefault()
    boite.bouton.click()
    assert boite.result() == QDialog.DialogCode.Accepted
    boite.deleteLater()

    information = BoiteMessage(None, boites.INFORMATION, "Glossaire chargé", "40 entrées.")
    assert information.signe.property("alerte") is False
    information.deleteLater()


def test_un_texte_trop_long_defile_dans_la_boite(application):
    erreurs = "\n".join(f"Ligne {numero} : terme arabe manquant." for numero in range(1, 400))
    boite = BoiteMessage(None, boites.ALERTE, "Import impossible", erreurs)
    assert boite.defilement is not None and boite.defilement.widget() is boite.texte
    assert boite.sizeHint().width() == boites.LARGEUR
    assert boite.texte.height() > boite.defilement.height() >= boites.HAUTEUR_MINIMALE_DU_TEXTE
    assert boite.texte.text() == erreurs
    boite.deleteLater()
