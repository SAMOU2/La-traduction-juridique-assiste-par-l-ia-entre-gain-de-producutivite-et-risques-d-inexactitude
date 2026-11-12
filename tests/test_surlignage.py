"""Repérage du terme dans les phrases d'exemple (mise en évidence)."""

import pytest

from traducteur.glossaire import Entree
from traducteur.langues import AR, FR
from traducteur.surlignage import positions_du_terme


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
    ],
)
def test_reperage_en_arabe(phrase, champs, attendu):
    assert reperes(phrase, AR, **champs) == attendu


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
