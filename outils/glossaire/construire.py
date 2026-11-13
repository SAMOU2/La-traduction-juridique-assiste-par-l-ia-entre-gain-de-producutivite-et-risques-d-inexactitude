#!/usr/bin/env python3
"""Construit donnees/glossaire_juridique.csv : les 40 entrées d'origine, puis les lots de nouveaux termes.

Emploi, depuis le dossier du projet :

    python outils/glossaire/construire.py            vérifie les lots et les exemples, sans rien écrire ;
                                                     dit si le fichier CSV leur correspond
    python outils/glossaire/construire.py --ecrire   récrit le fichier CSV

Les 40 premières entrées du CSV sont gardées telles quelles. Toutes les suivantes sont récrites à partir des
lots et des exemples : une correction faite à la main dans le CSV après la 40e entrée est perdue. Pour la
conserver, la faire dans le lot ou dans le fichier d'exemples, ou ne plus utiliser ce script.

Options d'affichage : --pluriels (pluriels français calculés pour les termes de plusieurs mots), --homonymes
(termes qui désignent plusieurs entrées), --domaines (nombre d'entrées nouvelles par domaine), --manquants
(entrées qui n'ont pas encore de phrase d'exemple), --coherence (phrases d'exemple où un autre terme du
glossaire figure en français sans que son équivalent figure en arabe : à relire une par une).

Format d'un lot (fichier texte, UTF-8) :

    ## Domaine | Sous-domaine ## CLE_DE_RESSOURCES+AUTRE_CLE
    terme français | terme arabe | codes | pluriel arabe | définition française | définition arabe | options…

Une ligne vide sépare deux groupes de termes voisins (ils deviennent « termes associés » les uns des autres).
Codes : genre français (m, f), puis nature du terme arabe (m, f : nom ; a : nom + adjectif sans article ;
i : annexion, article sur le dernier mot ; c : autre groupe de mots), puis « p » si le terme français est un pluriel.
Options : pf= pluriel français (« - » pour aucun), sf= synonymes français (séparés par « , »),
sa= synonymes arabes (séparés par « ، »), va= termes associés ajoutés (séparés par « , »).

Format d'un fichier d'exemples (dossier exemples/, un fichier par lot) : une phrase par terme, qui emploie le
terme en français et son équivalent en arabe. Elle remplit les colonnes contexte_fr et contexte_ar.

    terme français | phrase française | phrase arabe
    terme français = terme arabe | phrase française | phrase arabe

La seconde forme sert quand le terme français désigne deux entrées (« action » : « دعوى » ou « سهم »).
Le script vérifie que chaque phrase contient bien le terme, avec la même règle que l'application.
"""
from __future__ import annotations

import collections
import csv
import io
import pathlib
import sys
import unicodedata

import regex

DEPOT = pathlib.Path(__file__).resolve().parents[2]
CSV = DEPOT / "donnees" / "glossaire_juridique.csv"
LOTS = pathlib.Path(__file__).parent / "lots"
EXEMPLES = pathlib.Path(__file__).parent / "exemples"
#: Nombre d'entrées placées au début du CSV et écrites à la main : le script n'y touche pas.
ENTREES_D_ORIGINE = 40
SOURCE = "à vérifier (définition d’exemple)"
#: Source écrite pour les phrases d'exemple : elles ont été rédigées pour la démonstration, sans texte officiel.
SOURCE_EXEMPLE = "à vérifier (phrase d’exemple)"
#: Longueur maximale d'une phrase d'exemple, pour qu'elle tienne dans le champ ④ sans le remplir.
LONGUEUR_EXEMPLE = 170
OBJECTIF = 1000

sys.path.insert(0, str(DEPOT))
from traducteur.glossaire import Entree  # noqa: E402
from traducteur.langues import AR, FR, cle_souple  # noqa: E402
from traducteur.segmentation import segmenter_en_phrases  # noqa: E402
from traducteur.surlignage import motif_du_terme  # noqa: E402
from traducteur.traduction import cle_phrase  # noqa: E402

JO = "Journal officiel (JORADP), www.joradp.dz"
RESSOURCES = {
    "CIVIL": [
        "Code civil algérien, ordonnance n° 75-58 du 26 septembre 1975, modifiée et complétée",
        "القانون المدني، الأمر رقم 75-58 المؤرخ في 26 سبتمبر 1975، المعدل والمتمم",
        "Journal officiel (JORADP) n° 78 du 30 septembre 1975, www.joradp.dz",
    ],
    "CPCA": [
        "Code de procédure civile et administrative, loi n° 08-09 du 25 février 2008, modifiée et complétée",
        "قانون الإجراءات المدنية والإدارية، القانون رقم 08-09 المؤرخ في 25 فبراير 2008، المعدل والمتمم",
    ],
    "CP": [
        "Code pénal, ordonnance n° 66-156 du 8 juin 1966, modifiée et complétée",
        "قانون العقوبات، الأمر رقم 66-156 المؤرخ في 8 يونيو 1966، المعدل والمتمم",
    ],
    "CPP": [
        "Code de procédure pénale, loi n° 25-14 du 3 août 2025",
        "قانون الإجراءات الجزائية، القانون رقم 25-14 المؤرخ في 3 غشت 2025",
        "Journal officiel (JORADP) n° 54 du 13 août 2025, www.joradp.dz",
    ],
    "FAMILLE": [
        "Code de la famille, loi n° 84-11 du 9 juin 1984, modifiée et complétée",
        "قانون الأسرة، القانون رقم 84-11 المؤرخ في 9 يونيو 1984، المعدل والمتمم",
    ],
    "COMMERCE": [
        "Code de commerce, ordonnance n° 75-59 du 26 septembre 1975, modifiée et complétée",
        "القانون التجاري، الأمر رقم 75-59 المؤرخ في 26 سبتمبر 1975، المعدل والمتمم",
    ],
    "TRAVAIL": [
        "Loi n° 90-11 du 21 avril 1990 relative aux relations de travail, modifiée et complétée",
        "القانون رقم 90-11 المؤرخ في 21 أبريل 1990 المتعلق بعلاقات العمل، المعدل والمتمم",
    ],
    "CONSTITUTION": [
        "Constitution de la République algérienne démocratique et populaire, révision du 1er novembre 2020 "
        "(décret présidentiel n° 20-442 du 30 décembre 2020)",
        "دستور الجمهورية الجزائرية الديمقراطية الشعبية، التعديل الدستوري لأول نوفمبر 2020 "
        "(المرسوم الرئاسي رقم 20-442 المؤرخ في 30 ديسمبر 2020)",
        "Journal officiel (JORADP) n° 82 du 30 décembre 2020, www.joradp.dz",
    ],
    "ORGJUD": [
        "Loi organique n° 22-10 du 9 juin 2022 relative à l’organisation judiciaire",
        "القانون العضوي رقم 22-10 المؤرخ في 9 يونيو 2022 المتعلق بالتنظيم القضائي",
    ],
    "MARCHES": [
        "Loi n° 23-12 du 5 août 2023 fixant les règles générales relatives aux marchés publics",
        "القانون رقم 23-12 المؤرخ في 5 غشت 2023 الذي يحدد القواعد العامة المتعلقة بالصفقات العمومية",
    ],
    "BANQUE": [
        "Loi n° 23-09 du 21 juin 2023 portant loi monétaire et bancaire",
        "القانون رقم 23-09 المؤرخ في 21 يونيو 2023 المتضمن القانون النقدي والمصرفي",
    ],
    "ASSURANCES": [
        "Ordonnance n° 95-07 du 25 janvier 1995 relative aux assurances, modifiée et complétée",
        "الأمر رقم 95-07 المؤرخ في 25 يناير 1995 المتعلق بالتأمينات، المعدل والمتمم",
    ],
    "NATIONALITE": [
        "Code de la nationalité algérienne, ordonnance n° 70-86 du 15 décembre 1970, modifiée et complétée",
        "قانون الجنسية الجزائرية، الأمر رقم 70-86 المؤرخ في 15 ديسمبر 1970، المعدل والمتمم",
    ],
    "ETATCIVIL": [
        "Ordonnance n° 70-20 du 19 février 1970 relative à l’état civil, modifiée et complétée",
        "الأمر رقم 70-20 المؤرخ في 19 فبراير 1970 المتعلق بالحالة المدنية، المعدل والمتمم",
    ],
    "DOUANES": [
        "Code des douanes, loi n° 79-07 du 21 juillet 1979, modifiée et complétée",
        "قانون الجمارك، القانون رقم 79-07 المؤرخ في 21 يوليو 1979، المعدل والمتمم",
    ],
    "MARITIME": [
        "Code maritime, ordonnance n° 76-80 du 23 octobre 1976, modifiée et complétée",
        "القانون البحري، الأمر رقم 76-80 المؤرخ في 23 أكتوبر 1976، المعدل والمتمم",
    ],
    "CONSOMMATION": [
        "Loi n° 09-03 du 25 février 2009 relative à la protection du consommateur et à la répression des fraudes",
        "القانون رقم 09-03 المؤرخ في 25 فبراير 2009 المتعلق بحماية المستهلك وقمع الغش",
    ],
    "CONCURRENCE": [
        "Ordonnance n° 03-03 du 19 juillet 2003 relative à la concurrence, modifiée et complétée",
        "الأمر رقم 03-03 المؤرخ في 19 يوليو 2003 المتعلق بالمنافسة، المعدل والمتمم",
    ],
    "PI": [
        "Ordonnances n° 03-05 (droits d’auteur et droits voisins), n° 03-06 (marques) et n° 03-07 "
        "(brevets d’invention) du 19 juillet 2003",
        "الأوامر رقم 03-05 (حقوق المؤلف والحقوق المجاورة) ورقم 03-06 (العلامات) ورقم 03-07 "
        "(براءات الاختراع) المؤرخة في 19 يوليو 2003",
    ],
    "SECU": [
        "Loi n° 83-11 du 2 juillet 1983 relative aux assurances sociales, modifiée et complétée",
        "القانون رقم 83-11 المؤرخ في 2 يوليو 1983 المتعلق بالتأمينات الاجتماعية، المعدل والمتمم",
    ],
    "FONCIER": [
        "Loi n° 90-25 du 18 novembre 1990 portant orientation foncière, modifiée et complétée",
        "القانون رقم 90-25 المؤرخ في 18 نوفمبر 1990 المتضمن التوجيه العقاري، المعدل والمتمم",
        "Ordonnance n° 75-74 du 12 novembre 1975 portant établissement du cadastre général et institution "
        "du livre foncier",
    ],
    "ENVIRONNEMENT": [
        "Loi n° 03-10 du 19 juillet 2003 relative à la protection de l’environnement dans le cadre "
        "du développement durable",
        "القانون رقم 03-10 المؤرخ في 19 يوليو 2003 المتعلق بحماية البيئة في إطار التنمية المستدامة",
    ],
    "URBANISME": [
        "Loi n° 90-29 du 1er décembre 1990 relative à l’aménagement et l’urbanisme, modifiée et complétée",
        "القانون رقم 90-29 المؤرخ في أول ديسمبر 1990 المتعلق بالتهيئة والتعمير، المعدل والمتمم",
    ],
    "NUMERIQUE": [
        "Loi n° 18-07 du 10 juin 2018 relative à la protection des personnes physiques dans le traitement "
        "des données à caractère personnel",
        "القانون رقم 18-07 المؤرخ في 10 يونيو 2018 المتعلق بحماية الأشخاص الطبيعيين في مجال معالجة "
        "المعطيات ذات الطابع الشخصي",
        "Loi n° 18-05 du 10 mai 2018 relative au commerce électronique",
    ],
    "FISCAL": [
        "Code des impôts directs et taxes assimilées ; Code des procédures fiscales",
        "قانون الضرائب المباشرة والرسوم المماثلة؛ قانون الإجراءات الجبائية",
        "Direction générale des impôts, www.mfdgi.gov.dz",
    ],
    "FINANCES": [
        "Loi organique n° 18-15 du 2 septembre 2018 relative aux lois de finances, modifiée et complétée",
        "القانون العضوي رقم 18-15 المؤرخ في 2 سبتمبر 2018 المتعلق بقوانين المالية، المعدل والمتمم",
        "Loi n° 23-07 du 21 juin 2023 relative aux règles de comptabilité publique et de gestion financière",
    ],
    "DIP": [
        "Charte des Nations Unies, San Francisco, 26 juin 1945",
        "ميثاق الأمم المتحدة، سان فرانسيسكو، 26 يونيو 1945",
        "Convention de Vienne sur le droit des traités, 23 mai 1969",
        "Nations Unies, Collection des traités, treaties.un.org",
    ],
    "DH": [
        "Déclaration universelle des droits de l’homme, 10 décembre 1948",
        "الإعلان العالمي لحقوق الإنسان، 10 ديسمبر 1948",
        "Pacte international relatif aux droits civils et politiques, 16 décembre 1966",
    ],
    "ARBITRAGE": [
        "Convention de New York pour la reconnaissance et l’exécution des sentences arbitrales étrangères, "
        "10 juin 1958",
    ],
    "PENITENTIAIRE": [
        "Code de l’organisation pénitentiaire et de la réinsertion sociale des détenus, loi n° 05-04 "
        "du 6 février 2005, modifiée et complétée",
        "قانون تنظيم السجون وإعادة الإدماج الاجتماعي للمحبوسين، القانون رقم 05-04 المؤرخ في 6 فبراير 2005، "
        "المعدل والمتمم",
    ],
    "CORRUPTION": [
        "Loi n° 06-01 du 20 février 2006 relative à la prévention et à la lutte contre la corruption, "
        "modifiée et complétée",
        "القانون رقم 06-01 المؤرخ في 20 فبراير 2006 المتعلق بالوقاية من الفساد ومكافحته، المعدل والمتمم",
    ],
    "FONCTIONPUBLIQUE": [
        "Ordonnance n° 06-03 du 15 juillet 2006 portant statut général de la fonction publique",
        "الأمر رقم 06-03 المؤرخ في 15 يوليو 2006 المتضمن القانون الأساسي العام للوظيفة العمومية",
    ],
    "EXPROPRIATION": [
        "Loi n° 91-11 du 27 avril 1991 fixant les règles relatives à l’expropriation pour cause d’utilité publique",
        "القانون رقم 91-11 المؤرخ في 27 أبريل 1991 الذي يحدد القواعد المتعلقة بنزع الملكية من أجل المنفعة العمومية",
    ],
    "DOMAINE": [
        "Loi n° 90-30 du 1er décembre 1990 portant loi domaniale, modifiée et complétée",
        "القانون رقم 90-30 المؤرخ في أول ديسمبر 1990 المتضمن قانون الأملاك الوطنية، المعدل والمتمم",
    ],
    "ETRANGERS": [
        "Loi n° 08-11 du 25 juin 2008 relative aux conditions d’entrée, de séjour et de circulation des étrangers "
        "en Algérie",
        "القانون رقم 08-11 المؤرخ في 25 يونيو 2008 المتعلق بشروط دخول الأجانب إلى الجزائر وإقامتهم بها وتنقلهم فيها",
    ],
    "DIPLOMATIE": [
        "Convention de Vienne sur les relations diplomatiques, 18 avril 1961",
        "اتفاقية فيينا للعلاقات الدبلوماسية، 18 أبريل 1961",
        "Convention de Vienne sur les relations consulaires, 24 avril 1963",
    ],
    "DIH": [
        "Conventions de Genève du 12 août 1949",
        "اتفاقيات جنيف المؤرخة في 12 غشت 1949",
        "Statut de Rome de la Cour pénale internationale, 17 juillet 1998",
        "Convention relative au statut des réfugiés, Genève, 28 juillet 1951",
    ],
    "WAKF": [
        "Loi n° 91-10 du 27 avril 1991 relative aux biens wakfs, modifiée et complétée",
        "القانون رقم 91-10 المؤرخ في 27 أبريل 1991 المتعلق بالأوقاف، المعدل والمتمم",
    ],
    "CORNU": ["G. Cornu (dir.), Vocabulaire juridique, Association Henri Capitant, PUF"],
}

_ARABE = regex.compile(r"\p{Arabic}")
_LATIN = regex.compile(r"\p{Latin}")
# Lettres arabes, tanwin kasra (nom défectueux) et espace : rien d'autre dans un terme arabe.
_TERME_ARABE = regex.compile(r"[\u0621-\u064A\u064D ]+")
_TEXTE_ARABE = regex.compile(r"[\u0621-\u064A\u064D 0-9،؛:.()«»\-]+")
_ARRETS = {"de", "du", "des", "à", "au", "aux", "en", "par", "pour", "sans", "sous", "sur", "contre", "entre",
           "avec", "dans", "hors", "ou", "et", "ad", "non", "près", "devant", "après", "selon", "envers"}
_EN_AL = {"aval", "bal", "carnaval", "festival", "récital", "régal", "chacal", "naval", "fatal", "natal", "banal"}
_EN_AIL = {"bail", "travail", "vitrail", "corail", "émail", "soupirail", "vantail"}
# Noms féminins sans ta marbuta, et noms masculins qui en portent une ou finissent par alif maqsura.
_FEMININS = {"أرض", "دار", "نفس", "حرب", "يمين", "سن", "عين", "يد", "بئر", "سوق", "طريق", "حال", "فوائد"}
_MASCULINS = {"خليفة", "مستشفى", "مبنى", "معنى", "مدعى", "مأوى", "مجرى", "مرعى"}
_SANS_ARTICLE = {"التزام", "التزامات", "التماس", "التحاق", "التقاء", "التفات", "التباس", "التقاط", "التصاق"}


def pluriel_mot(mot: str) -> str:
    if "-" in mot:
        debut, _, fin = mot.rpartition("-")
        return f"{debut}-{pluriel_mot(fin)}"
    bas = mot.casefold()
    if bas.endswith(("s", "x", "z")):
        return mot
    if bas.endswith("al") and bas not in _EN_AL:
        return mot[:-2] + "aux"
    if bas in _EN_AIL:
        return mot[:-3] + "aux"
    if bas.endswith(("au", "eu")):
        return mot + "x"
    return mot + "s"


def pluriel_fr(terme: str) -> str:
    mots = terme.split(" ")
    sortie, fige = [], False
    for rang, mot in enumerate(mots):
        bas = mot.casefold()
        if rang and (bas in _ARRETS or bas.startswith(("d'", "l'", "qu'"))):
            fige = True
        sortie.append(mot if fige else pluriel_mot(mot))
    return " ".join(sortie)


def a_l_article(mot: str) -> bool:
    return len(mot) >= 4 and mot.startswith("ال") and mot not in _SANS_ARTICLE


class Erreurs(list):
    def signaler(self, lot: str, numero: int, message: str) -> None:
        self.append(f"{lot}:{numero}: {message}")


def lire_les_lots(erreurs: Erreurs) -> list[dict]:
    entrees: list[dict] = []
    groupe = 0
    for lot in sorted(LOTS.glob("*.txt")):
        domaine, cles = "", []
        for numero, ligne in enumerate(lot.read_text(encoding="utf-8").splitlines(), 1):
            ligne = unicodedata.normalize("NFC", ligne.strip())
            if not ligne:
                groupe += 1
                continue
            if ligne.startswith("##"):
                morceaux = [m.strip() for m in ligne.strip("# ").split("##")]
                domaine = " | ".join(m.strip() for m in morceaux[0].split("|"))
                cles = [c.strip() for c in morceaux[1].split("+")] if len(morceaux) > 1 else []
                for cle in cles:
                    if cle not in RESSOURCES:
                        erreurs.signaler(lot.name, numero, f"ressource inconnue : {cle}")
                groupe += 1
                continue
            if ligne.startswith("#"):
                continue
            champs = [champ.strip() for champ in ligne.split(" | ")]
            if len(champs) < 6:
                erreurs.signaler(lot.name, numero, f"{len(champs)} champs au lieu de 6 : {ligne[:60]}")
                continue
            fr, ar, codes, pluriel_ar, def_fr, def_ar, *options = champs
            entree = {"lot": lot.name, "numero": numero, "fr": fr, "ar": ar, "codes": codes, "pluriel_ar": pluriel_ar,
                      "def_fr": def_fr, "def_ar": def_ar, "domaine": domaine, "cles": cles, "groupe": groupe,
                      "pf": None, "sf": [], "sa": [], "va": []}
            for option in options:
                nom, egal, valeur = option.partition("=")
                if not egal or nom not in ("pf", "sf", "sa", "va"):
                    erreurs.signaler(lot.name, numero, f"option inconnue : {option[:40]}")
                    continue
                if nom == "pf":
                    entree["pf"] = valeur.strip()
                elif nom == "sa":
                    entree["sa"] = [v.strip() for v in valeur.split("،") if v.strip()]
                else:
                    entree[nom] = [v.strip() for v in valeur.split(",") if v.strip()]
            entrees.append(entree)
    return entrees


def verifier(entree: dict, erreurs: Erreurs) -> None:
    lot, numero = entree["lot"], entree["numero"]

    def signaler(message: str) -> None:
        erreurs.signaler(lot, numero, f"« {entree['fr']} » : {message}")

    fr, ar, codes = entree["fr"], entree["ar"], entree["codes"]
    if not fr or _ARABE.search(fr):
        signaler("terme français vide ou avec de l'arabe")
    if "’" in fr or "  " in fr or fr != fr.strip():
        signaler("apostrophe courbe ou espaces dans le terme français")
    if not _TERME_ARABE.fullmatch(ar):
        signaler(f"caractère inattendu dans le terme arabe : {ar}")
    if not regex.fullmatch(r"[mf][mfaic]p?", codes):
        signaler(f"codes invalides : {codes}")
        return
    mots = ar.split()
    nature = codes[1]
    if (len(mots) == 1) != (nature in "mf"):
        signaler(f"nature arabe « {nature} » incompatible avec {len(mots)} mot(s)")
    if len(mots) == 1 and nature in "mf":
        feminin = ar.endswith(("ة", "ى", "ات")) or ar in _FEMININS
        if (nature == "f") != feminin and ar not in _MASCULINS:
            signaler(f"genre arabe à vérifier : {ar} noté « {nature} »")
    if nature == "i" and (not a_l_article(mots[-1]) or a_l_article(mots[0])):
        signaler("annexion : l'article doit être sur le dernier mot et pas sur le premier")
    if nature == "a" and any(a_l_article(mot) for mot in mots):
        signaler("nom + adjectif : aucun mot ne doit porter l'article")
    if nature == "c" and len(mots) > 1 and not any(a_l_article(mot) for mot in mots) and len(mots) == 2:
        pass  # groupe indéfini (préposition, etc.) : accepté tel quel
    if entree["pluriel_ar"] and not _TERME_ARABE.fullmatch(entree["pluriel_ar"]):
        signaler(f"caractère inattendu dans le pluriel arabe : {entree['pluriel_ar']}")
    for nom in ("def_fr",):
        texte = entree[nom]
        if not texte or _ARABE.search(texte) or not texte[0].isupper() or not texte.endswith("."):
            signaler("définition française : vide, arabe, sans majuscule ou sans point final")
        if "  " in texte or " ," in texte or " ." in texte:
            signaler("définition française : espace mal placée")
    texte = entree["def_ar"]
    if not texte or _LATIN.search(texte) or not texte.endswith(".") or not _TEXTE_ARABE.fullmatch(texte):
        signaler(f"définition arabe : vide, lettres latines, signe inattendu ou sans point final : {texte}")
    if "  " in texte or " ،" in texte or " ." in texte or "," in texte or ";" in texte:
        signaler("définition arabe : ponctuation ou espace mal placée")
    for synonyme in entree["sa"]:
        if not _TERME_ARABE.fullmatch(synonyme):
            signaler(f"synonyme arabe inattendu : {synonyme}")
    for synonyme in (*entree["sf"], *entree["va"]):
        if _ARABE.search(synonyme) or "’" in synonyme:
            signaler(f"synonyme ou terme associé inattendu : {synonyme}")


def pluriel_francais(entree: dict) -> str:
    """Pluriel français écrit dans le CSV : celui du lot (pf=), sinon le pluriel calculé, sinon rien."""
    if entree["pf"] == "-" or entree["codes"].endswith("p"):
        return ""
    if entree["pf"]:
        return entree["pf"]
    return pluriel_fr(entree["fr"]) if entree["pluriel_ar"] else ""


def lire_les_exemples(entrees: list[dict], erreurs: Erreurs) -> None:
    """Lit les fichiers d'exemples et range chaque phrase dans son entrée (clé « exemple »)."""
    par_terme: dict[str, list[dict]] = collections.defaultdict(list)
    for entree in entrees:
        par_terme[cle_souple(entree["fr"])].append(entree)
    for fichier in sorted(EXEMPLES.glob("*.txt")):
        for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
            ligne = unicodedata.normalize("NFC", ligne.strip())
            if not ligne or ligne.startswith("#"):
                continue
            champs = [champ.strip() for champ in ligne.split(" | ")]
            if len(champs) != 3:
                erreurs.signaler(fichier.name, numero, f"{len(champs)} champs au lieu de 3 : {ligne[:60]}")
                continue
            cle, phrase_fr, phrase_ar = champs
            fr, _, ar = (morceau.strip() for morceau in cle.partition(" = "))
            candidates = par_terme.get(cle_souple(fr), [])
            if ar:
                candidates = [entree for entree in candidates if cle_souple(entree["ar"]) == cle_souple(ar)]
            if not candidates:
                erreurs.signaler(fichier.name, numero, f"exemple d'un terme absent des lots : {cle}")
            elif len(candidates) > 1:
                choix = " ou ".join(f"« {fr} = {entree['ar']} »" for entree in candidates)
                erreurs.signaler(fichier.name, numero, f"« {fr} » désigne plusieurs entrées : écrire {choix}")
            elif "exemple" in candidates[0]:
                erreurs.signaler(fichier.name, numero, f"« {cle} » a déjà un exemple")
            else:
                candidates[0]["exemple"] = (phrase_fr, phrase_ar)
                candidates[0]["origine_exemple"] = f"{fichier.name}:{numero}"


def verifier_l_exemple(entree: dict, erreurs: Erreurs) -> None:
    """La phrase d'exemple d'une entrée : écriture, ponctuation, présence du terme dans les deux langues."""
    fichier, _, numero = entree["origine_exemple"].partition(":")

    def signaler(message: str) -> None:
        erreurs.signaler(fichier, int(numero), f"« {entree['fr']} » : {message}")

    phrase_fr, phrase_ar = entree["exemple"]
    if (not phrase_fr or _ARABE.search(phrase_fr) or not (phrase_fr[0].isupper() or phrase_fr[0].isdigit())
            or not phrase_fr.endswith(".")):
        signaler("phrase française : vide, avec de l'arabe, sans majuscule ou sans point final")
    if "  " in phrase_fr or " ," in phrase_fr or " ." in phrase_fr or "|" in phrase_fr or "’" in phrase_fr:
        signaler("phrase française : espace mal placée, barre verticale ou apostrophe courbe")
    if (not phrase_ar or _LATIN.search(phrase_ar) or not phrase_ar.endswith(".")
            or not _TEXTE_ARABE.fullmatch(phrase_ar) or "ـ" in phrase_ar):
        signaler(f"phrase arabe : vide, lettres latines, signe inattendu ou sans point final : {phrase_ar}")
    if "  " in phrase_ar or " ،" in phrase_ar or " ." in phrase_ar:
        signaler("phrase arabe : ponctuation ou espace mal placée")
    for langue, phrase in (("française", phrase_fr), ("arabe", phrase_ar)):
        if len(phrase) > LONGUEUR_EXEMPLE:
            signaler(f"phrase {langue} trop longue : {len(phrase)} caractères (maximum {LONGUEUR_EXEMPLE})")
    # Le terme doit se trouver dans la phrase, d'après la règle que l'application applique pour le mettre
    # en évidence (terme ou pluriel ; en arabe, article, particules collées et terminaisons courantes).
    modele = Entree(numero=0, terme_fr=entree["fr"], terme_ar=entree["ar"], pluriel_fr=pluriel_francais(entree),
                    pluriel_ar=entree["pluriel_ar"])
    for langue, nom, phrase in ((FR, "française", phrase_fr), (AR, "arabe", phrase_ar)):
        motif = motif_du_terme(modele, langue)
        if motif is None or not motif.search(phrase):
            signaler(f"la phrase {nom} ne contient pas « {modele.terme(langue)} » : {phrase}")


def incoherences(anciennes: list[dict], nouvelles: list[dict]) -> list[str]:
    """Phrases d'exemple où un autre terme du glossaire figure en français, mais pas son équivalent en arabe.

    Ce n'est pas toujours une erreur : un mot peut avoir un autre sens dans la phrase. La liste sert à relire.
    """
    # Pour chaque terme du glossaire : le terme français, l'entrée qui sert de modèle, ses synonymes arabes.
    modeles: list[tuple[str, Entree, list[str]]] = []
    for ancienne in anciennes:
        modele = Entree(numero=0, terme_fr=ancienne["terme_fr"], terme_ar=ancienne["terme_ar"],
                        pluriel_fr=ancienne["pluriel_fr"], pluriel_ar=ancienne["pluriel_ar"])
        synonymes = [s.strip() for s in ancienne["synonymes_ar"].split("|") if s.strip()]
        modeles.append((ancienne["terme_fr"], modele, synonymes))
    for entree in nouvelles:
        modele = Entree(numero=0, terme_fr=entree["fr"], terme_ar=entree["ar"], pluriel_fr=pluriel_francais(entree),
                        pluriel_ar=entree["pluriel_ar"])
        modeles.append((entree["fr"], modele, entree["sa"]))
    motifs = []
    for terme, modele, synonymes in modeles:
        arabes = [motif_du_terme(modele, AR)] + [
            motif_du_terme(Entree(numero=0, terme_fr=terme, terme_ar=synonyme), AR) for synonyme in synonymes]
        motifs.append((terme, modele.terme_ar, motif_du_terme(modele, FR), [m for m in arabes if m is not None]))
    remarques = []
    for entree in nouvelles:
        if "exemple" not in entree:
            continue
        phrase_fr, phrase_ar = entree["exemple"]
        # Chaque terme du glossaire trouvé dans la phrase française : (début, fin, terme, équivalent, présent en arabe).
        trouves = []
        couverts = []  # passages occupés par le terme de l'entrée, ou par un terme dont l'équivalent est présent
        for terme, arabe, francais, arabes in motifs:
            if francais is None:
                continue
            for trouve in francais.finditer(phrase_fr):
                propre = cle_souple(terme) == cle_souple(entree["fr"])
                present = propre or any(motif.search(phrase_ar) for motif in arabes)
                if present:
                    couverts.append((trouve.start(), trouve.end()))
                if not propre:
                    trouves.append((trouve.start(), trouve.end(), terme, arabe, present))
        presents = {cle_souple(terme) for _, _, terme, _, present in trouves if present}
        absents: dict[str, list[str]] = collections.defaultdict(list)
        for depart, arrivee, terme, arabe, present in trouves:
            # Un terme pris dans un terme déjà traduit (« cour » dans « Cour suprême », « intérêt » dans
            # « intérêts ») n'est pas signalé.
            dans_un_autre = any(a <= depart and arrivee <= b for a, b in couverts)
            signale = not present and not dans_un_autre and cle_souple(terme) not in presents
            if signale and f"{terme} = {arabe}" not in absents[cle_souple(terme)]:
                absents[cle_souple(terme)].append(f"{terme} = {arabe}")
        manques = [" / ".join(choix) for choix in absents.values()]
        if manques:
            remarques.append(f"{entree['origine_exemple']} « {entree['fr']} » : {' ; '.join(manques)}\n"
                             f"      {phrase_fr}\n      {phrase_ar}")
    return remarques


def categories(entree: dict) -> tuple[str, str]:
    genre, nature, pluriel = entree["codes"][0], entree["codes"][1], entree["codes"].endswith("p")
    locution = " " in entree["fr"]
    if pluriel:
        fr = (f"locution nominale ({'masculin' if genre == 'm' else 'féminin'} pluriel)" if locution
              else f"nom {'masculin' if genre == 'm' else 'féminin'} pluriel")
    elif locution:
        fr = "locution nominale " + ("masculine" if genre == "m" else "féminine")
    else:
        fr = "nom " + ("masculin" if genre == "m" else "féminin")
    ar = {"m": "اسم مذكر", "f": "اسم مؤنث", "a": "مركب وصفي", "i": "مركب إضافي", "c": "مركب اسمي"}[nature]
    return fr, ar


def lire_l_origine() -> str:
    """Début du CSV actuel : la ligne des noms de colonnes et les entrées d'origine, sans modification."""
    lignes = CSV.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    origine = "".join(lignes[:ENTREES_D_ORIGINE + 1])
    if len(list(csv.reader(io.StringIO(origine, newline=""), delimiter=";"))) != ENTREES_D_ORIGINE + 1:
        sys.exit(f"{CSV} : les {ENTREES_D_ORIGINE} premières entrées ne tiennent pas sur une ligne chacune.")
    return origine


def construire() -> int:
    origine = lire_l_origine()
    anciennes = list(csv.DictReader(io.StringIO(origine, newline=""), delimiter=";"))
    colonnes = list(anciennes[0].keys())
    erreurs = Erreurs()
    nouvelles = lire_les_lots(erreurs)
    for entree in nouvelles:
        verifier(entree, erreurs)
    lire_les_exemples(nouvelles, erreurs)
    # Une phrase ne sert qu'une fois, en français comme en arabe : dans l'application, une phrase du texte
    # identique à un exemple reçoit la traduction de cet exemple. Les exemples des entrées d'origine comptent.
    phrases: dict[tuple[str, str], str] = {}
    for ancienne in anciennes:
        for langue, colonne in ((FR, "contexte_fr"), (AR, "contexte_ar")):
            for exemple in ancienne[colonne].split("|"):
                for phrase in (exemple, *(segment.texte for segment in segmenter_en_phrases(exemple))):
                    if cle_phrase(phrase):
                        phrases[langue, cle_phrase(phrase)] = ancienne["terme_fr"]
    for entree in nouvelles:
        if "exemple" in entree:
            verifier_l_exemple(entree, erreurs)
            fichier, ligne = entree["origine_exemple"].split(":")[:2]
            for langue, phrase in zip((FR, AR), entree["exemple"], strict=True):
                cle = (langue, cle_phrase(phrase))
                if cle in phrases:
                    erreurs.signaler(fichier, int(ligne), f"même phrase que « {phrases[cle]} » : {phrase}")
                phrases[cle] = entree["fr"]

    # Doublons : même couple (terme français, terme arabe).
    vus: dict[tuple[str, str], str] = {
        (cle_souple(a["terme_fr"]), cle_souple(a["terme_ar"])): "origine" for a in anciennes}
    par_fr: dict[str, list[str]] = collections.defaultdict(list)
    par_ar: dict[str, list[str]] = collections.defaultdict(list)
    for a in anciennes:
        par_fr[cle_souple(a["terme_fr"])].append(a["terme_ar"])
        par_ar[cle_souple(a["terme_ar"])].append(a["terme_fr"])
    for entree in nouvelles:
        cle = (cle_souple(entree["fr"]), cle_souple(entree["ar"]))
        if cle in vus:
            erreurs.signaler(entree["lot"], entree["numero"],
                             f"doublon de « {entree['fr']} / {entree['ar']} » ({vus[cle]})")
        vus[cle] = f"{entree['lot']}:{entree['numero']}"
        par_fr[cle[0]].append(entree["ar"])
        par_ar[cle[1]].append(entree["fr"])

    # Termes associés : les voisins du même groupe, les plus proches d'abord.
    groupes: dict[int, list[dict]] = collections.defaultdict(list)
    for entree in nouvelles:
        groupes[entree["groupe"]].append(entree)
    termes_connus = {cle_souple(a["terme_fr"]) for a in anciennes} | {cle_souple(e["fr"]) for e in nouvelles}
    for membres in groupes.values():
        for rang, entree in enumerate(membres):
            voisins = sorted((autre for autre in membres if autre is not entree),
                             key=lambda autre: (abs(membres.index(autre) - rang), membres.index(autre)))
            associes = list(entree["va"])
            for autre in voisins:
                if len(associes) >= 4:
                    break
                if cle_souple(autre["fr"]) != cle_souple(entree["fr"]) and autre["fr"] not in associes:
                    associes.append(autre["fr"])
            entree["associes"] = associes[:4]
            for terme in entree["va"]:
                if cle_souple(terme) not in termes_connus:
                    erreurs.signaler(entree["lot"], entree["numero"], f"terme associé absent du glossaire : {terme}")

    sortie = io.StringIO()
    sortie.write(origine if origine.endswith("\n") else origine + "\n")
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\n")
    pluriels_composes = []
    for entree in nouvelles:
        categorie_fr, categorie_ar = "", ""
        if regex.fullmatch(r"[mf][mfaic]p?", entree["codes"]):
            categorie_fr, categorie_ar = categories(entree)
        pluriel = pluriel_francais(entree)
        if pluriel and not entree["pf"] and (" " in entree["fr"] or "-" in entree["fr"]):
            pluriels_composes.append(f"{entree['fr']} -> {pluriel}")
        phrase_fr, phrase_ar = entree.get("exemple", ("", ""))
        ressources = [r for cle in entree["cles"] for r in RESSOURCES.get(cle, [])]
        sans_journal_officiel = ("CORNU", "DIP", "DH", "ARBITRAGE", "FISCAL", "DIPLOMATIE", "DIH")
        if not any("joradp" in r for r in ressources) and any(
                cle not in sans_journal_officiel for cle in entree["cles"]):
            ressources.append(JO)
        valeurs = {
            "terme_fr": entree["fr"], "terme_ar": entree["ar"], "categorie_fr": categorie_fr,
            "categorie_ar": categorie_ar, "pluriel_fr": pluriel, "pluriel_ar": entree["pluriel_ar"],
            "domaine": entree["domaine"], "synonymes_fr": " | ".join(entree["sf"]),
            "synonymes_ar": " | ".join(entree["sa"]), "termes_associes": " | ".join(entree["associes"]),
            "definition_fr": entree["def_fr"].replace("'", "’"), "definition_ar": entree["def_ar"],
            "source_definition": SOURCE, "contexte_fr": phrase_fr.replace("'", "’"), "contexte_ar": phrase_ar,
            "source_contexte": SOURCE_EXEMPLE if phrase_fr else "",
            "ressources": " | ".join(ressources),
        }
        ecrivain.writerow([valeurs[colonne] for colonne in colonnes])

    total = len(anciennes) + len(nouvelles)
    print(f"{len(anciennes)} entrées d'origine + {len(nouvelles)} nouvelles = {total} (objectif {OBJECTIF}, "
          f"reste {OBJECTIF - total})")
    sans_exemple = [entree for entree in nouvelles if "exemple" not in entree]
    print(f"phrases d'exemple : {len(nouvelles) - len(sans_exemple)} sur {len(nouvelles)} entrées nouvelles"
          + (f" ; il en manque {len(sans_exemple)} (--manquants pour la liste)" if sans_exemple else ""))
    if "--coherence" in sys.argv:
        remarques = incoherences(anciennes, nouvelles)
        print(f"\n{len(remarques)} phrase(s) à relire (terme français sans son équivalent arabe) :")
        print("\n".join(remarques))
    if "--manquants" in sys.argv:
        for lot, membres in collections.Counter(entree["lot"] for entree in sans_exemple).items():
            print(f"{membres:4d}  {lot}")
    if "--pluriels" in sys.argv:
        print("\n".join(pluriels_composes))
    if "--homonymes" in sys.argv:
        for cle, termes in sorted(par_fr.items()):
            if len(termes) > 1:
                print("FR", cle, "->", " / ".join(termes))
        for cle, termes in sorted(par_ar.items()):
            if len(termes) > 1:
                print("AR", cle, "->", " / ".join(termes))
    if "--domaines" in sys.argv:
        for domaine, nombre in collections.Counter(e["domaine"] for e in nouvelles).most_common():
            print(f"{nombre:4d}  {domaine}")
    if erreurs:
        print(f"\n{len(erreurs)} ERREUR(S) :")
        print("\n".join(erreurs))
        return 1
    # Le CSV actuel est-il celui que donnent les lots et les exemples ? Sinon, il a été corrigé à la main,
    # ou bien un lot a changé depuis la dernière écriture.
    actuelles, prevues = CSV.read_text(encoding="utf-8-sig").splitlines(), sortie.getvalue().splitlines()
    differentes = sum(1 for actuelle, prevue in zip(actuelles, prevues, strict=False) if actuelle != prevue)
    differentes += abs(len(actuelles) - len(prevues))
    if "--ecrire" in sys.argv:
        CSV.write_bytes(b"\xef\xbb\xbf" + sortie.getvalue().encode("utf-8"))
        print(f"écrit : {CSV} ({differentes} ligne(s) modifiée(s))")
    elif differentes:
        print(f"\nLe fichier CSV diffère des lots et des exemples : {differentes} ligne(s). L'option --ecrire le "
              f"récrit ;\nune correction faite à la main dans le CSV après la {ENTREES_D_ORIGINE}e entrée serait "
              "alors perdue.")
    else:
        print("Le fichier CSV correspond aux lots et aux exemples.")
    return 0


if __name__ == "__main__":
    sys.exit(construire())
