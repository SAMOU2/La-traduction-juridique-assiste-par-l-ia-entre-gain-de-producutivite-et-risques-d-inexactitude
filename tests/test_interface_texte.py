"""Écran « Traduction d'un texte » : saisie, traduction, termes relevés, import et export (tests sans écran)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QLabel
from test_documents import fabriquer_doc

from traducteur import documents
from traducteur.interface.composants import MARQUE_RTL
from traducteur.interface.fenetre import MODE_TERME, MODE_TEXTE, FenetrePrincipale
from traducteur.interface.texte import ETAPES, EXEMPLES
from traducteur.langues import AR, FR

ARTICLE_106 = "Le contrat fait la loi des parties."
ARTICLE_106_AR = "العقد شريعة المتعاقدين."


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
    return [etape.resultat() for etape in page.bande.etapes]


def message_du_tableau(page) -> str:
    """Le message affiché à la place des lignes quand le tableau des termes est vide."""
    return page.termes.defilement.widget().findChild(QLabel).text()


# ------------------------------------------------------------------ les deux écrans
def test_le_selecteur_affiche_l_ecran_texte(fenetre, application):
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.bouton_glossaire.isVisible()
    assert not fenetre.bouton_importer.isVisible() and not fenetre.bouton_exporter.isVisible()

    fenetre.boutons_mode[MODE_TEXTE].click()
    application.processEvents()
    assert fenetre.mode == MODE_TEXTE
    assert fenetre.pile.currentWidget() is fenetre.page_texte
    assert fenetre.boutons_mode[MODE_TEXTE].isChecked() and fenetre.actions_mode[MODE_TEXTE].isChecked()
    assert fenetre.bouton_importer.isVisible() and fenetre.bouton_exporter.isVisible()
    assert not fenetre.bouton_glossaire.isVisible()
    assert fenetre.page_texte.zone_source.hasFocus()

    fenetre.actions_mode[MODE_TERME].trigger()  # menu Affichage → Recherche d'un terme (Ctrl+1)
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.boutons_mode[MODE_TERME].isChecked()


def test_etat_initial(fenetre, page):
    assert page.texte() == ""
    assert page.traduction is None
    assert page.zone_source.placeholderText() == "Saisissez, collez ou importez le texte à traduire…"
    assert page.zone_cible.isReadOnly()
    assert page.zone_cible.placeholderText() == "La traduction s’affichera ici."
    assert page.lien_exemple.isVisible()
    assert not page.fichier_importe.isVisible()
    assert not page.etat.isVisible()
    assert page.decompte_source.texte_complet() == "0 phrase · 0 mot · 0 caractère"
    assert page.decompte_cible.texte_complet() == ""
    assert [etape.titre.text() for etape in page.bande.etapes] == [textes[0] for textes in ETAPES]
    assert resultats_des_etapes(page) == [textes[2] for textes in ETAPES]
    assert page.termes.lignes_affichees() == []
    assert "s’afficheront ici après la traduction" in message_du_tableau(page)
    # Rien à copier ni à exporter tant qu'il n'y a pas de traduction.
    assert not page.bouton_copier.isEnabled()
    assert not fenetre.bouton_exporter.isEnabled()
    assert not fenetre.action_exporter.isEnabled() and not fenetre.action_copier.isEnabled()


# ------------------------------------------------------------------ traduction
def test_inserer_un_exemple_puis_traduire(fenetre, page):
    page.lien_exemple.click()
    assert page.texte() == EXEMPLES[FR]
    assert not page.lien_exemple.isVisible()
    assert page.traduction is None  # l'exemple n'est traduit qu'à la demande

    page.bouton_traduire.click()
    traduction = page.traduction
    assert traduction.source == FR and traduction.cible == AR
    assert texte_traduit(page) == traduction.texte
    # Les articles 106 et 107 sont repris des exemples du glossaire ; la dernière phrase est traduite mot à mot.
    assert traduction.texte.startswith("العقد شريعة المتعاقدين. فلا يجوز نقضه، ولا تعديله إلا باتفاق الطرفين")
    assert traduction.texte.endswith("\nبطلان عقد البيع protège المشتري.")

    assert page.etat.isVisible() and page.etat.text() == "Traduction partielle"
    assert "1 mot sur 84 ne figure pas dans le glossaire" in page.etat.toolTip()
    assert page.aide.texte_complet() == "En gris : mots absents du glossaire, à traduire"
    assert page.decompte_source.texte_complet() == "5 phrases · 84 mots · 473 caractères"
    assert page.decompte_cible.texte_complet() == "5 phrases · 54 mots · 321 caractères"
    assert resultats_des_etapes(page) == [
        "5 phrases détectées", "84 mots", "83 mots trouvés sur 84", "8 règles appliquées", "5 phrases reconstruites"]
    assert "Mots absents du glossaire : protège." in page.bande.etapes[2].toolTip()
    assert "Complément du nom : 1" in page.bande.etapes[3].toolTip()
    assert ("4 phrases reprises des exemples du glossaire, 1 phrase traduite mot à mot."
            in page.bande.etapes[4].toolTip())
    assert fenetre.statusBar().currentMessage() == "Traduction : 83 mots sur 84 trouvés dans le glossaire."
    assert page.bouton_copier.isEnabled()
    assert fenetre.bouton_exporter.isEnabled() and fenetre.action_exporter.isEnabled()


def test_les_mots_absents_du_glossaire_sont_en_gris_et_les_termes_en_couleur(page):
    traduire(page, "La nullité du contrat protège l’acheteur.")
    html = page.zone_cible.toHtml()
    document = page.zone_cible.document()

    def couleur_de(mot: str) -> str:
        curseur = document.find(mot)
        assert not curseur.isNull(), mot
        return curseur.charFormat().foreground().color().name()

    assert "protège" in html
    assert couleur_de("protège") == "#8a97aa"  # gris : mot resté en français
    assert couleur_de("بطلان") == couleur_de("المشتري") != couleur_de("protège")
    assert couleur_de("بطلان") != document.find(".").charFormat().foreground().color().name()


def test_le_tableau_des_termes(page):
    page.inserer_un_exemple()
    page.traduire()
    lignes = page.termes.lignes_affichees()
    assert [ligne.bouton.text() for ligne in lignes] == [
        "contrat", "loi", "partie", "consentement", "bonne foi", "contractant", "usage", "équité", "obligation",
        "nullité", "contrat de vente", "acheteur"]
    assert page.termes.resume.texte_complet() == "12 termes · cliquez sur un terme pour afficher sa fiche"

    # Les cinq colonnes de la ligne « contrat » : terme, définition, équivalent, contextualisation, ressources.
    cellules = [[label.text().replace(MARQUE_RTL, "") for label in cellule.parentWidget().findChildren(QLabel)]
                for cellule in lignes[0].cellules]
    assert cellules[0] == ["nom masculin · 3 occurrences"]
    assert cellules[1][0].startswith("Convention par laquelle une ou plusieurs personnes s’obligent")
    assert cellules[2][0] == "عقد"
    assert "contrat" in cellules[3][0] and "العقد" in cellules[3][1]
    assert "Code civil algérien" in cellules[4][0]
    assert cellules[4][-1].startswith("+ ") and "référence" in cellules[4][-1]


def test_un_texte_entierement_reconnu(page):
    traduire(page, ARTICLE_106)
    assert page.traduction.texte == ARTICLE_106_AR
    assert page.traduction.complete
    assert page.etat.text() == "Traduction terminée"
    assert page.aide.texte_complet() == ""
    assert resultats_des_etapes(page)[2] == "7 mots trouvés sur 7"


def test_un_texte_sans_aucun_mot_du_glossaire(fenetre, page):
    traduire(page, "This sentence is written in English.")
    assert page.traduction.texte == "This sentence is written in English."
    assert page.etat.text() == "Aucun mot trouvé"
    assert "recopié tel quel" in page.etat.toolTip()
    assert resultats_des_etapes(page)[2:4] == ["0 mot trouvé sur 6", "aucune règle appliquée"]
    assert page.termes.lignes_affichees() == []
    assert page.termes.resume.texte_complet() == "aucun terme du glossaire dans ce texte"
    assert message_du_tableau(page) == "Aucun terme du glossaire n’a été relevé dans ce texte."
    assert fenetre.statusBar().currentMessage() == "Traduction : 0 mot sur 6 trouvé dans le glossaire."


def sens_des_paragraphes(page) -> list[Qt.LayoutDirection]:
    sens = []
    bloc = page.zone_cible.document().begin()
    while bloc.isValid():
        sens.append(bloc.textDirection())
        bloc = bloc.next()
    return sens


def test_un_paragraphe_non_traduit_garde_son_sens_d_ecriture(page):
    """Dans la zone arabe, un paragraphe resté en français s'écrit de gauche à droite (et inversement)."""
    gauche_a_droite, droite_a_gauche = Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft
    traduire(page, f"Bonjour à tous, comment allez-vous ?\n{ARTICLE_106}\nLe juge décide.\nMerci (fin).")
    assert texte_traduit(page) == (
        f"Bonjour à tous, comment allez-vous ?\n{ARTICLE_106_AR}\nالقاضي décide.\nMerci (fin).")
    assert sens_des_paragraphes(page) == [gauche_a_droite, droite_a_gauche, droite_a_gauche, gauche_a_droite]

    traduire(page, f"مرحبا بالجميع، كيف حالكم؟\n{ARTICLE_106_AR}\nشكرا (انتهى).")
    assert page.source == AR
    assert texte_traduit(page) == f"مرحبا بالجميع، كيف حالكم؟\n{ARTICLE_106}\nشكرا (انتهى)."
    assert sens_des_paragraphes(page) == [droite_a_gauche, gauche_a_droite, droite_a_gauche]


def test_traduire_sans_texte(fenetre, page):
    page.zone_source.setPlainText("  \n ")
    page.bouton_traduire.click()
    assert page.traduction is None
    assert fenetre.statusBar().currentMessage() == "Saisissez, collez ou importez d’abord un texte à traduire."


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


def test_les_termes_sont_colores_dans_le_texte_source(page):
    traduire(page, "😀 Le contrat de vente et la loi.")  # l'émoticône occupe deux unités UTF-16
    selections = page.zone_source.extraSelections()
    assert [selection.cursor.selectedText() for selection in selections] == ["contrat de vente", "loi"]
    page.zone_source.insertPlainText(" Suite.")
    assert page.zone_source.extraSelections() == []  # les couleurs ne correspondent plus au texte


# ------------------------------------------------------------------ sens de traduction
def test_un_texte_arabe_inverse_le_sens(fenetre, page):
    assert page.source == FR
    traduire(page, "بطلان العقد يحمي المشتري.")
    assert page.source == AR and page.cible == FR
    assert page.traduction.source == AR
    assert page.traduction.texte == "La nullité du contrat يحمي l’acheteur."
    assert fenetre.pastille_source.code.text() == "AR" and fenetre.pastille_cible.code.text() == "FR"
    assert page.panneau_source.nom.text() == "العربية" and page.panneau_cible.nom.text() == "Français"
    assert page.zone_source.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert page.zone_cible.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert fenetre.etat_sens.text().startswith("Sens : arabe › français")
    # La première colonne du tableau est écrite dans la langue source.
    assert [ligne.bouton.text() for ligne in page.termes.lignes_affichees()] == ["بطلان", "عقد", "مشترٍ"]


def test_inverser_le_sens_garde_le_texte_et_efface_la_traduction(fenetre, page):
    traduire(page, ARTICLE_106)
    fenetre.bouton_inverser.click()
    assert page.source == AR
    assert page.texte() == ARTICLE_106
    assert page.traduction is None and texte_traduit(page) == ""
    assert not fenetre.bouton_exporter.isEnabled()
    assert page.zone_source.placeholderText().startswith("أدخل النص")
    # Le texte est toujours en français : « Traduire » rétablit le sens français › arabe.
    page.bouton_traduire.click()
    assert page.source == FR and page.traduction.texte == ARTICLE_106_AR
    assert "le sens de traduction a été inversé" not in fenetre.statusBar().currentMessage()


def test_chaque_ecran_garde_son_sens(fenetre, page):
    fenetre.bouton_inverser.click()
    assert page.source == AR and fenetre.page.source == FR
    assert fenetre.pastille_source.code.text() == "AR"
    fenetre.definir_mode(MODE_TERME)
    assert fenetre.pastille_source.code.text() == "FR"
    assert fenetre.etat_sens.text().startswith("Sens : français › arabe")
    fenetre.definir_mode(MODE_TEXTE)
    assert fenetre.pastille_source.code.text() == "AR"
    assert fenetre.etat_sens.text().startswith("Sens : arabe › français")


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
    lignes = page.termes.lignes_affichees()
    assert [ligne.bouton.text() for ligne in lignes] == ["nullité", "contrat de vente", "acheteur"]
    lignes[1].bouton.click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.pile.currentWidget() is fenetre.page
    assert fenetre.page.entree.terme_fr == "contrat de vente"
    assert fenetre.page.entree.terme_ar == "عقد البيع"
    # Le texte et sa traduction sont conservés quand on revient à l'écran « Texte ».
    fenetre.definir_mode(MODE_TEXTE)
    assert page.traduction is not None and len(page.termes.lignes_affichees()) == 3


def test_la_fiche_s_ouvre_dans_le_sens_du_texte(fenetre, page):
    traduire(page, "بطلان العقد يحمي المشتري.")
    page.termes.lignes_affichees()[0].bouton.click()
    assert fenetre.mode == MODE_TERME
    assert fenetre.page.source == AR
    assert fenetre.page.entree.terme_ar == "بطلان"
    assert fenetre.pastille_source.code.text() == "AR"


# ------------------------------------------------------------------ modification, effacement, copie
def test_modifier_le_texte_signale_que_la_traduction_n_est_plus_a_jour(page):
    traduire(page, ARTICLE_106)
    assert page.etat.text() == "Traduction terminée"
    page.zone_source.moveCursor(QTextCursor.MoveOperation.End)
    page.zone_source.insertPlainText(" La vente.")
    assert page.texte() == ARTICLE_106 + " La vente."
    assert page.etat.text() == "Texte modifié"
    assert "cliquez sur « Traduire »" in page.etat.toolTip()
    assert texte_traduit(page) == ARTICLE_106_AR  # l'ancienne traduction reste lisible
    page.bouton_traduire.click()
    assert page.etat.text() == "Traduction terminée"
    assert page.traduction.texte == "العقد شريعة المتعاقدين. البيع."


def test_effacer(fenetre, page, tmp_path):
    fichier = tmp_path / "texte.txt"
    fichier.write_text(ARTICLE_106, encoding="utf-8")
    assert page.importer(fichier)
    assert page.fichier_importe.isVisible() and not page.lien_exemple.isVisible()

    page.bouton_effacer.click()
    assert page.texte() == "" and page.traduction is None and page.fichier is None
    assert texte_traduit(page) == ""
    assert not page.fichier_importe.isVisible() and page.lien_exemple.isVisible()
    assert not page.etat.isVisible()
    assert page.termes.lignes_affichees() == []
    assert resultats_des_etapes(page)[0] == "le texte est découpé en phrases"
    assert not fenetre.bouton_exporter.isEnabled()


def test_copier_la_traduction(fenetre, page):
    traduire(page, ARTICLE_106 + "\nLa vente.")
    QGuiApplication.clipboard().setText("avant")
    page.bouton_copier.click()
    assert QGuiApplication.clipboard().text() == "العقد شريعة المتعاقدين.\nالبيع."
    assert page.bouton_copier.text() == "Copié"
    assert fenetre.statusBar().currentMessage() == "Traduction copiée dans le presse-papiers"
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
    assert page.fichier_importe.isVisible() and page.nom_du_fichier.texte_complet() == fichier.name
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
    assert fenetre.statusBar().currentMessage() == f"Traduction enregistrée : traduction{extension}"


def test_exporter_sans_traduction(fenetre, page, tmp_path):
    fichier = tmp_path / "rien.docx"
    assert not page.exporter(fichier)
    assert not fichier.exists()
    assert fenetre.statusBar().currentMessage() == "Il n’y a pas encore de traduction à exporter."


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
    page.exporter()
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
    assert [ligne.bouton.text() for ligne in page.termes.lignes_affichees()] == ["juge", "loi"]
    fichier = tmp_path / "autre.csv"
    fichier.write_text("terme_fr;terme_ar\njuge;حاكم\n", encoding="utf-8")
    assert fenetre.charger_glossaire(fichier)
    assert page.traduction.texte == "الحاكم applique la loi."
    assert [ligne.bouton.text() for ligne in page.termes.lignes_affichees()] == ["juge"]
    assert resultats_des_etapes(page)[2] == "2 mots trouvés sur 5"


def test_sans_glossaire(application, reglages, avertissements, tmp_path, monkeypatch):
    monkeypatch.setattr("traducteur.interface.fenetre.GLOSSAIRE_EXEMPLE", tmp_path / "absent.csv")
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.show()
    application.processEvents()
    page = fenetre.page_texte
    fenetre.definir_mode(MODE_TEXTE)
    assert page.etat.isVisible() and page.etat.text() == "Aucun glossaire"
    traduire(page, ARTICLE_106)
    assert page.traduction is None
    assert fenetre.statusBar().currentMessage().startswith("Aucun glossaire n’est chargé")
    fenetre.close()
    fenetre.deleteLater()


# ------------------------------------------------------------------ fenêtre étroite
def test_avant_la_traduction_les_etapes_ne_sont_jamais_coupees(fenetre, page, application):
    """La description de chaque étape passe à sa forme courte plutôt que d'être coupée par « … »."""
    for largeur in (1440, 1280, 1100, 900):
        fenetre.resize(largeur, 700)
        application.processEvents()
        for etape, (titre, titre_court, description, description_courte) in zip(page.bande.etapes, ETAPES,
                                                                               strict=True):
            assert etape.titre.text() in (titre, titre_court), largeur
            assert etape.detail.text() in (description, description_courte), largeur
    fenetre.resize(1440, 860)
    application.processEvents()


def test_les_etapes_sont_abregees_dans_une_fenetre_etroite(fenetre, page, application):
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    etape = page.bande.etapes[2]
    assert etape.titre.text() == "Recherche dans le CSV" and etape.detail.text() == "83 mots trouvés sur 84"

    assert all(chevron.isVisible() for chevron in page.bande.chevrons)

    fenetre.resize(900, 560)
    application.processEvents()
    # Titres courts, jamais coupés par « … » (quelle que soit la police du système).
    assert [etape.titre.text() for etape in page.bande.etapes] == [textes[1] for textes in ETAPES]
    for etape_etroite, courts in zip(page.bande.etapes, (
            ("5 phrases détectées", "5 phrases"), ("84 mots",), ("83 sur 84",),
            ("8 règles appliquées", "8 règles"), ("5 phrases reconstruites", "5 phrases")), strict=True):
        assert etape_etroite.detail.text() in courts
    assert etape.resultat() == "83 mots trouvés sur 84"  # l'infobulle garde la forme longue
    assert "83 mots trouvés sur 84" in etape.toolTip()
    # Les zones de texte et le tableau gardent une hauteur utilisable.
    assert page.zone_source.height() >= 60 and page.termes.defilement.height() >= 50

    fenetre.resize(1440, 860)
    application.processEvents()
    assert etape.titre.text() == "Recherche dans le CSV" and etape.detail.text() == "83 mots trouvés sur 84"
