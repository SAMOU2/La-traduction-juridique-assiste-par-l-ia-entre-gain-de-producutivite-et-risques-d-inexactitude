"""Écran « Texte » : saisie, traduction, termes du texte, import et export (tests exécutés sans écran).

L'écran montre le texte et sa traduction, côte à côte. Dessous, une case par terme juridique du
texte : un clic sur une case, ou sur un terme coloré de l'un des deux textes, ouvre la fiche du
terme sur l'écran « Terme » ; le bouton « Retour au texte » ramène ici. Le terme que le pointeur
désigne s'allume dans le texte, dans la traduction et dans la liste. Les cinq étapes du
traitement ne sont pas affichées en permanence : un clic sur l'état de la traduction les ouvre
dans une petite fenêtre.

Comme dans ``test_interface.py``, les tests ne dépendent pas de la police du système : les textes
qui se raccourcissent selon la place sont comparés à leurs formes prévues, pas à une valeur exacte.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QObject, QPoint, QStandardPaths, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget
from test_documents import fabriquer_doc
from test_interface import points_de_couleur, textes

from traducteur import documents
from traducteur.interface import theme
from traducteur.interface.composants import MARQUE_RTL
from traducteur.interface.fenetre import MODE_PARAMETRES, MODE_TERME, MODE_TEXTE, FenetrePrincipale
from traducteur.interface.texte import ETAPES, EXEMPLES, BandeEtapes
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


def termes_detectes(page) -> list[str]:
    """Le terme français de chaque case, dans l'ordre des cases."""
    return [case.entree.terme_fr for case in page.termes.cellules]


def message_des_termes(page) -> tuple[str, str]:
    """Le message affiché à la place des cases quand aucun terme n'est à montrer."""
    return page.termes.message.titre, page.termes.message.texte


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


def test_le_texte_et_sa_traduction_sont_cote_a_cote_les_termes_dessous(fenetre, page, application):
    def haut(widget) -> int:
        return widget.mapTo(page, QPoint(0, 0)).y()

    def gauche(widget) -> int:
        return widget.mapTo(page, QPoint(0, 0)).x()

    source, cible, termes = page.cadre_source, page.cadre_cible, page.termes
    for traduit in (False, True):
        if traduit:
            page.inserer_un_exemple()
            page.traduire()
        for taille in ((1440, 860), (1080, 620), (900, 600)):
            fenetre.resize(*taille)
            application.processEvents()
            repere = (traduit, taille)
            # En haut, deux colonnes de même taille : le texte à gauche, sa traduction à droite.
            assert gauche(source) == theme.MARGE and haut(source) == haut(cible) == 0, repere
            assert abs(source.width() - cible.width()) <= 1 and source.height() == cible.height(), repere
            assert gauche(cible) == gauche(source) + source.width() + page.ECART, repere
            assert gauche(cible) + cible.width() == page.width() - theme.MARGE, repere
            # Dessous, sur toute la largeur : les termes juridiques du texte.
            assert gauche(termes) == theme.MARGE and termes.width() == page.width() - 2 * theme.MARGE, repere
            assert haut(termes) == haut(source) + source.height() + page.ECART, repere
            assert haut(termes) + termes.height() == page.height() - page.MARGE_BASSE, repere
            # Les termes n'occupent qu'une part de l'écran : les deux textes gardent l'essentiel de la hauteur.
            assert termes.height() <= termes.PART_DE_L_ECRAN * page.height() < source.height(), repere
            assert page.zone_source.height() >= 150 and page.zone_cible.height() >= 150, repere
    # Les étapes du traitement ne sont plus dans l'écran : elles s'ouvrent à la demande.
    assert not page.bande.isVisible() and not page.volet_etapes.isVisible()


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
    assert not page.bande.isVisible() and not page.volet_etapes.isVisible()  # elles s'ouvrent à la demande
    assert page.termes.titre.text() == "Termes juridiques détectés"
    assert page.termes.cellules == [] and not page.termes.nombre.isVisible() and not page.termes.aide.isVisible()
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
    assert "Cliquez pour voir les étapes du traitement." in page.badge.toolTip()
    # Pied des deux zones : décomptes, et légende des couleurs du texte traduit.
    assert page.decompte_source.texte_complet() == "5 phrases · 84 mots · 473 caractères"
    assert page.decompte_cible.texte_complet() == "5 phrases · 54 mots · 321 caractères"
    assert page.legende.libelles() == ["terme du glossaire", "mot absent, à traduire"]
    # Les cinq étapes et leur résultat (dans la petite fenêtre des étapes) ; le détail est dans leur infobulle.
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


def test_une_case_par_terme(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    panneau = page.termes
    assert termes_detectes(page) == [
        "contrat", "loi", "partie", "consentement", "bonne foi", "contractant", "usage", "équité", "obligation",
        "nullité", "contrat de vente", "acheteur"]
    assert panneau.titre.text() == "Termes juridiques détectés"
    assert panneau.nombre.isVisible() and panneau.nombre.text() == "12"
    assert panneau.aide.isVisible() and panneau.aide.texte_complet() == "Cliquez sur un terme pour ouvrir sa fiche"
    assert panneau.defilement.isVisible() and not panneau.message.isVisible()

    # Une case : le terme français à gauche, le terme arabe à droite. Rien d'autre n'y est écrit.
    case = panneau.cellules[0]
    assert case.text() == "contrat — عقد" and case.textes_affiches() == ("contrat", "عقد")
    assert case.detecte.entree is case.entree and panneau.cellule_de(case.entree) is case
    assert textes(panneau.grille) == []  # ni définition, ni exemple, ni référence : ils sont sur la fiche
    # L'infobulle donne le nombre d'occurrences du terme dans le texte.
    assert (case.occurrences, case.incertain, case.alerte, case.a_verifier) == ("3 occurrences", False, "", False)
    assert "contrat — عقد" in case.toolTip() and "3 occurrences dans le texte." in case.toolTip()
    assert case.accessibleDescription() == "3 occurrences"
    # Les cases se suivent de gauche à droite, puis de haut en bas : quatre colonnes dans la fenêtre de référence.
    grille = panneau.grille
    assert (grille.colonnes(), grille.rangees()) == (4, 3)
    premiere_ligne = panneau.cellules[:4]
    assert [autre.x() for autre in premiere_ligne] == sorted({autre.x() for autre in panneau.cellules})
    assert {autre.y() for autre in premiere_ligne} == {0} and panneau.cellules[4].y() == grille.HAUTEUR_DE_LIGNE
    assert all(autre.height() == grille.HAUTEUR_DE_LIGNE for autre in panneau.cellules)
    # Toutes sont visibles : le panneau a pris la hauteur de ses trois lignes.
    assert panneau.defilement.verticalScrollBar().maximum() == 0


def test_les_termes_defilent_quand_ils_sont_nombreux(fenetre, page, application):
    """Dans une petite fenêtre, la liste des termes ne prend qu'une part de l'écran : elle défile."""
    page.inserer_un_exemple()
    page.traduire()
    fenetre.resize(900, 600)
    application.processEvents()
    panneau, grille = page.termes, page.termes.grille
    assert (grille.colonnes(), grille.rangees()) == (3, 4)
    visibles = panneau.defilement.viewport().height() // grille.HAUTEUR_DE_LIGNE
    assert 1 <= visibles < 4 and panneau.defilement.verticalScrollBar().maximum() > 0
    assert panneau.height() == panneau.hauteur_pour(panneau.width(), page.height() - page.MARGE_BASSE)
    # Un seul terme : une seule ligne, et le texte garde toute la place.
    traduire(page, "Le juge.")
    application.processEvents()
    assert termes_detectes(page) == ["juge"] and panneau.nombre.text() == "1"
    assert panneau.height() == panneau.HAUTEUR_DU_TITRE + 1 + panneau.MARGE_BASSE + grille.HAUTEUR_DE_LIGNE
    assert panneau.defilement.verticalScrollBar().maximum() == 0


def test_les_informations_d_un_terme_du_texte_sont_sur_sa_fiche(fenetre, page):
    """La case ne donne que le terme et son équivalent : le reste se lit sur l'écran « Terme », à un clic."""
    traduire(page, "Le vendeur et l’acheteur signent le contrat de vente.")
    assert termes_detectes(page) == ["vendeur", "acheteur", "contrat de vente"]
    details = fenetre.page.details
    page.termes.cellules[0].click()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "vendeur"
    # « vendeur » : l'exemple de son entrée, puis une définition du glossaire qui emploie le terme.
    assert [(emploi.origine, emploi.provenance()) for emploi in details.colonne_contexte.emplois] == [
        ("propre", "Code civil, art. 351"), ("definition", "Définition de « prix »")]
    fenetre.bouton_retour.click()
    page.termes.cellules[2].click()
    assert fenetre.page.entree.terme_fr == "contrat de vente"
    # « contrat de vente » n'a pas d'exemple : ses deux contextes viennent d'autres entrées.
    assert fenetre.page.entree.contextes == [] and details.etats()["contexte"] == (True, 2)
    assert [emploi.provenance() for emploi in details.colonne_contexte.emplois] == [
        "Définition de « acheteur »", "Définition de « vendeur »"]


def test_un_equivalent_a_verifier_est_signale(fenetre, page, tmp_path):
    """Un terme sans définition, donné comme « à vérifier » par le glossaire : sa case et sa fiche le disent."""
    fichier = tmp_path / "seuls.csv"
    fichier.write_text(
        "terme_fr;terme_ar;categorie_fr;source_definition\n"
        "cédant;محيل;nom masculin;à vérifier (équivalent d’exemple)\n"
        "bail;إيجار;nom masculin;\n",
        encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)

    traduire(page, "Le cédant signe le bail.")
    cedant, bail = page.termes.cellules
    assert cedant.a_verifier and "Équivalent à vérifier : il n’est repris d’aucune source citée." in cedant.toolTip()
    assert cedant.accessibleDescription() == "1 occurrence. Équivalent à vérifier"
    # Un terme sans définition et sans mention : le glossaire ne dit rien de lui.
    assert not bail.a_verifier and "vérifier" not in bail.toolTip()
    # Sur la fiche, la mention est écrite au pied de l'équivalent.
    cedant.click()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "cédant"
    assert textes(fenetre.page.fiche.colonne_equivalent.pied) == ["À vérifier", "· équivalent d’exemple"]


def test_une_phrase_reprise_d_un_exemple_a_verifier_est_signalee(fenetre, page, tmp_path):
    """Une phrase du texte identique à un exemple « à vérifier » : l'état de la traduction et l'étape 5 le disent."""
    fichier = tmp_path / "exemples.csv"
    fichier.write_text(
        "terme_fr;terme_ar;contexte_fr;contexte_ar;source_contexte\n"
        "bail;إيجار;Le bail est écrit.;الإيجار مكتوب.;à vérifier (phrase d’exemple)\n"
        "preneur;مستأجر;Le preneur signe le bail.;يوقع المستأجر الإيجار.;à vérifier (phrase d’exemple)\n"
        "loyer;بدل الإيجار;Le loyer est payé chaque mois.;يدفع بدل الإيجار كل شهر.;Code civil, art. 498\n",
        encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)

    # Aucune phrase n'est reprise d'un exemple : rien n'est signalé dans le bilan.
    traduire(page, "Le bail prend fin.")
    assert termes_detectes(page) == ["bail"]
    assert page.traduction.phrases_a_verifier == 0 and "à vérifier" not in page.badge.toolTip()
    assert "0 phrase reprise des exemples du glossaire, 1 phrase traduite mot à mot." in page.bande.infobulle(4)

    # Une phrase identique à un exemple reçoit sa traduction ; l'étape 5 et l'état disent d'où elle vient.
    traduire(page, "Le bail est écrit. Le loyer est payé chaque mois. Le preneur paie le loyer.")
    traduction = page.traduction
    assert texte_traduit(page).startswith("الإيجار مكتوب. يدفع بدل الإيجار كل شهر. ")
    assert (traduction.phrases_attestees, traduction.phrases_a_verifier) == (2, 1)
    assert ("2 phrases reprises des exemples du glossaire (dont 1 d’un exemple à vérifier), "
            "1 phrase traduite mot à mot.") in page.bande.infobulle(4)
    assert ("1 phrase est reprise d’un exemple du glossaire qui porte la mention « à vérifier »."
            in page.badge.toolTip())
    # Sur la fiche du terme, la contextualisation signale les deux phrases à vérifier.
    page.termes.cellule_de(traduction.termes[0].entree).click()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "bail"
    assert [(emploi.provenance(), emploi.a_verifier) for emploi in fenetre.page.details.colonne_contexte.emplois] == [
        ("", True), ("Exemple de « preneur »", True)]


def test_le_pointeur_d_attente_s_affiche_pendant_la_traduction(page, monkeypatch):
    """Traduire un long texte peut durer : le pointeur d'attente l'indique."""
    pointeurs = []

    def relever() -> None:
        pointeur = QGuiApplication.overrideCursor()
        pointeurs.append(None if pointeur is None else pointeur.shape())

    traduire_vraiment = page.traducteur.traduire
    monkeypatch.setattr(page.traducteur, "traduire", lambda *arguments: (relever(), traduire_vraiment(*arguments))[1])
    page.inserer_un_exemple()
    page.traduire()
    assert pointeurs == [Qt.CursorShape.WaitCursor] and QGuiApplication.overrideCursor() is None
    assert page.traduction is not None and len(page.termes.cellules) > 2


def test_le_pointeur_est_retabli_si_la_traduction_echoue(page, monkeypatch):
    def echouer(*arguments):
        raise RuntimeError("panne")

    monkeypatch.setattr(page.traducteur, "traduire", echouer)
    page.inserer_un_exemple()
    with pytest.raises(RuntimeError):
        page.traduire()
    assert QGuiApplication.overrideCursor() is None


def point_du_mot(zone, mot: str) -> QPoint:
    """Le point de la zone où est écrit le milieu d'un mot."""
    texte = zone.toPlainText()
    # Qt compte en unités UTF-16 : un caractère hors du plan de base (une émoticône) en occupe deux.
    position = len(texte[:texte.index(mot) + len(mot) // 2].encode("utf-16-le")) // 2
    curseur = zone.textCursor()
    curseur.setPosition(position)
    return zone.cursorRect(curseur).center()


def test_cliquer_sur_un_terme_de_l_un_des_deux_textes_ouvre_sa_fiche(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    # Dans le texte source : « consentement ».
    point = point_du_mot(page.zone_source, "consentement")
    assert page.terme_a(page.zone_source, point).terme_fr == "consentement"
    QTest.mouseClick(page.zone_source.viewport(), Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "consentement"
    assert fenetre.cadre_retour.isVisible()
    fenetre.bouton_retour.click()
    application.processEvents()
    assert page.texte() == EXEMPLES[FR] and page.traduction is not None  # le clic n'a rien changé au texte
    # Dans la traduction : « القانون » (loi).
    point = point_du_mot(page.zone_cible, "القانون")
    assert page.terme_a(page.zone_cible, point).terme_fr == "loi"
    QTest.mouseClick(page.zone_cible.viewport(), Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "loi"
    fenetre.bouton_retour.click()
    application.processEvents()
    # Un mot qui n'est pas un terme du glossaire ne mène nulle part.
    point = point_du_mot(page.zone_source, "mutuel")
    assert page.terme_a(page.zone_source, point) is None
    QTest.mouseClick(page.zone_source.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert fenetre.mode == MODE_TEXTE
    # Seul un simple clic compte : relâcher la souris après avoir sélectionné un passage n'ouvre rien.
    curseur = page.zone_source.textCursor()
    curseur.select(QTextCursor.SelectionType.Document)
    page.zone_source.setTextCursor(curseur)
    QTest.mouseRelease(page.zone_source.viewport(), Qt.MouseButton.LeftButton,
                       pos=point_du_mot(page.zone_source, "consentement"))
    assert fenetre.mode == MODE_TEXTE


# ------------------------------------------------------------------ le terme allumé
def pointer(application, widget, point: QPoint | None = None) -> None:
    """Amène le pointeur de la souris sur un widget : au point donné, ou en son milieu."""
    QTest.mouseMove(widget, point if point is not None else widget.rect().center())
    application.processEvents()


def passages_allumes(zone) -> list[str]:
    """Le texte de chaque passage d'une zone écrit sur le fond du terme allumé, dans l'ordre du texte."""
    allumes = [passage for passage in zone.extraSelections()
               if passage.format.background().style() != Qt.BrushStyle.NoBrush]
    # Un passage allumé a le fond et la couleur du terme allumé, et rien d'autre.
    assert all(passage.format.background().color().name().upper() == theme.FOND_TERME_ALLUME
               and passage.format.foreground().color().name().upper() == theme.TERME_ALLUME for passage in allumes)
    return [passage.cursor.selectedText() for passage in allumes]


def cases_allumees(page) -> list[str]:
    """Le terme français de chaque case allumée, dans la liste des termes."""
    return [case.entree.terme_fr for case in page.termes.cellules if case.allumee]


def points_allumes(widget) -> int:
    """Nombre de points d'un widget peints de la couleur de fond du terme allumé."""
    return points_de_couleur(widget, theme.FOND_TERME_ALLUME, 4)


class Peintures(QObject):
    """Compte les fois où un widget est repeint à l'écran."""

    def __init__(self, widget) -> None:
        super().__init__()
        self.nombre = 0
        widget.installEventFilter(self)

    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802 (nom imposé par Qt)
        if evenement.type() == QEvent.Type.Paint:
            self.nombre += 1
        return False


def rien_n_est_allume(page) -> bool:
    return (page.terme_allume is None and not cases_allumees(page)
            and not passages_allumes(page.zone_source) and not passages_allumes(page.zone_cible))


def contraste(couleur: str, fond: str) -> float:
    """Rapport de contraste entre deux couleurs (formule des règles d'accessibilité WCAG 2)."""
    def luminance(nom: str) -> float:
        parts = [valeur / 255 for valeur in QColor(nom).getRgb()[:3]]
        rouge, vert, bleu = (part / 12.92 if part <= 0.04045 else ((part + 0.055) / 1.055) ** 2.4 for part in parts)
        return 0.2126 * rouge + 0.7152 * vert + 0.0722 * bleu

    claire, sombre = sorted((luminance(couleur), luminance(fond)), reverse=True)
    return (claire + 0.05) / (sombre + 0.05)


def test_le_terme_que_le_pointeur_designe_s_allume_partout(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    source, cible = page.zone_source, page.zone_cible
    case = page.termes.cellule_de(page.traduction.termes[0].entree)
    assert case.entree.terme_fr == "contrat"
    # Au repos, rien n'est allumé : aucun point de l'écran n'a la couleur de fond du terme allumé. La traduction
    # ne reçoit aucun passage : ses termes sont écrits en bleu dans son texte.
    assert rien_n_est_allume(page) and cible.extraSelections() == []
    assert [points_allumes(widget) for widget in (source.viewport(), cible.viewport(), page.termes)] == [0, 0, 0]
    assert points_de_couleur(source.viewport(), theme.TERME_ALLUME, 4) == 0
    # Le pointeur vient sur le premier « contrat » du texte : le terme s'allume à ses trois occurrences, …
    pointer(application, source.viewport(), point_du_mot(source, "contrat"))
    assert page.terme_allume is case.entree
    assert passages_allumes(source) == ["contrat", "contrat", "contrat"]
    # … aux trois passages de la traduction qui le rendent, et sur sa case. Aucun autre terme n'est allumé :
    # « contrat de vente » est une autre entrée du glossaire.
    assert passages_allumes(cible) == ["العقد", "العقد", "العقد"] and len(cible.extraSelections()) == 3
    assert cases_allumees(page) == ["contrat"]
    # Les autres termes du texte source gardent leur couleur : le terme allumé a remplacé la sienne, sans rien
    # retirer ni ajouter.
    passages = source.extraSelections()
    assert [passage.cursor.selectedText() for passage in passages] == [
        occurrence.forme for occurrence in page.traduction.occurrences]
    assert {passage.format.foreground().color().name().upper() for passage in passages
            if passage.format.background().style() == Qt.BrushStyle.NoBrush} == {theme.BLEU}
    # Le fond est peint pour de bon, aux trois endroits, et le terme y est écrit dans sa couleur.
    assert points_allumes(source.viewport()) > 500 and points_allumes(cible.viewport()) > 500
    assert points_allumes(case) > 2000
    assert points_de_couleur(source.viewport(), theme.TERME_ALLUME, 4) > 0
    assert points_de_couleur(cible.viewport(), theme.TERME_ALLUME, 4) > 0
    # Le pointeur garde la forme d'une main, et le texte n'a pas changé.
    assert source.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert page.texte() == EXEMPLES[FR] and texte_traduit(page) == page.traduction.texte
    # Sur un mot qui n'est pas un terme du glossaire, plus rien n'est allumé.
    pointer(application, source.viewport(), point_du_mot(source, "mutuel"))
    assert rien_n_est_allume(page)
    assert [points_allumes(widget) for widget in (source.viewport(), cible.viewport(), page.termes)] == [0, 0, 0]
    assert source.viewport().cursor().shape() == Qt.CursorShape.IBeamCursor
    assert len(source.extraSelections()) == len(page.traduction.occurrences)  # les termes restent colorés
    assert cible.extraSelections() == []


def test_un_terme_de_la_traduction_allume_le_texte_source(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    case = next(case for case in page.termes.cellules if case.entree.terme_fr == "loi")
    peintures = Peintures(case)
    # « القانون » (loi), dans la traduction : la traduction rend deux des trois « loi » du texte par ce terme.
    pointer(application, page.zone_cible.viewport(), point_du_mot(page.zone_cible, "القانون"))
    assert page.terme_allume.terme_fr == "loi"
    assert passages_allumes(page.zone_source) == ["loi", "loi", "loi"]
    assert passages_allumes(page.zone_cible) == ["القانون", "للقانون"]
    assert cases_allumees(page) == ["loi"]
    # La case, loin du pointeur, est repeinte à l'écran sans attendre.
    assert peintures.nombre >= 1
    allumee = peintures.nombre
    # D'un terme à l'autre, un seul terme est allumé à la fois.
    pointer(application, page.zone_cible.viewport(), point_du_mot(page.zone_cible, "المشتري"))
    assert page.terme_allume.terme_fr == "acheteur"
    assert passages_allumes(page.zone_source) == ["acheteur"] and passages_allumes(page.zone_cible) == ["المشتري"]
    assert cases_allumees(page) == ["acheteur"]
    assert peintures.nombre > allumee  # la case de « loi » est repeinte, éteinte
    # Tant que le pointeur reste sur le même terme, elle n'est pas repeinte.
    eteinte = peintures.nombre
    pointer(application, page.zone_cible.viewport(), point_du_mot(page.zone_cible, "المشتري") + QPoint(2, 1))
    assert page.terme_allume.terme_fr == "acheteur" and peintures.nombre == eteinte
    # Le pointeur quitte la traduction : tout s'éteint.
    pointer(application, page.bouton_copier)
    assert rien_n_est_allume(page)


def test_une_case_de_la_liste_allume_son_terme_dans_les_deux_textes(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    cases = {case.entree.terme_fr: case for case in page.termes.cellules}
    # La liste dit quelle case reçoit le pointeur, et quand il la quitte.
    survols = []
    page.termes.survol.connect(lambda entree: survols.append(entree.terme_fr if entree is not None else None))
    pointer(application, cases["bonne foi"])
    assert survols == ["bonne foi"]
    assert page.terme_allume is cases["bonne foi"].entree
    assert passages_allumes(page.zone_source) == ["bonne foi"]
    assert passages_allumes(page.zone_cible) == ["وبحسن نية"]
    assert cases_allumees(page) == ["bonne foi"]
    assert points_allumes(page.zone_source.viewport()) > 200 and points_allumes(page.zone_cible.viewport()) > 200
    # La case sous le pointeur a le même fond que le terme dans les textes.
    assert points_allumes(cases["bonne foi"]) > 2000 and points_allumes(cases["usage"]) == 0
    # D'une case à l'autre.
    pointer(application, cases["usage"])
    assert survols == ["bonne foi", None, "usage"]
    assert page.terme_allume is cases["usage"].entree
    assert passages_allumes(page.zone_source) == ["usage"] and passages_allumes(page.zone_cible) == ["والعرف"]
    assert cases_allumees(page) == ["usage"]
    assert points_allumes(cases["bonne foi"]) == 0 and points_allumes(cases["usage"]) > 2000
    # Le pointeur quitte la liste : tout s'éteint.
    pointer(application, page.bouton_effacer)
    assert survols == ["bonne foi", None, "usage", None]
    assert rien_n_est_allume(page)
    assert points_allumes(page.termes) == 0


def test_un_terme_que_la_traduction_ne_reprend_pas_ne_s_allume_que_dans_le_texte_et_la_liste(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    # La première phrase est reprise d'un exemple du glossaire : sa traduction est celle de l'exemple, qui rend
    # « des parties » par « المتعاقدين ». Le terme de l'entrée « partie » (« طرف ») n'y est pas écrit.
    assert page.traduction.phrases[0].attestation is not None
    pointer(application, page.zone_source.viewport(), point_du_mot(page.zone_source, "parties"))
    assert page.terme_allume.terme_fr == "partie" and page.terme_allume.terme_ar == "طرف"
    assert passages_allumes(page.zone_source) == ["parties"]
    assert passages_allumes(page.zone_cible) == []
    assert points_allumes(page.zone_cible.viewport()) == 0
    assert cases_allumees(page) == ["partie"]


def test_le_terme_allume_s_eteint_quand_l_ecran_change(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    entree = page.traduction.termes[0].entree
    # Le texte est modifié : il ne correspond plus à la traduction, plus rien n'est allumé.
    page.allumer(entree)
    assert page.terme_allume is entree and cases_allumees(page) == ["contrat"]
    page.zone_source.insertPlainText("Suite. ")
    assert rien_n_est_allume(page) and page.zone_source.extraSelections() == []
    # Les termes du texte modifié ne sont plus repérés ; ceux de la traduction le sont encore.
    page.allumer(entree)
    assert passages_allumes(page.zone_source) == []
    assert passages_allumes(page.zone_cible) == ["العقد", "العقد", "العقد"] and cases_allumees(page) == ["contrat"]
    # Une nouvelle traduction : rien n'est allumé, et les termes du texte sont de nouveau colorés.
    page.traduire()
    assert rien_n_est_allume(page)
    assert len(page.zone_source.extraSelections()) == len(page.traduction.occurrences) > 0
    # Un autre écran s'affiche : le terme s'éteint, et il est éteint quand on revient. (Le pointeur est mis
    # ailleurs : sinon Qt, en cachant la zone qu'il survole, la préviendrait de son départ.)
    pointer(application, fenetre.barre_etat)
    entree = page.traduction.termes[0].entree
    page.allumer(entree)
    assert page.terme_allume is entree and passages_allumes(page.zone_source)
    fenetre.definir_mode(MODE_PARAMETRES)
    application.processEvents()
    assert rien_n_est_allume(page)
    fenetre.definir_mode(MODE_TEXTE)
    application.processEvents()
    assert rien_n_est_allume(page)
    # Le texte est effacé.
    page.allumer(entree)
    page.effacer()
    assert rien_n_est_allume(page) and page.zone_cible.extraSelections() == []
    # Sans traduction, il n'y a rien à allumer.
    pointer(application, page.zone_source.viewport(), QPoint(40, 20))
    assert rien_n_est_allume(page)


def test_un_terme_allume_s_ouvre_d_un_clic_et_le_texte_se_selectionne(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    zone = page.zone_source.viewport()
    point = point_du_mot(page.zone_source, "consentement")
    pointer(application, zone, point)
    assert page.terme_allume.terme_fr == "consentement"
    # Sélectionner un passage (bouton enfoncé) ne change pas le terme allumé, et n'ouvre aucune fiche.
    autre = point_du_mot(page.zone_source, "contractant")
    QTest.mousePress(zone, Qt.MouseButton.LeftButton, pos=point)
    pointer(application, zone, autre)
    assert page.terme_allume.terme_fr == "consentement"
    QTest.mouseRelease(zone, Qt.MouseButton.LeftButton, pos=autre)
    application.processEvents()
    assert "mutuel ou pour les causes prévues par la loi." in page.zone_source.textCursor().selectedText()
    assert fenetre.mode == MODE_TEXTE and page.texte() == EXEMPLES[FR]
    # Bouton relâché, le terme sous le pointeur s'allume, sans attendre que la souris bouge.
    assert page.terme_allume.terme_fr == "contractant"
    assert passages_allumes(page.zone_source) == ["contractant"] and cases_allumees(page) == ["contractant"]
    # Un clic sur le terme allumé ouvre sa fiche : l'écran « Texte » n'est plus affiché, plus rien n'y est allumé.
    curseur = page.zone_source.textCursor()
    curseur.clearSelection()
    page.zone_source.setTextCursor(curseur)
    pointer(application, zone, point)
    QTest.mouseClick(zone, Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_fr == "consentement"
    assert rien_n_est_allume(page)
    # Retour au texte sans toucher à la souris (raccourci du clavier) : le pointeur est resté à la même place, le
    # terme qui revient sous lui se rallume. Comme pour une case, que Qt prévient de l'arrivée du pointeur.
    fenetre.bouton_retour.click()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE and page.terme_allume.terme_fr == "consentement"
    assert passages_allumes(page.zone_source) == ["consentement"] and cases_allumees(page) == ["consentement"]
    # Un clic sur une case allumée ouvre aussi sa fiche.
    case = page.termes.cellule_de(page.traduction.termes[1].entree)
    pointer(application, case)
    assert page.terme_allume is case.entree
    QTest.mouseClick(case, Qt.MouseButton.LeftButton)
    application.processEvents()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree is case.entree


def haut_du_paragraphe(zone, rang: int) -> int:
    """Hauteur, dans la zone, du haut d'un paragraphe du texte."""
    return zone.cursorRect(QTextCursor(zone.document().findBlockByNumber(rang))).top()


def test_le_terme_allume_suit_le_pointeur_quand_le_texte_defile(fenetre, page, application):
    # Trente lignes d'un seul mot, chacun au début de sa ligne : « contrat » et « loi », tour à tour.
    page.definir_texte("\n".join(["contrat", "loi"] * 15))
    page.traduire()
    application.processEvents()
    zone = page.zone_source
    barre = zone.verticalScrollBar()
    pas = haut_du_paragraphe(zone, 1) - haut_du_paragraphe(zone, 0)  # d'une ligne à la suivante
    assert pas > 0 and barre.maximum() >= 3 * pas  # le texte dépasse de la zone : il défile
    point = point_du_mot(zone, "con")
    # Un point plus bas que la zone ne désigne rien, même si le texte continue à cette hauteur, hors de la vue.
    lignes = zone.viewport().height() // pas + 1
    assert lignes < 30 and not zone.viewport().rect().contains(point + QPoint(0, lignes * pas))
    assert page.terme_a(zone, point + QPoint(0, 2 * pas)).terme_fr == "contrat"
    assert page.terme_a(zone, point + QPoint(0, lignes * pas)) is None
    pointer(application, zone.viewport(), point)
    assert page.terme_allume.terme_fr == "contrat"
    assert passages_allumes(zone) == ["contrat"] * 15 and cases_allumees(page) == ["contrat"]
    # Le texte défile d'une ligne (molette, clavier) : le pointeur n'a pas bougé, il est maintenant sur « loi ».
    barre.setValue(pas)
    assert page.terme_allume.terme_fr == "contrat"  # le pointeur est relu juste après le défilement
    application.processEvents()
    assert page.terme_a(zone, point).terme_fr == "loi"
    assert page.terme_allume.terme_fr == "loi"
    assert passages_allumes(zone) == ["loi"] * 15 and cases_allumees(page) == ["loi"]
    assert passages_allumes(page.zone_cible) == ["قانون"] * 15
    assert zone.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor
    # Encore une ligne : de nouveau « contrat ».
    barre.setValue(2 * pas)
    application.processEvents()
    assert page.terme_allume.terme_fr == "contrat" and passages_allumes(zone) == ["contrat"] * 15
    # Pendant qu'un bouton de la souris est enfoncé, le terme allumé ne change pas, même si le texte défile.
    QTest.mousePress(zone.viewport(), Qt.MouseButton.LeftButton, pos=point)
    barre.setValue(3 * pas)
    application.processEvents()
    assert page.terme_a(zone, point).terme_fr == "loi" and page.terme_allume.terme_fr == "contrat"
    # Le bouton relâché, le terme allumé rattrape le pointeur. (Deux lettres affichées sont sélectionnées :
    # relâcher le bouton n'ouvre alors aucune fiche.)
    curseur = zone.cursorForPosition(point)
    curseur.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, 2)
    zone.setTextCursor(curseur)
    QTest.mouseRelease(zone.viewport(), Qt.MouseButton.LeftButton, pos=point)
    application.processEvents()
    assert barre.value() == 3 * pas and fenetre.mode == MODE_TEXTE
    assert page.terme_allume.terme_fr == "loi" and passages_allumes(zone) == ["loi"] * 15
    # L'autre texte défile, loin du pointeur : rien ne change.
    cible = page.zone_cible
    cible.verticalScrollBar().setValue(pas)
    application.processEvents()
    assert page.terme_allume.terme_fr == "loi" and passages_allumes(zone) == ["loi"] * 15
    # La traduction défile de la même façon sous le pointeur : « عقد » (contrat), puis « قانون » (loi).
    cible.verticalScrollBar().setValue(0)
    pas_de_la_cible = haut_du_paragraphe(cible, 1) - haut_du_paragraphe(cible, 0)
    assert 0 < pas_de_la_cible <= cible.verticalScrollBar().maximum()
    pointer(application, cible.viewport(), point_du_mot(cible, "عقد"))
    assert page.terme_allume.terme_fr == "contrat" and passages_allumes(cible) == ["عقد"] * 15
    cible.verticalScrollBar().setValue(pas_de_la_cible)
    application.processEvents()
    assert page.terme_allume.terme_fr == "loi" and passages_allumes(cible) == ["قانون"] * 15
    assert passages_allumes(zone) == ["loi"] * 15 and cases_allumees(page) == ["loi"]
    # Le pointeur parti, un défilement n'allume rien.
    pointer(application, page.bouton_effacer)
    assert rien_n_est_allume(page)
    barre.setValue(0)
    cible.verticalScrollBar().setValue(0)
    application.processEvents()
    assert rien_n_est_allume(page)


def test_le_pointeur_n_est_relu_que_s_il_est_vraiment_sur_le_texte(fenetre, page, application, monkeypatch):
    """Deux précautions : la place du pointeur peut être un vieux souvenir (il a quitté la fenêtre), et autre
    chose peut recouvrir le texte à cet endroit."""
    page.definir_texte("\n".join(["contrat", "loi"] * 15))
    page.traduire()
    application.processEvents()
    zone = page.zone_source
    vue = zone.viewport()
    barre = zone.verticalScrollBar()
    pas = haut_du_paragraphe(zone, 1) - haut_du_paragraphe(zone, 0)
    point = point_du_mot(zone, "con")
    pointer(application, vue, point)
    assert page.terme_allume.terme_fr == "contrat" and vue.underMouse()
    # Le pointeur s'en va. Sa dernière place connue est encore sur le texte (comme sous un système qui ne dit
    # pas où est le pointeur hors de la fenêtre) : le texte défile, rien ne s'allume.
    place = QCursor.pos()
    pointer(application, page.bouton_effacer)
    assert rien_n_est_allume(page) and not vue.underMouse()
    with monkeypatch.context() as remplacement:
        remplacement.setattr(QCursor, "pos", staticmethod(lambda: place))
        assert fenetre.childAt(fenetre.mapFromGlobal(QCursor.pos())) is vue
        barre.setValue(pas)
        application.processEvents()
        assert rien_n_est_allume(page)
    # Le pointeur revient sur le texte ; puis un panneau recouvre le texte à cet endroit : le texte peut défiler
    # dessous, le terme allumé ne change pas.
    pointer(application, vue, point)
    assert page.terme_allume.terme_fr == "loi"
    panneau = QWidget(vue)
    panneau.setGeometry(vue.rect())
    panneau.show()
    application.processEvents()
    assert fenetre.childAt(fenetre.mapFromGlobal(QCursor.pos())) is panneau and vue.underMouse()
    assert page.terme_allume.terme_fr == "loi"
    barre.setValue(2 * pas)
    application.processEvents()
    assert page.terme_a(zone, point).terme_fr == "contrat" and page.terme_allume.terme_fr == "loi"
    # Le panneau retiré, le défilement suivant relit le pointeur.
    panneau.hide()
    panneau.deleteLater()
    barre.setValue(4 * pas)
    application.processEvents()
    assert page.terme_allume.terme_fr == "contrat" and passages_allumes(zone) == ["contrat"] * 15


def test_le_terme_reste_sous_le_pointeur_se_rallume_apres_une_nouvelle_traduction(page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    source = page.zone_source
    pointer(application, source.viewport(), point_du_mot(source, "contrat"))
    assert page.terme_allume.terme_fr == "contrat"
    anciennes = list(page.termes.cellules)
    # Le texte est traduit de nouveau (Ctrl+Entrée) : la liste des termes est refaite, ses cases sont éteintes…
    page.traduire()
    assert rien_n_est_allume(page)
    assert all(nouvelle not in anciennes for nouvelle in page.termes.cellules)
    # … puis le terme resté sous le pointeur se rallume, sans que la souris ait bougé.
    application.processEvents()
    assert page.terme_allume.terme_fr == "contrat"
    assert passages_allumes(source) == ["contrat"] * 3 and passages_allumes(page.zone_cible) == ["العقد"] * 3
    assert cases_allumees(page) == ["contrat"]
    assert source.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor
    # Le texte est effacé sous le pointeur : il n'y a plus rien à allumer.
    page.effacer()
    application.processEvents()
    assert rien_n_est_allume(page)
    assert source.viewport().cursor().shape() == Qt.CursorShape.IBeamCursor


def test_la_case_allumee_suit_le_pointeur_quand_la_liste_defile(fenetre, page, application, monkeypatch):
    fenetre.resize(900, 600)  # dans une petite fenêtre, la liste des termes du texte d'essai défile
    fenetre.move(300, 40)  # la fenêtre n'est pas dans le coin de l'écran : elle en est à plus d'une case
    application.processEvents()
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    barre = page.termes.defilement.verticalScrollBar()
    grille = page.termes.grille
    assert barre.maximum() > grille.HAUTEUR_DE_LIGNE // 2
    assert fenetre.mapToGlobal(QPoint(0, 0)).x() >= 300 > page.termes.cellules[0].width()
    case = page.termes.cellules[0]
    position = case.mapToGlobal(case.rect().center())  # la place du pointeur à l'écran : elle ne changera pas
    pointer(application, case)
    assert page.terme_allume is case.entree and cases_allumees(page) == ["contrat"]
    # La liste défile sous le pointeur : il désigne maintenant la case de la ligne suivante.
    barre.setValue(barre.maximum())
    application.processEvents()
    dessous = next(autre for autre in page.termes.cellules
                   if autre.geometry().contains(grille.mapFromGlobal(position)))
    assert dessous is not case
    assert page.terme_allume is dessous.entree and cases_allumees(page) == [dessous.entree.terme_fr]
    assert passages_allumes(page.zone_source) == [
        occurrence.forme for occurrence in page.traduction.occurrences if occurrence.entree is dessous.entree]
    # La liste revient en haut : de nouveau la première case.
    barre.setValue(0)
    application.processEvents()
    assert page.terme_allume is case.entree and cases_allumees(page) == ["contrat"]
    assert passages_allumes(page.zone_source) == ["contrat", "contrat", "contrat"]
    # Le pointeur n'est plus sur la liste : elle peut défiler, rien ne s'allume. Même si sa dernière place connue
    # est encore sur une case (comme sous un système qui ne dit pas où est le pointeur hors de la fenêtre).
    pointer(application, page.bouton_effacer)
    assert rien_n_est_allume(page) and not page.termes.defilement.viewport().underMouse()
    barre.setValue(barre.maximum())
    application.processEvents()
    assert rien_n_est_allume(page)
    with monkeypatch.context() as remplacement:
        remplacement.setattr(QCursor, "pos", staticmethod(lambda: position))
        assert isinstance(fenetre.childAt(fenetre.mapFromGlobal(QCursor.pos())), type(case))
        barre.setValue(0)
        application.processEvents()
        assert rien_n_est_allume(page)


def test_une_case_arrivee_sous_un_pointeur_immobile_s_eteint_quand_il_repart(page, application):
    """Qt ne prévient pas une case qui arrive sous un pointeur immobile (liste refaite, liste qui défile) : elle
    ne saurait pas que le pointeur est reparti. Le fond de la liste le dit à sa place."""
    traduire(page, "Le contrat fait la loi.")  # deux termes : la troisième place de la ligne reste vide
    application.processEvents()
    assert termes_detectes(page) == ["contrat", "loi"]
    grille = page.termes.grille
    pointer(application, page.termes.cellules[1])
    assert page.terme_allume.terme_fr == "loi"
    # Nouvelle traduction : la case est refaite sous le pointeur, et se rallume sans que Qt l'ait prévenue.
    page.traduire()
    application.processEvents()
    case = page.termes.cellules[1]
    assert page.terme_allume.terme_fr == "loi" and case.allumee and not case.underMouse()
    # Le pointeur saute à la place vide de la ligne, sans passer par un autre point de la case : elle s'éteint.
    vide = QPoint(grille.width() - 20, case.geometry().center().y())
    assert grille.childAt(vide) is None
    pointer(application, grille, vide)
    assert rien_n_est_allume(page)
    # De même quand il saute hors de la liste.
    pointer(application, case)
    page.traduire()
    application.processEvents()
    case = page.termes.cellules[1]
    assert page.terme_allume.terme_fr == "loi" and case.allumee and not case.underMouse()
    pointer(application, page.bouton_effacer)
    assert rien_n_est_allume(page)
    # Un bouton enfoncé sur le fond de la liste ne change rien au terme allumé.
    page.allumer(case.entree)
    QTest.mousePress(grille, Qt.MouseButton.LeftButton, pos=vide)
    QTest.mouseMove(grille, vide + QPoint(-3, 1))
    application.processEvents()
    assert page.terme_allume is case.entree
    QTest.mouseRelease(grille, Qt.MouseButton.LeftButton, pos=vide + QPoint(-3, 1))
    application.processEvents()


def test_une_case_allumee_qui_a_le_clavier_garde_son_contour(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    case = page.termes.cellules[0]
    # Allumée sans avoir le clavier : un fond, pas de contour.
    page.allumer(case.entree)
    assert case.allumee and not case.hasFocus()
    assert points_allumes(case) > 2000 and points_de_couleur(case, theme.BLEU, 4) == 0
    # La touche Tab amène le clavier sur la case : son contour se voit sur le fond du terme allumé.
    fenetre.activateWindow()
    case.setFocus(Qt.FocusReason.TabFocusReason)
    application.processEvents()
    assert case.hasFocus() and case.allumee
    assert points_de_couleur(case, theme.BLEU, 4) > 200
    assert contraste(theme.BLEU, theme.FOND_TERME_ALLUME) >= 3  # un contour, pas un texte : 3 suffit (WCAG 2)
    # Le clavier sur une case n'allume rien : seul le pointeur désigne un terme. La case éteinte garde le
    # contour clair d'une case qui a le clavier (un trait fin, de la couleur du fond du terme allumé).
    page.allumer(None)
    assert case.hasFocus() and rien_n_est_allume(page)
    assert 0 < points_allumes(case) < 1000 and points_de_couleur(case, theme.BLEU, 4) == 0


def test_le_terme_allume_dans_un_texte_arabe(fenetre, page, application):
    page.definir_sens(AR)
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    assert (page.source, page.cible) == (AR, FR)
    pointer(application, page.zone_source.viewport(), point_du_mot(page.zone_source, "القانون"))
    assert page.terme_allume.terme_fr == "loi"
    assert passages_allumes(page.zone_source) == ["القانون", "للقانون"]
    assert passages_allumes(page.zone_cible) == ["loi", "loi"]
    assert cases_allumees(page) == ["loi"]
    # Depuis la traduction française : l'article et la préposition écrits avec le terme s'allument avec lui.
    pointer(application, page.zone_cible.viewport(), point_du_mot(page.zone_cible, "contrat de vente"))
    assert page.terme_allume.terme_fr == "contrat de vente"
    assert passages_allumes(page.zone_source) == ["عقد البيع"]
    assert passages_allumes(page.zone_cible) == ["du contrat de vente"]
    assert cases_allumees(page) == ["contrat de vente"]


def test_le_terme_allume_est_a_sa_place_apres_une_emoticone(page, application):
    # L'émoticône occupe deux unités UTF-16 : elle décale la place des termes dans les deux zones.
    traduire(page, "😀 Le contrat de vente et la loi.")
    application.processEvents()
    assert texte_traduit(page) == "😀 عقد البيع et القانون."
    pointer(application, page.zone_source.viewport(), point_du_mot(page.zone_source, "loi"))
    assert page.terme_allume.terme_fr == "loi"
    assert passages_allumes(page.zone_source) == ["loi"] and passages_allumes(page.zone_cible) == ["القانون"]
    pointer(application, page.zone_cible.viewport(), point_du_mot(page.zone_cible, "عقد البيع"))
    assert page.terme_allume.terme_fr == "contrat de vente"
    assert passages_allumes(page.zone_source) == ["contrat de vente"]
    assert passages_allumes(page.zone_cible) == ["عقد البيع"]


def test_le_terme_allume_reste_lisible():
    # Texte courant : un rapport de contraste d'au moins 4,5 (niveau AA des règles d'accessibilité WCAG 2).
    assert contraste(theme.TERME_ALLUME, theme.FOND_TERME_ALLUME) >= 4.5
    # Le fond se distingue du blanc du panneau, et de la couleur d'un passage sélectionné.
    assert theme.FOND_TERME_ALLUME not in (theme.SURFACE, theme.BLEU)
    assert contraste("#000000", "#FFFFFF") == pytest.approx(21) and contraste("#FFFFFF", "#FFFFFF") == 1


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
    assert page.termes.cellules == [] and page.termes.message.isVisible()
    assert page.termes.nombre.isVisible() and page.termes.nombre.text() == "0"
    assert not page.termes.aide.isVisible() and not page.termes.defilement.isVisible()
    assert message_des_termes(page) == ("Aucun terme du glossaire dans ce texte",
                                        "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
    assert fenetre.barre_etat.texte() == "Traduction : 0 mot sur 6 trouvé dans le glossaire."


def test_un_terme_ambigu_est_signale_dans_sa_case(fenetre, page, application):
    traduire(page, "Le droit et le juge.")
    application.processEvents()
    droit, juge = page.termes.cellules
    assert droit.text() == "droit — حق"
    # « droit » a deux sens dans le glossaire et rien, dans la phrase, ne permet de choisir.
    assert droit.incertain and droit.alerte == "Ambigu : aussi « قانون »"
    assert ("Ambigu : aussi « قانون ». Le contexte n’a pas permis de choisir entre les sens de ce terme : "
            "vérifiez l’équivalent.") in droit.toolTip()
    assert droit.accessibleDescription() == "1 occurrence. Ambigu : aussi « قانون »"
    assert not juge.incertain and juge.alerte == "" and "Ambigu" not in juge.toolTip()
    # Un signe orange précède le terme ambigu, et lui seul.
    assert droit.retrait == droit.LARGEUR_DU_SIGNE > 0 and juge.retrait == 0
    assert points_de_couleur(droit, theme.AMBRE) > 8 and points_de_couleur(juge, theme.AMBRE) == 0
    # Sa fiche s'ouvre sur le sens retenu par la traduction ; ses onglets donnent l'autre sens.
    droit.click()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_ar == "حق"
    assert [onglet.text() for onglet in fenetre.page.fiche.onglets.onglets] == ["Sens 1 : حق", "Sens 2 : قانون"]
    fenetre.bouton_retour.click()

    # Le contexte a permis de choisir : pas de signe, mais l'infobulle rappelle l'autre sens.
    traduire(page, "Le droit de propriété est garanti par la loi.")
    application.processEvents()
    droit = page.termes.cellules[0]
    assert (droit.text(), droit.incertain, droit.alerte) == ("droit — حق", False, "Autre sens : « قانون »")
    assert "Autre sens : « قانون ». Ce terme a d’autres sens dans le glossaire." in droit.toolTip()
    assert droit.retrait == 0 and points_de_couleur(droit, theme.AMBRE) == 0


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
    # Les termes sont reconnus au milieu de ces signes.
    assert termes_detectes(page) == ["contrat", "loi"]


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
    # Les cases gardent leur ordre dans les deux sens : le terme français à gauche, le terme arabe à droite.
    assert [case.text() for case in page.termes.cellules] == ["nullité — بطلان", "contrat — عقد", "acheteur — مشترٍ"]


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
def test_un_clic_sur_une_case_ouvre_la_fiche_du_terme(fenetre, page, application):
    traduire(page, "La nullité du contrat de vente protège l’acheteur.")
    assert termes_detectes(page) == ["nullité", "contrat de vente", "acheteur"]
    assert not fenetre.cadre_retour.isVisible() and not fenetre.venu_du_texte
    page.termes.cellules[1].click()
    application.processEvents()
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page and fenetre.rail.boutons[MODE_TERME].isChecked()
    assert fenetre.page.entree.terme_fr == "contrat de vente"
    assert fenetre.page.entree.terme_ar == "عقد البيع"
    assert fenetre.page.champ.text() == "contrat de vente"
    # Le bouton « Retour au texte » s'affiche au début de la barre d'outils, devant le sens de traduction.
    bouton = fenetre.bouton_retour
    assert fenetre.venu_du_texte and fenetre.cadre_retour.isVisible() and bouton.text() == "Retour au texte"
    assert "Revenir à l’écran « Texte »" in bouton.toolTip()
    assert bouton.mapTo(fenetre, QPoint(bouton.width(), 0)).x() <= fenetre.sens.mapTo(fenetre, QPoint(0, 0)).x()
    assert bouton.width() >= QPushButton.sizeHint(bouton).width()  # son texte n'est pas coupé
    # Il ramène à l'écran « Texte » : le texte, sa traduction et ses termes y sont restés.
    bouton.click()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE and not fenetre.cadre_retour.isVisible() and not fenetre.venu_du_texte
    assert page.texte() == "La nullité du contrat de vente protège l’acheteur."
    assert page.traduction is not None and len(page.termes.cellules) == 3


def test_le_bouton_retour_au_texte(fenetre, page, application):
    """Le bouton accompagne une fiche ouverte depuis l'écran « Texte », tant qu'on n'est pas revenu au texte."""
    traduire(page, ARTICLE_106)
    # L'écran « Terme » ouvert par la barre latérale : pas de bouton.
    fenetre.rail.boutons[MODE_TERME].click()
    assert not fenetre.cadre_retour.isVisible()
    fenetre.definir_mode(MODE_TEXTE)
    page.termes.cellules[0].click()
    assert fenetre.cadre_retour.isVisible()
    # Il reste affiché quand on poursuit sur l'écran « Terme » : une autre recherche, une autre fiche.
    fenetre.page.rechercher("loi")
    fenetre.page.fiche.colonne_terme.bouton_suivant.click()
    assert fenetre.cadre_retour.isVisible()
    # Il se cache avec la barre d'outils des autres écrans, et revient avec l'écran « Terme ».
    fenetre.definir_mode(MODE_PARAMETRES)
    assert not fenetre.cadre_retour.isVisible()
    fenetre.definir_mode(MODE_TERME)
    assert fenetre.cadre_retour.isVisible()
    # Dans la plus petite fenêtre, la barre d'outils garde le bouton, le sens de traduction et le champ de saisie.
    fenetre.resize(900, 600)
    application.processEvents()
    bouton, barre = fenetre.bouton_retour, fenetre.page.barre
    assert bouton.width() >= QPushButton.sizeHint(bouton).width()
    assert fenetre.sens.width() >= 200 and fenetre.page.champ.width() >= 120
    # (La barre de recherche réserve, de chaque côté, la place de son halo.)
    assert barre.mapTo(fenetre, QPoint(barre.width(), 0)).x() <= 900 - theme.MARGE + barre.HALO
    # Revenir au texte par un autre chemin (la barre latérale) le retire pour de bon.
    fenetre.rail.boutons[MODE_TEXTE].click()
    fenetre.rail.boutons[MODE_TERME].click()
    assert not fenetre.cadre_retour.isVisible() and not fenetre.venu_du_texte


def test_la_fiche_s_ouvre_dans_le_sens_du_texte(fenetre, page):
    traduire(page, "بطلان العقد يحمي المشتري.")
    assert fenetre.page.source == FR  # l'écran « Terme » avait gardé son propre sens
    page.termes.cellules[0].click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.page.source == AR
    assert fenetre.page.entree.terme_ar == "بطلان" and fenetre.page.champ.text() == "بطلان"
    assert fenetre.sens.source.text() == "العربية"
    # Au centre du menu « Plus de détails » : le terme arabe.
    assert (fenetre.page.details.roue.terme, fenetre.page.details.roue.langue) == ("بطلان", AR)
    fenetre.bouton_retour.click()
    assert fenetre.mode == MODE_TEXTE and page.source == AR and page.texte() == "بطلان العقد يحمي المشتري."


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
    assert page.termes.cellules == [] and not page.termes.nombre.isVisible()
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
    # « Étapes du traitement… » affiche l'écran « Texte » et y ouvre la petite fenêtre des étapes.
    fenetre.definir_mode(MODE_TERME)
    fenetre.action_etapes.trigger()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE and fenetre.page_texte.volet_etapes.isVisible()
    fenetre.page_texte.volet_etapes.hide()
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
    assert termes_detectes(page) == ["juge", "loi"]
    fichier = tmp_path / "autre.csv"
    fichier.write_text("terme_fr;terme_ar\njuge;حاكم\n", encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)
    assert page.traduction.texte == "الحاكم applique la loi."
    assert termes_detectes(page) == ["juge"] and page.termes.cellules[0].text() == "juge — حاكم"
    assert resultats_des_etapes(page)[2] == "2 mots sur 5"
    # Ce glossaire n'a ni définition ni ressource : sur la fiche du terme, les cercles du menu restent gris.
    page.termes.cellules[0].click()
    assert fenetre.mode == MODE_TERME and fenetre.page.entree.terme_ar == "حاكم"
    assert fenetre.page.details.renseignes() == []


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
def test_les_etapes_du_traitement_s_ouvrent_a_la_demande(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    volet, bande = page.volet_etapes, page.bande
    for taille in ((1440, 860), (900, 600)):
        fenetre.resize(*taille)
        application.processEvents()
        # L'écran n'affiche pas les étapes ; un clic sur l'état de la traduction les ouvre dans une petite fenêtre.
        assert not volet.isVisible() and not bande.isVisible(), taille
        QTest.mouseClick(page.badge, Qt.MouseButton.LeftButton)
        application.processEvents()
        assert volet.isVisible() and bande.isVisible() and volet.bande is bande, taille
        assert volet.windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup  # un clic ailleurs la referme
        assert volet.titre.text() == "Étapes du traitement"
        # Les cinq étapes, allumées, avec leur résultat écrit en entier.
        assert bande.allumage.allumees() == [True] * 5
        affiches = bande.textes_affiches()
        assert [resultat for _, resultat in affiches] == [
            "5 phrases", "84 mots", "83 mots sur 84", "8 appliquées", "5 phrases"], taille
        assert [nom for nom, _ in affiches] in ([nom for nom, _, _ in ETAPES], [court for _, court, _ in ETAPES])
        assert volet.width() >= volet.LARGEUR and bande.width() >= bande.largeur_confortable()
        # La petite fenêtre s'ouvre sous l'état de la traduction, sans sortir de la fenêtre de l'application.
        coin, bord = volet.mapToGlobal(QPoint(0, 0)), fenetre.mapToGlobal(QPoint(0, 0))
        assert coin.y() >= page.badge.mapToGlobal(QPoint(0, page.badge.height())).y(), taille
        assert bord.x() <= coin.x() and coin.x() + volet.width() <= bord.x() + fenetre.width(), taille
        volet.hide()
        application.processEvents()

    # Sans traduction, la commande du menu montre quand même les cinq étapes : leur nom, sans résultat.
    page.effacer()
    assert not page.badge.isVisible()
    fenetre.action_etapes.trigger()
    application.processEvents()
    assert volet.isVisible() and bande.allumage.allumees() == [False] * 5
    assert [resultat for _, resultat in bande.textes_affiches()] == [""] * 5
    volet.hide()


def bande_seule(application, traduction=None) -> BandeEtapes:
    """La bande des étapes, hors de sa petite fenêtre : sa largeur se règle à la main."""
    bande = BandeEtapes()
    bande.afficher(traduction)
    bande.show()
    application.processEvents()
    return bande


def test_avant_la_traduction_les_etapes_ne_sont_jamais_coupees(application):
    """Le nom de chaque étape passe à sa forme courte, puis disparaît, plutôt que d'être coupé par « … »."""
    bande = bande_seule(application)
    for largeur in (1400, 1000, 720, 560, 420, 300, 240):
        bande.resize(largeur, bande.height())
        application.processEvents()
        affiches = bande.textes_affiches()
        for (nom_affiche, resultat), (nom, nom_court, _) in zip(affiches, ETAPES, strict=True):
            assert nom_affiche in (nom, nom_court, "") and resultat == "", largeur
        # Les cinq étapes ont la même forme : toutes nommées, ou aucune.
        assert len({bool(nom) for nom, _ in affiches}) == 1, largeur
        # Les étapes tiennent dans la bande, sans se chevaucher.
        _, abscisses, ecart = bande.disposition()
        assert abscisses[0] == bande.MARGE and abscisses == sorted(abscisses) and ecart >= 4, largeur
    bande.resize(1400, bande.height())
    application.processEvents()
    assert [nom for nom, _ in bande.textes_affiches()] == [nom for nom, _, _ in ETAPES]
    assert not bande.empilee()
    bande.close()
    bande.deleteLater()


def test_les_etapes_sont_abregees_dans_une_bande_etroite(page, application):
    page.inserer_un_exemple()
    page.traduire()
    bande = bande_seule(application, page.traduction)
    bande.resize(1400, bande.height())
    application.processEvents()
    assert bande.textes_affiches()[2] == ("Recherche dans le glossaire", "83 mots sur 84") and not bande.empilee()

    bande.resize(bande.largeur_confortable(), bande.height())
    application.processEvents()
    # La largeur « confortable » : le nom court de chaque étape, et son résultat en entier.
    assert bande.textes_affiches()[2] == ("Recherche", "83 mots sur 84") and not bande.empilee()

    bande.resize(420, bande.height())
    application.processEvents()
    # Bande étroite : les noms sont gardés, ou retirés ; ils ne sont jamais coupés par « … ».
    affiches = bande.textes_affiches()
    assert [nom for nom, _ in affiches] in ([nom_court for _, nom_court, _ in ETAPES], [""] * 5)
    for (_, resultat), etape in zip(affiches, bande.etapes, strict=True):
        assert resultat in (etape.resultat, etape.resultat_court, "")

    bande.resize(bande.minimumWidth(), bande.height())
    application.processEvents()
    for (nom, resultat), etape in zip(bande.textes_affiches(), bande.etapes, strict=True):
        assert nom in (etape.nom_court, "") and resultat in (etape.resultat_court, "")
    assert bande.etapes[2].resultat_court == "83 / 84"
    assert "<b>3. Recherche dans le glossaire</b>" in bande.infobulle(2)  # l'infobulle garde le nom entier…
    assert "Résultat : 83 mots sur 84." in bande.infobulle(2)  # … et le résultat en toutes lettres
    bande.close()
    bande.deleteLater()


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

    fenetre.resize(900, 600)
    application.processEvents()
    # Les deux zones de texte gardent une hauteur utilisable, au-dessus de la liste des termes.
    assert page.zone_source.height() >= 150 and page.zone_cible.height() >= 150
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
