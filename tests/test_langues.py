"""Normalisation du texte : clés de comparaison, détection de la langue."""

import pytest

from traducteur.langues import (
    AR,
    FR,
    autre_langue,
    cle_souple,
    cle_stricte,
    cles_de_recherche,
    contient_arabe,
    deviner_langue,
    est_rtl,
)


def test_cle_stricte_ignore_la_casse_les_espaces_et_la_forme_des_apostrophes():
    assert cle_stricte("  L’Usage  ") == "l'usage"
    assert cle_stricte("Bonne\u00a0 foi") == "bonne foi"
    assert cle_stricte("peut‑être") == "peut-être"


def test_cle_stricte_garde_les_accents_francais():
    assert cle_stricte("Équité") == "équité"
    assert cle_stricte("côte") != cle_stricte("coté")


def test_cle_stricte_supprime_les_signes_diacritiques_arabes():
    assert cle_stricte("العَقْدُ") == "العقد"
    assert cle_stricte("قاضٍ") == "قاض"
    assert cle_stricte("عـقـد") == "عقد"  # tatwil


def test_cle_souple_supprime_les_accents():
    assert cle_souple("Équité") == "equite"
    assert cle_souple("œuvre") == "oeuvre"
    assert cle_souple("Créancier") == cle_souple("creancier")


@pytest.mark.parametrize(
    ("avec_variante", "sans_variante"),
    [("أهلية", "اهلية"), ("إيجار", "ايجار"), ("ملكية", "ملكيه"), ("مسؤولية", "مسووليه"), ("مستشفى", "مستشفي")],
)
def test_cle_souple_unifie_les_variantes_arabes(avec_variante, sans_variante):
    assert cle_souple(avec_variante) == cle_souple(sans_variante)


def test_deviner_langue():
    assert deviner_langue("contrat") == FR
    assert deviner_langue("العقد") == AR
    assert deviner_langue("المادة 54 du Code civil") == FR  # l'écriture majoritaire l'emporte
    assert deviner_langue("art. 54 : العقد شريعة المتعاقدين") == AR
    assert deviner_langue("1975 – 78") is None
    assert deviner_langue("") is None


def test_outils_de_langue():
    assert autre_langue(FR) == AR and autre_langue(AR) == FR
    assert est_rtl(AR) and not est_rtl(FR)
    assert contient_arabe("art. 54 عقد") and not contient_arabe("art. 54")


def test_cles_de_recherche_ajoutent_la_forme_sans_article():
    assert cles_de_recherche("العقد", AR) == ("العقد", "عقد")
    assert cles_de_recherche("عقد", AR) == ("عقد",)
    assert "حسن نيه" in cles_de_recherche("حسن النية", AR)
    assert cles_de_recherche("l’usage", FR) == ("l'usage", "usage")
    assert cles_de_recherche("Le contrat", FR) == ("le contrat", "contrat")
    assert cles_de_recherche("contrat", FR) == ("contrat",)


def test_cles_de_recherche_ne_coupent_pas_un_mot_court():
    # « الم » (douleur) ne commence pas par l'article.
    assert cles_de_recherche("ألم", AR) == ("الم",)


def test_cles_de_recherche_d_un_nom_defectueux():
    # « قاضٍ » doit aussi être reconnu sous la forme « قاضي » (et donc « القاضي »).
    assert cles_de_recherche("قاضٍ", AR) == ("قاض", "قاضي")
    assert set(cles_de_recherche("القاضي", AR)) & set(cles_de_recherche("قاضٍ", AR))


def test_requete_vide():
    assert cles_de_recherche("   ", FR) == ()
