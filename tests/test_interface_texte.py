"""Écran « Texte » : saisie, traduction, termes relevés, import et export (tests exécutés sans écran).

Comme dans ``test_interface.py``, les tests ne dépendent pas de la police du système : les textes
qui se raccourcissent selon la place sont comparés à leurs formes prévues, pas à une valeur exacte.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog
from test_documents import fabriquer_doc

from traducteur import documents
from traducteur.interface import theme
from traducteur.interface.composants import MARQUE_RTL, bornes_des_colonnes
from traducteur.interface.dessin import extrait_autour, police, sur_une_ligne
from traducteur.interface.fenetre import MODE_TERME, MODE_TEXTE, FenetrePrincipale
from traducteur.interface.texte import COLONNES, ETAPES, EXEMPLES, cases_du_tableau
from traducteur.langues import AR, FR

ARTICLE_106 = "Le contrat fait la loi des parties."
ARTICLE_106_AR = "العقد شريعة المتعاقدين."

GAUCHE_A_DROITE, DROITE_A_GAUCHE = Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft


@pytest.fixture
def page(fenetre, application):
    """L'écran « Texte » de la fenêtre, affiché."""
    fenetre.definir_mode(MODE_TEXTE)
    application.processEvents()
    return fenetre.page_texte


def traduire(page, texte: str) -> None:
    page.zone_source.setPlainText(texte)
    page.bouton_traduire.click()


def texte_traduit(page) -> str:
    """Le texte affiché dans la zone de droite (sans la marque de direction)."""
    return page.zone_cible.toPlainText().replace(MARQUE_RTL, "")


def resultats_des_etapes(page) -> list[str]:
    return [etape.resultat for etape in page.bande.etapes]


def termes_du_tableau(page) -> list[str]:
    """Première colonne du tableau des termes."""
    return [ligne.libelle for ligne in page.termes.lignes_affichees()]


def message_du_tableau(page) -> tuple[str, str]:
    """Le message affiché à la place des lignes quand le tableau des termes est vide."""
    return page.termes.contenu.titre_du_message, page.termes.contenu.texte_du_message


def sens_d_ecriture(zone) -> Qt.LayoutDirection:
    """Sens d'écriture du texte d'une zone."""
    return zone.document().defaultTextOption().textDirection()


# ------------------------------------------------------------------ les deux écrans
def test_le_selecteur_affiche_l_ecran_texte(fenetre, application):
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.page.barre.isVisible()
    assert not fenetre.bouton_importer.isVisible() and not fenetre.page_texte.bouton_traduire.isVisible()

    fenetre.boutons_mode[MODE_TEXTE].click()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE
    assert fenetre.pile.currentWidget() is fenetre.page_texte
    assert fenetre.boutons_mode[MODE_TEXTE].isChecked() and fenetre.actions_mode[MODE_TEXTE].isChecked()
    # La barre d'outils montre les commandes de l'écran : importer, exporter, traduire.
    assert fenetre.bouton_importer.isVisible() and fenetre.bouton_exporter.isVisible()
    assert fenetre.page_texte.bouton_traduire.isVisible() and not fenetre.page.barre.isVisible()
    assert fenetre.page_texte.zone_source.hasFocus()

    fenetre.actions_mode[MODE_TERME].trigger()  # menu Affichage → Recherche d'un terme (Ctrl+1)
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.boutons_mode[MODE_TERME].isChecked() and fenetre.page.barre.isVisible()


def test_etat_initial(fenetre, page):
    assert page.texte() == ""
    assert page.traduction is None
    assert page.panneau_source.nom.text() == "Français" and page.panneau_source.legende.text() == "texte source"
    assert page.panneau_cible.nom.text() == "العربية" and page.panneau_cible.legende.text() == "traduction"
    # Chaque zone vide porte une invitation, écrite dans sa langue.
    assert page.zone_source.invite() == "Saisissez, collez ou importez le texte à traduire…"
    assert page.zone_cible.isReadOnly()
    assert page.zone_cible.invite() == "ستظهر الترجمة هنا."
    assert page.lien_exemple.isVisible()
    assert not page.fichier_importe.isVisible() and not page.importe_de.isVisible()
    assert not page.badge.isVisible() and page.legende.libelles() == []
    assert page.decompte_source.texte_complet() == "0 phrase · 0 mot · 0 caractère"
    assert page.decompte_cible.texte_complet() == ""
    assert page.aide_outils.texte_complet() == "Import : .txt, .docx, .doc · Export : .docx, .txt"
    # Les cinq étapes sont nommées ; elles n'ont pas encore de résultat.
    assert [etape.nom for etape in page.bande.etapes] == [nom for nom, _, _ in ETAPES]
    assert resultats_des_etapes(page) == [""] * 5 and not page.bande.faite
    assert "Le texte est découpé en phrases." in page.bande.infobulle(0)
    assert "Résultat" not in page.bande.infobulle(0)
    assert page.termes.lignes_affichees() == [] and not page.termes.nombre.isVisible()
    assert message_du_tableau(page) == ("Les termes juridiques du texte s’afficheront ici",
                                        "Saisissez ou importez un texte, puis cliquez sur « Traduire ».")
    # Rien à effacer, à copier ni à exporter tant qu'il n'y a ni texte ni traduction.
    assert not page.bouton_effacer.isEnabled() and not page.bouton_copier.isEnabled()
    assert not fenetre.bouton_exporter.isEnabled()
    assert not fenetre.action_exporter.isEnabled() and not fenetre.action_copier.isEnabled()
    assert fenetre.barre_etat.texte() == "Glossaire chargé : 40 entrées."


# ------------------------------------------------------------------ traduction
def test_inserer_un_exemple_puis_traduire(fenetre, page):
    page.lien_exemple.click()
    assert page.texte() == EXEMPLES[FR]
    assert not page.lien_exemple.isVisible() and page.bouton_effacer.isEnabled()
    assert page.traduction is None  # l'exemple n'est traduit qu'à la demande

    page.bouton_traduire.click()
    traduction = page.traduction
    assert traduction.source == FR and traduction.cible == AR
    assert texte_traduit(page) == traduction.texte
    # Les articles 106 et 107 sont repris des exemples du glossaire ; la dernière phrase est traduite mot à mot.
    assert traduction.texte.startswith("العقد شريعة المتعاقدين. فلا يجوز نقضه، ولا تعديله إلا باتفاق الطرفين")
    assert traduction.texte.endswith("\nبطلان عقد البيع protège المشتري.")

    # En-tête de la traduction : son état, avec le décompte des mots trouvés.
    assert page.badge.isVisible() and page.badge.etat == "partiel"
    assert page.badge.texte() == "Traduction partielle · 83 mots sur 84 trouvés"
    assert "1 mot sur 84 ne figure pas dans le glossaire : il reste à traduire." in page.badge.toolTip()
    assert "relisez et complétez la traduction" in page.badge.toolTip()
    # Pied des deux zones : décomptes, et légende des couleurs du texte traduit.
    assert page.decompte_source.texte_complet() == "5 phrases · 84 mots · 473 caractères"
    assert page.decompte_cible.texte_complet() == "5 phrases · 54 mots · 321 caractères"
    assert page.legende.libelles() == ["terme du glossaire", "mot absent, à traduire"]
    # Les cinq étapes et leur résultat ; le détail est dans l'infobulle de chaque étape.
    assert page.bande.faite
    assert resultats_des_etapes(page) == ["5 phrases", "84 mots", "83 mots sur 84", "8 appliquées", "5 phrases"]
    assert "Résultat : 5 phrases." in page.bande.infobulle(0)
    assert "Mots absents du glossaire : protège." in page.bande.infobulle(2)
    assert "Grammaire — Complément du nom : 1" in page.bande.infobulle(3)
    assert ("4 phrases reprises des exemples du glossaire, 1 phrase traduite mot à mot."
            in page.bande.infobulle(4))
    assert fenetre.barre_etat.texte() == "Traduction : 83 mots sur 84 trouvés dans le glossaire."
    assert page.bouton_copier.isEnabled()
    assert fenetre.bouton_exporter.isEnabled() and fenetre.action_exporter.isEnabled()


def test_les_mots_absents_du_glossaire_sont_en_gris_et_les_termes_en_bleu(page):
    traduire(page, "La nullité du contrat protège l’acheteur.")
    document = page.zone_cible.document()

    def format_de(mot: str):
        curseur = document.find(mot)
        assert not curseur.isNull(), mot
        return curseur.charFormat()

    def couleur_de(mot: str) -> str:
        return format_de(mot).foreground().color().name().upper()

    assert couleur_de("protège") == theme.TEXTE_4  # gris : mot resté en français
    assert format_de("protège").fontItalic()
    assert couleur_de("بطلان") == couleur_de("المشتري") == theme.BLEU  # termes du glossaire
    assert not format_de("بطلان").fontItalic()
    assert couleur_de(".") not in (theme.TEXTE_4, theme.BLEU)  # la ponctuation garde la couleur du texte


def test_le_tableau_des_termes(page):
    page.inserer_un_exemple()
    page.traduire()
    tableau = page.termes
    assert termes_du_tableau(page) == [
        "contrat", "loi", "partie", "consentement", "bonne foi", "contractant", "usage", "équité", "obligation",
        "nullité", "contrat de vente", "acheteur"]
    assert tableau.titre.text() == "Termes juridiques détectés"
    assert tableau.nombre.isVisible() and tableau.nombre.text() == "12"
    assert tableau.aide.texte_complet() == "Cliquez sur un terme pour ouvrir sa fiche"
    assert tableau.entete.titres == ["Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
    # La légende ne cite que les signes présents dans la colonne « Définition ».
    assert tableau.legende.libelles() == ["Définition à vérifier", "Source citée"]

    # Les cinq champs de la ligne « contrat ».
    ligne = tableau.lignes_affichees()[0]
    assert ligne.text() == "contrat — عقد"
    assert (ligne.libelle, ligne.categorie, ligne.occurrences) == ("contrat", "nom masculin", "3 occurrences")
    assert ligne.definition.startswith("Convention par laquelle une ou plusieurs personnes s’obligent")
    assert not ligne.a_verifier  # sa définition cite sa source
    assert (ligne.equivalent, ligne.grammaire, ligne.alerte) == ("عقد", "اسم مذكر، ج. عقود", "")
    assert ligne.passage_source == (ARTICLE_106, [(3, 10)])  # la phrase du texte ; le terme y est mis en évidence
    assert ligne.passage_cible == (ARTICLE_106_AR, [(0, 5)])
    assert (ligne.titre_ressource, ligne.autres_ressources) == ("Code civil algérien", 3)
    assert ligne.detail_ressource == "ordonnance n° 75-58 du 26 septembre 1975, art. 54, 106 et 107"

    # Ce que la ligne abrège est donné en entier dans les infobulles.
    assert ligne.infobulle(0) == "<qt>Ouvrir la fiche de « contrat »</qt>"
    assert "à donner, à faire ou à ne pas faire quelque chose." in ligne.infobulle(1)
    assert "Source : Code civil, art. 54" in ligne.infobulle(1)
    # Chaque paragraphe d'une infobulle est écrit dans le sens de sa langue.
    assert ligne.infobulle(3) == (
        f'<qt><p dir="ltr" align="left" style="margin: 0px 0 0 0;">{ARTICLE_106}</p>'
        f'<p dir="rtl" align="right" style="margin: 10px 0 0 0; font-size: 14px;">{MARQUE_RTL}{ARTICLE_106_AR}</p>'
        "</qt>")
    assert ligne.infobulle(4).count("<p ") == 4 and "Vocabulaire juridique" in ligne.infobulle(4)
    assert ligne.infobulle(4).count('dir="rtl"') == 1  # la référence écrite en arabe

    # « loi » : sa définition n'est reprise d'aucune source citée.
    loi = tableau.lignes_affichees()[1]
    assert loi.a_verifier and "Définition à vérifier" in loi.infobulle(1)


def test_les_textes_du_tableau_s_ajustent_a_la_largeur(page):
    page.inserer_un_exemple()
    page.traduire()
    ligne = page.termes.lignes_affichees()[0]
    # Sous le terme : la catégorie et le nombre d'occurrences ; « occurrences » est abrégé, puis la catégorie retirée.
    assert ligne.sous_le_terme(1000) == ("nom masculin", "3 occurrences")
    assert ligne.sous_le_terme(1) == ("", "3 occ.")
    assert ligne.sous_le_terme() in (("nom masculin", "3 occurrences"), ("nom masculin", "3 occ."),
                                     ("", "3 occurrences"), ("", "3 occ."))
    # Sous l'équivalent : la catégorie et le pluriel ; la catégorie seule si le pluriel ne tient pas.
    assert ligne.grammaire_affichee(1000) == "اسم مذكر، ج. عقود"
    assert ligne.grammaire_affichee(1) == "اسم مذكر"
    # La définition tient sur deux lignes au plus ; le passage du texte montre le terme.
    lignes = ligne.lignes_de_definition()
    assert 1 <= len(lignes) <= 2 and lignes[0].startswith("Convention par laquelle")
    passages = ligne.passages_affiches()
    assert [langue for langue, _ in passages] == [FR, AR]
    assert "contrat" in passages[0][1] and "العقد" in passages[1][1]


def test_un_passage_ecrit_sur_une_ligne_garde_son_terme_en_evidence(application):
    """Un texte collé depuis un tableau contient des tabulations : le terme reste en évidence au bon endroit."""
    texte = "  Le\t\tcontrat   de \t vente est nul.  "
    terme = (texte.index("contrat"), texte.index("vente") + len("vente"))
    ligne, evidences = sur_une_ligne(texte, [terme])
    assert ligne == "Le contrat de vente est nul."
    assert [ligne[debut:fin] for debut, fin in evidences] == ["contrat de vente"]
    # Un texte déjà propre est rendu tel quel, avec les espaces insécables du français.
    assert sur_une_ligne("prix\u00a0: 1\u202f000 DA", [(0, 4)]) == ("prix\u00a0: 1\u202f000 DA", [(0, 4)])

    police_du_passage = police(application.font(), 13)
    # Assez de place : la phrase entière.
    passage, evidences = extrait_autour(texte, [terme], police_du_passage, 2000)
    assert passage == "Le contrat de vente est nul."
    assert [passage[debut:fin] for debut, fin in evidences] == ["contrat de vente"]
    # Peu de place : le passage est pris autour du terme ; « … » marque chaque côté coupé.
    phrase = "Selon la loi, \t le contrat de vente oblige le vendeur à livrer la chose vendue à l'acheteur."
    debut = phrase.index("vendeur")
    passage, evidences = extrait_autour(phrase, [(debut, debut + len("vendeur"))], police_du_passage, 170)
    assert passage.startswith("… ") and passage.endswith("…") and "\t" not in passage
    assert [passage[debut:fin] for debut, fin in evidences] == ["vendeur"]


@pytest.mark.parametrize("largeur", [852, 1032, 1392, 1900])
def test_les_cases_du_tableau_restent_dans_leur_colonne(largeur):
    bornes = bornes_des_colonnes(largeur, COLONNES)
    cases = cases_du_tableau(largeur)
    assert len(cases) == 5
    for rang, (gauche, place) in enumerate(cases):
        assert bornes[rang] < gauche and gauche + place < bornes[rang + 1] and place > 60
    # Les bords du tableau gardent la marge des panneaux.
    assert cases[0][0] == theme.MARGE and cases[-1][0] + cases[-1][1] == largeur - theme.MARGE


def test_un_texte_entierement_reconnu(page):
    traduire(page, ARTICLE_106)
    assert page.traduction.texte == ARTICLE_106_AR
    assert page.traduction.complete
    assert page.badge.etat == "termine" and page.badge.texte() == "Traduction terminée · 7 mots sur 7 trouvés"
    assert "Tous les mots du texte ont été trouvés dans le glossaire." in page.badge.toolTip()
    assert page.legende.libelles() == ["terme du glossaire"]
    assert resultats_des_etapes(page)[2] == "7 mots sur 7"
    assert "Tous les mots du texte ont été trouvés dans le glossaire." in page.bande.infobulle(2)


def test_un_texte_sans_aucun_mot_du_glossaire(fenetre, page):
    traduire(page, "This sentence is written in English.")
    assert page.traduction.texte == "This sentence is written in English."
    assert page.badge.etat == "partiel" and page.badge.texte() == "Aucun mot trouvé dans le glossaire"
    assert "recopié tel quel" in page.badge.toolTip()
    assert page.legende.libelles() == ["mot absent, à traduire"]
    assert resultats_des_etapes(page) == ["1 phrase", "6 mots", "0 mot sur 6", "aucune appliquée", "1 phrase"]
    assert page.termes.lignes_affichees() == []
    assert page.termes.nombre.isVisible() and page.termes.nombre.text() == "0"
    assert not page.termes.aide.isVisible() and page.termes.legende.libelles() == []
    assert message_du_tableau(page) == ("Aucun terme du glossaire dans ce texte",
                                        "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
    assert fenetre.barre_etat.texte() == "Traduction : 0 mot sur 6 trouvé dans le glossaire."


def test_un_terme_ambigu_est_signale_dans_le_tableau(page):
    traduire(page, "Le droit et le juge.")
    droit, juge = page.termes.lignes_affichees()
    assert (droit.libelle, droit.equivalent) == ("droit", "حق")
    # « droit » a deux sens dans le glossaire et rien, dans la phrase, ne permet de choisir.
    assert droit.incertain and droit.alerte == "Ambigu : aussi « قانون »"
    assert "vérifiez l’équivalent" in droit.infobulle(2)
    assert not juge.incertain and juge.alerte == ""
    assert juge.infobulle(2) == "<qt>Ouvrir la fiche de « juge »</qt>"


def sens_des_paragraphes(page) -> list[Qt.LayoutDirection]:
    sens = []
    bloc = page.zone_cible.document().begin()
    while bloc.isValid():
        sens.append(bloc.textDirection())
        bloc = bloc.next()
    return sens


def test_un_paragraphe_non_traduit_garde_son_sens_d_ecriture(page):
    """Dans la zone arabe, un paragraphe resté en français s'écrit de gauche à droite (et inversement)."""
    traduire(page, f"Bonjour à tous, comment allez-vous ?\n{ARTICLE_106}\nLe juge décide.\nMerci (fin).")
    assert texte_traduit(page) == (
        f"Bonjour à tous, comment allez-vous ?\n{ARTICLE_106_AR}\nالقاضي décide.\nMerci (fin).")
    assert sens_des_paragraphes(page) == [GAUCHE_A_DROITE, DROITE_A_GAUCHE, DROITE_A_GAUCHE, GAUCHE_A_DROITE]

    traduire(page, f"مرحبا بالجميع، كيف حالكم؟\n{ARTICLE_106_AR}\nشكرا (انتهى).")
    assert page.source == AR
    assert texte_traduit(page) == f"مرحبا بالجميع، كيف حالكم؟\n{ARTICLE_106}\nشكرا (انتهى)."
    assert sens_des_paragraphes(page) == [DROITE_A_GAUCHE, GAUCHE_A_DROITE, DROITE_A_GAUCHE]


def test_traduire_sans_texte(fenetre, page):
    page.zone_source.setPlainText("  \n ")
    page.bouton_traduire.click()
    assert page.traduction is None
    assert fenetre.barre_etat.texte() == "Saisissez, collez ou importez d’abord un texte à traduire."


def test_le_raccourci_ctrl_entree_traduit(page, application):
    page.zone_source.setPlainText(ARTICLE_106)
    QTest.keyClick(page.zone_source, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    application.processEvents()
    assert page.texte() == ARTICLE_106  # le raccourci n'ajoute pas de ligne au texte
    assert page.traduction is not None and page.traduction.texte == ARTICLE_106_AR


def test_les_signes_speciaux_du_texte_sont_affiches_tels_quels(page):
    texte = "Le <b>contrat</b> & la loi : a < b > c « d »\n\tfin"
    traduire(page, texte)
    assert texte_traduit(page) == page.traduction.texte
    assert "<b>" in texte_traduit(page) and "</b> &" in texte_traduit(page)
    assert texte_traduit(page).endswith("\n\tfin")
    # Dans le tableau, le passage cité garde lui aussi ses signes.
    assert page.termes.lignes_affichees()[0].passage_source[0] == "Le <b>contrat</b> & la loi : a < b > c « d »"
    assert "&lt;b&gt;contrat&lt;/b&gt; &amp;" in page.termes.lignes_affichees()[0].infobulle(3)


def test_les_termes_sont_colores_dans_le_texte_source(page):
    traduire(page, "😀 Le contrat de vente et la loi.")  # l'émoticône occupe deux unités UTF-16
    selections = page.zone_source.extraSelections()
    assert [selection.cursor.selectedText() for selection in selections] == ["contrat de vente", "loi"]
    assert all(selection.format.foreground().color().name().upper() == theme.BLEU for selection in selections)
    page.zone_source.insertPlainText(" Suite.")
    assert page.zone_source.extraSelections() == []  # les couleurs ne correspondent plus au texte


# ------------------------------------------------------------------ sens de traduction
def test_un_texte_arabe_inverse_le_sens(fenetre, page):
    assert page.source == FR
    assert (sens_d_ecriture(page.zone_source), sens_d_ecriture(page.zone_cible)) == (GAUCHE_A_DROITE, DROITE_A_GAUCHE)
    traduire(page, "بطلان العقد يحمي المشتري.")
    assert page.source == AR and page.cible == FR
    assert page.traduction.source == AR
    assert page.traduction.texte == "La nullité du contrat يحمي l’acheteur."
    assert fenetre.etiquette_source.text() == "العربية" and fenetre.etiquette_cible.text() == "Français"
    assert page.panneau_source.nom.text() == "العربية" and page.panneau_cible.nom.text() == "Français"
    assert (sens_d_ecriture(page.zone_source), sens_d_ecriture(page.zone_cible)) == (DROITE_A_GAUCHE, GAUCHE_A_DROITE)
    # Seul le texte change de sens : la barre de défilement de chaque zone reste à droite.
    assert page.zone_source.layoutDirection() == page.zone_cible.layoutDirection() == GAUCHE_A_DROITE
    assert page.zone_cible.invite() == "La traduction s’affichera ici."
    assert fenetre.barre_etat.sens() == "Sens : arabe → français"
    assert fenetre.barre_etat.texte() == "Texte écrit en arabe : le sens de traduction a été inversé."
    assert fenetre.barre_etat.etat() == "Traduction : 3 mots sur 4 trouvés dans le glossaire."
    # La première colonne du tableau est écrite dans la langue source.
    assert termes_du_tableau(page) == ["بطلان", "عقد", "مشترٍ"]
    assert page.termes.lignes_affichees()[1].equivalent == "contrat"


def test_inverser_le_sens_garde_le_texte_et_efface_la_traduction(fenetre, page):
    traduire(page, ARTICLE_106)
    fenetre.bouton_inverser.click()
    assert page.source == AR
    assert page.texte() == ARTICLE_106
    assert page.traduction is None and texte_traduit(page) == ""
    assert not page.badge.isVisible() and not fenetre.bouton_exporter.isEnabled()
    assert page.zone_source.invite().startswith("أدخل النص")
    # Le texte est toujours en français : « Traduire » rétablit le sens français → arabe.
    page.bouton_traduire.click()
    assert page.source == FR and page.traduction.texte == ARTICLE_106_AR
    assert fenetre.barre_etat.texte() == "Texte écrit en français : le sens de traduction a été inversé."


def test_chaque_ecran_garde_son_sens(fenetre, page):
    fenetre.bouton_inverser.click()
    assert page.source == AR and fenetre.page.source == FR
    assert fenetre.etiquette_source.text() == "العربية"
    fenetre.definir_mode(MODE_TERME)
    assert fenetre.etiquette_source.text() == "Français"
    assert fenetre.barre_etat.sens() == "Sens : français → arabe"
    fenetre.definir_mode(MODE_TEXTE)
    assert fenetre.etiquette_source.text() == "العربية"
    assert fenetre.barre_etat.sens() == "Sens : arabe → français"


def test_l_exemple_suit_le_sens_de_traduction(fenetre, page):
    fenetre.bouton_inverser.click()
    page.lien_exemple.click()
    assert page.texte() == EXEMPLES[AR]
    page.bouton_traduire.click()
    assert page.source == AR
    assert page.traduction.texte.startswith("Le contrat fait la loi des parties. Il ne peut être révoqué")
    assert page.traduction.phrases_attestees == 4


# ------------------------------------------------------------------ du texte à la fiche d'un terme
def test_cliquer_sur_un_terme_ouvre_sa_fiche(fenetre, page):
    traduire(page, "La nullité du contrat de vente protège l’acheteur.")
    assert termes_du_tableau(page) == ["nullité", "contrat de vente", "acheteur"]
    page.termes.lignes_affichees()[1].click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.page.entree.terme_fr == "contrat de vente"
    assert fenetre.page.entree.terme_ar == "عقد البيع"
    assert fenetre.page.champ.text() == "contrat de vente"
    # Le texte et sa traduction sont conservés quand on revient à l'écran « Texte ».
    fenetre.definir_mode(MODE_TEXTE)
    assert page.traduction is not None and len(page.termes.lignes_affichees()) == 3


def test_la_fiche_s_ouvre_dans_le_sens_du_texte(fenetre, page):
    traduire(page, "بطلان العقد يحمي المشتري.")
    page.termes.lignes_affichees()[0].click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.page.source == AR
    assert fenetre.page.entree.terme_ar == "بطلان"
    assert fenetre.etiquette_source.text() == "العربية"


# ------------------------------------------------------------------ modification, effacement, copie
def test_modifier_le_texte_signale_que_la_traduction_n_est_plus_a_jour(fenetre, page):
    traduire(page, ARTICLE_106)
    assert page.badge.etat == "termine"
    page.zone_source.moveCursor(QTextCursor.MoveOperation.End)
    page.zone_source.insertPlainText(" La vente.")
    assert page.texte() == ARTICLE_106 + " La vente."
    assert page.badge.etat == "attente" and page.badge.texte() == "Texte modifié · traduction à refaire"
    assert "cliquez sur « Traduire »" in page.badge.toolTip()
    assert fenetre.barre_etat.texte().startswith("Le texte source a changé")
    assert texte_traduit(page) == ARTICLE_106_AR  # l'ancienne traduction reste lisible
    page.bouton_traduire.click()
    assert page.badge.etat == "termine"
    assert page.traduction.texte == "العقد شريعة المتعاقدين. البيع."


def test_effacer(fenetre, page, tmp_path):
    fichier = tmp_path / "texte.txt"
    fichier.write_text(ARTICLE_106, encoding="utf-8")
    assert page.importer(fichier)
    assert page.fichier_importe.isVisible() and page.importe_de.isVisible() and not page.lien_exemple.isVisible()

    page.bouton_effacer.click()
    assert page.texte() == "" and page.traduction is None and page.fichier is None
    assert texte_traduit(page) == ""
    assert not page.fichier_importe.isVisible() and page.lien_exemple.isVisible()
    assert not page.badge.isVisible() and page.legende.libelles() == []
    assert page.termes.lignes_affichees() == []
    assert resultats_des_etapes(page) == [""] * 5
    assert not fenetre.bouton_exporter.isEnabled() and not page.bouton_effacer.isEnabled()
    assert fenetre.barre_etat.texte() == "Glossaire chargé : 40 entrées."

    # La croix placée après le nom du fichier importé efface elle aussi le texte.
    assert page.importer(fichier)
    page.fichier_importe.bouton_fermer.click()
    assert page.texte() == "" and page.fichier is None and not page.fichier_importe.isVisible()


def test_copier_la_traduction(fenetre, page):
    traduire(page, ARTICLE_106 + "\nLa vente.")
    QGuiApplication.clipboard().setText("avant")
    page.bouton_copier.click()
    assert QGuiApplication.clipboard().text() == "العقد شريعة المتعاقدين.\nالبيع."
    assert page.bouton_copier.text() == "Copié"
    assert fenetre.barre_etat.texte() == "Traduction copiée dans le presse-papiers"
    page._retour_copier.timeout.emit()
    assert page.bouton_copier.text() == "Copier"


def test_le_menu_traduction(fenetre, application):
    """Les commandes du menu affichent l'écran « Texte », même lancées depuis l'écran « Terme »."""
    assert fenetre.mode == MODE_TERME
    fenetre._inserer_un_exemple()
    assert fenetre.mode == MODE_TEXTE and fenetre.page_texte.texte() == EXEMPLES[FR]
    fenetre.definir_mode(MODE_TERME)
    fenetre._traduire_le_texte()
    assert fenetre.mode == MODE_TEXTE and fenetre.page_texte.traduction is not None
    QGuiApplication.clipboard().setText("avant")
    fenetre.action_copier.trigger()
    assert QGuiApplication.clipboard().text() == fenetre.page_texte.traduction.texte
    fenetre._effacer_le_texte()
    assert fenetre.page_texte.texte() == "" and not fenetre.action_copier.isEnabled()


# ------------------------------------------------------------------ import
@pytest.mark.parametrize("extension", [".txt", ".docx", ".doc"])
def test_importer_un_fichier(fenetre, page, avertissements, tmp_path, extension):
    fichier = tmp_path / f"Article 106{extension}"
    if extension == ".txt":
        fichier.write_text(ARTICLE_106 + "\nLa vente.", encoding="utf-8")
    elif extension == ".docx":
        documents.ecrire(fichier, ARTICLE_106 + "\nLa vente.", FR)
    else:
        fichier.write_bytes(fabriquer_doc([(ARTICLE_106 + "\rLa vente.\r", True)]))

    assert page.importer(fichier)
    assert avertissements == []
    assert page.texte() == ARTICLE_106 + "\nLa vente."
    assert page.fichier == fichier
    # L'en-tête du texte source rappelle le fichier : « Importé de [Article 106.docx ×] ».
    assert page.fichier_importe.isVisible() and page.nom_du_fichier.texte_complet() == fichier.name
    assert page.importe_de.texte_complet() == "Importé de"
    assert str(fichier) in page.fichier_importe.toolTip()
    assert not page.lien_exemple.isVisible()
    # Le texte importé est traduit aussitôt.
    assert page.traduction.texte == "العقد شريعة المتعاقدين.\nالبيع."
    assert fenetre.bouton_exporter.isEnabled()


def test_importer_un_texte_arabe_inverse_le_sens(page, tmp_path):
    fichier = tmp_path / "نص.doc"
    fichier.write_bytes(fabriquer_doc([(ARTICLE_106_AR + "\r", False)]))
    assert page.importer(fichier)
    assert page.source == AR
    assert page.texte() == ARTICLE_106_AR
    assert page.traduction.texte == ARTICLE_106


def test_import_par_la_fenetre_de_choix_du_fichier(fenetre, monkeypatch, tmp_path):
    fichier = tmp_path / "texte.txt"
    fichier.write_text(ARTICLE_106, encoding="utf-8")
    demandes = []

    def choisir(parent, titre, dossier, filtre):
        demandes.append((titre, filtre))
        return str(fichier), filtre

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(choisir))
    assert fenetre.mode == MODE_TERME
    fenetre.action_importer.trigger()  # Fichier → Importer un texte (Ctrl+Maj+O)
    assert fenetre.mode == MODE_TEXTE
    assert fenetre.page_texte.texte() == ARTICLE_106
    titre, filtre = demandes[0]
    assert titre == "Importer un texte"
    assert all(extension in filtre for extension in ("*.txt", "*.docx", "*.doc"))

    # Fenêtre fermée sans choisir de fichier : rien ne change.
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *arguments: ("", "")))
    fenetre.bouton_importer.click()
    assert fenetre.page_texte.texte() == ARTICLE_106


def test_un_fichier_refuse_ne_remplace_pas_le_texte(page, avertissements, tmp_path):
    traduire(page, ARTICLE_106)
    pdf = tmp_path / "jugement.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    vide = tmp_path / "vide.txt"
    vide.write_text("  \n\n", encoding="utf-8")
    absent = tmp_path / "absent.docx"

    for fichier in (pdf, vide, absent):
        assert not page.importer(fichier)
    assert [titre for titre, _ in avertissements] == ["Import impossible"] * 3
    assert "PDF" in avertissements[0][1]
    assert avertissements[1][1] == "« vide.txt » ne contient pas de texte."
    assert "absent.docx" in avertissements[2][1]
    assert page.texte() == ARTICLE_106 and page.fichier is None
    assert page.traduction.texte == ARTICLE_106_AR


# ------------------------------------------------------------------ export
@pytest.mark.parametrize("extension", [".docx", ".txt"])
def test_exporter_la_traduction(fenetre, page, avertissements, tmp_path, extension):
    traduire(page, ARTICLE_106 + "\nLa vente du bien.")
    fichier = tmp_path / f"traduction{extension}"
    assert page.exporter(fichier)
    assert avertissements == []
    assert documents.lire(fichier) == "العقد شريعة المتعاقدين.\nالبيع du bien."
    assert fenetre.barre_etat.texte() == f"Traduction enregistrée : traduction{extension}"


def test_exporter_sans_traduction(fenetre, page, tmp_path):
    fichier = tmp_path / "rien.docx"
    assert not page.exporter(fichier)
    assert not fichier.exists()
    assert fenetre.barre_etat.texte() == "Il n’y a pas encore de traduction à exporter."


def test_export_par_la_fenetre_d_enregistrement(fenetre, page, monkeypatch, tmp_path):
    source = tmp_path / "Article 106.docx"
    documents.ecrire(source, ARTICLE_106, FR)
    assert page.importer(source)
    demandes = []

    def choisir(parent, titre, propose, filtres):
        demandes.append((titre, propose, filtres))
        # L'utilisateur saisit un nom sans extension et choisit le format « texte ».
        return str(tmp_path / "ma traduction"), documents.FILTRES_EXPORT[".txt"]

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(choisir))
    fenetre.action_exporter.trigger()  # Fichier → Exporter la traduction (Ctrl+E)
    titre, propose, filtres = demandes[0]
    assert titre == "Exporter la traduction"
    # Le nom proposé reprend celui du fichier importé, dans le même dossier.
    assert propose == str(tmp_path / "Article 106_traduction.docx")
    assert filtres.split(";;") == list(documents.FILTRES_EXPORT.values())
    assert (tmp_path / "ma traduction.txt").read_text(encoding="utf-8-sig") == ARTICLE_106_AR

    # Fenêtre fermée sans enregistrer.
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *arguments: ("", "")))
    assert not page.exporter()

    # Texte saisi à la main : le fichier est proposé dans le dossier « Documents ».
    page.effacer()
    traduire(page, ARTICLE_106)
    monkeypatch.setattr(QStandardPaths, "writableLocation", staticmethod(lambda emplacement: str(tmp_path / "docs")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(choisir))
    fenetre.bouton_exporter.click()
    assert demandes[-1][1] == str(tmp_path / "docs" / "traduction.docx")


def test_export_impossible(page, avertissements, tmp_path):
    traduire(page, ARTICLE_106)
    assert not page.exporter(tmp_path / "dossier absent" / "traduction.docx")
    assert not page.exporter(tmp_path / "traduction.pdf")
    assert [titre for titre, _ in avertissements] == ["Export impossible"] * 2


# ------------------------------------------------------------------ glossaire
def test_changer_de_glossaire_refait_la_traduction(fenetre, page, tmp_path):
    traduire(page, "Le juge applique la loi.")
    assert page.traduction.texte == "القاضي applique القانون."
    assert termes_du_tableau(page) == ["juge", "loi"]
    fichier = tmp_path / "autre.csv"
    fichier.write_text("terme_fr;terme_ar\njuge;حاكم\n", encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)
    assert page.traduction.texte == "الحاكم applique la loi."
    assert termes_du_tableau(page) == ["juge"]
    assert resultats_des_etapes(page)[2] == "2 mots sur 5"
    # Ce glossaire n'a ni définition ni ressource : la ligne le dit, la légende disparaît.
    ligne = page.termes.lignes_affichees()[0]
    assert (ligne.definition, ligne.ressource, ligne.grammaire) == ("", "", "")
    assert page.termes.legende.libelles() == []


def test_sans_glossaire(application, reglages, avertissements, tmp_path, monkeypatch):
    monkeypatch.setattr("traducteur.interface.fenetre.GLOSSAIRE_EXEMPLE", tmp_path / "absent.csv")
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    application.processEvents()
    page = fenetre.page_texte
    fenetre.definir_mode(MODE_TEXTE)
    assert page.badge.isVisible() and page.badge.texte() == "Aucun glossaire chargé"
    assert message_du_tableau(page) == ("Aucun glossaire n’est chargé",
                                        "Ouvrez un fichier CSV : menu Fichier → Ouvrir un glossaire.")
    traduire(page, ARTICLE_106)
    assert page.traduction is None
    assert fenetre.barre_etat.texte().startswith("Aucun glossaire n’est chargé")
    fenetre.close()
    fenetre.deleteLater()


# ------------------------------------------------------------------ fenêtre étroite
def test_avant_la_traduction_les_etapes_ne_sont_jamais_coupees(fenetre, page, application):
    """Le nom de chaque étape passe à sa forme courte plutôt que d'être coupé par « … »."""
    for largeur in (1440, 1280, 1100, 900):
        fenetre.resize(largeur, 700)
        application.processEvents()
        for (nom_affiche, resultat), (nom, nom_court, _) in zip(page.bande.textes_affiches(), ETAPES, strict=True):
            assert nom_affiche in (nom, nom_court) and resultat == "", largeur
    fenetre.resize(1440, 860)
    application.processEvents()
    assert [nom for nom, _ in page.bande.textes_affiches()] == [nom for nom, _, _ in ETAPES]


def test_les_etapes_sont_abregees_dans_une_fenetre_etroite(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    assert page.bande.textes_affiches()[2] == ("Recherche dans le CSV", "83 mots sur 84")

    fenetre.resize(900, 560)
    application.processEvents()
    # Noms courts, jamais coupés par « … » ; les résultats raccourcissent, ou disparaissent.
    affiches = page.bande.textes_affiches()
    assert [nom for nom, _ in affiches] == [nom_court for _, nom_court, _ in ETAPES]
    for (_, resultat), etape in zip(affiches, page.bande.etapes, strict=True):
        assert resultat in (etape.resultat, etape.resultat_court, "")
    assert page.bande.etapes[2].resultat_court == "83 / 84"
    assert "Résultat : 83 mots sur 84." in page.bande.infobulle(2)  # l'infobulle garde la forme longue
    # Les zones de texte et le tableau gardent une hauteur utilisable.
    assert page.zone_source.height() >= 56 and page.termes.defilement.height() >= 62

    fenetre.resize(1440, 860)
    application.processEvents()
    assert page.bande.textes_affiches()[2] == ("Recherche dans le CSV", "83 mots sur 84")


def test_l_ecran_s_adapte_a_une_fenetre_etroite(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    longue = "Traduction partielle · 83 mots sur 84 trouvés"
    assert page.badge.texte_affiche() == longue
    assert page.aide_outils.text() == page.aide_outils.texte_complet()  # le rappel des formats est affiché
    assert [libelle for _, _, libelle, _ in page.legende.reperes_affiches()] == page.legende.libelles()
    assert page.decompte_cible.text() == "5 phrases · 54 mots · 321 caractères"

    fenetre.resize(900, 560)
    application.processEvents()
    # L'état de la traduction prend une forme courte ; sa forme longue reste connue.
    assert page.badge.texte_affiche() in ("Traduction partielle · 83 / 84", "Traduction partielle")
    assert page.badge.texte() == longue
    # Le rappel des formats laisse sa place aux boutons ; les trois boutons restent entiers.
    assert page.aide_outils.text() == ""
    assert fenetre.bouton_importer.width() == fenetre.bouton_exporter.width() == 116
    assert page.bouton_traduire.width() == 132
    assert page.bouton_traduire.mapTo(fenetre, page.bouton_traduire.rect().topRight()).x() <= 900 - theme.MARGE
    # La légende garde d'abord son repère le plus utile ; le décompte se réduit, sans être coupé.
    visibles = [libelle for _, _, libelle, _ in page.legende.reperes_affiches()]
    assert visibles in (["terme du glossaire", "mot absent, à traduire"], ["mot absent, à traduire"], [])
    assert page.decompte_cible.text() in ("5 phrases · 54 mots · 321 caractères", "5 phrases · 54 mots", "54 mots")
    assert page.bouton_copier.width() == 96 and page.bouton_effacer.width() == 84
