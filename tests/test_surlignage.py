"""Repérage du terme dans les phrases d'exemple (mise en évidence)."""

import pytest

from traducteur.glossaire import Entree
from traducteur.langues import AR, FR
from traducteur.surlignage import (
    ADJECTIF,
    INVARIABLE,
    NOM,
    VERBE,
    accords,
    nature_du_terme,
    participe_passe,
    positions_du_terme,
)
from traducteur.traduction import se_remplace_dans_un_texte

#: Catégories écrites dans le glossaire fourni pour un adjectif, un verbe, une préposition et leurs locutions.
ADJ, LOC_ADJ, V, LOC_V, PREP, CONJ = ("adjectif", "locution adjectivale", "verbe", "locution verbale",
                                      "locution prépositive", "locution conjonctive")


def reperes(phrase, langue, **champs):
    entree = Entree(numero=1, **{"terme_fr": "x", "terme_ar": "س", **champs})
    return [phrase[debut:fin] for debut, fin in positions_du_terme(phrase, entree, langue)]


@pytest.mark.parametrize(
    ("phrase", "champs", "attendu"),
    [
        ("Le contrat fait la loi des parties.", {"terme_fr": "contrat"}, ["contrat"]),
        ("Les Contrats spéciaux et le contrat.", {"terme_fr": "contrat"}, ["Contrats", "contrat"]),
        ("Les baux ruraux et le bail.", {"terme_fr": "bail", "pluriel_fr": "baux"}, ["baux", "bail"]),
        ("Exécuté de bonne  foi.", {"terme_fr": "bonne foi"}, ["bonne  foi"]),
        ("selon la loi, l’usage et l’équité", {"terme_fr": "usage"}, ["usage"]),
        ("le chef d’accusation", {"terme_fr": "chef d'accusation"}, ["chef d’accusation"]),
        ("Un emploi légal.", {"terme_fr": "loi"}, []),  # pas à l'intérieur d'un autre mot
        ("Le contrat doit être exécuté.", {"terme_fr": "exécution du contrat"}, []),
    ],
)
def test_reperage_en_francais(phrase, champs, attendu):
    assert reperes(phrase, FR, **champs) == attendu


@pytest.mark.parametrize(
    ("phrase", "champs", "attendu"),
    [
        ("العقد شريعة المتعاقدين.", {"terme_ar": "عقد"}, ["العقد"]),
        ("يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية.", {"terme_ar": "حسن النية"}, ["وبحسن نية"]),
        ("يتبادل الطرفان التعبير عن إرادتهما", {"terme_ar": "طرف"}, ["الطرفان"]),
        ("ويسبب ضررا للغير", {"terme_ar": "ضرر"}, ["ضررا"]),
        ("يرتكبه الشخص بخطئه،", {"terme_ar": "خطأ"}, ["بخطئه"]),
        ("حكم القاضي بمقتضى", {"terme_ar": "قاضٍ"}, ["القاضي"]),
        ("أن ينقل للمشتري ملكية شيء", {"terme_ar": "مشترٍ"}, ["للمشتري"]),
        ("بحسب طبيعة الالتزام.", {"terme_ar": "التزام"}, ["الالتزام"]),
        ("مقابل بدل إيجار معلوم.", {"terme_ar": "بدل الإيجار"}, ["بدل إيجار"]),
        ("يتضمن القانون المدني، معدل", {"terme_ar": "القانون المدني"}, ["القانون المدني"]),
        ("العَقْدُ شريعة", {"terme_ar": "عقد"}, ["العَقْدُ"]),  # texte vocalisé
        ("العقود المسماة", {"terme_ar": "عقد", "pluriel_ar": "عقود"}, ["العقود"]),
        ("هذه حقيقة ثابتة", {"terme_ar": "حق"}, []),  # « حقيقة » n'est pas une forme de « حق »
        # Dans un terme de plusieurs mots, le premier prend l'alif du cas direct, ou le « ي » d'un nom défectueux.
        ("اتخذ القاضي تدبيرا مؤقتا", {"terme_ar": "تدبير مؤقت"}, ["تدبيرا مؤقتا"]),
        ("يسلم المرقي العقاري السكنات", {"terme_ar": "مرقٍ عقاري"}, ["المرقي العقاري"]),
        ("عقد مع مرق عقاري", {"terme_ar": "مرقٍ عقاري"}, ["مرق عقاري"]),
    ],
)
def test_reperage_en_arabe(phrase, champs, attendu):
    assert reperes(phrase, AR, **champs) == attendu


# ------------------------------------------------------------------ adjectifs, verbes et locutions (version 0.11)
@pytest.mark.parametrize(
    ("categorie", "nature"),
    [
        ("", NOM), ("nom masculin", NOM), ("locution nominale féminine", NOM), ("n. f.", NOM),
        ("nom et adjectif", NOM),  # un nom l'emporte : la traduction d'un texte le remplace
        ("adjectif", ADJECTIF), ("locution adjectivale", ADJECTIF), ("participe passé", ADJECTIF), ("adj.", ADJECTIF),
        ("verbe", VERBE), ("locution verbale", VERBE), ("v.", VERBE),
        ("adverbe", INVARIABLE), ("locution adverbiale", INVARIABLE), ("préposition", INVARIABLE),
        ("locution prépositive", INVARIABLE), ("conjonction", INVARIABLE), ("locution conjonctive", INVARIABLE),
    ],
)
def test_la_nature_d_un_terme(categorie, nature):
    entree = Entree(numero=1, terme_fr="x", terme_ar="س", categorie_fr=categorie)
    assert nature_du_terme(entree) == nature
    # La même lecture que le moteur de traduction : seul un nom est remplacé dans un texte.
    assert (nature == NOM) == se_remplace_dans_un_texte(entree)


def test_la_nature_des_termes_du_glossaire_fourni(glossaire_fourni):
    for entree in glossaire_fourni.entrees:
        assert (nature_du_terme(entree) == NOM) == se_remplace_dans_un_texte(entree), entree.terme_fr


@pytest.mark.parametrize(
    ("infinitif", "participe"),
    [
        ("abroger", "abrogé"), ("garantir", "garanti"), ("vendre", "vendu"), ("permettre", "permis"),
        ("prendre", "pris"), ("enfreindre", "enfreint"), ("contraindre", "contraint"), ("interdire", "interdit"),
        ("souscrire", "souscrit"), ("faire", "fait"), ("contrefaire", "contrefait"), ("prévoir", "prévu"),
        ("pourvoir", "pourvu"), ("percevoir", "perçu"), ("promouvoir", "promu"), ("reconnaître", "reconnu"),
        ("comparaître", "comparu"), ("naître", "né"), ("conclure", "conclu"), ("acquérir", "acquis"),
        ("requérir", "requis"), ("convenir", "convenu"), ("abstenir", "abstenu"), ("offrir", "offert"),
        ("interrompre", "interrompu"), ("poursuivre", "poursuivi"), ("détruire", "détruit"), ("nuire", "nui"),
        ("dissoudre", "dissous"), ("résoudre", "résolu"), ("surseoir", "sursis"), ("élire", "élu"),
        ("fait", None), ("lu", None),  # ce ne sont pas des infinitifs
    ],
)
def test_le_participe_passe(infinitif, participe):
    assert participe_passe(infinitif) == participe


@pytest.mark.parametrize(
    ("adjectif", "formes"),
    [
        ("légal", ["légal", "légale", "légaux", "légals", "légales"]),
        ("protégé", ["protégé", "protégée", "protégés", "protégées"]),
        ("juridique", ["juridique", "juridiques"]),
        ("contractuel", ["contractuel", "contractuelle", "contractuels", "contractuelles"]),
        ("abusif", ["abusif", "abusive", "abusifs", "abusives"]),
        ("régulier", ["régulier", "régulière", "réguliers", "régulières"]),
        ("religieux", ["religieux", "religieuse", "religieuses"]),
        ("public", ["public", "publique", "publics", "publiques"]),
        ("nul", ["nul", "nulle", "nuls", "nulles"]),
        ("exprès", ["exprès", "expresse", "expresses"]),
        ("dû", ["dû", "due", "dus", "dues"]),
        ("antérieur", ["antérieur", "antérieure", "antérieurs", "antérieures"]),
        ("trompeur", ["trompeur", "trompeuse", "trompeurs", "trompeuses"]),
        ("aérien", ["aérien", "aérienne", "aériens", "aériennes"]),
    ],
)
def test_les_accords_d_un_adjectif(adjectif, formes):
    assert accords(adjectif) == formes


@pytest.mark.parametrize(
    ("phrase", "champs", "attendu"),
    [
        # Un adjectif s'accorde avec son nom.
        ("Les œuvres protégées et le droit protégé.", {"terme_fr": "protégé", "categorie_fr": ADJ},
         ["protégées", "protégé"]),
        ("Des actes légaux, une cause légale.", {"terme_fr": "légal", "categorie_fr": ADJ}, ["légaux", "légale"]),
        ("Une copie certifiée conforme.", {"terme_fr": "certifié conforme", "categorie_fr": LOC_ADJ},
         ["certifiée conforme"]),
        ("Des jugements susceptibles d'appel.", {"terme_fr": "susceptible d'appel", "categorie_fr": LOC_ADJ},
         ["susceptibles d'appel"]),
        ("La loi relative à la monnaie, les textes relatifs au crédit.",
         {"terme_fr": "relatif à", "categorie_fr": LOC_ADJ}, ["relative à", "relatifs au"]),
        ("La protection est assurée.", {"terme_fr": "protégé", "categorie_fr": ADJ}, []),
        # Un nom ne s'accorde pas : « contrat » n'est pas repéré dans « contrate ».
        ("La contrate.", {"terme_fr": "contrat", "categorie_fr": "nom masculin"}, []),
        # Un verbe : l'infinitif et le participe passé, accordé ou non.
        ("Le législateur a abrogé cette loi.", {"terme_fr": "abroger", "categorie_fr": V}, ["abrogé"]),
        ("Le Parlement peut abroger la loi abrogée.", {"terme_fr": "abroger", "categorie_fr": V},
         ["abroger", "abrogée"]),
        ("L'abrogation de la loi, qu'il abroge.", {"terme_fr": "abroger", "categorie_fr": V}, []),
        ("La loi a permis la vente.", {"terme_fr": "permettre", "categorie_fr": V}, ["permis"]),
        ("Le vendeur s'est engagé à livrer.", {"terme_fr": "s'engager", "categorie_fr": V}, ["s'est engagé"]),
        ("Les époux se sont mariés à Oran.", {"terme_fr": "se marier", "categorie_fr": V}, ["se sont mariés"]),
        # Une locution verbale : le verbe et la suite se suivent, ou sont séparés par trois mots au plus.
        ("Le débiteur a été mis en demeure.", {"terme_fr": "mettre en demeure", "categorie_fr": LOC_V},
         ["mis en demeure"]),
        ("Le créancier a mis le débiteur en demeure.", {"terme_fr": "mettre en demeure", "categorie_fr": LOC_V},
         ["mis", "en demeure"]),
        ("Il a mis fin, sans préavis, au contrat ; il reste en demeure.",
         {"terme_fr": "mettre en demeure", "categorie_fr": LOC_V}, []),  # une virgule sépare les deux parties
        ("Le bailleur a mis fin au contrat.", {"terme_fr": "mettre fin à", "categorie_fr": LOC_V}, ["mis fin au"]),
        ("La loi est entrée en vigueur.", {"terme_fr": "entrer en vigueur", "categorie_fr": LOC_V},
         ["entrée en vigueur"]),
        # Une locution qui finit par « à », « de » ou « que » se contracte avec le mot qui suit.
        ("Conformément au code, conformément à la loi, conformément aux usages.",
         {"terme_fr": "conformément à", "categorie_fr": PREP},
         ["Conformément au", "conformément à", "conformément aux"]),
        ("En vertu du contrat, en vertu d'un titre, en vertu des textes, en vertu de la loi.",
         {"terme_fr": "en vertu de", "categorie_fr": PREP},
         ["En vertu du", "en vertu d'", "en vertu des", "en vertu de"]),
        ("À moins qu'il ne paie, à moins que le juge décide.", {"terme_fr": "à moins que", "categorie_fr": CONJ},
         ["À moins qu'", "à moins que"]),
        ("Jusqu'au jugement, jusqu'à la vente.", {"terme_fr": "jusqu'à", "categorie_fr": "préposition"},
         ["Jusqu'au", "jusqu'à"]),
        ("En vertu des textes.", {"terme_fr": "en vertu", "categorie_fr": PREP}, ["En vertu"]),
        # Une locution ne prend pas de « s » : « de plein droit » n'est pas repéré dans « de plein droits ».
        ("De plein droits.", {"terme_fr": "de plein droit", "categorie_fr": "locution adverbiale"}, []),
    ],
)
def test_reperage_des_autres_mots_en_francais(phrase, champs, attendu):
    assert reperes(phrase, FR, **champs) == attendu


@pytest.mark.parametrize(
    ("phrase", "champs", "attendu"),
    [
        # Un adjectif : féminin, article, cas direct, pluriel ; chaque mot d'une locution peut s'accorder.
        ("المصنفات المحمية والحق المحمي", {"terme_ar": "محمي", "categorie_fr": ADJ}, ["المحمية", "المحمي"]),
        ("يجب أن يكون السبب مشروعا", {"terme_ar": "مشروع", "categorie_fr": ADJ}, ["مشروعا"]),
        ("عقود قابلة للإبطال", {"terme_ar": "قابل للإبطال", "categorie_fr": LOC_ADJ}, ["قابلة للإبطال"]),
        ("الأملاك غير قابلة للتصرف فيها", {"terme_ar": "غير قابل للتصرف فيه", "categorie_fr": LOC_ADJ},
         ["غير قابلة للتصرف فيها"]),
        ("قيمة صافية ودخل صاف والدخل الصافي", {"terme_ar": "صافٍ", "categorie_fr": ADJ},
         ["صافية", "صاف", "الصافي"]),
        ("دولة ذات سيادة ومتعاقدا ذا أهلية", {"terme_ar": "ذو سيادة", "categorie_fr": LOC_ADJ}, ["ذات سيادة"]),
        ("القانون المتعلق بالنقد والأحكام المتعلقة بالقرض", {"terme_ar": "المتعلق ب", "categorie_fr": LOC_ADJ},
         ["المتعلق بالنقد", "المتعلقة بالقرض"]),
        # Un verbe au passé : masculin, féminin (la lettre faible finale tombe), pronom complément.
        ("ألغى المشرع القانون", {"terme_ar": "ألغى", "categorie_fr": V}, ["ألغى"]),
        ("ألغت المحكمة القرار", {"terme_ar": "ألغى", "categorie_fr": V}, ["ألغت"]),
        ("نشرت الحكومة المرسوم ونشره الوزير", {"terme_ar": "نشر", "categorie_fr": V}, ["نشرت", "ونشره"]),
        ("ينشر القانون في الجريدة", {"terme_ar": "نشر", "categorie_fr": V}, []),  # le présent n'est pas repéré
        # Une locution verbale : le sujet se place entre le verbe et la suite.
        ("رفع المدعي دعوى أمام المحكمة", {"terme_ar": "رفع دعوى", "categorie_fr": LOC_V}, ["رفع", "دعوى"]),
        ("وصادقت الجزائر على الاتفاقية", {"terme_ar": "صادق على", "categorie_fr": LOC_V}, ["وصادقت", "على"]),
        ("ألقت الشرطة القبض على المتهم", {"terme_ar": "ألقى القبض على", "categorie_fr": LOC_V},
         ["ألقت", "القبض على"]),
        ("المدين الذي أخل بالتزامه", {"terme_ar": "أخل ب", "categorie_fr": LOC_V}, ["أخل بالتزامه"]),
        ("أخل المدين بالتزامه", {"terme_ar": "أخل ب", "categorie_fr": LOC_V}, ["أخل", "بالتزامه"]),
        # Une particule d'une lettre, à la fin d'une locution, se colle au mot qui suit.
        ("طبقا للقانون وطبقا لأحكام العقد", {"terme_ar": "طبقا ل", "categorie_fr": PREP},
         ["طبقا للقانون", "وطبقا لأحكام"]),
        ("دون الإخلال بأحكام المادة 5", {"terme_ar": "دون الإخلال ب", "categorie_fr": PREP},
         ["دون الإخلال بأحكام"]),
        ("طبقا ثم", {"terme_ar": "طبقا ل", "categorie_fr": PREP}, []),
    ],
)
def test_reperage_des_autres_mots_en_arabe(phrase, champs, attendu):
    assert reperes(phrase, AR, **champs) == attendu


def test_les_phrases_des_termes_seuls_du_glossaire_fourni(glossaire_fourni):
    """Version 0.11 : dans sa phrase d'exemple, chaque terme seul est repéré, quelle que soit sa nature."""
    natures = {NOM: 0, ADJECTIF: 0, VERBE: 0, INVARIABLE: 0}
    for entree in glossaire_fourni.entrees:
        if entree.definition_fr:
            continue
        for contexte in entree.contextes:
            natures[nature_du_terme(entree)] += 1
            for langue in (FR, AR):
                assert positions_du_terme(contexte.texte(langue), entree, langue), (entree.terme_fr, langue)
    # Tous les adjectifs, les verbes et les locutions invariables du glossaire ont leur phrase.
    assert (natures[ADJECTIF], natures[VERBE], natures[INVARIABLE]) == (356, 246, 190) and natures[NOM] >= 1095


def test_exemples_du_glossaire_en_arabe(glossaire):
    """Le terme arabe est repéré dans tous les exemples, sauf un.

    L'article 106 rend « consentement mutuel » par « اتفاق الطرفين » : le mot « رضا » n'y figure pas.
    """
    sans_repere = [entree.terme_ar for entree in glossaire.entrees for contexte in entree.contextes
                   if not positions_du_terme(contexte.ar, entree, AR)]
    assert sans_repere == ["رضا"]


def test_exemples_du_glossaire_en_francais(glossaire):
    """Trois exemples emploient une autre tournure que le terme : « exécuté », « réparer », « capable »."""
    sans_repere = [entree.terme_fr for entree in glossaire.entrees for contexte in entree.contextes
                   if not positions_du_terme(contexte.fr, entree, FR)]
    assert sans_repere == ["exécution du contrat", "réparation", "capacité"]
