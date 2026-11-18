"""Le glossaire fourni avec l'application : ``donnees/glossaire_juridique.csv``.

Les autres tests utilisent le petit glossaire d'essai (voir ``conftest.py``). Ceux-ci
vérifient le fichier que l'application ouvre au démarrage : il se lit sans perte, ses
entrées sont complètes, et les deux écrans fonctionnent avec lui.

Les nombres attendus (nombre d'entrées, résultats pour « contrat »…) décrivent le
contenu actuel du fichier : ils sont à mettre à jour quand le glossaire est enrichi.
Le nombre d'entrées est écrit dans ``conftest.py``.

Depuis la version 0.8, le fichier a deux parties : 1 000 entrées complètes (définition et
phrase d'exemple), puis des « termes seuls » (terme, équivalent, catégorie, domaine). Depuis
la version 0.11, les termes seuls reçoivent à leur tour une phrase d'exemple, par étapes.
"""

from collections import Counter

import pytest
from conftest import ENTREES_COMPLETES, GLOSSAIRE_FOURNI, NOMBRE_D_ENTREES, TERMES_SEULS_AVEC_EXEMPLE

from traducteur.glossaire import COLONNES, mention_a_verifier
from traducteur.langues import AR, FR, cle_souple, cle_stricte, contient_arabe
from traducteur.surlignage import positions_du_terme
from traducteur.traduction import (
    ATTESTE,
    NEUTRE,
    SOURCE,
    TERME,
    Traducteur,
    cle_phrase,
    se_remplace_dans_un_texte,
)

#: Catégories des noms, et catégories des mots que la traduction d'un texte ne remplace pas.
NOMS = {"nom", "nom masculin", "nom féminin", "nom masculin pluriel", "nom féminin pluriel",
        "locution nominale masculine", "locution nominale féminine", "locution nominale (masculin pluriel)",
        "locution nominale (féminin pluriel)"}
AUTRES_MOTS = {"adjectif", "locution adjectivale", "verbe", "locution verbale", "adverbe", "locution adverbiale",
               "préposition", "locution prépositive", "conjonction", "locution conjonctive"}


def nombre(valeur: int) -> str:
    """Un nombre écrit comme dans l'application : 1 000, avec une espace fine insécable."""
    return f"{valeur:,}".replace(",", "\u202f")


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
    """Les 1 000 premières entrées : terme, catégorie, domaine, définition, source, ressources, exemple."""
    for entree in glossaire_fourni.entrees[:ENTREES_COMPLETES]:
        nom = f"n° {entree.numero} : {entree.terme_fr}"
        assert entree.categorie_fr in NOMS, nom
        assert entree.terme_fr and contient_arabe(entree.terme_ar), nom
        assert not contient_arabe(entree.terme_fr), nom
        assert entree.categorie_fr and entree.categorie_ar and entree.domaines, nom
        assert entree.definition_fr and contient_arabe(entree.definition_ar), nom
        assert not contient_arabe(entree.definition_fr), nom
        assert entree.source_definition and entree.ressources, nom
        assert entree.pluriel_fr or not entree.pluriel_ar, nom  # un pluriel arabe a son pluriel français
        assert entree.contextes, nom  # chaque entrée a sa phrase d'exemple
        for contexte in entree.contextes:
            assert contexte.fr and contexte.ar and contexte.source, nom
            assert not contient_arabe(contexte.fr) and contient_arabe(contexte.ar), nom


def test_les_termes_seuls(glossaire_fourni):
    """Les entrées suivantes (versions 0.8 et 0.9) : terme, équivalent, catégorie, domaine et ressources.

    Elles n'ont pas de définition. Depuis les versions 0.11 et 0.12, une partie d'entre elles ont une phrase
    d'exemple : tous les adjectifs, les verbes et les locutions, et une partie des noms (vocabulaire général,
    droit civil, justice et procédure, droit pénal, droit des affaires, droit constitutionnel, droit administratif,
    droit de la famille, droit du travail et sécurité sociale, droit maritime et nationalité). Aucune forme d'un
    nom seul ne désigne
    un autre nom : la traduction d'un texte n'aurait rien pour choisir entre les deux. Un adjectif, un verbe ou
    une locution peut partager une forme avec une autre entrée (« منع » : « interdiction » et « interdire »),
    puisque la traduction d'un texte ne le remplace pas.
    """
    seuls = glossaire_fourni.entrees[ENTREES_COMPLETES:]
    assert len(seuls) == NOMBRE_D_ENTREES - ENTREES_COMPLETES
    noms = Traducteur(glossaire_fourni)._noms  # les entrées que la traduction d'un texte remplace
    for entree in seuls:
        nom = f"n° {entree.numero} : {entree.terme_fr}"
        assert entree.terme_fr and not contient_arabe(entree.terme_fr) and contient_arabe(entree.terme_ar), nom
        assert entree.categorie_fr in NOMS | AUTRES_MOTS and contient_arabe(entree.categorie_ar), nom
        assert entree.domaines and entree.ressources, nom
        assert not entree.definition_fr and not entree.definition_ar, nom
        # Faute de définition, la mention « à vérifier » porte sur l'équivalent : la fiche l'affiche à son pied.
        assert mention_a_verifier(entree.source_definition) == "équivalent d’exemple", nom
        # Au plus une phrase d'exemple, dans les deux langues, rédigée pour le glossaire : « à vérifier ».
        assert len(entree.contextes) <= 1, nom
        for contexte in entree.contextes:
            assert contexte.fr and contient_arabe(contexte.ar) and not contient_arabe(contexte.fr), nom
            assert mention_a_verifier(contexte.source) == "phrase d’exemple", nom
        assert entree.pluriel_fr or not entree.pluriel_ar, nom
        if entree.categorie_fr in AUTRES_MOTS:
            assert entree.contextes, nom  # chaque adjectif, chaque verbe et chaque locution a sa phrase
            assert not entree.pluriel_fr and not entree.pluriel_ar, nom
            assert not se_remplace_dans_un_texte(entree), nom
            continue
        assert se_remplace_dans_un_texte(entree), nom
        for langue in (FR, AR):
            for forme in (*entree.formes(langue), *entree.synonymes(langue)):
                assert [autre for autre, _ in noms.reconnaitre(forme, langue)] == [entree], (nom, forme)
    # Les mots qui ne sont pas des noms se trouvent tous dans cette seconde partie.
    assert all(se_remplace_dans_un_texte(entree) for entree in glossaire_fourni.entrees[:ENTREES_COMPLETES])
    # Le nombre de termes seuls qui ont leur phrase ne baisse pas d'une version à l'autre.
    assert sum(1 for entree in seuls if entree.contextes) >= TERMES_SEULS_AVEC_EXEMPLE


def test_les_phrases_d_exemple(glossaire_fourni):
    """Chaque entrée complète a sa phrase d'exemple. Une phrase « à vérifier » est courte et emploie le terme.

    Les phrases des termes seuls (version 0.11) sont du nombre : un adjectif y est accordé, un verbe y est au passé.

    Dans la version 0.5, 969 phrases sur 1 002 portent la mention « à vérifier » : elles ont été rédigées pour
    le glossaire. Le test ne compte pas ces phrases : leur nombre baisse à mesure que le glossaire est relu
    et que leur source est écrite dans la colonne ``source_contexte``.
    """
    exemples = [(entree, contexte) for entree in glossaire_fourni.entrees for contexte in entree.contextes]
    assert len(exemples) >= ENTREES_COMPLETES
    assert all(entree.contextes for entree in glossaire_fourni.entrees[:ENTREES_COMPLETES])
    a_verifier = [(entree, contexte) for entree, contexte in exemples if contexte.a_verifier]
    for entree, contexte in a_verifier:
        nom = f"n° {entree.numero} : {entree.terme_fr}"
        # Une phrase courte, qui commence par une majuscule ou un nombre et finit par un point.
        for phrase in (contexte.fr, contexte.ar):
            assert len(phrase) <= 170 and phrase.endswith(".") and phrase == phrase.strip() and "  " not in phrase, nom
        assert contexte.fr[0].isupper() or contexte.fr[0].isdigit(), nom
        # Elle emploie le terme dans les deux langues : l'application l'y met en évidence.
        assert positions_du_terme(contexte.fr, entree, FR), (nom, contexte.fr)
        assert positions_du_terme(contexte.ar, entree, AR), (nom, contexte.ar)
    # Une entrée n'a qu'une phrase à vérifier : les entrées qui ont deux exemples citent un texte.
    assert len({entree.numero for entree, _ in a_verifier}) == len(a_verifier)


def test_une_phrase_redigee_ne_sert_qu_une_fois(glossaire_fourni):
    """Une phrase du texte identique à un exemple reçoit sa traduction : une phrase rédigée n'a donc qu'un emploi."""
    for langue in (FR, AR):
        vues: dict[str, tuple[str, bool]] = {}
        for entree in glossaire_fourni.entrees:
            for contexte in entree.contextes:
                cle = cle_phrase(contexte.texte(langue))
                if cle in vues:
                    # Seul un article du Code civil est cité dans plusieurs entrées.
                    assert not contexte.a_verifier and not vues[cle][1], (langue, entree.terme_fr, vues[cle][0])
                vues[cle] = (entree.terme_fr, contexte.a_verifier)


def test_aucun_couple_de_termes_n_est_repete(glossaire_fourni):
    couples = Counter((cle_souple(entree.terme_fr), cle_stricte(entree.terme_ar))
                      for entree in glossaire_fourni.entrees)
    assert [couple for couple, nombre in couples.items() if nombre > 1] == []


def test_les_termes_associes_sont_des_entrees(glossaire_fourni):
    """Les puces « Termes associés » ouvrent une fiche : chaque terme associé a son entrée."""
    absents = {terme for entree in glossaire_fourni.entrees for terme in entree.termes_associes
               if glossaire_fourni.par_terme(terme, FR) is None}
    assert absents == set()


def test_les_homonymes(glossaire_fourni):
    """Formes qui désignent plusieurs noms : la traduction d'un texte choisit d'après le contexte.

    Ces homonymes se trouvent tous parmi les 1 000 entrées complètes : un nom seul n'en ajoute aucun.
    """
    def homonymes(langue):
        return {entree.terme(langue) for entree in glossaire_fourni.entrees
                if sum(se_remplace_dans_un_texte(autre)
                       for autre in glossaire_fourni.homonymes(entree, langue)) > 1}

    assert homonymes(FR) == {"action", "auteur", "droit", "majorité"}
    assert homonymes(AR) == {"القانون المدني", "تأمين", "حكم", "دين", "شريك", "عرف", "قانون", "قرار", "كفالة",
                             "ولاية"}
    # Un verbe ou un adjectif peut s'écrire comme un nom : l'écran « Terme » propose alors les deux fiches.
    juger = glossaire_fourni.par_terme("juger", FR)
    assert [(autre.terme_fr, autre.categorie_fr) for autre in glossaire_fourni.homonymes(juger, AR)] == [
        ("disposition", "nom féminin"), ("jugement", "nom masculin"), ("juger", "verbe")]
    assert glossaire_fourni.libelle(juger, AR) == "حكم (juger)"


def test_les_termes_au_pluriel_sont_signales(glossaire_fourni):
    """« biens », « droits de l'homme »… : la catégorie contient « pluriel », pour l'article « les »."""
    complets = glossaire_fourni.entrees[:ENTREES_COMPLETES]
    pluriels = {entree.terme_fr for entree in complets if "pluriel" in entree.categorie_fr}
    assert len(pluriels) == 24
    assert {"biens", "dépens", "arrhes", "droits de l'homme", "libertés fondamentales"} <= pluriels
    assert all(terme.split()[0].endswith("s") for terme in pluriels)
    # Parmi les termes seuls aussi, un terme noté au pluriel commence par un mot au pluriel (« travaux publics »).
    seuls = {entree.terme_fr for entree in glossaire_fourni.entrees[ENTREES_COMPLETES:]
             if "pluriel" in entree.categorie_fr}
    assert all(terme.split()[0].endswith(("s", "x")) for terme in seuls), sorted(seuls)


# ------------------------------------------------------------------ recherche
#: Nombre d'entrées dont le terme contient « contrat », sans compter « contrat » lui-même.
EXPRESSIONS_AVEC_CONTRAT = 69


def test_recherche_dans_le_glossaire_fourni(glossaire_fourni):
    contrats = [entree.terme_fr for entree in glossaire_fourni.chercher("contrat", FR)]
    assert len(contrats) == EXPRESSIONS_AVEC_CONTRAT + 1
    assert contrats[:3] == ["contrat", "contrat-type", "contrat réel"]  # le terme, puis les plus courts
    assert {"contrat de bail", "contrat de vente", "contrat-cadre", "formation du contrat"} <= set(contrats)
    assert glossaire_fourni.chercher("عقد", AR)[0].terme_fr == "contrat"
    # Un synonyme passe avant les expressions qui commencent par lui : son entrée donne l'équivalent du mot cherché.
    prejudices = [entree.terme_fr for entree in glossaire_fourni.chercher("préjudice", FR)]
    assert prejudices[:2] == ["dommage", "préjudice futur"]
    assert prejudices[-2:] == ["réparer le préjudice", "divorce pour préjudice"]
    assert [entree.terme_ar for entree in glossaire_fourni.chercher("droit", FR)[:2]] == ["حق", "قانون"]
    assert [entree.terme_fr for entree in glossaire_fourni.propositions("contart", FR)] == ["contrat", "constat",
                                                                                           "constater"]
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
        ("Le condamné et l'assuré ; la cause du contrat.", "[المحكوم عليه] {et} [المؤمن له]؛ [سبب العقد]."),
        # Une majuscule peut ne pas porter son accent.
        ("L'Etat garantit la propriété.", "[الدولة] {garantit} [الملكية]."),
        # Deux expressions qui se suivent : « principe de légalité » puis « légalité des délits et des peines »,
        # « délai d'exécution » puis « exécution du contrat » puis « contrat de vente ».
        ("Le principe de légalité des délits et des peines s'impose au juge.",
         "[مبدأ] [شرعية الجرائم والعقوبات] {s'}{impose} {au} [القاضي]."),
        ("Le principe de légalité soumet l'administration à la loi.",
         "[مبدأ المشروعية] {soumet} [الإدارة] {à} [القانون]."),
        ("Le délai d'exécution du contrat de vente est dépassé.", "[أجل] [تنفيذ] [عقد البيع] {est} {dépassé}."),
        ("Le wali veille au maintien de l'ordre public.", "[الوالي] {veille} {au} [حفظ النظام العام]."),
        # « nomination » est donné comme synonyme de « désignation » (تعيين).
        ("La nomination des fonctionnaires et la désignation d'un expert.",
         "[تعيين] [الموظفون] {et} [التعيين] {d'}[خبير]."),
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
        # Des mots à double sens que des locutions gardent entiers : « حيز التنفيذ » (en vigueur) n'est pas
        # « l'exécution », « من طرف » (par) n'est pas « la partie », ni « من أجل » (pour) « le délai ».
        ("يدخل القانون حيز التنفيذ بعد نشره.", "{يدخل} [la loi] {حيز} {التنفيذ} {بعد} [sa publication]."),
        ("يعين الخبير من طرف القاضي من أجل تقييم الضرر.",
         "{يعين} [l’expert] {من} {طرف} [le juge] {من} {أجل} [l’évaluation] [du dommage]."),
        # « بحرية » : « maritime », ou « librement ». Le glossaire n'a que le pluriel « حريات » (libertés), pour
        # ne pas lire « ب + حرية » dans « عمارة بحرية » (bâtiment de mer).
        ("عمارة بحرية مخصصة للملاحة البحرية.", "{عمارة} {بحرية} {مخصصة} {لـ} [la navigation maritime]."),
        ("تعيين القضاة وحرياتهم.", "[La désignation] [des juges] {و} [leurs libertés]."),
        # « ديون الدولة » : les dettes de l'État. Aucune expression ne lit ici « دين » comme la religion.
        ("ارتفعت ديون الدولة.", "{ارتفعت} [les dettes] [de l’État]."),
        # Deux expressions qui se suivent : « حكم الطلاق » puis « طلاق بالتراضي ».
        ("صدر حكم الطلاق بالتراضي.", "{صدر} [le jugement] [du divorce par consentement mutuel]."),
        ("يحدد مكتب المجلس الشعبي الوطني جدول الأعمال.",
         "{يحدد} [le bureau] [de l’Assemblée populaire nationale] [l’ordre du jour]."),
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

from PySide6.QtWidgets import QLabel  # noqa: E402
from test_interface import textes  # noqa: E402

from traducteur.interface.fiche import LigneDeProvenance  # noqa: E402


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
    # Le glossaire est chargé à l'ouverture ; l'écran « Paramètres » le présente.
    parametres = fenetre_fournie.page_parametres
    assert parametres.nom_du_glossaire.texte_complet() == "Glossaire juridique"
    assert parametres.dossier_du_glossaire.texte_complet() == "Fourni avec l’application"
    assert parametres.taille_du_glossaire.text() == f"{nombre(NOMBRE_D_ENTREES)} entrées"
    assert fenetre_fournie.barre_etat.texte() == ""
    assert f"glossaire de {nombre(NOMBRE_D_ENTREES)} entrées" in fenetre_fournie.page_description.presentation.text()

    page = fenetre_fournie.page
    details = page.details
    # Les termes proposés à l'accueil sont pris parmi les entrées complètes : leur fiche a une définition.
    assert len(page.accueil.puces) == 5
    assert [entree.numero for entree in page._exemples()] == [1, 201, 401, 601, 801]
    assert [puce.text() for puce in page.accueil.puces] == [entree.terme_fr for entree in page._exemples()]
    page.rechercher("contrat")
    expressions = EXPRESSIONS_AVEC_CONTRAT
    assert page.barre.texte_du_resume() == f"1 terme · {expressions} expressions"
    assert fenetre_fournie.barre_etat.etat() == f"« contrat » : {expressions + 1} entrées trouvées dans le glossaire."
    assert page.fiche.colonne_terme.rang.texte_complet() == f"Entrée 1 sur {nombre(NOMBRE_D_ENTREES)}"
    # Le menu « Plus de détails » : les six cercles de « contrat » sont colorés, aucun n'est ouvert d'office.
    assert details.renseignes() == list(details.colonnes) and details.detail == ""
    assert details.etats()["expressions"] == (True, expressions)
    details.roue.boutons["expressions"].click()
    assert details.titre_du_detail.texte_complet() == "Expressions avec « contrat »"
    assert details.nombre.text() == str(expressions) and len(details.colonne_expressions.entrees()) == expressions

    # « loi organique » n'avait aucune phrase avant la version 0.5. La contextualisation affiche maintenant son
    # exemple, sous la mention « À vérifier » tant que le glossaire ne cite pas de source pour cette phrase.
    page.rechercher("loi organique")
    details.roue.boutons["contexte"].click()
    colonne = details.colonne_contexte
    exemple = colonne.emplois[0]
    assert exemple.origine == "propre" and exemple.entree.terme_fr == "loi organique"
    lignes = textes(colonne.corps)
    assert exemple.fr in lignes and exemple.ar in lignes
    assert (lignes[0] == "À vérifier") == exemple.a_verifier
    assert exemple.a_verifier or lignes[0] == exemple.source
    assert details.renseignes() == ["definition", "contexte", "ressources", "associes"]
    # « consentement » : son exemple (un article du Code civil, cité avec son numéro), puis la phrase d'une
    # autre entrée. L'étiquette de cette phrase dit d'où elle vient, si elle est à vérifier, et ouvre son entrée.
    page.rechercher("consentement")
    assert details.detail == "contexte"  # l'information choisie reste ouverte d'un terme à l'autre
    propre, autre = colonne.emplois
    assert (propre.origine, propre.a_verifier) == ("propre", False) and autre.origine != "propre"
    assert textes(colonne.corps)[0] == propre.source == "Code civil, art. 106"
    provenance, = colonne.corps.findChildren(LigneDeProvenance)
    assert provenance.lien.texte_complet == autre.provenance() and provenance.a_verifier() == autre.a_verifier
    assert ("À vérifier" in textes(colonne.corps)) == autre.a_verifier
    provenance.lien.click()
    assert page.fiche.colonne_terme.terme.terme == autre.entree.terme_fr != "consentement"

    # « droit » : deux entrées de même forme (un onglet chacune), puis les expressions et les termes proches.
    page.rechercher("droit")
    assert [onglet.text() for onglet in page.fiche.onglets.onglets] == ["Sens 1 : حق", "Sens 2 : قانون"]
    assert details.colonne_expressions.entrees()[0].terme_fr == "droit réel"
    assert details.roue.boutons["expressions"].libelle in ("Termes proches", "Proches")

    # Les suggestions pendant la saisie couvrent tout le glossaire. Un terme porté par plusieurs entrées n'est
    # proposé qu'une fois : « droit », « majorité », « action », « auteur », « récidiviste » (nom et adjectif) et
    # « en vigueur » (adjectif et adverbe).
    suggestions = page.suggestions.model().stringList()
    assert len(suggestions) == NOMBRE_D_ENTREES - 6 == len({entree.terme_fr for entree in page.glossaire.entrees})
    assert {"protégé", "protéger", "protection", "grève", "grevé", "de plein droit"} <= set(suggestions)

    # Fenêtre étroite : la fiche garde tout son contenu, et la liste des 33 expressions défile à droite de la roue.
    page.rechercher("responsabilité")
    details.choisir("expressions")
    fenetre_fournie.resize(1080, 620)
    application.processEvents()
    assert page.fiche.defilement.verticalScrollBar().maximum() == 0
    assert page.fiche.height() >= page.fiche.hauteur_du_contenu(page.fiche.width())
    assert details.height() >= details.HAUTEUR_MINIMALE
    assert len(details.colonne_expressions.entrees()) == 33
    assert details.colonne_expressions.grille.height() > details.height()  # plus haute que le panneau : elle défile


def test_la_fiche_d_un_terme_seul_avec_le_glossaire_fourni(fenetre_fournie, application):
    """Un des 4 000 termes seuls : la fiche donne l'équivalent, « à vérifier » ; le menu dit ce qui manque."""
    page = fenetre_fournie.page
    details = page.details
    page.rechercher("protege")  # saisi sans accent
    application.processEvents()
    entree = page.entree
    assert entree.terme_fr == "protégé" and entree.numero > ENTREES_COMPLETES
    assert not entree.definition_fr and len(entree.contextes) == 1
    # La fiche : le terme, son équivalent et, au pied de l'équivalent, la mention « À vérifier ».
    assert textes(page.fiche.colonne_terme.corps)[:2] == ["FRANÇAIS · SOURCE", "protégé"]
    assert page.fiche.colonne_equivalent.terme.terme == entree.terme_ar
    assert textes(page.fiche.colonne_equivalent.pied) == ["À vérifier", "· équivalent d’exemple"]
    # Le menu : pas de définition (cercle gris) ; l'invitation ne nomme que ce qui existe.
    etats = details.etats()
    assert etats["definition"] == (False, 0) and "definition" not in details.renseignes()
    assert "définition" not in details.invite.texte.text()
    details.roue.boutons["definition"].click()
    assert textes(details.colonne_definition.corps) == [
        "Aucune définition pour ce terme", "Le glossaire n’en donne pas encore."]
    # Depuis la version 0.11, le terme a sa phrase d'exemple : le cercle « Contextualisation » est coloré. La
    # phrase porte la mention « À vérifier », et l'adjectif y est mis en évidence, accordé ou non.
    assert etats["contexte"][0] and "contexte" in details.renseignes()
    details.roue.boutons["contexte"].click()
    colonne = details.colonne_contexte
    exemple = colonne.emplois[0]
    assert exemple.origine == "propre" and exemple.a_verifier
    lignes = textes(colonne.corps)
    assert lignes[0] == "À vérifier" and exemple.fr in lignes and exemple.ar in lignes
    assert "protégé" in exemple.fr and "محمي" in exemple.ar
    # Un verbe : la phrase l'emploie au passé, « a abrogé » et « ألغى » ; les deux formes sont mises en évidence.
    page.rechercher("abroger")
    assert page.entree.terme_fr == "abroger" and details.detail == "contexte"
    abroger = colonne.emplois[0]
    assert abroger.origine == "propre" and "a abrogé" in abroger.fr and abroger.ar.startswith("ألغى ")
    riches = [label.text() for label in colonne.corps.findChildren(QLabel) if "font-weight" in label.text()]
    assert any(">abrogé</span>" in texte for texte in riches) and any(">ألغى</span>" in texte for texte in riches)
    # Un terme absent du glossaire : la première entrée trouvée est affichée, et la liste des autres s'ouvre.
    details.bouton_fermer.click()
    page.rechercher("magistrat")
    assert page.entree.terme_fr != "magistrat" and "magistrat" in page.entree.terme_fr
    assert details.detail == "expressions"
    assert details.titre_du_detail.texte_complet() == "Autres résultats pour « magistrat »"


def test_ecran_texte_avec_le_glossaire_fourni(fenetre_fournie, application):
    from traducteur.interface.fenetre import MODE_TERME, MODE_TEXTE

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
    # L'écran en rend compte : état de la traduction, une case par terme, barre d'état.
    assert page.badge.texte() == "Traduction partielle · 83 mots sur 84 trouvés"
    cases = page.termes.cellules
    assert page.termes.nombre.text() == "13" and len(cases) == 13
    assert [case.entree for case in cases] == [terme.entree for terme in traduction.termes]
    assert cases[0].text() == "contrat — عقد"
    # Ces treize termes sont des entrées complètes : aucun équivalent n'est signalé « à vérifier ».
    assert not any(case.a_verifier for case in cases)
    assert fenetre_fournie.barre_etat.etat() == "Traduction : 83 mots sur 84 trouvés dans le glossaire."
    # Un clic sur une case ouvre la fiche du terme : sa définition, ses exemples et ses références y sont.
    for case in (cases[0], cases[4], cases[-1]):
        case.click()
        assert fenetre_fournie.mode == MODE_TERME and fenetre_fournie.page.entree is case.entree
        etats = fenetre_fournie.page.details.etats()
        assert etats["definition"][0] and etats["contexte"][0] and etats["ressources"][0], case.text()
        assert etats["ressources"][1] == len(case.entree.ressources)
        fenetre_fournie.bouton_retour.click()
        assert fenetre_fournie.mode == MODE_TEXTE and page.traduction is traduction
