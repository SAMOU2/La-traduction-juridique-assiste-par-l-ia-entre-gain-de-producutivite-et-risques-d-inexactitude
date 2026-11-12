"""Lecture du glossaire CSV et recherche des termes."""

import pytest

from traducteur.glossaire import COLONNES, ErreurGlossaire, Glossaire, decoder, detecter_separateur
from traducteur.langues import AR, FR


def termes(entrees, langue=FR):
    return [entree.terme(langue) for entree in entrees]


# ------------------------------------------------------------------ glossaire d'exemple
def test_le_glossaire_d_exemple_se_charge(glossaire):
    assert len(glossaire) == 40
    assert glossaire.nom == "glossaire_essai.csv"
    assert glossaire.encodage == "UTF-8"
    assert glossaire.separateur == ";"
    assert glossaire.colonnes == list(COLONNES)  # toutes les colonnes, dans l'ordre documenté
    assert glossaire.colonnes_ignorees == []
    assert glossaire.lignes_ignorees == 0


def test_les_entrees_d_exemple_sont_completes(glossaire):
    for entree in glossaire.entrees:
        assert entree.terme_fr and entree.terme_ar
        assert bool(entree.definition_fr) == bool(entree.definition_ar)
        assert not entree.definition_fr or entree.source_definition
        for contexte in entree.contextes:
            assert contexte.fr and contexte.ar and contexte.source
    assert [entree.numero for entree in glossaire.entrees] == list(range(1, 41))


def test_les_termes_associes_d_exemple_existent_presque_tous(glossaire):
    """Seuls « cocontractant » et « clause » ne sont pas des entrées (puces non cliquables)."""
    absents = {terme for entree in glossaire.entrees for terme in entree.termes_associes
               if glossaire.par_terme(terme, FR) is None}
    assert absents == {"cocontractant", "clause"}


def test_contenu_de_l_entree_contrat(glossaire):
    contrat = glossaire.par_terme("contrat", FR)
    assert contrat.terme_ar == "عقد"
    assert contrat.categorie_fr == "nom masculin" and contrat.pluriel_fr == "contrats"
    assert contrat.categorie_ar == "اسم مذكر" and contrat.pluriel_ar == "عقود"
    assert contrat.domaines == ["Droit civil", "Obligations"]
    assert contrat.synonymes_fr == ["convention", "accord"]
    assert contrat.termes_associes == ["contractant", "cocontractant", "clause", "obligation"]
    assert contrat.definition_fr.startswith("Convention par laquelle")
    assert contrat.definition_ar.startswith("اتفاق يلتزم بموجبه")
    assert contrat.source_definition == "Code civil, art. 54"
    assert [contexte.source for contexte in contrat.contextes] == ["Code civil, art. 106", "Code civil, art. 107"]
    assert contrat.contextes[0].fr == "Le contrat fait la loi des parties."
    assert contrat.contextes[0].ar == "العقد شريعة المتعاقدين."
    assert len(contrat.ressources) == 4


# ------------------------------------------------------------------ recherche en français
def test_recherche_exacte_puis_expressions(glossaire):
    assert termes(glossaire.chercher("contrat", FR)) == [
        "contrat", "contrat de bail", "contrat de vente", "contrat de travail",
        "exécution du contrat", "conclusion du contrat",
    ]


@pytest.mark.parametrize("requete", ["Contrat", "  CONTRAT ", "contrats", "le contrat", "des contrats"])
def test_recherche_tolerante_en_francais(glossaire, requete):
    assert termes(glossaire.chercher(requete, FR))[0] == "contrat"


def test_recherche_sans_accent(glossaire):
    assert termes(glossaire.chercher("equite", FR)) == ["équité"]
    assert termes(glossaire.chercher("l’équité", FR)) == ["équité"]


def test_recherche_par_le_pluriel_irregulier(glossaire):
    assert termes(glossaire.chercher("baux", FR)) == ["bail"]


def test_recherche_par_le_debut_du_terme(glossaire):
    assert termes(glossaire.chercher("contr", FR))[:2] == ["contrat", "contractant"]
    assert termes(glossaire.chercher("bail", FR)) == ["bail", "bailleur", "contrat de bail"]


def test_recherche_d_un_mot_a_l_interieur_d_une_expression(glossaire):
    assert termes(glossaire.chercher("foi", FR)) == ["bonne foi", "mauvaise foi"]


def test_une_partie_de_mot_ne_suffit_pas(glossaire):
    # « tra » est à l'intérieur de « contrat », mais pas au début d'un terme ni d'un mot entier.
    assert glossaire.chercher("tra", FR) == []


def test_recherche_par_un_synonyme(glossaire):
    assert termes(glossaire.chercher("convention", FR)) == ["contrat"]
    assert termes(glossaire.chercher("usage", FR)) == ["usage", "coutume"]  # terme exact d'abord


def test_homonymes(glossaire):
    droits = glossaire.chercher("droit", FR)
    assert termes(droits, AR) == ["حق", "قانون"]
    assert glossaire.homonymes(droits[0], FR) == droits
    assert glossaire.libelle(droits[0], FR) == "droit (حق)"
    assert glossaire.libelle(droits[1], FR) == "droit (قانون)"
    contrat = glossaire.par_terme("contrat", FR)
    assert glossaire.libelle(contrat, FR) == "contrat"


def test_aucun_resultat_et_termes_proches(glossaire):
    assert glossaire.chercher("contart", FR) == []
    assert termes(glossaire.propositions("contart", FR)) == ["contrat"]
    assert glossaire.chercher("xyz", FR) == []
    assert glossaire.propositions("xyz", FR) == []
    assert glossaire.chercher("", FR) == []


def test_expressions_qui_contiennent_le_terme(glossaire):
    contrat = glossaire.par_terme("contrat", FR)
    assert termes(glossaire.expressions(contrat, FR)) == [
        "contrat de bail", "contrat de vente", "contrat de travail", "exécution du contrat", "conclusion du contrat",
    ]
    assert set(termes(glossaire.expressions(contrat, AR), AR)) == {
        "عقد البيع", "عقد العمل", "عقد الإيجار", "إبرام العقد", "تنفيذ العقد",
    }
    loi = glossaire.par_terme("loi", FR)
    assert glossaire.expressions(loi, FR) == []


# ------------------------------------------------------------------ recherche en arabe
@pytest.mark.parametrize("requete", ["عقد", "العقد", "عَقْد", "العقود"])
def test_recherche_tolerante_en_arabe(glossaire, requete):
    assert termes(glossaire.chercher(requete, AR))[0] == "contrat"


@pytest.mark.parametrize(
    ("requete", "attendu"),
    [
        ("القاضي", "juge"), ("قاضي", "juge"), ("قاضٍ", "juge"),
        ("المشتري", "acheteur"),
        ("حسن نية", "bonne foi"), ("حسن النية", "bonne foi"),
        ("الالتزام", "obligation"), ("التزام", "obligation"),
        ("قانون مدني", "code civil"), ("القانون المدني", "code civil"),
        ("اهلية", "capacité"), ("ملكيه", "propriété"), ("الايجار", "bail"),
    ],
)
def test_article_et_variantes_d_ecriture_en_arabe(glossaire, requete, attendu):
    assert termes(glossaire.chercher(requete, AR))[0] == attendu


def test_un_terme_arabe_pour_deux_termes_francais(glossaire):
    assert termes(glossaire.chercher("عرف", AR)) == ["coutume", "usage"]
    assert termes(glossaire.chercher("قانون", AR)) == ["loi", "droit", "code civil"]


def test_termes_proches_en_arabe(glossaire):
    assert glossaire.chercher("عقدد", AR) == []
    assert termes(glossaire.propositions("عقدد", AR), AR) == ["عقد"]


# ------------------------------------------------------------------ formats de fichier acceptés
def test_separateur_virgule_et_noms_de_colonnes_en_clair():
    glossaire = Glossaire.depuis_texte(
        "Français,Arabe,Définition\n"
        'contrat,عقد,"Convention, accord de volontés"\n'
        "loi,قانون,\n"
    )
    assert glossaire.separateur == ","
    assert glossaire.colonnes == ["terme_fr", "terme_ar", "definition_fr"]
    assert termes(glossaire.entrees) == ["contrat", "loi"]
    assert glossaire.entrees[0].definition_fr == "Convention, accord de volontés"
    assert glossaire.entrees[1].definition_fr == ""


def test_fichier_sans_en_tete_colonnes_reperees_par_l_ecriture():
    glossaire = Glossaire.depuis_texte("عقد;contrat\nقانون;loi\n")
    assert termes(glossaire.entrees) == ["contrat", "loi"]
    assert termes(glossaire.entrees, AR) == ["عقد", "قانون"]
    assert glossaire.colonnes == ["terme_ar", "terme_fr"]


def test_un_terme_nomme_mot_n_est_pas_pris_pour_un_en_tete():
    glossaire = Glossaire.depuis_texte("mot;كلمة\nloi;قانون\n")
    assert termes(glossaire.entrees) == ["mot", "loi"]


def test_en_tete_aux_noms_inconnus():
    glossaire = Glossaire.depuis_texte("Mot source;Mot cible;Remarque\ncontrat;عقد;à vérifier\nloi;قانون;\n")
    assert termes(glossaire.entrees) == ["contrat", "loi"]
    assert termes(glossaire.entrees, AR) == ["عقد", "قانون"]
    assert glossaire.colonnes_ignorees == ["Remarque"]  # les deux autres servent de colonnes de termes


def test_en_tete_aux_noms_inconnus_et_une_seule_ligne():
    glossaire = Glossaire.depuis_texte("Mot source;Mot cible\ncontrat;عقد\n")
    assert termes(glossaire.entrees) == ["contrat"]


def test_une_seule_ligne_sans_en_tete():
    glossaire = Glossaire.depuis_texte("contrat;عقد")
    assert (glossaire.entrees[0].terme_fr, glossaire.entrees[0].terme_ar) == ("contrat", "عقد")


def test_colonne_arabe_au_nom_inconnu():
    glossaire = Glossaire.depuis_texte("terme_fr;definition_fr;terme cible\ncontrat;Convention;عقد\n")
    assert glossaire.entrees[0].terme_ar == "عقد"
    assert glossaire.entrees[0].definition_fr == "Convention"
    assert glossaire.colonnes == ["terme_fr", "definition_fr", "terme_ar"]
    assert glossaire.colonnes_ignorees == []


def test_lignes_incompletes_et_lignes_vides():
    glossaire = Glossaire.depuis_texte("terme_fr;terme_ar\ncontrat;عقد\n\n;قانون\nloi;\nbail;إيجار\n")
    assert termes(glossaire.entrees) == ["contrat", "bail"]
    assert glossaire.lignes_ignorees == 2
    assert [entree.numero for entree in glossaire.entrees] == [1, 2]


def test_valeurs_multiples_et_exemples():
    glossaire = Glossaire.depuis_texte(
        "terme_fr;terme_ar;synonymes_fr;contexte_fr;contexte_ar;source_contexte;ressources\n"
        "contrat;عقد; convention |accord | ;Phrase un. | Phrase deux.;جملة أولى.;Source 1;Code civil | www.joradp.dz\n"
    )
    entree = glossaire.entrees[0]
    assert entree.synonymes_fr == ["convention", "accord"]
    assert [(c.fr, c.ar, c.source) for c in entree.contextes] == [
        ("Phrase un.", "جملة أولى.", "Source 1"), ("Phrase deux.", "", ""),
    ]
    assert entree.ressources == ["Code civil", "www.joradp.dz"]


def test_cellule_entre_guillemets_avec_separateur_et_retour_a_la_ligne():
    glossaire = Glossaire.depuis_texte(
        'terme_fr;terme_ar;definition_fr\ncontrat;عقد;"Convention ; accord\nde volontés"\nloi;قانون;Règle\n'
    )
    assert len(glossaire) == 2
    assert glossaire.entrees[0].definition_fr == "Convention ; accord\nde volontés"


@pytest.mark.parametrize(
    ("encodage_python", "nom_attendu"),
    [("utf-8", "UTF-8"), ("utf-8-sig", "UTF-8"), ("utf-16", "UTF-16"), ("cp1256", "Windows-1256")],
)
def test_encodages_reconnus(tmp_path, encodage_python, nom_attendu):
    fichier = tmp_path / "glossaire.csv"
    fichier.write_bytes("terme_fr\tterme_ar\néquité\tعدالة\ncréancier\tدائن\n".encode(encodage_python))
    glossaire = Glossaire.charger(fichier)
    assert glossaire.encodage == nom_attendu
    assert glossaire.separateur == "\t"
    assert termes(glossaire.entrees) == ["équité", "créancier"]
    assert termes(glossaire.entrees, AR) == ["عدالة", "دائن"]
    assert glossaire.chemin == fichier


def test_decoder_un_fichier_occidental_sans_arabe():
    texte, encodage = decoder("Équité;créancier".encode("cp1252"))
    assert (texte, encodage) == ("Équité;créancier", "Windows-1252")


def test_detecter_separateur():
    assert detecter_separateur("a;b;c\n1;2;3\n") == ";"
    assert detecter_separateur("a,b\n1,2\n") == ","
    assert detecter_separateur("a\tb\n1\t2\n") == "\t"
    assert detecter_separateur('"x, y";"z"\n"t, u";"v"\n') == ";"
    assert detecter_separateur("une seule colonne\n") == ";"


# ------------------------------------------------------------------ fichiers refusés
def test_fichier_vide():
    with pytest.raises(ErreurGlossaire, match="vide"):
        Glossaire.depuis_texte("\n\n")


def test_fichier_sans_colonne_arabe():
    with pytest.raises(ErreurGlossaire, match="terme_ar"):
        Glossaire.depuis_texte("terme_fr;definition_fr\ncontrat;Convention\n")


def test_arabe_perdu_a_l_enregistrement():
    # Un tableur qui enregistre en « CSV » classique remplace l'arabe par des points d'interrogation.
    with pytest.raises(ErreurGlossaire, match="CSV UTF-8"):
        Glossaire.depuis_texte("terme_fr;terme_ar\ncontrat;???\nloi;?????\n")


def test_en_tete_sans_aucune_ligne():
    with pytest.raises(ErreurGlossaire):
        Glossaire.depuis_texte("terme_fr;terme_ar\n")


@pytest.mark.parametrize("debut", [b"PK\x03\x04\x14\x00", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00"])
def test_classeur_excel_pris_pour_un_csv(tmp_path, debut):
    fichier = tmp_path / "glossaire.xlsx"
    fichier.write_bytes(debut + bytes(64))
    with pytest.raises(ErreurGlossaire, match="classeur"):
        Glossaire.charger(fichier)


def test_fichier_introuvable(tmp_path):
    with pytest.raises(ErreurGlossaire, match=r"absent\.csv"):
        Glossaire.charger(tmp_path / "absent.csv")


# ------------------------------------------------------------------ priorité de la forme exacte
def test_la_forme_accentuee_exacte_passe_avant_la_forme_sans_accent():
    glossaire = Glossaire.depuis_texte("terme_fr;terme_ar\ncôte;ساحل\ncote;تسعيرة\n")
    assert termes(glossaire.trouver("côte", FR), AR) == ["ساحل"]
    assert termes(glossaire.trouver("cote", FR), AR) == ["تسعيرة"]
    assert termes(glossaire.trouver("COTÉ", FR), AR) == ["ساحل", "تسعيرة"]  # aucune forme exacte : les deux
