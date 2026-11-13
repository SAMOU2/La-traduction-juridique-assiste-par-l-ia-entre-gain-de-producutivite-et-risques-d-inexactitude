"""Interface de bureau : fenêtre, barre de menus, écran « Terme », fiche (tests exécutés sans écran).

La barre latérale, les écrans « Paramètres », « Description de la plateforme » et « Centre
d'aide », l'allumage des étapes et l'écran de démarrage sont testés dans ``test_interface_ecrans.py``.

La largeur d'un texte dépend de la police du système. Les tests ne comparent donc pas les textes
abrégés ou raccourcis à une valeur exacte : ils vérifient leur forme (une des formes prévues,
abrégée ou non), et les contenus complets.
"""

import re
from html import unescape

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QPushButton

from traducteur.interface import boites, theme
from traducteur.interface import fenetre as module_fenetre
from traducteur.interface.boites import BoiteMessage
from traducteur.interface.composants import ESPACE_INVISIBLE, MARQUE_RTL, EtiquetteCourte
from traducteur.interface.fenetre import MODE_PARAMETRES, MODE_TERME, MODE_TEXTE, BarreEtat, FenetrePrincipale
from traducteur.interface.fiche import LARGEUR_MINIMALE
from traducteur.interface.navigation import LARGEUR as LARGEUR_DU_RAIL
from traducteur.interface.recherche import LEGENDES
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
    assert (fenetre.minimumWidth(), fenetre.minimumHeight()) == (900, 560)
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
    # Les cinq champs de l'enchaînement, chacun avec sa légende (longue ou courte selon la place).
    assert accueil.entete.titres == ["Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
    for legende, formes in zip(accueil.entete.legendes_affichees(), LEGENDES, strict=True):
        assert legende in formes or legende.endswith("…")
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
def test_recherche_d_un_terme_francais(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    fiche = page.fiche
    assert page.entree.terme_fr == "contrat"
    assert page.pile.currentWidget() is page.vue_fiche
    assert page.barre.texte_du_resume() == "1 terme · 5 expressions"
    assert page.barre.resume.isVisible() and page.barre.effacer.isVisible()
    assert fenetre.barre_etat.texte() == "« contrat » : 6 entrées trouvées dans le glossaire."
    assert fiche.entete.titres == ["Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
    assert not fiche.onglets.isVisible()  # un seul sens : pas d'onglets

    # 1 Terme
    assert grand_terme(fiche.colonne_terme) == "contrat"
    contenu = textes(fiche.colonne_terme.corps)
    assert contenu[0] == "FRANÇAIS · SOURCE"
    assert "nom masculin · pl. contrats" in contenu
    assert {"DOMAINE", "SYNONYMES", "TERMES ASSOCIÉS"} <= set(contenu)
    assert {"Droit civil › Obligations", "convention", "accord", "cocontractant", "clause"} <= set(contenu)
    assert puces(fiche.colonne_terme.corps) == ["contractant", "obligation"]  # entrées du glossaire : cliquables
    assert fiche.colonne_terme.rang.texte_complet() == "Entrée 1 sur 40"
    assert not fiche.colonne_terme.bouton_precedent.isEnabled() and fiche.colonne_terme.bouton_suivant.isEnabled()

    # 2 Définition
    contenu = textes(fiche.colonne_definition.corps)
    assert contenu[0] == "FRANÇAIS" and contenu[1].startswith("Convention par laquelle")
    assert contenu[2] == "العربية" and contenu[3].startswith("اتفاق يلتزم بموجبه")
    assert textes(fiche.colonne_definition.pied) == ["Source :", "Code civil, art. 54"]

    # 3 Équivalent
    assert grand_terme(fiche.colonne_equivalent) == "عقد"
    assert textes(fiche.colonne_equivalent.corps) == [
        "ARABE · CIBLE", "عقد", "اسم مذكر، ج. عقود", "AUTRE ÉQUIVALENT", "اتفاق"]
    assert fiche.colonne_equivalent.bouton_copier.text() == "Copier l’équivalent"

    # 4 Contextualisation : le terme est mis en évidence dans les deux langues
    contenu = textes(fiche.colonne_contexte.corps)
    assert contenu[:3] == ["Code civil, art. 106", "Le contrat fait la loi des parties.", "العقد شريعة المتعاقدين."]
    assert textes(fiche.colonne_contexte.pied) == ["2 exemples dans le glossaire"]
    assert [emploi.origine for emploi in fiche.colonne_contexte.emplois] == ["propre", "propre"]
    riches = [label.text() for label in fiche.colonne_contexte.corps.findChildren(QLabel) if "<span" in label.text()]
    assert len(riches) == 4
    assert any('font-weight: 600;">contrat</span>' in texte for texte in riches)
    assert any('font-weight: 600;">العقد</span>' in texte for texte in riches)

    # 5 Ressources
    contenu = textes(fiche.colonne_ressources.corps)
    assert contenu[0] == "Code civil algérien\nordonnance n° 75-58 du 26 septembre 1975, art. 54, 106 et 107"
    liens = [label.text() for label in fiche.colonne_ressources.corps.findChildren(QLabel) if "<a href" in label.text()]
    assert len(liens) == 1 and 'href="https://www.joradp.dz"' in liens[0]
    assert fiche.colonne_ressources.bouton_copier.text() == "Copier les références"

    # Sous la fiche : les autres entrées trouvées.
    assert page.liste.isVisible()
    assert page.liste.titre.texte_complet() == "Expressions avec « contrat »" and page.liste.nombre.text() == "5"
    assert [entree.terme_fr for entree in page.liste.entrees()] == [
        "contrat de bail", "contrat de vente", "contrat de travail", "exécution du contrat", "conclusion du contrat"]
    assert page.liste.grille.cellules[0].text() == "contrat de bail — عقد الإيجار"


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
    page.rechercher("contrat")
    page.liste.grille.cellules[1].click()
    assert page.entree.terme_fr == "contrat de vente"
    assert grand_terme(page.fiche.colonne_equivalent) == "عقد البيع"
    assert page.champ.text() == "contrat"  # la recherche saisie est conservée
    # La liste présente alors les autres résultats de cette recherche, « contrat » compris.
    assert page.liste.titre.texte_complet() == "Autres résultats pour « contrat »"
    assert [entree.terme_fr for entree in page.liste.entrees()] == [
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
    # La colonne du terme arabe s'aligne à droite.
    assert page.fiche.colonne_terme.corps.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert fenetre.sens.source.text() == "العربية" and fenetre.sens.cible.text() == "Français"
    assert page.champ.placeholderText() == "أدخل مصطلحا قانونيا، بالعربية أو بالفرنسية..."
    assert page.champ.layoutDirection() == Qt.LayoutDirection.RightToLeft
    # Un message passager l'annonce ; l'état de l'écran reste le résultat de la recherche.
    assert fenetre.barre_etat.texte() == "Terme saisi en arabe : le sens de traduction a été inversé."
    assert fenetre.barre_etat.etat() == "« العقد » : 6 entrées trouvées dans le glossaire."


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


def test_un_terme_qui_a_plusieurs_sens(fenetre):
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
    assert not page.liste.isVisible()  # aucune autre entrée trouvée

    bande.onglets[1].click()
    assert page.entree.terme_ar == "قانون"
    assert grand_terme(page.fiche.colonne_equivalent) == "قانون"
    assert [onglet.isChecked() for onglet in page.fiche.onglets.onglets] == [False, True]
    assert page.champ.text() == "droit"


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
    # Au pied du panneau, un conseil remplace les raccourcis : les fiches viennent du fichier CSV.
    assert accueil.conseil.isVisible() and not accueil.raccourcis.isVisible()
    assert accueil.conseil.texte_complet() == (
        "Pour obtenir sa fiche, ajoutez ce terme au fichier CSV, puis rechargez le glossaire (F5).")
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
    page.fiche.colonne_terme.corps.findChild(QPushButton).click()  # puce « contractant »
    assert page.entree.terme_fr == "contractant" and page.champ.text() == "contractant"

    # Au pied du champ « Terme » : l'entrée précédente et l'entrée suivante du glossaire.
    numero = page.entree.numero
    page.fiche.colonne_terme.bouton_suivant.click()
    assert page.entree.numero == numero + 1 and page.champ.text() == page.entree.terme_fr
    page.fiche.colonne_terme.bouton_precedent.click()
    assert page.entree.terme_fr == "contractant"

    page.ouvrir(fenetre.glossaire.entrees[-1])
    assert page.fiche.colonne_terme.rang.texte_complet() == "Entrée 40 sur 40"
    assert not page.fiche.colonne_terme.bouton_suivant.isEnabled()


def test_entree_sans_definition_ni_exemple_ni_ressource(fenetre, tmp_path):
    """Un glossaire réduit aux deux colonnes de termes : les champs 2, 4 et 5 le signalent."""
    assert fenetre.charger_glossaire(ecrire(tmp_path / "deux_colonnes.csv", "terme_fr;terme_ar\ncapacité;أهلية\n"))
    page = fenetre.page
    page.rechercher("capacité")
    fiche = page.fiche
    assert textes(fiche.colonne_terme.corps) == ["FRANÇAIS · SOURCE", "capacité"]
    assert textes(fiche.colonne_definition.corps)[0] == "Aucune définition pour ce terme"
    assert "definition_fr et definition_ar" in textes(fiche.colonne_definition.corps)[1]
    assert textes(fiche.colonne_contexte.corps)[0] == "Aucun exemple pour ce terme"
    assert textes(fiche.colonne_ressources.corps)[0] == "Aucune ressource pour ce terme"
    assert textes(fiche.colonne_definition.pied) == [] and textes(fiche.colonne_contexte.pied) == []
    assert grand_terme(fiche.colonne_equivalent) == "أهلية"
    assert textes(fiche.colonne_equivalent.corps) == ["ARABE · CIBLE", "أهلية"]
    assert fiche.colonne_terme.rang.texte_complet() == "Entrée 1 sur 1"


def test_une_definition_sans_source_est_a_verifier(fenetre, tmp_path):
    fenetre.charger_glossaire(ecrire(tmp_path / "sources.csv", (
        "terme_fr;terme_ar;definition_fr;source_definition\n"
        "bail;إيجار;Contrat de location.;à vérifier (définition d’exemple)\n"
        "vente;بيع;Contrat de vente.;à vérifier\n"
        "prêt;قرض;Contrat de prêt.;\n")))
    page = fenetre.page
    page.rechercher("bail")
    assert textes(page.fiche.colonne_definition.pied) == ["À vérifier", "· définition d’exemple"]
    assert textes(page.fiche.colonne_definition.corps)[-1] == "Pas de définition en arabe dans le glossaire."
    page.rechercher("vente")
    assert textes(page.fiche.colonne_definition.pied) == ["À vérifier"]
    # Sans source dans le glossaire, la définition est aussi à vérifier (comme dans le tableau de l'écran « Texte »).
    page.rechercher("prêt")
    assert textes(page.fiche.colonne_definition.pied) == ["À vérifier", "· source non indiquée"]


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
    lien = page.fiche.colonne_ressources.bouton_copier
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
    page.rechercher("contrat")
    application.processEvents()
    # Aucune entrée ne s'appelle « contrat » : la première trouvée est affichée, les autres sont dans la liste.
    assert len(page.resultats) == 10 and page.entree.terme_fr == "contrat type a"
    assert page.barre.texte_du_resume() == "10 résultats"
    assert page.liste.titre.texte_complet() == "Autres résultats pour « contrat »" and page.liste.nombre.text() == "9"
    assert [entree.terme_fr[-1] for entree in page.liste.entrees()] == list("bcdefghij")
    # Quatre colonnes dans la fenêtre de référence, trois dans une fenêtre étroite.
    grille = page.liste.grille
    assert (grille.colonnes(), grille.rangees()) == (4, 3)
    fenetre.resize(900, 560)
    application.processEvents()
    assert (grille.colonnes(), grille.rangees()) == (3, 3)
    # La liste garde au moins son titre et deux lignes ; les autres lignes défilent.
    assert page.liste.height() >= page.liste.hauteur_minimale()
    assert page.fiche.height() >= page.fiche.hauteur_minimale()

    page.liste.grille.cellules[-1].click()
    assert page.entree.terme_fr == "contrat type j" and len(page.liste.entrees()) == 9


def test_la_fiche_defile_dans_une_fenetre_etroite(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat")
    barre = page.defilement_fiche.horizontalScrollBar()

    def place(largeur: int) -> int:
        """Largeur laissée à la fiche : la fenêtre, moins la barre latérale et les marges."""
        return largeur - LARGEUR_DU_RAIL - 2 * theme.MARGE

    fenetre.resize(1080, 620)
    application.processEvents()
    assert barre.maximum() == 0 and page.fiche.width() == place(1080)  # les cinq champs tiennent
    assert page.barre.resume.isVisible()
    fenetre.resize(900, 560)
    application.processEvents()
    # La fiche garde sa largeur minimale et défile ; le résumé laisse sa place au champ de saisie.
    assert page.fiche.width() == LARGEUR_MINIMALE and barre.maximum() == LARGEUR_MINIMALE - place(900)
    assert not page.barre.resume.isVisible() and page.barre.texte_du_resume() == "1 terme · 5 expressions"


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
    fiche = page.fiche
    assert fenetre.barre_etat.etat() == "« dommages & intérêts » : 1 entrée trouvée dans le glossaire."
    assert fenetre.barre_etat.message.textFormat() == Qt.TextFormat.PlainText
    assert grand_terme(fiche.colonne_terme) == "dommages & intérêts"
    assert grand_terme(fiche.colonne_equivalent) == "تعويض <1>"
    simples = {label.text(): label for label in fiche.colonne_terme.corps.findChildren(QLabel)}
    assert {"Droit <civil>", "<b>gras</b>"} <= set(simples)
    assert all(simples[texte].textFormat() == Qt.TextFormat.PlainText for texte in ("Droit <civil>", "<b>gras</b>"))
    assert [bouton.text() for bouton in fiche.colonne_terme.corps.findChildren(QPushButton)] == ["droits && devoirs"]
    assert "Somme <b>due</b> & payée." in textes(fiche.colonne_definition.corps)
    assert textes(fiche.colonne_definition.pied) == ["Source :", "Source <x> & y"]
    exemple = next(label.text() for label in fiche.colonne_contexte.corps.findChildren(QLabel)
                   if "<span" in label.text())
    assert '600;">dommages &amp; intérêts</span> &lt;dus&gt;.' in exemple
    ressource = next(label.text() for label in fiche.colonne_ressources.corps.findChildren(QLabel)
                     if "<span" in label.text())
    assert "Titre &lt;b&gt;x&lt;/b&gt;</span>" in ressource and "suite &amp; fin" in ressource

    fiche.colonne_terme.corps.findChild(QPushButton).click()
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
    mot = "anticonstitutionnellement"
    fenetre.charger_glossaire(ecrire(tmp_path / "long.csv",
                                     f"terme_fr;terme_ar\nrecours {mot};على نحو مخالف للدستور\n"))
    page = fenetre.page
    fenetre.resize(1080, 620)
    page.rechercher(mot)
    application.processEvents()
    terme = page.fiche.colonne_terme.terme
    # Même écrit à la plus petite taille, le mot dépasse : il passe à la ligne au lieu d'être rogné.
    assert terme.taille == 14 and terme.fontMetrics().horizontalAdvance(mot) > terme.contentsRect().width()
    assert terme.text() == "recours " + ESPACE_INVISIBLE.join(mot)
    assert terme.height() >= 2 * terme.fontMetrics().height()  # le terme occupe plusieurs lignes…
    assert terme.height() == terme.heightForWidth(terme.width())  # … et toutes sont visibles
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction
    assert terme.terme == f"recours {mot}"

    fenetre.resize(1900, 860)  # avec plus de place, le mot redevient entier (et sélectionnable)
    application.processEvents()
    assert terme.text() == f"recours {mot}" and terme.taille > 14
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.TextSelectableByMouse
    assert terme.fontMetrics().horizontalAdvance(mot) <= terme.contentsRect().width()


def test_le_terme_trop_long_est_ecrit_plus_petit(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat")
    application.processEvents()
    assert page.fiche.colonne_terme.terme.taille == 34 and page.fiche.colonne_equivalent.terme.taille == 58
    page.rechercher("responsabilité")
    application.processEvents()
    normale = page.fiche.colonne_terme.terme.taille
    fenetre.resize(1080, 620)
    application.processEvents()
    terme = page.fiche.colonne_terme.terme
    assert 14 <= terme.taille < normale <= 26
    # Le terme ne dépasse pas de sa colonne.
    assert terme.fontMetrics().horizontalAdvance("responsabilité") <= terme.contentsRect().width()
    assert terme.geometry().right() < page.fiche.colonne_terme.corps.width()


def test_les_termes_trop_longs_de_la_liste_sont_abreges(fenetre, application, tmp_path):
    longue = "responsabilité civile du fait des choses inanimées dont on a la garde et des animaux"
    fenetre.charger_glossaire(ecrire(tmp_path / "expressions.csv", (
        "terme_fr;terme_ar\nfaute;خطأ\nfaute lourde;خطأ جسيم\n"
        f"faute et {longue};خطأ والمسؤولية المدنية عن فعل الأشياء غير الحية التي تكون تحت الحراسة وعن الحيوانات\n")))
    page = fenetre.page
    page.rechercher("faute")
    application.processEvents()
    courte, etendue = page.liste.grille.cellules
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
    assert fenetre.page_parametres.nom_du_glossaire.texte_complet() == "glossaire_essai.csv"


def test_recharger_le_glossaire_garde_l_entree_affichee(fenetre, tmp_path):
    fichier = ecrire(tmp_path / "g.csv", "terme_fr;terme_ar\ndroit;حق\ndroit;قانون\n")
    fenetre.charger_glossaire(fichier)
    fenetre.page.rechercher("droit")
    fenetre.page.fiche.onglets.onglets[1].click()
    ecrire(fichier, "terme_fr;terme_ar;definition_fr\ndroit;حق;\ndroit;قانون;Ensemble de règles\nloi;قانون;\n")
    fenetre.page_parametres.bouton_recharger.click()  # Paramètres → Recharger (ou F5)
    assert len(fenetre.glossaire) == 3
    assert fenetre.page.entree.terme_ar == "قانون"
    assert "Ensemble de règles" in textes(fenetre.page.fiche.colonne_definition.corps)
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
    assert len(avertissements) == 1 and "dernier.csv" in avertissements[0][1]
    assert avertissements[0][0] == "Glossaire non chargé"
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
    assert parametres.dossier_du_glossaire.texte_complet() == "Glossaire fourni avec l’application"
    fichier = ecrire(tmp_path / "autre.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    fenetre.charger_glossaire(fichier)
    assert reglages.contains("glossaire/chemin") and parametres.bouton_fourni.isEnabled()
    parametres.bouton_fourni.click()
    assert fenetre.glossaire.nom == "glossaire_essai.csv" and len(fenetre.glossaire) == 40
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

    # Un fichier choisi dans « Paramètres » est chargé ; la recherche en attente est relancée.
    fichier = ecrire(tmp_path / "nouveau.csv", "terme_fr;terme_ar\ncontrat;عقد\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *arguments: (str(fichier), "")))
    parametres.bouton_choisir.click()
    assert fenetre.glossaire.nom == "nouveau.csv" and page.entree.terme_fr == "contrat"
    assert fenetre.action_recharger.isEnabled() and parametres.bouton_recharger.isEnabled()
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
    assert libelles(menus["Traduction"]) == [
        "Traduire le texte", "Copier la traduction", "Insérer un texte d’exemple", "Effacer le texte"]
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
