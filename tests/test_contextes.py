"""Contextes d'emploi d'un terme, cherchés dans tout le glossaire (champ ④ « Contextualisation »)."""

import pytest

from traducteur.contextes import DEFINITION, EXEMPLE, NOMBRE_VISE, PROPRE, Emploi, emplois
from traducteur.glossaire import Glossaire
from traducteur.langues import AR, FR
from traducteur.surlignage import motif_du_terme, positions_du_terme

EN_TETE = "terme_fr;terme_ar;domaine;definition_fr;definition_ar;contexte_fr;contexte_ar;source_contexte\n"


def charger(tmp_path, lignes: str, en_tete: str = EN_TETE) -> Glossaire:
    fichier = tmp_path / "glossaire.csv"
    fichier.write_text(en_tete + lignes, encoding="utf-8")
    return Glossaire.charger(fichier)


def entree(glossaire: Glossaire, terme: str):
    return next(entree for entree in glossaire.entrees if entree.terme_fr == terme)


def provenances(glossaire: Glossaire, terme: str, nombre: int = NOMBRE_VISE) -> list[tuple[str, str]]:
    return [(emploi.origine, emploi.provenance()) for emploi in emplois(glossaire, entree(glossaire, terme), nombre)]


# ------------------------------------------------------------------ les exemples de l'entrée
def test_les_exemples_de_l_entree_viennent_en_premier(glossaire):
    contrat = entree(glossaire, "contrat")
    trouves = emplois(glossaire, contrat)
    assert [emploi.origine for emploi in trouves] == [PROPRE, PROPRE]
    assert [(emploi.fr, emploi.ar, emploi.source) for emploi in trouves] == [
        (contexte.fr, contexte.ar, contexte.source) for contexte in contrat.contextes]
    assert trouves[0].provenance() == "Code civil, art. 106" and trouves[0].entree is contrat
    assert trouves[0].texte(FR) == "Le contrat fait la loi des parties."
    assert trouves[0].texte(AR) == "العقد شريعة المتعاقدين."


def test_tous_les_exemples_de_l_entree_sont_gardes(tmp_path):
    glossaire = charger(tmp_path, (
        "bail;إيجار;;;;Le bail est écrit. | Le bail dure un an. | Le bail prend fin.;"
        "الإيجار مكتوب. | مدة الإيجار سنة. | ينتهي الإيجار.;\n"))
    # Trois exemples dans l'entrée : tous sont gardés, même au-delà du nombre visé.
    assert len(emplois(glossaire, glossaire.entrees[0], 2)) == 3
    assert emplois(None, glossaire.entrees[0]) == emplois(glossaire, glossaire.entrees[0])


def test_sans_glossaire_seuls_les_exemples_de_l_entree_sont_connus(glossaire):
    vente = entree(glossaire, "contrat de vente")
    assert vente.contextes == [] and emplois(None, vente) == []


# ------------------------------------------------------------------ les phrases des autres entrées
def test_une_entree_sans_exemple_recoit_les_phrases_des_autres_entrees(glossaire):
    assert provenances(glossaire, "contrat de vente") == [
        (DEFINITION, "Définition de « acheteur »"), (DEFINITION, "Définition de « vendeur »")]
    trouves = emplois(glossaire, entree(glossaire, "contrat de vente"))
    assert trouves[0].fr == "Partie au contrat de vente qui acquiert la chose et doit en payer le prix."
    assert trouves[0].ar == "الطرف في عقد البيع الذي يكتسب الشيء ويلتزم بدفع ثمنه."
    assert trouves[0].entree.terme_fr == "acheteur" and trouves[0].source == ""
    # Dans l'autre sens de traduction, l'entrée d'origine est nommée en arabe.
    assert trouves[0].provenance(AR) == "Définition de « مشترٍ »"


def test_un_seul_exemple_est_complete_par_le_glossaire(glossaire):
    # « vendeur » a un exemple ; une définition qui emploie le terme complète la liste.
    assert provenances(glossaire, "vendeur") == [
        (PROPRE, "Code civil, art. 351"), (DEFINITION, "Définition de « prix »")]
    # « loi » : l'exemple d'une autre entrée passe avant les définitions ; il cite sa source.
    assert provenances(glossaire, "loi") == [(PROPRE, "Code civil, art. 1er"), (EXEMPLE, "Code civil, art. 107")]


def test_un_terme_que_le_glossaire_n_emploie_nulle_part_n_a_pas_de_contexte(glossaire):
    assert provenances(glossaire, "contrat de travail") == []
    assert provenances(glossaire, "Journal officiel") == []


def test_le_nombre_de_contextes_demande(glossaire):
    contrat = entree(glossaire, "contrat")
    assert len(emplois(glossaire, contrat, 2)) == 2
    plus = emplois(glossaire, contrat, 5)
    assert len(plus) == 5 and plus[:2] == emplois(glossaire, contrat, 2)
    assert [emploi.origine for emploi in plus[:3]] == [PROPRE, PROPRE, EXEMPLE]
    # Une même phrase n'est jamais citée deux fois.
    assert len({(emploi.fr, emploi.ar) for emploi in plus}) == 5


def test_la_phrase_doit_employer_le_terme_dans_les_deux_langues(tmp_path):
    glossaire = charger(tmp_path, (
        "action;دعوى;Procédure;;;;;\n"
        "action;سهم;Sociétés;;;;;\n"
        "intérêt;مصلحة;Procédure;Avantage qu’une personne retire d’une action en justice.;"
        "المنفعة التي يجنيها الشخص من الدعوى.;;;\n"
        "actionnaire;مساهم;Sociétés;Titulaire d’une action de la société.;صاحب سهم في الشركة.;;;\n"
        "réaction;رد فعل;;Une réaction n’est pas une action au sens du droit.;رد الفعل ليس تصرفا قانونيا.;;;\n"))
    proces, titre = glossaire.entrees[0], glossaire.entrees[1]
    # Chaque sens de « action » reçoit la phrase qui emploie son équivalent arabe, et elle seule.
    assert [emploi.entree.terme_fr for emploi in emplois(glossaire, proces)] == ["intérêt"]
    assert [emploi.entree.terme_fr for emploi in emplois(glossaire, titre)] == ["actionnaire"]
    # « réaction » contient « action » en français, mais aucun des deux équivalents en arabe : écartée.
    assert all(emploi.entree.terme_fr != "réaction" for emploi in emplois(glossaire, proces, 9))


def test_les_exemples_passent_avant_les_definitions_et_le_meme_domaine_d_abord(tmp_path):
    glossaire = charger(tmp_path, (
        "tribunal;محكمة;Procédure;;;;;\n"
        "juge;قاض;Sociétés;Magistrat qui siège au tribunal.;قاض يجلس في المحكمة.;;;\n"
        "greffe;كتابة الضبط;Procédure;Service administratif du tribunal, chargé des actes.;"
        "مصلحة إدارية في المحكمة مكلفة بالعقود.;;;\n"
        "audience;جلسة;Sociétés;;;L’audience se tient au tribunal de la ville.;تنعقد الجلسة في المحكمة.;art. 7\n"
        "appel;استئناف;Procédure;;;L’appel suspend le jugement du tribunal.;يوقف الاستئناف حكم المحكمة.;\n"))
    tribunal = glossaire.entrees[0]
    trouves = emplois(glossaire, tribunal, 9)
    assert [(emploi.origine, emploi.entree.terme_fr) for emploi in trouves] == [
        (EXEMPLE, "appel"),  # exemple, même domaine
        (EXEMPLE, "audience"),  # exemple, autre domaine
        (DEFINITION, "greffe"),  # définition, même domaine (bien que plus longue)
        (DEFINITION, "juge"),  # définition, autre domaine
    ]
    # Un exemple sans source est attribué à son entrée ; avec une source, c'est elle qui est citée.
    assert [emploi.provenance() for emploi in trouves] == [
        "Exemple de « appel »", "art. 7", "Définition de « greffe »", "Définition de « juge »"]


def test_a_domaine_egal_la_phrase_la_plus_courte_d_abord(tmp_path):
    glossaire = charger(tmp_path, (
        "bail;إيجار;;;;;;\n"
        "loyer;بدل الإيجار;;Somme que le locataire verse au bailleur en exécution du bail.;"
        "مبلغ يدفعه المستأجر للمؤجر تنفيذا لعقد الإيجار.;;;\n"
        "preneur;مستأجر;;Partie au bail.;طرف في الإيجار.;;;\n"))
    assert [emploi.entree.terme_fr for emploi in emplois(glossaire, glossaire.entrees[0])] == ["preneur", "loyer"]


def test_la_definition_de_l_entree_elle_meme_n_est_pas_un_contexte(tmp_path):
    glossaire = charger(tmp_path, "bail;إيجار;;Le bail est un contrat.;الإيجار عقد.;;;\n")
    assert emplois(glossaire, glossaire.entrees[0]) == []


def test_les_phrases_incompletes_sont_ecartees(tmp_path):
    glossaire = charger(tmp_path, (
        "bail;إيجار;;;;;;\n"
        "loyer;بدل الإيجار;;Prix du bail.;;;;\n"  # définition en français seulement
        "preneur;مستأجر;;;;Le preneur signe le bail.;;\n"))  # exemple en français seulement
    assert emplois(glossaire, glossaire.entrees[0]) == []


def test_la_recherche_est_gardee_en_memoire(glossaire, monkeypatch):
    from traducteur import contextes

    vente = entree(glossaire, "contrat de vente")
    premier = emplois(glossaire, vente)
    monkeypatch.setattr(contextes, "_chercher", lambda *arguments: pytest.fail("la recherche est refaite"))
    assert emplois(glossaire, vente) == premier


def test_un_emploi():
    emploi = Emploi("Le bail est écrit.", "الإيجار مكتوب.", PROPRE, "", None)
    assert emploi.provenance() == ""
    assert emploi.texte(FR) == "Le bail est écrit." and emploi.texte(AR) == "الإيجار مكتوب."


# ------------------------------------------------------------------ le glossaire fourni
def test_contextes_du_glossaire_fourni(glossaire_fourni):
    """Près des deux tiers des entrées n'ont encore aucune phrase : le glossaire fourni n'en contient pas pour elles."""
    avec_exemple = sum(1 for entree in glossaire_fourni.entrees if entree.contextes)
    avec_contexte = sum(1 for entree in glossaire_fourni.entrees if emplois(glossaire_fourni, entree))
    assert avec_exemple == 31
    assert avec_contexte == 360  # 329 entrées sans exemple reçoivent une phrase d'une autre entrée
    # Les contextes trouvés emploient bien le terme, dans les deux langues.
    for element in glossaire_fourni.entrees:
        for emploi in emplois(glossaire_fourni, element):
            if emploi.origine != PROPRE:
                assert positions_du_terme(emploi.fr, element, FR), (element.terme_fr, emploi.fr)
                assert positions_du_terme(emploi.ar, element, AR), (element.terme_fr, emploi.ar)


def test_les_deux_sens_d_action_ont_chacun_leurs_contextes(glossaire_fourni):
    proces, titre = (entree for entree in glossaire_fourni.entrees if entree.terme_fr == "action")
    assert (proces.terme_ar, titre.terme_ar) == ("دعوى", "سهم")
    for sens in (proces, titre):
        trouves = emplois(glossaire_fourni, sens)
        assert len(trouves) == 2
        assert all(motif_du_terme(sens, AR).search(emploi.ar) for emploi in trouves)
    assert {emploi.fr for emploi in emplois(glossaire_fourni, proces)}.isdisjoint(
        emploi.fr for emploi in emplois(glossaire_fourni, titre))
