"""Traduction d'un texte à l'aide du glossaire : recherche, règles, reconstruction."""

import pytest
from test_segmentation import ARTICLES_AR, ARTICLES_FR

from traducteur.glossaire import Glossaire
from traducteur.langues import AR, FR
from traducteur.traduction import ATTESTE, NEUTRE, REGLES, SOURCE, TERME, Traducteur, cle_phrase


@pytest.fixture(scope="module")
def traducteur(glossaire):
    return Traducteur(glossaire)


def balise(traduction) -> str:
    """Texte traduit, les termes du glossaire entre crochets et les mots non traduits entre accolades."""
    marques = {TERME: "[{}]", SOURCE: "{{{}}}", ATTESTE: "{}", NEUTRE: "{}"}
    return "".join(marques[morceau.nature].format(morceau.texte) for morceau in traduction.morceaux)


# ------------------------------------------------------------------ phrases reprises des exemples
def test_les_articles_106_et_107_sont_repris_des_exemples(traducteur):
    """Les quatre phrases figurent parmi les exemples du glossaire : la traduction est le texte officiel."""
    traduction = traducteur.traduire(ARTICLES_FR, FR)
    assert traduction.texte == ARTICLES_AR
    assert len(traduction.phrases) == traduction.phrases_attestees == 4
    assert (traduction.mots, traduction.mots_reconnus) == (76, 76)
    assert traduction.complete and traduction.mots_absents == []
    assert traduction.regles["phrase"] == 4
    assert traduction.decompte_cible() == (4, 49, 288)
    assert [(terme.entree.terme_fr, len(terme.occurrences)) for terme in traduction.termes] == [
        ("contrat", 3), ("loi", 3), ("partie", 1), ("consentement", 1), ("bonne foi", 1), ("contractant", 1),
        ("usage", 1), ("équité", 1), ("obligation", 1)]
    # Les équivalents des termes relevés sont repérés dans le texte arabe.
    assert [morceau.texte for morceau in traduction.morceaux if morceau.nature == TERME][:4] == [
        "العقد", "القانون", "العقد", "وبحسن نية"]


def test_meme_texte_de_l_arabe_vers_le_francais(traducteur):
    traduction = traducteur.traduire(ARTICLES_AR, AR)
    assert traduction.texte == ARTICLES_FR
    assert traduction.complete and (traduction.mots, traduction.mots_reconnus) == (49, 49)


def test_une_phrase_est_reconnue_malgre_la_ponctuation_et_les_majuscules(traducteur):
    traduction = traducteur.traduire("le contrat fait la loi des parties", FR)
    assert traduction.phrases_attestees == 1
    assert traduction.texte == "العقد شريعة المتعاقدين."
    assert cle_phrase("« Le contrat, fait la loi des parties ! »") == "le contrat fait la loi des parties"


def test_une_phrase_reprise_d_un_exemple_a_verifier_est_comptee_a_part(traducteur, tmp_path):
    """La traduction vient de l'exemple dans les deux cas ; le compte dit combien d'exemples sont « à vérifier »."""
    # Les exemples du glossaire d'essai citent tous le Code civil.
    assert traducteur.traduire(ARTICLES_FR, FR).phrases_a_verifier == 0
    fichier = tmp_path / "exemples.csv"
    fichier.write_text(
        "terme_fr;terme_ar;contexte_fr;contexte_ar;source_contexte\n"
        "bail;إيجار;Le bail est écrit.;الإيجار مكتوب.;à vérifier (phrase d’exemple)\n"
        "loyer;بدل الإيجار;Le loyer est payé chaque mois.;يدفع بدل الإيجار كل شهر.;Code civil, art. 498\n"
        "caution;كفيل;La caution paie la dette.;يوفي الكفيل الدين.;\n",
        encoding="utf-8")
    rediges = Traducteur(Glossaire.charger(fichier))
    traduction = rediges.traduire("Le bail est écrit. Le loyer est payé chaque mois. La caution paie la dette.", FR)
    assert traduction.texte == "الإيجار مكتوب. يدفع بدل الإيجار كل شهر. يوفي الكفيل الدين."
    assert (traduction.phrases_attestees, traduction.phrases_a_verifier) == (3, 1)
    assert [phrase.attestation.a_verifier for phrase in traduction.phrases] == [True, False, False]
    # Dans l'autre sens aussi.
    retour = rediges.traduire("الإيجار مكتوب.", AR)
    assert retour.texte == "Le bail est écrit." and retour.phrases_a_verifier == 1
    # Une phrase traduite mot à mot ne vient d'aucun exemple.
    assert rediges.traduire("Le bail prend fin.", FR).phrases_a_verifier == 0


def test_les_positions_des_termes_dans_le_texte_source(traducteur):
    texte = "  Le contrat fait la loi des parties.\nLa vente et le bail."
    traduction = traducteur.traduire(texte, FR)
    assert [texte[occurrence.debut:occurrence.fin] for occurrence in traduction.occurrences] == [
        "contrat", "loi", "parties", "vente", "bail"]
    assert [occurrence.phrase for occurrence in traduction.occurrences] == [0, 0, 0, 1, 1]
    # Les espaces et les retours à la ligne qui séparent les phrases sont conservés.
    assert traduction.texte.startswith("  العقد شريعة المتعاقدين.\n")


# ------------------------------------------------------------------ du français vers l'arabe
@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        # Article défini, article indéfini.
        ("Le juge applique la loi.", "[القاضي] {applique} [القانون]."),
        ("Un contrat et une obligation.", "[عقد] {et} [التزام]."),
        ("L’équité, d’après l’usage.", "[العدالة]، {d’}{après} [العرف]."),
        # Complément du nom : le premier nom perd l'article, le second le prend.
        ("La nullité du contrat de vente protège l'acheteur.", "[بطلان] [عقد البيع] {protège} [المشتري]."),
        ("Le prix de vente. Un prix de vente.", "[ثمن] [البيع]. [ثمن] [بيع]."),
        ("L'équité du juge.", "[عدالة] [القاضي]."),
        # Après une locution, le complément est introduit par « لـ ».
        ("La bonne foi du contractant.", "[حسن النية] [للمتعاقد]."),
        # Pluriel.
        ("Les obligations du vendeur et les droits de l’acheteur.",
         "[التزامات] [البائع] {et} [حقوق] [المشتري]."),
        ("Des contrats conclus par les bailleurs.", "[عقود] {conclus} {par} [المؤجرون]."),
        # Pluriel d'une expression : en arabe, seul le premier mot de l'annexion se met au pluriel.
        ("Les contrats de bail et les contrats de travail.", "[عقود الإيجار] {et} [عقود العمل]."),
        # Pluriel inconnu (le premier mot n'est pas dans le glossaire, ou le terme est un nom suivi
        # d'un adjectif) : le terme reste au singulier.
        ("Les loyers et les codes civils.", "[بدل الإيجار] {et} [القانون المدني]."),
        # « du », « au » restent dans le texte ; le nom qui suit prend l'article.
        ("Il est dû au créancier, en vertu du contrat.", "{Il} {est} {dû} {au} [الدائن]، {en} {vertu} {du} [العقد]."),
        # Synonyme ramené au terme du glossaire.
        ("La convention et le dédommagement.", "[العقد] {et} [التعويض]."),
        # Ponctuation arabe, nombres recopiés.
        ("Quel est le prix ; 1 500 ou 2,5 % ?", "{Quel} {est} [الثمن]؛ 1 500 {ou} 2,5 %؟"),
    ],
)
def test_du_francais_vers_l_arabe(traducteur, texte, attendu):
    assert balise(traducteur.traduire(texte, FR)) == attendu


def test_regles_appliquees_et_mots_absents(traducteur):
    traduction = traducteur.traduire("Les obligations du vendeur sont fixées par un contrat de vente.", FR)
    assert balise(traduction) == "[التزامات] [البائع] {sont} {fixées} {par} [عقد البيع]."
    assert dict(traduction.regles) == {"pluriel": 1, "annexion": 1, "expression": 1, "indefini": 1}
    assert (traduction.mots, traduction.mots_reconnus) == (11, 8)
    assert not traduction.complete
    assert traduction.mots_absents == ["sont", "fixées", "par"]
    familles = traduction.regles_par_famille()
    assert familles["lexique"] == [(REGLES["expression"][1], 1)]
    assert [libelle for libelle, _ in familles["grammaire"]] == [
        "Accord en nombre : pluriel", "Article indéfini", "Complément du nom"]
    assert familles["sémantique"] == []


def test_l_expression_la_plus_longue_l_emporte(traducteur):
    traduction = traducteur.traduire("Le contrat de vente, le contrat et la vente.", FR)
    assert [terme.entree.terme_fr for terme in traduction.termes] == ["contrat de vente", "contrat", "vente"]
    assert balise(traduction) == "[عقد البيع]، [العقد] {et} [البيع]."


def test_pluriel_d_une_expression_les_regles_sont_comptees(traducteur):
    traduction = traducteur.traduire("Les contrats de bail.", FR)
    assert dict(traduction.regles) == {"expression": 1, "article": 1, "pluriel": 1}
    # « بدل الإيجار » : pluriel inconnu, la règle du pluriel n'est donc pas comptée.
    assert dict(traducteur.traduire("Les loyers.", FR).regles) == {"article": 1}
    retour = traducteur.traduire("عقود الإيجار.", AR)
    assert dict(retour.regles) == {"expression": 1, "article": 1, "pluriel": 1}
    assert [terme.entree.terme_fr for terme in retour.termes] == ["contrat de bail"]


@pytest.mark.parametrize(
    ("texte", "langue", "attendu"),
    [
        ("Bonjour à tous, comment allez-vous ?", FR, "{Bonjour} {à} {tous}, {comment} {allez-vous} ?"),
        ("مرحبا بالجميع، كيف حالكم؟", AR, "{مرحبا} {بالجميع}، {كيف} {حالكم}؟"),
        ("في ٢٦ سبتمبر ١٩٧٥؛ ثم ماذا؟", AR, "{في} ٢٦ {سبتمبر} ١٩٧٥؛ {ثم} {ماذا}؟"),
        # Dès qu'un terme est trouvé, la phrase reçoit la ponctuation de la langue cible.
        ("Bonjour, voici le contrat ; merci.", FR, "{Bonjour}، {voici} [العقد]؛ {merci}."),
    ],
)
def test_une_phrase_sans_terme_est_recopiee_telle_quelle(traducteur, texte, langue, attendu):
    """Ponctuation et chiffres compris : seule une phrase en partie traduite est récrite."""
    traduction = traducteur.traduire(texte, langue)
    assert balise(traduction) == attendu
    if "[" not in attendu:
        assert traduction.texte == texte


def test_un_texte_sans_accent_est_compare_sans_les_accents(traducteur):
    assert balise(traducteur.traduire("LA NULLITE ET L'EQUITE", FR)) == "[البطلان] {ET} [العدالة]"
    assert balise(traducteur.traduire("la nullite du contrat et l'equite", FR)) == "[بطلان] [العقد] {et} [العدالة]"


def test_dans_un_texte_accentue_les_accents_comptent():
    """« cause » n'est pas « causé », ni « condamne » « condamné » : ce ne sont pas les mêmes mots."""
    traducteur = Traducteur(glossaire_de(
        "terme_fr;terme_ar;categorie_fr;pluriel_fr;pluriel_ar\n"
        "cause;سبب;nom féminin;causes;أسباب\n"
        "condamné;المحكوم عليه;nom masculin;;\n"
        "grève;إضراب;nom féminin;;\n"
        "tribunal;محكمة;nom masculin;;\n"
        "État;دولة;nom masculin;;\n"
        "équité;عدالة;nom féminin;;\n"))
    assert balise(traducteur.traduire("Le tribunal condamne l'État ; le condamné.", FR)) == (
        "[المحكمة] {condamne} [الدولة]؛ [المحكوم عليه].")
    assert balise(traducteur.traduire("Le dommage causé, les dommages causés et un bien grevé.", FR)) == (
        "{Le} {dommage} {causé}, {les} {dommages} {causés} {et} {un} {bien} {grevé}.")
    assert balise(traducteur.traduire("La cause, les causes et la grève générale.", FR)) == (
        "[السبب]، [الأسباب] {et} [الإضراب] {générale}.")
    # Une majuscule peut ne pas porter son accent ; une minuscule doit le porter.
    assert balise(traducteur.traduire("L'Etat, l'EQUITE et l'équité, mais pas l'equite.", FR)) == (
        "[الدولة]، [العدالة] {et} [العدالة]، {mais} {pas} {l'}{equite}.")
    # Dans un texte sans aucun accent, la comparaison reste tolérante : le verbe est pris pour le nom.
    assert balise(traducteur.traduire("Le tribunal condamne.", FR)) == "[المحكمة] [المحكوم عليه]."


def test_un_glossaire_ecrit_sans_accents_est_compare_sans_les_accents():
    traducteur = Traducteur(glossaire_de("terme_fr;terme_ar\npropriete;ملكية\nequite;عدالة\n"))
    assert balise(traducteur.traduire("La propriété et l'équité sont protégées.", FR)) == (
        "[الملكية] {et} [العدالة] {sont} {protégées}.")


# ------------------------------------------------------------------ homonymes
def test_homonymes_departages_par_le_contexte(traducteur):
    """« droit » : حق (droit de propriété) ou قانون (ensemble des règles)."""
    traduction = traducteur.traduire("Le juge applique la loi ; le droit de propriété est garanti.", FR)
    droit = next(terme for terme in traduction.termes if terme.entree.terme_fr == "droit")
    assert droit.entree.terme_ar == "حق" and not droit.incertain
    assert [autre.terme_ar for autre in droit.autres_candidats] == ["قانون"]
    assert traduction.regles["homonyme"] == 1

    traduction = traducteur.traduire("Le droit et la loi, le code civil.", FR)
    assert traduction.termes[0].entree.terme_ar == "قانون"


def test_homonymes_que_le_contexte_ne_departage_pas(traducteur):
    traduction = traducteur.traduire("Le droit.", FR)
    droit = traduction.termes[0]
    assert droit.incertain and droit.entree.terme_ar == "حق"  # à défaut, la première entrée du glossaire
    assert traduction.regles["homonyme"] == 0


# ------------------------------------------------------------------ de l'arabe vers le français
@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        # Article, complément du nom, contraction « du », élision.
        ("بطلان العقد يحمي المشتري.", "[La nullité] [du contrat] {يحمي} [l’acheteur]."),
        ("ثمن البيع. عقد بيع.", "[Le prix] [de la vente]. [Contrat de vente]."),
        ("بطلان عقد الإيجار.", "[La nullité] [du contrat de bail]."),
        # Pluriel et duel ; la particule « و » est séparée du mot.
        ("التزامات البائع وحقوق المشتري.", "[Les obligations] [du vendeur] {و} [les droits] [de l’acheteur]."),
        ("وقع الطرفان عقدا.", "{وقع} [les parties] [un contrat]."),
        # Possessif.
        ("أبرم المؤجرون عقودهم بحسن نية.", "{أبرم} [les bailleurs] [leurs contrats] {بـ} [bonne foi]."),
        # Expression dont le premier mot est au pluriel ; expression déterminée.
        ("عقود الإيجار وعقود العمل.", "[Les contrats de bail] {و} [les contrats de travail]."),
        ("حسن النية في القانون المدني.", "[La bonne foi] {في} [le code civil]."),
        ("مسؤولية المدين وأهليته.", "[La responsabilité] [du débiteur] {و} [sa capacité]."),
        # « لـ » + article ; ponctuation française ; chiffres arabes.
        ("للدائن حق؛ في ٢٦ سبتمبر ١٩٧٥؟", "{لـ} [le créancier] [droit]\u00a0; {في} 26 {سبتمبر} 1975\u00a0?"),
        # Texte vocalisé.
        ("الْعَقْدُ وَالْقَانُونُ.", "[Le contrat] {و} [la loi]."),
        # Un nom sans article et sans complément reste sans article.
        ("عقد.", "[Contrat]."),
    ],
)
def test_de_l_arabe_vers_le_francais(traducteur, texte, attendu):
    assert balise(traducteur.traduire(texte, AR)) == attendu


def test_un_adjectif_de_relation_n_est_pas_pris_pour_un_possessif(traducteur):
    """« قانوني » (légal) n'est pas « قانون » suivi d'un pronom."""
    assert balise(traducteur.traduire("نص قانوني.", AR)) == "{نص} {قانوني}."


# ------------------------------------------------------------------ glossaires particuliers
def glossaire_de(texte: str) -> Glossaire:
    return Glossaire.depuis_texte(texte)


def test_particule_et_conjonction_presentes_dans_le_glossaire():
    """Si le glossaire contient « et » et « و », la conjonction est traduite et collée au mot arabe."""
    traducteur = Traducteur(glossaire_de("terme_fr;terme_ar;categorie_fr\net;و;\nloi;قانون;nom féminin\n"
                                         "usage;عرف;nom masculin\n"))
    assert balise(traducteur.traduire("La loi et l'usage.", FR)) == "[القانون] [و][العرف]."
    assert balise(traducteur.traduire("القانون والعرف.", AR)) == "[La loi] [et] [l’usage]."


def test_genre_inconnu_pas_d_article_devant_une_consonne():
    traducteur = Traducteur(glossaire_de("terme_fr;terme_ar\ntribunal;محكمة\nappel;استئناف\n"))
    # « tribunal » : genre inconnu, donc pas d'article ; « l’ » convient aux deux genres.
    assert balise(traducteur.traduire("المحكمة والاستئناف.", AR)) == "[Tribunal] {و} [l’appel]."
    # Le pluriel « محاكم » ne figure pas dans le glossaire : le mot reste tel quel.
    assert balise(traducteur.traduire("المحاكم.", AR)) == "{المحاكم}."


def test_pluriel_deduit_quand_la_colonne_est_vide():
    traducteur = Traducteur(glossaire_de(
        "terme_fr;terme_ar;categorie_fr\ntribunal;محكمة;nom masculin\njugement;حكم;nom masculin\n"
        "voie de recours;طريق الطعن;locution nominale féminine\n"))
    assert balise(traducteur.traduire("Les tribunaux et des jugements.", FR)) == "[المحكمة] {et} [حكم]."
    traduction = traducteur.traduire("Des voies de recours.", FR)
    assert [terme.entree.terme_fr for terme in traduction.termes] == ["voie de recours"]


def test_un_terme_francais_deja_au_pluriel():
    """« biens », « arrhes » : la catégorie indique un pluriel, donc « les », « des », « ses »."""
    traducteur = Traducteur(glossaire_de(
        "terme_fr;terme_ar;categorie_fr;categorie_ar\n"
        "biens;أموال;nom masculin pluriel;اسم مذكر\n"
        "arrhes;عربون;nom féminin pluriel;اسم مذكر\n"
        "droits de l'homme;حقوق الإنسان;locution nominale (masculin pluriel);مركب إضافي\n"
        "débiteur;مدين;nom masculin;اسم مذكر\n"))
    traduction = traducteur.traduire("الأموال وحقوق الإنسان.", AR)
    assert balise(traduction) == "[Les biens] {و} [les droits de l'homme]."
    assert traduction.regles["pluriel"] == 0  # le terme est écrit tel qu'il figure dans le glossaire
    assert balise(traducteur.traduire("أمواله وأموالهم وأموال المدين.", AR)) == (
        "[Ses biens] {و} [leurs biens] {و} [les biens] [du débiteur].")
    assert balise(traducteur.traduire("دفع المدين عربونا، ثم العربون.", AR)) == (
        "{دفع} [le débiteur] [des arrhes], {ثم} [les arrhes].")
    # Vers l'arabe, le terme est repris tel quel : il n'a pas d'autre pluriel.
    assert balise(traducteur.traduire("Les biens du débiteur et les droits de l'homme.", FR)) == (
        "[أموال] [المدين] {et} [حقوق الإنسان].")


def test_apres_un_determinant_singulier_un_mot_n_est_pas_un_pluriel():
    """« cours » est le pluriel de « cour » dans « les cours », pas dans « au cours de »."""
    traducteur = Traducteur(glossaire_de(
        "terme_fr;terme_ar;categorie_fr;categorie_ar;pluriel_fr;pluriel_ar\n"
        "cour;مجلس قضائي;nom féminin;مركب وصفي;cours;مجالس قضائية\n"
        "tribunal;محكمة;nom masculin;اسم مؤنث;tribunaux;محاكم\n"
        "audience;جلسة;nom féminin;اسم مؤنث;audiences;جلسات\n"
        "prix;ثمن;nom masculin;اسم مذكر;prix;أثمان\n"))
    assert balise(traducteur.traduire("Les cours et les tribunaux.", FR)) == "[المجالس القضائية] {et} [المحاكم]."
    assert balise(traducteur.traduire("Au cours de l'audience.", FR)) == "{Au} {cours} {de} [الجلسة]."
    assert balise(traducteur.traduire("Le cours des audiences ; son cours.", FR)) == (
        "{Le} {cours} [جلسات]؛ {son} {cours}.")
    # Un mot qui s'écrit de la même façon au singulier et au pluriel reste reconnu.
    assert balise(traducteur.traduire("Le prix et les prix.", FR)) == "[الثمن] {et} [الأثمان]."
    # Sans déterminant devant lui, le mot est lu comme un pluriel.
    assert balise(traducteur.traduire("En cours d'audience.", FR)) == "{En} [مجالس قضائية] [للجلسة]."

    # Même contrôle quand le pluriel est déduit par la règle générale (colonne « pluriel_fr » vide).
    traducteur = Traducteur(glossaire_de("terme_fr;terme_ar\ncour;مجلس قضائي\n"))
    assert balise(traducteur.traduire("Au cours de l'année.", FR)) == "{Au} {cours} {de} {l'}{année}."
    assert [terme.entree.terme_fr for terme in traducteur.traduire("Les cours.", FR).termes] == ["cour"]


def test_exemple_de_plusieurs_phrases():
    """Un exemple de deux phrases dans les deux langues : chaque phrase est aussi reconnue seule."""
    traducteur = Traducteur(glossaire_de(
        "terme_fr;terme_ar;contexte_fr;contexte_ar\n"
        "appel;استئناف;L'appel est recevable. Il suspend l'exécution.;الاستئناف مقبول. ويوقف التنفيذ.\n"))
    assert traducteur.traduire("Il suspend l'exécution.", FR).texte == "ويوقف التنفيذ."
    assert traducteur.traduire("L'appel est recevable. Il suspend l'exécution.", FR).phrases_attestees == 2


def test_texte_vide_ou_sans_mot(traducteur):
    for texte in ("", "   \n", "— ... —"):
        traduction = traducteur.traduire(texte, FR)
        assert traduction.texte == texte and traduction.phrases == [] and traduction.termes == []
        assert not traduction.complete
