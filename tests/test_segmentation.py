"""Découpage d'un texte en phrases et en mots (étapes 1 et 2 de la traduction d'un texte)."""

import pytest

from traducteur.segmentation import MOT, NOMBRE, PONCTUATION, compter, decouper_en_mots, segmenter_en_phrases

ARTICLES_FR = (
    "Le contrat fait la loi des parties. Il ne peut être révoqué, ni modifié que de leur consentement mutuel "
    "ou pour les causes prévues par la loi. Le contrat doit être exécuté conformément à son contenu, et de "
    "bonne foi. Il oblige le contractant, non seulement à ce qui y est exprimé, mais encore à tout ce que la "
    "loi, l’usage et l’équité considèrent comme une suite nécessaire de ce contrat d’après la nature de "
    "l’obligation."
)
ARTICLES_AR = (
    "العقد شريعة المتعاقدين. فلا يجوز نقضه، ولا تعديله إلا باتفاق الطرفين، أو للأسباب التي يقررها القانون. "
    "يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية. ولا يقتصر العقد على إلزام المتعاقد بما ورد فيه فحسب، "
    "بل يتناول أيضا ما هو من مستلزماته وفقا للقانون، والعرف، والعدالة، بحسب طبيعة الالتزام."
)


def phrases(texte):
    return [phrase.texte for phrase in segmenter_en_phrases(texte)]


def test_les_articles_106_et_107_comptent_quatre_phrases():
    """Mêmes nombres que dans la maquette : 4 phrases, 76 mots et 422 caractères en français."""
    assert compter(ARTICLES_FR) == (4, 76, 422)
    assert compter(ARTICLES_AR) == (4, 49, 288)
    assert phrases(ARTICLES_FR)[0] == "Le contrat fait la loi des parties."
    assert phrases(ARTICLES_AR)[2] == "يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية."


def test_chaque_phrase_garde_sa_position_dans_le_texte():
    texte = "  Première phrase.   Deuxième phrase !\n\n Troisième "
    for phrase in segmenter_en_phrases(texte):
        assert texte[phrase.debut:phrase.fin] == phrase.texte
    assert phrases(texte) == ["Première phrase.", "Deuxième phrase !", "Troisième"]


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        # Le point d'une abréviation, d'une initiale ou d'un sigle ne termine pas la phrase.
        ("Voir l'art. 106 du code civil, p. 12 et s. M. Dupont a signé.",
         ["Voir l'art. 106 du code civil, p. 12 et s. M. Dupont a signé."]),
        ("L'ordonnance n° 75-58 (J.O.R.A. n° 78) a été modifiée en 2005. Elle est en vigueur.",
         ["L'ordonnance n° 75-58 (J.O.R.A. n° 78) a été modifiée en 2005.", "Elle est en vigueur."]),
        ("Le taux est de 3.5 %, etc. Le juge statue.", ["Le taux est de 3.5 %, etc.", "Le juge statue."]),
        ("Cf. l'article L. 110-1 du code.", ["Cf. l'article L. 110-1 du code."]),
        # Numéros de liste.
        ("1. Le vendeur livre la chose. 2. L'acheteur paie le prix.",
         ["1. Le vendeur livre la chose.", "2. L'acheteur paie le prix."]),
        # Autres signes de fin, guillemets fermants, retour à la ligne.
        ("A-t-il payé ? Oui ! Non… peut-être. Fin", ["A-t-il payé ?", "Oui !", "Non… peut-être.", "Fin"]),
        ("Il a dit : « Le contrat est nul. » Puis il est parti.",
         ["Il a dit : « Le contrat est nul. »", "Puis il est parti."]),
        ("Titre sans point\nPremière phrase. Seconde phrase.\n\n", ["Titre sans point", "Première phrase.",
                                                                   "Seconde phrase."]),
        # Arabe : point d'interrogation arabe, lettre isolée suivie d'un point.
        ("هل العقد باطل؟ نعم. انظر ص. 12 من الجريدة الرسمية!",
         ["هل العقد باطل؟", "نعم.", "انظر ص. 12 من الجريدة الرسمية!"]),
        # Rien à traduire.
        ("", []),
        ("  \n --- \n ***", []),
    ],
)
def test_segmentation_en_phrases(texte, attendu):
    assert phrases(texte) == attendu


def test_decoupage_en_mots():
    jetons = decouper_en_mots("L’usage et l'équité, d’après l'art. 106 : aujourd’hui, qu'il paie 3,5 % (n° 75-58)…")
    assert [jeton.texte for jeton in jetons] == [
        "L’", "usage", "et", "l'", "équité", ",", "d’", "après", "l'", "art", ".", "106", ":", "aujourd’hui", ",",
        "qu'", "il", "paie", "3,5", "%", "(", "n", "°", "75-58", ")", "…"]
    natures = {jeton.texte: jeton.nature for jeton in jetons}
    assert natures["usage"] == MOT and natures["106"] == NOMBRE and natures["75-58"] == NOMBRE
    assert natures[","] == PONCTUATION and natures["…"] == PONCTUATION
    # L'article élidé est un jeton à part, mais « l'usage » compte pour un seul mot.
    assert [jeton.texte for jeton in jetons if jeton.elide] == ["L’", "l'", "d’", "l'", "qu'"]
    assert sum(1 for jeton in jetons if jeton.compte) == 9


def test_les_mots_composes_restent_entiers():
    assert [jeton.texte for jeton in decouper_en_mots("dommages-intérêts, c'est-à-dire prud'hommes")] == [
        "dommages-intérêts", ",", "c'", "est-à-dire", "prud'hommes"]


def test_decoupage_d_un_texte_arabe():
    jetons = decouper_en_mots("وَالعَقْدُ شريعة المتعاقدين، في ٢٦ سبتمبر 1975؟", decalage=10)
    assert [jeton.texte for jeton in jetons] == ["وَالعَقْدُ", "شريعة", "المتعاقدين", "،", "في", "٢٦", "سبتمبر",
                                                 "1975", "؟"]
    assert [jeton.nature for jeton in jetons].count(NOMBRE) == 2
    assert jetons[0].debut == 10 and jetons[0].fin == 20  # les positions tiennent compte du décalage
