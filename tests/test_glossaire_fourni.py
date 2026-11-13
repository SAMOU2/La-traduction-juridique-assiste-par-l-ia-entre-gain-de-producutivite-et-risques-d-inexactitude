"""Le glossaire fourni avec l'application : ``donnees/glossaire_juridique.csv``.

Les autres tests utilisent le petit glossaire d'essai (voir ``conftest.py``). Ceux-ci
vérifient le fichier que l'application ouvre au démarrage : il se lit sans perte, ses
entrées sont complètes, et les deux écrans fonctionnent avec lui.

Les nombres attendus (1 000 entrées, 24 résultats pour « contrat »…) décrivent le
contenu actuel du fichier : ils sont à mettre à jour quand le glossaire est enrichi.
"""

from collections import Counter

import pytest
from conftest import GLOSSAIRE_FOURNI

from traducteur.glossaire import COLONNES
from traducteur.langues import AR, FR, cle_souple, cle_stricte, contient_arabe
from traducteur.traduction import ATTESTE, NEUTRE, SOURCE, TERME, Traducteur

NOMBRE_D_ENTREES = 1000


def balise(traduction) -> str:
    """Texte traduit, les termes du glossaire entre crochets et les mots non traduits entre accolades."""
    marques = {TERME: "[{}]", SOURCE: "{{{}}}", ATTESTE: "{}", NEUTRE: "{}"}
    return "".join(marques[morceau.nature].format(morceau.texte) for morceau in traduction.morceaux)


@pytest.fixture(scope="module")
def traducteur(glossaire_fourni):
    return Traducteur(glossaire_fourni)


# ------------------------------------------------------------------ contenu du fichier
def test_le_glossaire_fourni_se_charge(glossaire_fourni):
    assert len(glossaire_fourni) == NOMBRE_D_ENTREES
    assert glossaire_fourni.nom == "glossaire_juridique.csv"
    assert glossaire_fourni.encodage == "UTF-8" and glossaire_fourni.separateur == ";"
    assert glossaire_fourni.colonnes == list(COLONNES)  # toutes les colonnes, dans l'ordre documenté
    assert glossaire_fourni.colonnes_ignorees == [] and glossaire_fourni.lignes_ignorees == 0
    assert [entree.numero for entree in glossaire_fourni.entrees] == list(range(1, NOMBRE_D_ENTREES + 1))


def test_le_fichier_s_ouvre_dans_un_tableur():
    """Marque d'ordre des octets au début (Excel reconnaît ainsi l'UTF-8) et fins de ligne simples."""
    brut = GLOSSAIRE_FOURNI.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in brut and brut.endswith(b"\n")


def test_chaque_entree_est_complete(glossaire_fourni):
    for entree in glossaire_fourni.entrees:
        nom = f"n° {entree.numero} : {entree.terme_fr}"
        assert entree.terme_fr and contient_arabe(entree.terme_ar), nom
        assert not contient_arabe(entree.terme_fr), nom
        assert entree.categorie_fr and entree.categorie_ar and entree.domaines, nom
        assert entree.definition_fr and contient_arabe(entree.definition_ar), nom
        assert not contient_arabe(entree.definition_fr), nom
        assert entree.source_definition and entree.ressources, nom
        assert entree.pluriel_fr or not entree.pluriel_ar, nom  # un pluriel arabe a son pluriel français
        for contexte in entree.contextes:
            assert contexte.fr and contexte.ar and contexte.source, nom


def test_aucun_couple_de_termes_n_est_repete(glossaire_fourni):
    couples = Counter((cle_souple(entree.terme_fr), cle_stricte(entree.terme_ar))
                      for entree in glossaire_fourni.entrees)
    assert [couple for couple, nombre in couples.items() if nombre > 1] == []


def test_les_termes_associes_sont_des_entrees(glossaire_fourni):
    """Les puces « Termes associés » ouvrent une fiche. Seul « cocontractant » n'a pas d'entrée."""
    absents = {terme for entree in glossaire_fourni.entrees for terme in entree.termes_associes
               if glossaire_fourni.par_terme(terme, FR) is None}
    assert absents == {"cocontractant"}


def test_les_homonymes(glossaire_fourni):
    """Formes qui désignent plusieurs entrées : la traduction d'un texte choisit d'après le contexte."""
    def homonymes(langue):
        return {entree.terme(langue) for entree in glossaire_fourni.entrees
                if len(glossaire_fourni.homonymes(entree, langue)) > 1}

    assert homonymes(FR) == {"action", "auteur", "droit", "majorité"}
    assert homonymes(AR) == {"القانون المدني", "تأمين", "حكم", "دين", "شريك", "عرف", "قانون", "قرار", "كفالة",
                             "ولاية"}


def test_les_termes_au_pluriel_sont_signales(glossaire_fourni):
    """« biens », « droits de l'homme »… : la catégorie contient « pluriel », pour l'article « les »."""
    pluriels = {entree.terme_fr for entree in glossaire_fourni.entrees if "pluriel" in entree.categorie_fr}
    assert len(pluriels) == 24
    assert {"biens", "dépens", "arrhes", "droits de l'homme", "libertés fondamentales"} <= pluriels
    assert all(terme.split()[0].endswith("s") for terme in pluriels)


# ------------------------------------------------------------------ recherche
def test_recherche_dans_le_glossaire_fourni(glossaire_fourni):
    contrats = [entree.terme_fr for entree in glossaire_fourni.chercher("contrat", FR)]
    assert len(contrats) == 24 and contrats[:3] == ["contrat", "contrat de bail", "contrat de vente"]
    assert glossaire_fourni.chercher("عقد", AR)[0].terme_fr == "contrat"
    assert [entree.terme_ar for entree in glossaire_fourni.chercher("droit", FR)[:2]] == ["حق", "قانون"]
    assert [entree.terme_fr for entree in glossaire_fourni.propositions("contart", FR)] == ["contrat", "constat"]
    assert glossaire_fourni.par_terme("procès-verbaux", FR).terme_ar == "محضر"
    assert glossaire_fourni.par_terme("المحاضر", AR).terme_fr == "procès-verbal"


# ------------------------------------------------------------------ traduction d'un texte
@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Le procureur de la République exerce l'action publique devant le tribunal criminel.",
         "[وكيل الجمهورية] {exerce} [الدعوى العمومية] {devant} [محكمة الجنايات]."),
        ("Les droits de l'homme et les libertés fondamentales sont garantis par la Constitution.",
         "[حقوق الإنسان] {et} [الحريات الأساسية] {sont} {garantis} {par} [الدستور]."),
        ("Le créancier demande la saisie des biens meubles du débiteur.",
         "[الدائن] [طلب] [حجز] [منقولات] [المدين]."),
        ("Les fonds de commerce et les permis de construire.", "[المحلات التجارية] {et} [رخص البناء]."),
        # « cours » : pluriel de « cour » après « les », mot ordinaire après « au ».
        ("Les cours et les tribunaux rendent la justice.", "[المجالس القضائية] {et} [المحاكم] {rendent} [العدل]."),
        ("Au cours de l'audience, le juge entend les parties.",
         "{Au} {cours} {de} [الجلسة]، [القاضي] {entend} [الأطراف]."),
        # Les accents comptent : « condamne » n'est pas « condamné », ni « causé » « cause ».
        ("Le tribunal condamne le défendeur à réparer le dommage causé.",
         "[المحكمة] {condamne} [المدعى عليه] {à} {réparer} [الضرر] {causé}."),
        ("Le condamné et l'assuré ; la cause du contrat.", "[المحكوم عليه] {et} [المؤمن له]؛ [سبب] [العقد]."),
        # Une majuscule peut ne pas porter son accent.
        ("L'Etat garantit la propriété.", "[الدولة] {garantit} [الملكية]."),
    ],
)
def test_du_francais_vers_l_arabe(traducteur, texte, attendu):
    assert balise(traducteur.traduire(texte, FR)) == attendu


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("يباشر وكيل الجمهورية الدعوى العمومية أمام محكمة الجنايات.",
         "{يباشر} [le procureur de la République] [l’action publique] {أمام} [le tribunal criminel]."),
        ("الحريات الأساسية وحقوق الإنسان مضمونة.",
         "[Les libertés fondamentales] {و} [les droits de l'homme] {مضمونة}."),
        ("قضت المحكمة العليا بنقض القرار.", "{قضت} [la Cour suprême] {بـ} [la cassation] [de l’arrêt]."),
        ("شركة المساهمة وشركات المساهمة والأسهم.",
         "[La société par actions] {و} [les sociétés par actions] {و} [les actions]."),
    ],
)
def test_de_l_arabe_vers_le_francais(traducteur, texte, attendu):
    assert balise(traducteur.traduire(texte, AR)) == attendu


@pytest.mark.parametrize(
    ("texte", "langue", "terme", "equivalent"),
    [
        ("L'auteur de l'infraction est puni d'une amende.", FR, "auteur", "فاعل"),
        ("L'auteur de l'œuvre jouit de droits moraux.", FR, "auteur", "مؤلف"),
        ("Les actions de la société sont cotées en bourse.", FR, "action", "سهم"),
        ("الولاية جماعة إقليمية للدولة.", AR, "ولاية", "wilaya"),
        ("الولاية على القاصر لأبيه.", AR, "ولاية", "tutelle"),
    ],
)
def test_homonymes_departages_par_le_contexte(traducteur, texte, langue, terme, equivalent):
    traduction = traducteur.traduire(texte, langue)
    cible = AR if langue == FR else FR
    trouve = next(detecte for detecte in traduction.termes if detecte.entree.terme(langue) == terme)
    assert trouve.entree.terme(cible) == equivalent and not trouve.incertain


def test_un_mot_courant_peut_etre_pris_pour_un_terme(traducteur):
    """Limite connue : le glossaire ne dit pas si « cause » est ici le nom ou le verbe."""
    assert balise(traducteur.traduire("Celui qui cause un dommage doit le réparer.", FR)) == (
        "{Celui} {qui} [سبب] [ضرر] {doit} {le} {réparer}.")


# ------------------------------------------------------------------ les deux écrans
pytest.importorskip("PySide6")


@pytest.fixture
def fenetre_fournie(application, reglages, avertissements, monkeypatch):
    """La fenêtre de l'application, ouverte comme au lancement : avec le glossaire fourni."""
    from traducteur.interface import fenetre as module_fenetre

    monkeypatch.setattr(module_fenetre, "GLOSSAIRE_EXEMPLE", GLOSSAIRE_FOURNI)
    fenetre = module_fenetre.FenetrePrincipale(reglages=reglages)
    fenetre.resize(1440, 860)
    fenetre.show()
    application.processEvents()
    yield fenetre
    fenetre.close()
    fenetre.deleteLater()
    application.processEvents()


def test_ecran_terme_avec_le_glossaire_fourni(fenetre_fournie, application, avertissements):
    assert avertissements == []
    assert fenetre_fournie.indicateur.nom.texte_complet() == "glossaire_juridique.csv"
    assert fenetre_fournie.indicateur.detail.text() == " · 1\u202f000 entrées"
    assert fenetre_fournie.barre_etat.texte() == "Glossaire chargé : 1\u202f000 entrées."

    page = fenetre_fournie.page
    assert len(page.accueil.puces) == 5  # termes proposés à l'accueil
    page.rechercher("contrat")
    assert page.barre.texte_du_resume() == "1 terme · 23 expressions"
    assert fenetre_fournie.barre_etat.etat() == "« contrat » : 24 entrées trouvées dans le glossaire."
    assert page.fiche.colonne_terme.rang.texte_complet() == "Entrée 1 sur 1\u202f000"
    assert page.liste.titre.texte_complet() == "Expressions avec « contrat »"
    assert page.liste.nombre.text() == "23" and len(page.liste.entrees()) == 23

    # « droit » : deux entrées de même forme (un onglet chacune), puis les expressions.
    page.rechercher("droit")
    assert [onglet.text() for onglet in page.fiche.onglets.onglets] == ["Sens 1 : حق", "Sens 2 : قانون"]
    assert page.liste.entrees()[0].terme_fr == "droit réel"

    # Les suggestions pendant la saisie couvrent tout le glossaire (les homonymes une seule fois).
    assert page.suggestions.model().rowCount() == NOMBRE_D_ENTREES - 4

    # Fenêtre étroite : la fiche garde ses cinq champs, la liste défile dans la place qui reste.
    page.rechercher("responsabilité")
    fenetre_fournie.resize(1080, 620)
    application.processEvents()
    assert page.defilement_fiche.horizontalScrollBar().maximum() == 0
    assert page.fiche.height() >= page.fiche.hauteur_minimale()
    assert page.liste.height() >= page.liste.hauteur_minimale()
    assert page.liste.defilement.verticalScrollBar().maximum() > 0


def test_ecran_texte_avec_le_glossaire_fourni(fenetre_fournie, application):
    from traducteur.interface.fenetre import MODE_TEXTE

    fenetre_fournie.definir_mode(MODE_TEXTE)
    page = fenetre_fournie.page_texte
    page.inserer_un_exemple()
    page.traduire()
    application.processEvents()
    traduction = page.traduction
    # Les quatre phrases du Code civil viennent des exemples du glossaire ; la cinquième est traduite mot à mot.
    assert traduction.phrases_attestees == 4 and (traduction.mots, traduction.mots_reconnus) == (84, 83)
    assert [terme.entree.terme_fr for terme in traduction.termes] == [
        "contrat", "loi", "partie", "consentement", "cause", "bonne foi", "contractant", "usage", "équité",
        "obligation", "nullité", "contrat de vente", "acheteur"]
    assert traduction.texte.endswith("بطلان عقد البيع protège المشتري.")
    # L'écran en rend compte : état de la traduction, tableau des termes, barre d'état.
    assert page.badge.texte() == "Traduction partielle · 83 mots sur 84 trouvés"
    assert page.termes.nombre.text() == "13" and len(page.termes.lignes_affichees()) == 13
    assert page.termes.legende.libelles() == ["Définition à vérifier", "Source citée"]
    assert fenetre_fournie.barre_etat.etat() == "Traduction : 83 mots sur 84 trouvés dans le glossaire."
