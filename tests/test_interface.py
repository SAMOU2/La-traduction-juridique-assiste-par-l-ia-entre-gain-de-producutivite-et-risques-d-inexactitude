"""Interface de bureau : fenêtre, recherche, cartes (tests exécutés sans écran)."""

import re

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from traducteur.interface import fenetre as module_fenetre
from traducteur.interface.composants import (
    ESPACE_INVISIBLE,
    MARQUE_RTL,
    EtiquetteCourte,
    LigneCliquable,
    TermeAjuste,
)
from traducteur.interface.fenetre import FenetrePrincipale
from traducteur.langues import AR, FR

_BALISE = re.compile(r"<[^>]+>")


@pytest.fixture(scope="session")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def reglages(tmp_path):
    return QSettings(str(tmp_path / "reglages.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def avertissements(monkeypatch):
    """Remplace les boîtes de dialogue par une simple liste de messages."""
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(FenetrePrincipale, "_boite", lambda self, icone, titre, texte: messages.append((titre, texte)))
    return messages


@pytest.fixture
def fenetre(application, reglages, avertissements):
    fenetre = FenetrePrincipale(reglages=reglages)
    fenetre.resize(1440, 860)
    fenetre.show()
    application.processEvents()
    yield fenetre
    fenetre.close()
    fenetre.deleteLater()
    application.processEvents()


def textes(widget) -> list[str]:
    """Textes affichés par les étiquettes d'un widget (sans balises ni marque de direction)."""
    resultat = []
    for label in widget.findChildren(QLabel):
        texte = label.texte_complet() if isinstance(label, EtiquetteCourte) else label.text()
        if label.textFormat() == Qt.TextFormat.RichText:
            texte = _BALISE.sub("", texte)
        texte = texte.replace(MARQUE_RTL, "").replace(ESPACE_INVISIBLE, "").strip()
        if texte:
            resultat.append(texte)
    return resultat


def puces(widget) -> list[str]:
    return [bouton.text() for bouton in widget.findChildren(QPushButton)]


def grand_terme(carte) -> str:
    """Le terme affiché en grand dans une carte."""
    return carte.findChild(TermeAjuste).text().replace(MARQUE_RTL, "")


# ------------------------------------------------------------------ démarrage
def test_la_fenetre_s_ouvre_avec_le_glossaire_d_exemple(fenetre, avertissements):
    assert avertissements == []
    assert fenetre.windowTitle() == "Traducteur juridique — Français / Arabe"
    etat = _BALISE.sub("", fenetre.etat_glossaire.text()).replace("&nbsp;", " ")
    assert "Glossaire chargé : glossaire_juridique.csv" in etat
    assert "40 entrées" in etat and "UTF-8" in etat
    assert fenetre.etat_sens.text().startswith("Sens : français › arabe")
    assert "Prototype v0.1" in fenetre.etat_sens.text()
    assert fenetre.pastille_source.nom.text() == "Français"
    assert fenetre.pastille_cible.nom.text() == "العربية"


def test_ecran_d_accueil(fenetre):
    page = fenetre.page
    assert page.entree is None
    assert textes(page.zone_resultats) == ["Saisissez un terme, puis appuyez sur Entrée. Par exemple :"]
    exemples = puces(page.zone_resultats)
    assert len(exemples) == 5 and exemples[0] == "contrat" and len(set(exemples)) == 5
    assert [carte.titre for carte in page.cartes] == [
        "Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
    for carte in page.cartes:
        assert carte.presentation in textes(carte)
    assert page.champ.placeholderText() == "Saisir un terme juridique…"


# ------------------------------------------------------------------ recherche
def test_recherche_d_un_terme_francais(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    assert page.entree.terme_fr == "contrat"
    assert textes(page.zone_resultats) == ["6 entrées trouvées dans le glossaire :"]
    boutons = page.groupe_resultats.buttons()
    assert [bouton.text() for bouton in boutons] == [
        "contrat", "contrat de bail", "contrat de vente", "contrat de travail",
        "exécution du contrat", "conclusion du contrat"]
    assert [bouton.isChecked() for bouton in boutons] == [True, False, False, False, False, False]

    # 1 Terme
    assert grand_terme(page.carte_terme) == "contrat"
    contenu = textes(page.carte_terme)
    assert "Langue source : français" in contenu
    assert "nom masculin · pl. contrats" in contenu
    assert {"DOMAINE", "SYNONYMES", "TERMES ASSOCIÉS"} <= set(contenu)
    assert {"Droit civil", "Obligations", "convention", "accord", "cocontractant", "clause"} <= set(contenu)
    assert puces(page.carte_terme) == ["contractant", "obligation"]  # entrées du glossaire : cliquables
    assert "Entrée n° 1 sur 40 du glossaire" in contenu

    # 2 Définition
    contenu = textes(page.carte_definition)
    assert any(texte.startswith("Convention par laquelle") for texte in contenu)
    assert any(texte.startswith("اتفاق يلتزم بموجبه") for texte in contenu)
    assert "Source : Code civil, art. 54" in contenu

    # 3 Équivalent
    assert grand_terme(page.carte_equivalent) == "عقد"
    contenu = textes(page.carte_equivalent)
    assert "اللغة الهدف: العربية" in contenu and "اسم مذكر، ج. عقود" in contenu
    assert "EXPRESSIONS" in contenu and "contrat de vente" in contenu and "عقد البيع" in contenu
    assert len(page.carte_equivalent.findChildren(LigneCliquable)) == 5

    # 4 Contextualisation : le terme est mis en évidence dans les deux langues
    contenu = textes(page.carte_contexte)
    assert {"Code civil, art. 106", "Le contrat fait la loi des parties.", "العقد شريعة المتعاقدين."} <= set(contenu)
    assert "2 exemples dans le glossaire" in contenu
    riches = [label.text() for label in page.carte_contexte.findChildren(QLabel) if "<span" in label.text()]
    assert len(riches) == 4
    assert any('font-weight: 600;">contrat</span>' in texte for texte in riches)
    assert any('font-weight: 600;">العقد</span>' in texte for texte in riches)

    # 5 Ressources
    contenu = textes(page.carte_ressources)
    assert any("Code civil algérien" in texte and "art. 54, 106 et 107" in texte for texte in contenu)
    liens = [label.text() for label in page.carte_ressources.findChildren(QLabel) if "<a href" in label.text()]
    assert len(liens) == 1 and 'href="https://www.joradp.dz"' in liens[0]


def test_la_saisie_au_clavier_lance_la_recherche(fenetre, application):
    page = fenetre.page
    page.champ.setFocus()
    QTest.keyClicks(page.champ, "bonne foi")
    QTest.keyClick(page.champ, Qt.Key.Key_Return)
    application.processEvents()
    assert page.entree.terme_fr == "bonne foi"
    assert grand_terme(page.carte_equivalent) == "حسن النية"


def test_le_bouton_rechercher(fenetre):
    page = fenetre.page
    page.champ.setText("  Équité ")
    page.bouton.click()
    assert page.entree.terme_fr == "équité"
    assert page.champ.text() == "Équité"


def test_choisir_une_autre_entree_trouvee(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    page.groupe_resultats.buttons()[2].click()
    assert page.entree.terme_fr == "contrat de vente"
    assert grand_terme(page.carte_equivalent) == "عقد البيع"
    assert page.champ.text() == "contrat"  # la recherche saisie est conservée


def test_un_terme_arabe_inverse_le_sens(fenetre):
    page = fenetre.page
    page.rechercher("العقد")
    assert page.source == AR
    assert page.entree.terme_fr == "contrat"
    assert grand_terme(page.carte_terme) == "عقد"
    assert grand_terme(page.carte_equivalent) == "contrat"
    assert "اللغة المصدر: العربية" in textes(page.carte_terme)
    assert "Langue cible : français" in textes(page.carte_equivalent)
    assert fenetre.etat_sens.text().startswith("Sens : arabe › français")
    assert fenetre.pastille_source.nom.text() == "العربية"
    assert fenetre.pastille_source.code.text() == "AR"
    assert page.champ.placeholderText() == "أدخل مصطلحا قانونيا…"
    assert page.champ.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert "inversé" in fenetre.statusBar().currentMessage()


def test_inverser_le_sens_garde_l_entree_affichee(fenetre):
    page = fenetre.page
    page.rechercher("usage")
    assert page.entree.terme_fr == "usage"
    fenetre.bouton_inverser.click()
    assert page.source == AR
    assert page.entree.terme_fr == "usage"  # et non « coutume », qui a le même équivalent arabe
    assert page.champ.text() == "عرف"
    boutons = page.groupe_resultats.buttons()
    assert [bouton.text() for bouton in boutons] == ["عرف (coutume)", "عرف (usage)"]
    assert [bouton.isChecked() for bouton in boutons] == [False, True]
    fenetre.bouton_inverser.click()
    assert page.source == FR and page.entree.terme_fr == "usage" and page.champ.text() == "usage"


def test_inverser_le_sens_sans_entree_affichee(fenetre):
    page = fenetre.page
    page.champ.setText("bail")  # texte saisi, pas encore recherché : il est conservé
    page.inverser()
    assert page.source == AR and page.entree is None
    assert puces(page.zone_resultats)[0] == "عقد"  # exemples proposés dans la nouvelle langue source
    assert page.champ.text() == "bail"

    page.rechercher("xyz")  # recherche sans résultat : elle est effacée quand on inverse le sens
    assert page.source == FR and page.entree is None
    page.inverser()
    assert page.source == AR and page.champ.text() == "" and page.requete == ""
    assert len(puces(page.zone_resultats)) == 5


def test_homonymes_distingues_par_leur_equivalent(fenetre):
    page = fenetre.page
    page.rechercher("droit")
    assert [bouton.text() for bouton in page.groupe_resultats.buttons()] == ["droit (حق)", "droit (قانون)"]
    assert grand_terme(page.carte_equivalent) == "حق"
    page.groupe_resultats.buttons()[1].click()
    assert grand_terme(page.carte_equivalent) == "قانون"


def test_aucun_resultat_propose_les_termes_proches(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    page.rechercher("contart")
    assert page.entree is None
    assert textes(page.zone_resultats) == ["Aucune entrée du glossaire ne correspond à « contart ». Termes proches :"]
    assert puces(page.zone_resultats) == ["contrat"]
    assert page.carte_terme.presentation in textes(page.carte_terme)
    page.zone_resultats.findChild(QPushButton).click()
    assert page.entree.terme_fr == "contrat" and page.champ.text() == "contrat"

    page.rechercher("xyz")
    assert textes(page.zone_resultats) == ["Aucune entrée du glossaire ne correspond à « xyz »."]
    assert puces(page.zone_resultats) == []


def test_effacer_la_recherche_revient_a_l_accueil(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    page.rechercher("")
    assert page.entree is None and page.requete == ""
    assert len(puces(page.zone_resultats)) == 5


def test_les_puces_et_les_expressions_ouvrent_l_entree(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    page.carte_terme.findChild(QPushButton).click()  # puce « contractant »
    assert page.entree.terme_fr == "contractant" and page.champ.text() == "contractant"

    page.rechercher("contrat")
    ligne = page.carte_equivalent.findChildren(LigneCliquable)[0]
    QTest.mouseClick(ligne, Qt.MouseButton.LeftButton)
    assert page.entree.terme_fr == "contrat de bail"


def test_entree_sans_definition_ni_exemple_ni_ressource(fenetre):
    page = fenetre.page
    page.rechercher("capacité")
    assert "Aucune définition dans le glossaire pour ce terme." in textes(page.carte_definition)
    assert "Aucun exemple dans le glossaire pour ce terme." in textes(page.carte_contexte)
    assert "Aucune ressource dans le glossaire pour ce terme." in textes(page.carte_ressources)
    assert grand_terme(page.carte_equivalent) == "أهلية"


def test_copier_l_equivalent_et_les_references(fenetre):
    page = fenetre.page
    page.rechercher("contrat")
    QGuiApplication.clipboard().clear()
    page.carte_equivalent.findChild(QPushButton).click()
    assert QGuiApplication.clipboard().text() == "عقد"
    assert "Équivalent copié" in fenetre.statusBar().currentMessage()
    lien = page.carte_ressources.findChild(QPushButton)
    lien.click()
    assert QGuiApplication.clipboard().text().splitlines() == page.entree.ressources
    assert lien.text() == "Références copiées"


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


def test_plus_de_huit_entrees_trouvees(fenetre, tmp_path):
    lignes = "".join(f"contrat type {lettre};عقد {arabe}\n" for lettre, arabe in zip("abcdefghij", "ابتثجحخدذر",
                                                                                     strict=True))
    fenetre.charger_glossaire(ecrire(tmp_path / "long.csv", "terme_fr;terme_ar\n" + lignes))
    page = fenetre.page
    page.rechercher("contrat")
    assert len(page.resultats) == 10 and len(page.groupe_resultats.buttons()) == 8
    assert textes(page.zone_resultats) == ["10 entrées trouvées dans le glossaire :",
                                           "et 2 autres : précisez la recherche."]
    page.rechercher("contrat type")
    assert len(page.resultats) == 10
    # Une entrée ouverte depuis une autre carte prend la dernière place quand elle n'est pas dans les huit premières.
    page.ouvrir(fenetre.glossaire.entrees[9])
    boutons = page.groupe_resultats.buttons()
    assert boutons[-1].text() == "contrat type j" and boutons[-1].isChecked()


def test_les_cartes_defilent_dans_une_fenetre_etroite(fenetre, application):
    page = fenetre.page
    barre = page.defilement_cartes.horizontalScrollBar()
    fenetre.resize(1080, 620)
    application.processEvents()
    assert barre.maximum() == 0  # les cinq cartes tiennent côte à côte
    fenetre.resize(900, 560)
    application.processEvents()
    assert barre.maximum() > 0  # elles gardent leur largeur minimale et la rangée défile
    assert all(carte.width() == 190 for carte in page.cartes)


def test_les_signes_speciaux_du_glossaire_sont_affiches_tels_quels(fenetre, tmp_path):
    """« < » et « & » ne sont pas pris pour des balises ou des raccourcis clavier."""
    fichier = ecrire(tmp_path / "a&b.csv", (
        "terme_fr;terme_ar;domaine;termes_associes;definition_fr;source_definition;contexte_fr;ressources\n"
        "dommages & intérêts;تعويض <1>;Droit <civil>;<b>gras</b> | droits & devoirs;Somme <b>due</b> & payée.;"
        "Source <x> & y;Les dommages & intérêts <dus>.;Titre <b>x</b>, suite & fin\n"
        "droits & devoirs;حقوق وواجبات;;;;;;\n"))
    assert fenetre.charger_glossaire(fichier)
    assert "a&amp;b.csv" in fenetre.etat_glossaire.text()
    page = fenetre.page
    page.rechercher("dommages & intérêts")
    assert [bouton.text() for bouton in page.groupe_resultats.buttons()] == ["dommages && intérêts"]
    assert grand_terme(page.carte_terme) == "dommages & intérêts"
    assert grand_terme(page.carte_equivalent) == "تعويض <1>"
    fixes = [label for label in page.carte_terme.findChildren(QLabel) if label.property("classe") == "puceFixe"]
    assert [label.text() for label in fixes] == ["Droit <civil>", "<b>gras</b>"]
    assert all(label.textFormat() == Qt.TextFormat.PlainText for label in fixes)
    assert puces(page.carte_terme) == ["droits && devoirs"]
    assert "Somme <b>due</b> & payée." in textes(page.carte_definition)
    assert "Source : Source <x> & y" in textes(page.carte_definition)
    exemple = next(label.text() for label in page.carte_contexte.findChildren(QLabel) if "<span" in label.text())
    assert '600;">dommages &amp; intérêts</span> &lt;dus&gt;.' in exemple
    ressource = next(label.text() for label in page.carte_ressources.findChildren(QLabel) if "<span" in label.text())
    assert "Titre &lt;b&gt;x&lt;/b&gt;</span><br>suite &amp; fin" in ressource


def test_un_texte_de_pied_trop_long_est_abrege(application):
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


def test_un_mot_plus_large_que_la_carte_est_coupe(fenetre, application, tmp_path):
    mot = "anticonstitutionnellement"
    fenetre.charger_glossaire(ecrire(tmp_path / "long.csv",
                                     f"terme_fr;terme_ar\nrecours {mot};على نحو مخالف للدستور\n"))
    page = fenetre.page
    fenetre.resize(1080, 620)
    page.rechercher(mot)
    application.processEvents()
    terme = page.carte_terme.findChild(TermeAjuste)
    # Même écrit à la plus petite taille, le mot dépasse : il passe à la ligne au lieu d'être rogné.
    assert terme.taille == 13 and terme.fontMetrics().horizontalAdvance(mot) > terme.contentsRect().width()
    assert terme.text() == "recours " + ESPACE_INVISIBLE.join(mot)
    assert terme.height() >= 3 * terme.fontMetrics().height()  # « recours », puis le mot sur deux lignes
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction
    assert terme.terme == f"recours {mot}"

    fenetre.resize(1700, 860)  # avec plus de place, le mot redevient entier (et sélectionnable)
    application.processEvents()
    assert terme.text() == f"recours {mot}" and terme.taille > 13
    assert terme.textInteractionFlags() == Qt.TextInteractionFlag.TextSelectableByMouse
    assert terme.fontMetrics().horizontalAdvance(mot) <= terme.contentsRect().width()


def test_le_terme_trop_long_est_ecrit_plus_petit(fenetre, application):
    page = fenetre.page
    page.rechercher("contrat")
    application.processEvents()
    assert page.carte_terme.findChild(TermeAjuste).taille == 36
    page.rechercher("responsabilité")
    application.processEvents()
    normale = page.carte_terme.findChild(TermeAjuste).taille
    fenetre.resize(1080, 620)
    application.processEvents()
    reduite = page.carte_terme.findChild(TermeAjuste).taille
    assert 15 <= reduite < normale <= 27
    # Rien ne dépasse de la carte : le contenu a la largeur de la zone visible.
    for carte in page.cartes:
        assert carte.defilement.widget().width() <= carte.defilement.viewport().width()


# ------------------------------------------------------------------ glossaire
def ecrire(chemin, texte):
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_ouvrir_un_autre_glossaire(fenetre, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "mon_glossaire.csv",
                     "Français,Arabe,Remarque\ntribunal,محكمة,\nappel,استئناف,voie de recours\n")
    fenetre.page.rechercher("contrat")
    assert fenetre.charger_glossaire(fichier, bilan=True)
    assert len(fenetre.glossaire) == 2
    etat = _BALISE.sub("", fenetre.etat_glossaire.text())
    assert "mon_glossaire.csv" in etat and "2 entrées" in etat
    assert reglages.value("glossaire/chemin") == str(fichier.resolve())
    titre, bilan = avertissements[-1]
    assert titre == "Glossaire chargé"
    assert "mon_glossaire.csv : 2 entrées." in bilan and "séparateur : virgule" in bilan
    assert "Colonnes reconnues : terme_fr, terme_ar." in bilan
    assert "Colonnes ignorées (nom inconnu) : Remarque." in bilan
    # La recherche en cours est relancée dans le nouveau glossaire.
    assert fenetre.page.entree is None
    assert textes(fenetre.page.zone_resultats)[0].startswith("Aucune entrée du glossaire ne correspond à « contrat »")
    fenetre.page.rechercher("tribunal")
    assert grand_terme(fenetre.page.carte_equivalent) == "محكمة"


def test_un_fichier_invalide_ne_remplace_pas_le_glossaire(fenetre, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "casse.csv", "terme_fr;terme_ar\ncontrat;???\n")
    assert not fenetre.charger_glossaire(fichier)
    assert len(fenetre.glossaire) == 40
    assert avertissements[-1][0] == "Glossaire non chargé" and "CSV UTF-8" in avertissements[-1][1]
    assert not reglages.contains("glossaire/chemin")


def test_recharger_le_glossaire_garde_l_entree_affichee(fenetre, tmp_path):
    fichier = ecrire(tmp_path / "g.csv", "terme_fr;terme_ar\ndroit;حق\ndroit;قانون\n")
    fenetre.charger_glossaire(fichier)
    fenetre.page.rechercher("droit")
    fenetre.page.groupe_resultats.buttons()[1].click()
    ecrire(fichier, "terme_fr;terme_ar;definition_fr\ndroit;حق;\ndroit;قانون;Ensemble de règles\nloi;قانون;\n")
    fenetre.action_recharger.trigger()
    assert len(fenetre.glossaire) == 3
    assert fenetre.page.entree.terme_ar == "قانون"
    assert "Ensemble de règles" in textes(fenetre.page.carte_definition)


def test_le_dernier_glossaire_ouvert_est_repris_au_demarrage(application, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "dernier.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    reglages.setValue("glossaire/chemin", str(fichier))
    fenetre = FenetrePrincipale(reglages=reglages)
    assert fenetre.glossaire.nom == "dernier.csv"
    fenetre.deleteLater()

    fichier.unlink()  # le fichier a disparu : retour au glossaire d'exemple, avec un avertissement
    fenetre = FenetrePrincipale(reglages=reglages)
    application.processEvents()
    assert fenetre.glossaire.nom == "glossaire_juridique.csv"
    assert not reglages.contains("glossaire/chemin")
    assert len(avertissements) == 1 and "dernier.csv" in avertissements[0][1]
    fenetre.deleteLater()


def test_glossaire_donne_au_lancement(application, reglages, avertissements, tmp_path):
    fichier = ecrire(tmp_path / "choisi.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    fenetre = FenetrePrincipale(fichier, reglages)
    assert fenetre.glossaire.nom == "choisi.csv"
    assert reglages.value("glossaire/chemin") == str(fichier.resolve())
    fenetre.deleteLater()


def test_revenir_au_glossaire_d_exemple(fenetre, reglages, tmp_path):
    fichier = ecrire(tmp_path / "autre.csv", "terme_fr;terme_ar\ntribunal;محكمة\n")
    fenetre.charger_glossaire(fichier)
    assert reglages.contains("glossaire/chemin")
    fenetre.action_exemple.trigger()
    assert fenetre.glossaire.nom == "glossaire_juridique.csv" and len(fenetre.glossaire) == 40
    assert not reglages.contains("glossaire/chemin")  # l'exemple est le glossaire par défaut


def test_sans_aucun_glossaire(application, reglages, avertissements, tmp_path, monkeypatch):
    monkeypatch.setattr(module_fenetre, "GLOSSAIRE_EXEMPLE", tmp_path / "absent.csv")
    fenetre = FenetrePrincipale(reglages=reglages)
    application.processEvents()
    assert fenetre.glossaire is None
    assert "Aucun glossaire chargé" in fenetre.etat_glossaire.text()
    assert not fenetre.action_recharger.isEnabled()
    assert len(avertissements) == 1
    fenetre.page.rechercher("contrat")
    assert fenetre.page.entree is None
    assert textes(fenetre.page.zone_resultats)[0].startswith("Aucun glossaire n’est chargé")
    fenetre.deleteLater()


def test_bilan_de_lecture(glossaire):
    bilan = FenetrePrincipale.bilan_de_lecture(glossaire)
    assert bilan.splitlines()[0] == "glossaire_juridique.csv : 40 entrées."
    assert "Encodage UTF-8, séparateur : point-virgule." in bilan
    assert "ignorée" not in bilan
