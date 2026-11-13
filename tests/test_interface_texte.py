"""Écran « Texte » : saisie, traduction, informations sur les termes, import et export (tests exécutés sans écran).

L'écran a deux colonnes. À gauche, de haut en bas : le texte, les cinq étapes du traitement, la
traduction. À droite : une carte par terme juridique du texte, avec les cinq champs de
l'enchaînement (terme, définition, équivalent, contextualisation, ressources).

Comme dans ``test_interface.py``, les tests ne dépendent pas de la police du système : les textes
qui se raccourcissent selon la place sont comparés à leurs formes prévues, pas à une valeur exacte.
"""

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton
from test_documents import fabriquer_doc
from test_interface import textes

from traducteur import documents
from traducteur.interface import theme
from traducteur.interface.composants import MARQUE_RTL
from traducteur.interface.dessin import extrait_autour, police, sur_une_ligne
from traducteur.interface.fenetre import MODE_TERME, MODE_TEXTE, FenetrePrincipale
from traducteur.interface.termes import CarteTerme
from traducteur.interface.texte import ETAPES, EXEMPLES, PARTS
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


def termes_des_cartes(page) -> list[str]:
    """Le terme de chaque carte, dans l'ordre des cartes."""
    return [carte.libelle for carte in page.termes.cartes]


def message_des_termes(page) -> tuple[str, str]:
    """Le message affiché à la place des cartes quand aucun terme n'est à montrer."""
    return page.termes.message.titre, page.termes.message.texte


def contenu(carte: CarteTerme) -> list[str]:
    """Les textes écrits dans une carte ouverte, de haut en bas."""
    return textes(carte.corps)


def sens_d_ecriture(zone) -> Qt.LayoutDirection:
    """Sens d'écriture du texte d'une zone."""
    return zone.document().defaultTextOption().textDirection()


# ------------------------------------------------------------------ les deux écrans
def test_la_barre_laterale_affiche_l_ecran_texte(fenetre, application):
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.page.barre.isVisible()
    assert not fenetre.bouton_importer.isVisible() and not fenetre.page_texte.bouton_traduire.isVisible()

    fenetre.rail.boutons[MODE_TEXTE].click()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE
    assert fenetre.pile.currentWidget() is fenetre.page_texte
    assert fenetre.rail.boutons[MODE_TEXTE].isChecked() and fenetre.actions_mode[MODE_TEXTE].isChecked()
    # La barre d'outils montre les commandes de l'écran : importer, exporter, traduire.
    assert fenetre.bouton_importer.isVisible() and fenetre.bouton_exporter.isVisible()
    assert fenetre.page_texte.bouton_traduire.isVisible() and not fenetre.page.barre.isVisible()
    assert fenetre.page_texte.zone_source.hasFocus()

    fenetre.actions_mode[MODE_TERME].trigger()  # menu Affichage → Recherche d'un terme (Ctrl+1)
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.rail.boutons[MODE_TERME].isChecked() and fenetre.page.barre.isVisible()


def test_le_texte_et_sa_traduction_sont_a_gauche_les_informations_a_droite(fenetre, page, application):
    def haut(widget) -> int:
        return widget.mapTo(page, QPoint(0, 0)).y()

    def gauche(widget) -> int:
        return widget.mapTo(page, QPoint(0, 0)).x()

    for taille in ((1440, 860), (1080, 620), (900, 560)):
        fenetre.resize(*taille)
        application.processEvents()
        # À gauche, de haut en bas : le texte, les étapes, la traduction ; les trois ont la même largeur.
        assert gauche(page.cadre_source) == gauche(page.bande) == gauche(page.cadre_cible) == theme.MARGE, taille
        assert page.cadre_source.width() == page.bande.width() == page.cadre_cible.width(), taille
        assert haut(page.cadre_source) + page.cadre_source.height() <= haut(page.bande), taille
        assert haut(page.bande) + page.bande.height() <= haut(page.cadre_cible), taille
        assert abs(page.cadre_source.height() - page.cadre_cible.height()) <= 1, taille
        # À droite, sur toute la hauteur : les informations sur les termes.
        assert gauche(page.termes) >= gauche(page.cadre_source) + page.cadre_source.width(), taille
        assert haut(page.termes) == haut(page.cadre_source), taille
        assert page.termes.height() == page.colonne_textes.height(), taille
        assert gauche(page.termes) + page.termes.width() == page.width() - theme.MARGE, taille
        # Les deux colonnes se partagent la largeur selon ``PARTS``.
        part = page.colonne_textes.width() / (page.colonne_textes.width() + page.termes.width())
        assert abs(part - PARTS[0] / sum(PARTS)) < 0.01, taille


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
    assert page.bande.allumage.allumees() == [False] * 5  # aucune étape n'est allumée
    assert page.termes.cartes == [] and not page.termes.nombre.isVisible()
    assert not page.termes.bouton_tout.isVisible() and not page.termes.aide.isVisible()
    assert message_des_termes(page) == ("Les termes juridiques du texte s’afficheront ici",
                                        "Saisissez ou importez un texte, puis cliquez sur « Traduire ».")
    # Rien à effacer, à copier ni à exporter tant qu'il n'y a ni texte ni traduction.
    assert not page.bouton_effacer.isEnabled() and not page.bouton_copier.isEnabled()
    assert not fenetre.bouton_exporter.isEnabled()
    assert not fenetre.action_exporter.isEnabled() and not fenetre.action_copier.isEnabled()
    assert fenetre.barre_etat.texte() == ""


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


def test_une_carte_par_terme(page):
    page.inserer_un_exemple()
    page.traduire()
    panneau = page.termes
    assert termes_des_cartes(page) == [
        "contrat", "loi", "partie", "consentement", "bonne foi", "contractant", "usage", "équité", "obligation",
        "nullité", "contrat de vente", "acheteur"]
    assert panneau.titre.text() == "Termes juridiques détectés"
    assert panneau.nombre.isVisible() and panneau.nombre.text() == "12"
    assert panneau.aide.texte_complet() == "Cliquez sur un terme pour afficher ses informations"
    assert panneau.defilement.isVisible() and not panneau.message.isVisible()
    # La première carte est ouverte, les autres sont fermées : leur contenu n'est pas encore construit.
    assert [carte.ouverte for carte in panneau.cartes] == [True] + [False] * 11
    assert all(carte.corps is None for carte in panneau.cartes[1:])

    # ① L'en-tête de la carte : le terme, sa catégorie, ses occurrences ; à droite, l'équivalent.
    carte = panneau.cartes[0]
    assert carte.entete.text() == "contrat — عقد"
    assert (carte.libelle, carte.categorie, carte.occurrences) == ("contrat", "nom masculin", "3 occurrences")
    assert (carte.equivalent, carte.grammaire, carte.alerte) == ("عقد", "اسم مذكر، ج. عقود", "")
    # ② La définition, dans la langue du texte puis dans l'autre langue, et sa source.
    assert [langue for langue, _ in carte.definitions] == [FR, AR]
    assert carte.definition.startswith("Convention par laquelle une ou plusieurs personnes s’obligent")
    assert not carte.a_verifier  # sa définition cite sa source
    lignes = contenu(carte)
    assert lignes[:2] == ["DÉFINITION", "Source : Code civil, art. 54"]
    assert lignes[2].endswith("à donner, à faire ou à ne pas faire quelque chose.") and lignes[3].startswith("اتفاق")
    # ③ L'équivalent, sa grammaire, les autres équivalents.
    rang = lignes.index("ÉQUIVALENT")
    assert lignes[rang + 1:rang + 4] == ["عقد", "اسم مذكر، ج. عقود", "اتفاق"]
    # ④ La phrase du texte et sa traduction, le terme en évidence ; puis les contextes du glossaire.
    assert carte.passage_source == (ARTICLE_106, [(3, 10)])
    assert carte.passage_cible == (ARTICLE_106_AR, [(0, 5)])
    rang = lignes.index("CONTEXTUALISATION")
    assert lignes[rang + 1:rang + 4] == ["Dans le texte", ARTICLE_106, ARTICLE_106_AR]
    # ⑤ Puis les ressources et, au pied de la carte, le lien vers la fiche complète.
    assert "RESSOURCES" in lignes[rang:]
    assert carte.lien_fiche.text() == "Ouvrir la fiche du terme"
    assert carte.lien_fiche.toolTip() == "Afficher « contrat » sur l’écran « Terme »"

    # « loi » : sa définition n'est reprise d'aucune source citée.
    loi = panneau.cartes[1]
    loi.definir_ouverte(True)
    assert loi.a_verifier and contenu(loi)[:2] == ["DÉFINITION", "À vérifier"]


def test_toutes_les_references_sont_ecrites_en_entier(page):
    """Aucun compteur du genre « +3 » : chaque référence de l'entrée est écrite, en entier."""
    page.inserer_un_exemple()
    page.traduire()
    carte = page.termes.cartes[0]
    assert len(carte.ressources) == 4 and carte.ressources == carte.entree.ressources
    lignes = contenu(carte)
    references = lignes[lignes.index("RESSOURCES") + 1:]
    assert references == [
        "Code civil algérien\nordonnance n° 75-58 du 26 septembre 1975, art. 54, 106 et 107",
        "القانون المدني\nالأمر رقم 75-58 المؤرخ في 26 سبتمبر 1975، المواد 54 و106 و107",
        "Journal officiel (JORADP) n° 78 du 30 septembre 1975\nwww.joradp.dz\u00a0↗",
        "G. Cornu (dir.)\nVocabulaire juridique, Association Henri Capitant, PUF"]
    assert not any(re.search(r"\+\s?\d", ligne) for ligne in lignes)
    # L'adresse d'un site est un lien.
    liens = [label.text() for label in carte.corps.findChildren(QLabel) if "<a href" in label.text()]
    assert len(liens) == 1 and 'href="https://www.joradp.dz"' in liens[0]


def test_les_contextes_d_un_terme_du_texte(page):
    """④ Chaque terme a au moins son passage du texte ; le glossaire fournit d'autres emplois."""
    traduire(page, "Le vendeur et l’acheteur signent le contrat de vente.")
    assert termes_des_cartes(page) == ["vendeur", "acheteur", "contrat de vente"]
    for carte in page.termes.cartes:
        carte.definir_ouverte(True)
        assert carte.etapes_renseignees()[3]
        assert "Dans le texte" in contenu(carte)
    vendeur, _, vente = page.termes.cartes
    # « vendeur » : l'exemple de son entrée, puis une définition du glossaire qui emploie le terme.
    assert [(emploi.origine, emploi.provenance()) for emploi in vendeur.emplois] == [
        ("propre", "Code civil, art. 351"), ("definition", "Définition de « prix »")]
    lignes = contenu(vendeur)
    assert "Dans le glossaire · Code civil, art. 351" in lignes
    assert "Dans le glossaire · Définition de « prix »" in lignes
    # « contrat de vente » n'a pas d'exemple : ses deux contextes viennent d'autres entrées.
    assert vente.entree.contextes == []
    assert [emploi.provenance() for emploi in vente.emplois] == [
        "Définition de « acheteur »", "Définition de « vendeur »"]
    lignes = contenu(vente)
    rang = lignes.index("Dans le glossaire · Définition de « acheteur »")
    assert lignes[rang + 1:rang + 3] == ["Partie au contrat de vente qui acquiert la chose et doit en payer le prix.",
                                         "الطرف في عقد البيع الذي يكتسب الشيء ويلتزم بدفع ثمنه."]


def test_un_exemple_identique_au_passage_n_est_pas_repete(page):
    traduire(page, ARTICLE_106)
    carte = page.termes.cartes[0]
    assert carte.passage_source[0] == ARTICLE_106
    # « Le contrat fait la loi des parties. » est aussi le premier exemple de l'entrée « contrat ».
    assert carte.entree.contextes[0].fr == ARTICLE_106
    assert ARTICLE_106 not in [emploi.fr for emploi in carte.emplois] and len(carte.emplois) == 2
    assert contenu(carte).count(ARTICLE_106) == 1


def test_l_en_tete_d_une_carte_s_ajuste_a_la_largeur(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    entete = page.termes.cartes[0].entete
    # Sous le terme : la catégorie et le nombre d'occurrences.
    assert entete.sous_le_terme() == ("nom masculin", "3 occurrences")
    gauche, place_du_terme, debut_de_l_equivalent, place_de_l_equivalent = entete.places()
    assert gauche + place_du_terme < debut_de_l_equivalent
    assert debut_de_l_equivalent + place_de_l_equivalent < entete.width()
    fenetre.resize(900, 560)
    application.processEvents()
    # Fenêtre étroite : « occurrences » est abrégé, puis la catégorie retirée ; rien ne se chevauche.
    assert entete.sous_le_terme() in (("nom masculin", "3 occurrences"), ("nom masculin", "3 occ."),
                                      ("", "3 occurrences"), ("", "3 occ."))
    gauche, place_du_terme, debut_de_l_equivalent, place_de_l_equivalent = entete.places()
    assert place_du_terme >= 90 and place_de_l_equivalent >= 60
    assert debut_de_l_equivalent + place_de_l_equivalent < entete.width()


def test_ouvrir_et_refermer_les_cartes(page, application):
    page.inserer_un_exemple()
    page.traduire()
    panneau = page.termes
    premiere, deuxieme = panneau.cartes[:2]
    assert panneau.bouton_tout.isVisible() and panneau.bouton_tout.text() == "Tout développer"
    # Un clic sur l'en-tête ouvre ou referme la carte ; les autres ne changent pas.
    deuxieme.entete.click()
    assert deuxieme.ouverte and premiere.ouverte and deuxieme.corps.isVisible()
    premiere.entete.click()
    assert not premiere.ouverte and not premiere.corps.isVisible() and deuxieme.ouverte
    # « Tout développer » ouvre toutes les cartes ; le bouton propose alors de tout réduire.
    panneau.bouton_tout.click()
    assert panneau.tout_ouvert() and all(carte.corps is not None for carte in panneau.cartes)
    assert panneau.bouton_tout.text() == "Tout réduire"
    panneau.bouton_tout.click()
    assert not any(carte.ouverte for carte in panneau.cartes) and panneau.bouton_tout.text() == "Tout développer"
    # Ouvrir la dernière carte à la main ne suffit pas : toutes ne sont pas ouvertes.
    panneau.cartes[-1].entete.click()
    assert panneau.bouton_tout.text() == "Tout développer"


def test_le_pointeur_d_attente_s_affiche_pendant_une_operation_longue(page, monkeypatch):
    """Traduire un long texte ou ouvrir toutes les cartes peut durer : le pointeur d'attente l'indique."""
    pointeurs = []

    def relever() -> None:
        pointeur = QGuiApplication.overrideCursor()
        pointeurs.append(None if pointeur is None else pointeur.shape())

    # Pendant la traduction.
    traduire_vraiment = page.traducteur.traduire
    monkeypatch.setattr(page.traducteur, "traduire", lambda *arguments: (relever(), traduire_vraiment(*arguments))[1])
    page.inserer_un_exemple()
    page.traduire()
    assert pointeurs == [Qt.CursorShape.WaitCursor] and QGuiApplication.overrideCursor() is None
    assert page.traduction is not None and len(page.termes.cartes) > 2
    # Pendant « Tout développer ».
    derniere = page.termes.cartes[-1]
    ouvrir_vraiment = derniere.definir_ouverte
    monkeypatch.setattr(derniere, "definir_ouverte",
                        lambda ouverte, **options: (relever(), ouvrir_vraiment(ouverte, **options))[1])
    page.termes.bouton_tout.click()
    assert pointeurs == [Qt.CursorShape.WaitCursor] * 2 and QGuiApplication.overrideCursor() is None
    assert page.termes.tout_ouvert()


def test_le_pointeur_est_retabli_si_la_traduction_echoue(page, monkeypatch):
    def echouer(*arguments):
        raise RuntimeError("panne")

    monkeypatch.setattr(page.traducteur, "traduire", echouer)
    page.inserer_un_exemple()
    with pytest.raises(RuntimeError):
        page.traduire()
    assert QGuiApplication.overrideCursor() is None


def test_un_seul_terme_n_a_pas_de_bouton_tout_developper(page):
    traduire(page, "Le juge.")
    assert termes_des_cartes(page) == ["juge"] and page.termes.cartes[0].ouverte
    assert not page.termes.bouton_tout.isVisible() and page.termes.nombre.text() == "1"


def point_du_mot(zone, mot: str) -> QPoint:
    """Le point de la zone où est écrit le milieu d'un mot."""
    position = zone.toPlainText().index(mot) + len(mot) // 2
    curseur = zone.textCursor()
    curseur.setPosition(position)
    return zone.cursorRect(curseur).center()


def test_cliquer_sur_un_terme_du_texte_ouvre_sa_carte(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    panneau = page.termes
    # Dans le texte source : « consentement ».
    point = point_du_mot(page.zone_source, "consentement")
    assert page.terme_a(page.zone_source, point).terme_fr == "consentement"
    QTest.mouseClick(page.zone_source.viewport(), Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert [carte.libelle for carte in panneau.cartes if carte.ouverte] == ["consentement"]
    # Dans la traduction : « القانون » (loi).
    point = point_du_mot(page.zone_cible, "القانون")
    assert page.terme_a(page.zone_cible, point).terme_fr == "loi"
    QTest.mouseClick(page.zone_cible.viewport(), Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert [carte.libelle for carte in panneau.cartes if carte.ouverte] == ["loi"]
    # Un mot qui n'est pas un terme du glossaire ne change rien.
    point = point_du_mot(page.zone_source, "mutuel")
    assert page.terme_a(page.zone_source, point) is None
    QTest.mouseClick(page.zone_source.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert [carte.libelle for carte in panneau.cartes if carte.ouverte] == ["loi"]


def test_les_etapes_d_une_carte_s_allument(page):
    page.inserer_un_exemple()
    page.traduire()
    carte = page.termes.cartes[0]
    # Les cinq champs de « contrat » sont renseignés : les cinq numéros sont allumés.
    assert carte.etapes_renseignees() == [True] * 5
    assert carte.allumage.allumees() == [True] * 5
    # La bande du traitement est allumée elle aussi, étape par étape.
    assert page.bande.allumage.allumees() == [True] * 5


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
    assert page.termes.cartes == [] and page.termes.message.isVisible()
    assert page.termes.nombre.isVisible() and page.termes.nombre.text() == "0"
    assert not page.termes.aide.isVisible() and not page.termes.bouton_tout.isVisible()
    assert message_des_termes(page) == ("Aucun terme du glossaire dans ce texte",
                                        "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
    assert fenetre.barre_etat.texte() == "Traduction : 0 mot sur 6 trouvé dans le glossaire."


def test_un_terme_ambigu_est_signale_dans_sa_carte(page):
    traduire(page, "Le droit et le juge.")
    droit, juge = page.termes.cartes
    assert (droit.libelle, droit.equivalent) == ("droit", "حق")
    # « droit » a deux sens dans le glossaire et rien, dans la phrase, ne permet de choisir.
    assert droit.incertain and droit.alerte == "Ambigu : aussi « قانون »"
    assert ("Ambigu : aussi « قانون ». Le contexte n’a pas permis de choisir entre les sens de ce terme : "
            "vérifiez l’équivalent.") in contenu(droit)
    juge.definir_ouverte(True)
    assert not juge.incertain and juge.alerte == ""
    assert not any("Ambigu" in ligne for ligne in contenu(juge))


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
    # Dans la carte du terme, le passage cité garde lui aussi ses signes.
    carte = page.termes.cartes[0]
    assert carte.passage_source[0] == "Le <b>contrat</b> & la loi : a < b > c « d »"
    assert "Le <b>contrat</b> & la loi : a < b > c « d »" in contenu(carte)
    passage = next(label.text() for label in carte.corps.findChildren(QLabel) if "&lt;b&gt;" in label.text())
    assert (f'&lt;b&gt;<span style="color: {theme.BLEU_FONCE}; font-weight: 600;">contrat</span>&lt;/b&gt; &amp;'
            in passage)


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
    assert fenetre.sens.source.text() == "العربية" and fenetre.sens.cible.text() == "Français"
    assert page.panneau_source.nom.text() == "العربية" and page.panneau_cible.nom.text() == "Français"
    assert (sens_d_ecriture(page.zone_source), sens_d_ecriture(page.zone_cible)) == (DROITE_A_GAUCHE, GAUCHE_A_DROITE)
    # Seul le texte change de sens : la barre de défilement de chaque zone reste à droite.
    assert page.zone_source.layoutDirection() == page.zone_cible.layoutDirection() == GAUCHE_A_DROITE
    assert page.zone_cible.invite() == "La traduction s’affichera ici."
    assert fenetre.barre_etat.texte() == "Texte écrit en arabe : le sens de traduction a été inversé."
    assert fenetre.barre_etat.etat() == "Traduction : 3 mots sur 4 trouvés dans le glossaire."
    # Les cartes sont écrites dans la langue source : le terme arabe, puis son équivalent français.
    assert termes_des_cartes(page) == ["بطلان", "عقد", "مشترٍ"]
    carte = page.termes.cartes[1]
    assert carte.equivalent == "contrat" and carte.entete.text() == "عقد — contrat"
    carte.definir_ouverte(True)
    # La définition arabe vient en premier ; le passage du texte aussi.
    assert [langue for langue, _ in carte.definitions] == [AR, FR]
    lignes = contenu(carte)
    rang = lignes.index("Dans le texte")
    assert lignes[rang + 1:rang + 3] == ["بطلان العقد يحمي المشتري.", "La nullité du contrat يحمي l’acheteur."]


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
    assert fenetre.sens.source.text() == "العربية" and fenetre.sens.cible.text() == "Français"
    fenetre.definir_mode(MODE_TERME)
    assert fenetre.sens.source.text() == "Français" and fenetre.sens.cible.text() == "العربية"
    fenetre.definir_mode(MODE_TEXTE)
    assert fenetre.sens.source.text() == "العربية"


def test_l_exemple_suit_le_sens_de_traduction(fenetre, page):
    fenetre.bouton_inverser.click()
    page.lien_exemple.click()
    assert page.texte() == EXEMPLES[AR]
    page.bouton_traduire.click()
    assert page.source == AR
    assert page.traduction.texte.startswith("Le contrat fait la loi des parties. Il ne peut être révoqué")
    assert page.traduction.phrases_attestees == 4


# ------------------------------------------------------------------ du texte à la fiche d'un terme
def test_le_lien_d_une_carte_ouvre_la_fiche_du_terme(fenetre, page):
    traduire(page, "La nullité du contrat de vente protège l’acheteur.")
    assert termes_des_cartes(page) == ["nullité", "contrat de vente", "acheteur"]
    carte = page.termes.cartes[1]
    carte.entete.click()  # l'en-tête ouvre la carte : on reste sur l'écran « Texte »
    assert carte.ouverte and fenetre.mode == MODE_TEXTE
    carte.lien_fiche.click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.page.entree.terme_fr == "contrat de vente"
    assert fenetre.page.entree.terme_ar == "عقد البيع"
    assert fenetre.page.champ.text() == "contrat de vente"
    # Le texte et sa traduction sont conservés quand on revient à l'écran « Texte ».
    fenetre.definir_mode(MODE_TEXTE)
    assert page.traduction is not None and len(page.termes.cartes) == 3


def test_la_fiche_s_ouvre_dans_le_sens_du_texte(fenetre, page):
    traduire(page, "بطلان العقد يحمي المشتري.")
    page.termes.cartes[0].lien_fiche.click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.page.source == AR
    assert fenetre.page.entree.terme_ar == "بطلان"
    assert fenetre.sens.source.text() == "العربية"


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
    assert page.termes.cartes == []
    assert resultats_des_etapes(page) == [""] * 5 and page.bande.allumage.allumees() == [False] * 5
    assert not fenetre.bouton_exporter.isEnabled() and not page.bouton_effacer.isEnabled()
    assert fenetre.barre_etat.texte() == ""

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
    assert termes_des_cartes(page) == ["juge", "loi"]
    fichier = tmp_path / "autre.csv"
    fichier.write_text("terme_fr;terme_ar\njuge;حاكم\n", encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)
    assert page.traduction.texte == "الحاكم applique la loi."
    assert termes_des_cartes(page) == ["juge"]
    assert resultats_des_etapes(page)[2] == "2 mots sur 5"
    # Ce glossaire n'a ni définition ni ressource : la carte le dit, et ces deux étapes restent éteintes.
    carte = page.termes.cartes[0]
    assert (carte.definition, carte.ressources, carte.grammaire) == ("", [], "")
    assert carte.etapes_renseignees() == [True, False, True, True, False]
    assert carte.allumage.allumees() == [True, False, True, True, False]
    lignes = contenu(carte)
    assert "Aucune définition dans le glossaire." in lignes and "Aucune ressource dans le glossaire." in lignes
    assert "Dans le texte" in lignes  # le passage du texte reste le contexte du terme


def test_sans_glossaire(application, reglages, avertissements, tmp_path, monkeypatch):
    monkeypatch.setattr("traducteur.interface.fenetre.GLOSSAIRE_EXEMPLE", tmp_path / "absent.csv")
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    application.processEvents()
    page = fenetre.page_texte
    fenetre.definir_mode(MODE_TEXTE)
    assert page.badge.isVisible() and page.badge.texte() == "Aucun glossaire chargé"
    assert message_des_termes(page) == ("Aucun glossaire n’est chargé",
                                        "Choisissez un fichier CSV dans « Paramètres ».")
    traduire(page, ARTICLE_106)
    assert page.traduction is None
    assert fenetre.barre_etat.texte().startswith("Aucun glossaire n’est chargé")
    fenetre.close()
    fenetre.deleteLater()


# ------------------------------------------------------------------ fenêtre étroite
def test_avant_la_traduction_les_etapes_ne_sont_jamais_coupees(fenetre, page, application):
    """Le nom de chaque étape passe à sa forme courte, puis disparaît, plutôt que d'être coupé par « … »."""
    for largeur in (1900, 1440, 1280, 1100, 900):
        fenetre.resize(largeur, 700)
        application.processEvents()
        affiches = page.bande.textes_affiches()
        for (nom_affiche, resultat), (nom, nom_court, _) in zip(affiches, ETAPES, strict=True):
            assert nom_affiche in (nom, nom_court, "") and resultat == "", largeur
        # Les cinq étapes ont la même forme : toutes nommées, ou aucune.
        assert len({bool(nom) for nom, _ in affiches}) == 1, largeur
        # Les étapes tiennent dans la bande, sans se chevaucher.
        _, abscisses, ecart = page.bande.disposition()
        assert abscisses[0] == page.bande.MARGE and abscisses == sorted(abscisses) and ecart >= 4, largeur
    fenetre.resize(1900, 860)
    application.processEvents()
    assert [nom for nom, _ in page.bande.textes_affiches()] == [nom_court for _, nom_court, _ in ETAPES]
    assert not page.bande.empilee()


def test_les_etapes_sont_abregees_dans_une_fenetre_etroite(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    fenetre.resize(1900, 860)
    application.processEvents()
    assert page.bande.textes_affiches()[2] == ("Recherche", "83 mots sur 84") and not page.bande.empilee()

    fenetre.resize(1100, 700)
    application.processEvents()
    # Bande étroite : les noms sont gardés, ou retirés ; ils ne sont jamais coupés par « … ».
    affiches = page.bande.textes_affiches()
    assert [nom for nom, _ in affiches] in ([nom_court for _, nom_court, _ in ETAPES], [""] * 5)
    for (_, resultat), etape in zip(affiches, page.bande.etapes, strict=True):
        assert resultat in (etape.resultat, etape.resultat_court, "")

    fenetre.resize(900, 560)
    application.processEvents()
    affiches = page.bande.textes_affiches()
    for (nom, resultat), etape in zip(affiches, page.bande.etapes, strict=True):
        assert nom in (etape.nom_court, "") and resultat in (etape.resultat_court, "")
    assert page.bande.etapes[2].resultat_court == "83 / 84"
    assert "<b>3. Recherche dans le glossaire</b>" in page.bande.infobulle(2)  # l'infobulle garde le nom entier…
    assert "Résultat : 83 mots sur 84." in page.bande.infobulle(2)  # … et le résultat en toutes lettres
    # Les zones de texte et les cartes gardent une hauteur utilisable.
    assert page.zone_source.height() >= 56 and page.zone_cible.height() >= 56
    assert page.termes.defilement.height() >= 200


def test_les_formes_de_la_bande_des_etapes(page, application):
    """De la plus large à la plus étroite : noms et résultats, formes courtes, noms sous les numéros, numéros seuls."""
    page.inserer_un_exemple()
    page.traduire()
    bande = page.bande
    formes = bande._formes()
    assert formes[0] == (False, [(etape.nom, etape.resultat) for etape in bande.etapes])
    assert formes[-1] == (False, [("", "")] * 5)
    assert [empilee for empilee, _ in formes].count(True) == 1
    largeurs = [sum(bande._largeurs(empilee, forme)) for empilee, forme in formes]
    assert largeurs == sorted(largeurs, reverse=True)  # chaque forme est plus étroite que la précédente
    # La forme empilée garde les noms dans moins de place que la forme normale qui la précède.
    rang = next(rang for rang, (empilee, _) in enumerate(formes) if empilee)
    assert [nom for nom, _ in formes[rang][1]] == [etape.nom_court for etape in bande.etapes]
    assert formes[rang][1] == formes[rang - 1][1] and largeurs[rang] < largeurs[rang - 1]


def test_l_ecran_s_adapte_a_une_fenetre_etroite(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    longue = "Traduction partielle · 83 mots sur 84 trouvés"
    fenetre.resize(1900, 860)
    application.processEvents()
    assert page.badge.texte_affiche() == longue
    assert page.aide_outils.text() == page.aide_outils.texte_complet()  # le rappel des formats est affiché
    assert [libelle for _, _, libelle, _ in page.legende.reperes_affiches()] == page.legende.libelles()
    assert page.decompte_cible.texte_complet() == "5 phrases · 54 mots · 321 caractères"

    fenetre.resize(900, 560)
    application.processEvents()
    # L'état de la traduction prend une forme courte ; sa forme longue reste connue.
    assert page.badge.texte_affiche() in ("Traduction partielle · 83 / 84", "Traduction partielle")
    assert page.badge.texte() == longue
    # Le rappel des formats laisse sa place aux boutons ; les trois boutons restent entiers.
    assert page.aide_outils.text() == ""
    for bouton, largeur_prevue in ((fenetre.bouton_importer, 116), (fenetre.bouton_exporter, 116),
                                   (page.bouton_traduire, 132)):
        assert bouton.width() == max(largeur_prevue, QPushButton.sizeHint(bouton).width()), bouton.text()
    assert page.bouton_traduire.mapTo(fenetre, page.bouton_traduire.rect().topRight()).x() <= 900 - theme.MARGE
    assert fenetre.cadre_sens.isVisible() and fenetre.sens.width() >= 200
    # La légende garde d'abord son repère le plus utile ; le décompte se réduit, sans être coupé.
    visibles = [libelle for _, _, libelle, _ in page.legende.reperes_affiches()]
    assert visibles in (["terme du glossaire", "mot absent, à traduire"], ["mot absent, à traduire"], [])
    assert page.decompte_cible.text() in ("5 phrases · 54 mots · 321 caractères", "5 phrases · 54 mots", "54 mots")
    for bouton, largeur_prevue in ((page.bouton_copier, 96), (page.bouton_effacer, 84)):
        assert bouton.width() == max(largeur_prevue, QPushButton.sizeHint(bouton).width()), bouton.text()
