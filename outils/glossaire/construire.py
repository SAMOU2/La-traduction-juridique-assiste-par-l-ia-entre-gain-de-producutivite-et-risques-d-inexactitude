#!/usr/bin/env python3
"""Construit donnees/glossaire_juridique.csv : les 40 entrées d'origine, les lots, puis les termes seuls.

Emploi, depuis le dossier du projet :

    python outils/glossaire/construire.py            vérifie les lots, les exemples et les définitions, sans rien
                                                     écrire ; dit si le fichier CSV leur correspond
    python outils/glossaire/construire.py --ecrire   récrit le fichier CSV

Les 40 premières entrées du CSV sont gardées telles quelles. Toutes les suivantes sont récrites à partir des
lots, des exemples, des termes seuls et de leurs définitions : une correction faite à la main dans le CSV après
la 40e entrée est perdue. Pour la conserver, la faire dans le lot, dans le fichier d'exemples, dans le fichier de
termes seuls ou dans le fichier de définitions, ou ne plus utiliser ce script.

Options d'affichage : --pluriels (pluriels français calculés pour les termes de plusieurs mots), --homonymes
(termes qui désignent plusieurs entrées), --domaines (nombre d'entrées nouvelles par domaine), --manquants
(entrées qui n'ont pas encore de phrase d'exemple, termes seuls qui n'ont pas encore de définition),
--coherence (phrases d'exemple où un autre terme du glossaire figure en français sans que son équivalent figure
en arabe : à relire une par une), --coherence-definitions (la même liste pour les définitions des termes seuls).

Format d'un lot (fichier texte, UTF-8) :

    ## Domaine | Sous-domaine ## CLE_DE_RESSOURCES+AUTRE_CLE
    terme français | terme arabe | codes | pluriel arabe | définition française | définition arabe | options…

Une ligne vide sépare deux groupes de termes voisins (ils deviennent « termes associés » les uns des autres).
Codes : genre français (m, f), puis nature du terme arabe (m, f : nom ; a : nom + adjectif sans article ;
i : annexion, article sur le dernier mot ; c : autre groupe de mots), puis « p » si le terme français est un pluriel.
Options : pf= pluriel français (« - » pour aucun), sf= synonymes français (séparés par « , »),
sa= synonymes arabes (séparés par « ، »), va= termes associés ajoutés (séparés par « , »).

Format d'un fichier d'exemples (dossier exemples/) : une phrase par terme, qui emploie le terme en français et
son équivalent en arabe. Elle remplit les colonnes contexte_fr et contexte_ar. Le fichier porte le nom du lot
ou du fichier de termes seuls qu'il illustre : exemples/41_vocabulaire_general.txt donne les phrases des termes
de termes/41_vocabulaire_general.txt, et de ceux-là seulement.

    terme français | phrase française | phrase arabe
    terme français = terme arabe | phrase française | phrase arabe

La seconde forme sert quand le terme français désigne deux entrées (« action » : « دعوى » ou « سهم »).
Le script vérifie que chaque phrase contient bien le terme, avec la même règle que l'application
(traducteur/surlignage.py). Un nom y figure tel quel ou au pluriel. Un adjectif peut s'accorder. Un verbe
s'écrit au passé dans les deux langues : en français l'infinitif ou le participe passé (« a abrogé »), en
arabe le passé à la troisième personne (« ألغى », « ألغت »). Quelques mots peuvent séparer le verbe d'une
locution verbale de sa suite (« a mis le débiteur en demeure », « رفع المدعي دعوى »).

Format d'un fichier de termes seuls (dossier termes/, à partir de la version 0.8) : le même en-tête de domaine
et les mêmes groupes que dans un lot, mais sans définition. Ces termes sont écrits dans le CSV après ceux des
lots. Le pluriel arabe et les options peuvent manquer. La phrase d'exemple d'un terme seul s'écrit dans le
dossier exemples/, dans le fichier du même nom ; un terme seul peut ne pas en avoir.

    terme français | terme arabe | codes | pluriel arabe | options…

Aux codes des noms s'ajoutent cinq codes : adj (adjectif), v (verbe), adv (adverbe ou locution adverbiale),
prep (préposition ou locution prépositive), conj (conjonction ou locution conjonctive). L'application ne
remplace pas ces mots dans la traduction d'un texte : il faudrait les accorder ou les conjuguer. Ils ont leur
fiche, et une locution de plusieurs mots reconnue dans un texte y reste entière (« de plein droit »).

Format d'un fichier de définitions (dossier definitions/, à partir de la version 0.13) : la définition d'un
terme seul, dans les deux langues, et ses synonymes s'il en a. Le fichier porte le nom du fichier de termes
seuls qu'il complète. Un terme seul peut ne pas avoir de définition.

    terme français | définition française | définition arabe | options…
    terme français = terme arabe | définition française | définition arabe | options…

Options : sf= synonymes français (séparés par « , »), sa= synonymes arabes (séparés par « ، »). Ils s'ajoutent
à ceux du fichier de termes. La définition ne reprend pas le terme lui-même : le script le refuse, en français
comme en arabe. Il refuse aussi deux définitions identiques, et une définition de plus de 200 caractères.
L'option homographe=ar (ou homographe=fr) lève le premier refus quand la définition emploie un autre mot qui
s'écrit comme le terme : « البلدية » (la commune) dans la définition de l'adjectif « بلدي » (communal).
Un synonyme est un autre nom de la même notion. Le synonyme d'un nom est remplacé comme lui dans la traduction
d'un texte : il ne doit désigner aucun autre nom du glossaire.

Le script refuse un nom seul dont une forme (terme, pluriel ou synonyme) désigne déjà un autre nom, en français
ou en arabe : l'application n'aurait ni définition ni exemple pour choisir entre les deux. Il refuse aussi un
nom d'un seul mot qui est un mot courant de la langue (« or », « est », « قبل ») : la traduction d'un texte le
remplacerait partout. Un adjectif, un verbe ou une locution peut partager une forme avec une autre entrée,
puisqu'il n'est pas remplacé : « عقد » est le nom « contrat » et le verbe « conclure ».
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
#: Termes seuls : terme, équivalent, catégorie, pluriel et domaine, sans définition.
TERMES = pathlib.Path(__file__).parent / "termes"
#: Définitions et synonymes des termes seuls (à partir de la version 0.13) : un fichier par fichier de termes.
DEFINITIONS = pathlib.Path(__file__).parent / "definitions"
#: Nombre d'entrées placées au début du CSV et écrites à la main : le script n'y touche pas.
ENTREES_D_ORIGINE = 40
SOURCE = "à vérifier (définition d’exemple)"
#: Source écrite pour les phrases d'exemple : elles ont été rédigées pour la démonstration, sans texte officiel.
SOURCE_EXEMPLE = "à vérifier (phrase d’exemple)"
#: Mention écrite dans la colonne « source_definition » d'un terme seul : il n'a pas de définition, la mention
#: porte sur son équivalent. L'application l'affiche dans la fiche du terme, au pied de l'équivalent.
SOURCE_SEUL = "à vérifier (équivalent d’exemple)"
#: Mention d'un terme seul qui a reçu une définition : son équivalent et sa définition sont tous deux à vérifier.
#: L'application l'affiche au pied de l'équivalent et au pied de la définition.
SOURCE_SEUL_DEFINI = "à vérifier (équivalent et définition d’exemple)"
#: Longueur maximale d'une phrase d'exemple, pour qu'elle reste courte à l'écran (« Contextualisation »).
LONGUEUR_EXEMPLE = 170
#: Longueur maximale de la définition d'un terme seul. La plus longue définition des lots compte 175 caractères.
LONGUEUR_DEFINITION = 200
OBJECTIF = 5000

sys.path.insert(0, str(DEPOT))
from traducteur.glossaire import Entree  # noqa: E402
from traducteur.langues import AR, FR, cle_souple, cles_de_recherche  # noqa: E402
from traducteur.segmentation import segmenter_en_phrases  # noqa: E402
from traducteur.surlignage import VERBE, motif_du_terme, nature_du_terme  # noqa: E402
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


#: Codes d'un nom : genre français, nature du terme arabe, « p » si le terme français est un pluriel.
_CODES_D_UN_NOM = regex.compile(r"[mf][mfaic]p?")
#: Autres natures de mots, admises dans les termes seuls : code -> (catégorie d'un mot, catégorie d'une locution),
#: en français puis en arabe. L'application ne remplace pas ces mots dans la traduction d'un texte.
AUTRES_NATURES = {
    "adj": (("adjectif", "locution adjectivale"), ("صفة", "عبارة وصفية")),
    "v": (("verbe", "locution verbale"), ("فعل", "عبارة فعلية")),
    "adv": (("adverbe", "locution adverbiale"), ("ظرف", "شبه جملة")),
    "prep": (("préposition", "locution prépositive"), ("شبه جملة", "شبه جملة")),
    "conj": (("conjonction", "locution conjonctive"), ("أداة ربط", "عبارة ربط")),
}
#: Mots courants du français et de l'arabe : un nom d'un seul mot ne doit pas se confondre avec l'un d'eux,
#: car la traduction d'un texte le remplacerait partout (« or » : le métal, ou la conjonction ?).
_MOTS_COURANTS_FR = (
    "a à au aux avec car ce ces cet cette comme dans de des dès donc du elle elles en entre est et eux il ils "
    "la là le les leur leurs lui ma mais me mes mon ne ni non nos notre nous on or ou où par pas plus pour "
    "que qui sa sans se ses si son sous sur ta te tes ton tous tout toute toutes très un une vers vos votre "
    "vous y été être avoir fait faire dit soit peut doit sont ont même autre autres après avant depuis lors "
    "alors ainsi aussi bien peu trop pendant selon contre envers hors près chez ici dont quand puis car "
    "cela ceci celui celle ceux celles chaque aucun aucune quel quelle tel telle dû sûr")
_MOTS_COURANTS_AR = (
    "على في من إلى عن مع أو أن إن كان كانت هذا هذه قبل بعد عند بين حتى كل غير ذلك تلك التي الذي الذين ما لا "
    "لم لن قد هو هي هم أي أية ثم حيث إذا إذ لدى ضد دون خلال منذ نحو ضمن حسب وفق أمام خلف فوق تحت بدون مثل "
    "نفس بعض جميع كما لكن بل أما إما سواء فقط أيضا جدا له لها به بها فيه فيها منه منها عليه عليها إليه "
    "يكون تكون ليس هناك هنا إلا لو هل كيف متى أين أنه أنها بأن لأن حين عندما بينما كذلك أكثر أقل آخر أخرى "
    "أول واحد أحد يجب يجوز يمكن تم يتم")
_MOTS_COURANTS = {langue: frozenset(cle_souple(mot) for mot in mots.split())
                  for langue, mots in ((FR, _MOTS_COURANTS_FR), (AR, _MOTS_COURANTS_AR))}


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


def lieu_du_synonyme(entree: dict, synonyme: str) -> tuple[str, int]:
    """Fichier et ligne où un synonyme est écrit : le lot ou le fichier de termes, ou le fichier de définitions."""
    return entree.get("origine_des_synonymes", {}).get(cle_souple(synonyme), (entree["lot"], entree["numero"]))


def lire_les_lots(erreurs: Erreurs, dossier: pathlib.Path | None = None, seuls: bool = False) -> list[dict]:
    """Lit les lots du dossier ``lots/`` ou, avec ``seuls``, les termes seuls du dossier ``termes/``."""
    dossier = dossier or (TERMES if seuls else LOTS)
    entrees: list[dict] = []
    groupe = 0
    for lot in sorted(dossier.glob("*.txt")):
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
            if seuls:
                # Terme seul : terme, équivalent, codes ; puis le pluriel arabe et les options, s'il y en a.
                if len(champs) < 3:
                    erreurs.signaler(lot.name, numero, f"{len(champs)} champs au lieu de 3 au moins : {ligne[:60]}")
                    continue
                fr, ar, codes, *options = champs
                pluriel_ar = options.pop(0) if options and "=" not in options[0] else ""
                def_fr = def_ar = ""
            else:
                if len(champs) < 6:
                    erreurs.signaler(lot.name, numero, f"{len(champs)} champs au lieu de 6 : {ligne[:60]}")
                    continue
                fr, ar, codes, pluriel_ar, def_fr, def_ar, *options = champs
            entree = {"lot": lot.name, "numero": numero, "fr": fr, "ar": ar, "codes": codes, "pluriel_ar": pluriel_ar,
                      "def_fr": def_fr, "def_ar": def_ar, "domaine": domaine, "cles": cles,
                      "groupe": (dossier.name, groupe), "seul": seuls, "pf": None, "sf": [], "sa": [], "va": []}
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
    if not (_CODES_D_UN_NOM.fullmatch(codes) or (entree["seul"] and codes in AUTRES_NATURES)):
        signaler(f"codes invalides : {codes}")
        return
    mots = ar.split()
    # Un adjectif, un verbe ou une locution : seule l'écriture est vérifiée ; la nature « x » ne correspond à aucun nom.
    nature = "x" if codes in AUTRES_NATURES else codes[1]
    if nature == "x":
        if entree["pluriel_ar"] or entree["pf"]:
            signaler("un adjectif, un verbe ou une locution n'a pas de pluriel dans le glossaire")
    elif (len(mots) == 1) != (nature in "mf"):
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
    if entree["seul"]:
        if nature != "x":
            for langue, mot in ((FR, fr), (AR, ar)):
                if len(mot.split()) == 1 and cle_souple(mot) in _MOTS_COURANTS[langue]:
                    signaler(f"« {mot} » est aussi un mot courant : la traduction d'un texte le remplacerait partout")
    else:
        verifier_le_texte_de_la_definition(entree, signaler)

    def signaler_le_synonyme(synonyme: str, message: str) -> None:
        # Un synonyme ajouté par un fichier de définitions est signalé à sa ligne dans ce fichier.
        erreurs.signaler(*lieu_du_synonyme(entree, synonyme), f"« {entree['fr']} » : {message} : {synonyme}")

    for synonyme in entree["sa"]:
        if not _TERME_ARABE.fullmatch(synonyme):
            signaler_le_synonyme(synonyme, "synonyme arabe inattendu")
    for synonyme in (*entree["sf"], *entree["va"]):
        if _ARABE.search(synonyme) or "’" in synonyme:
            signaler_le_synonyme(synonyme, "synonyme ou terme associé inattendu")
    # Un synonyme n'est ni le terme lui-même, ni son pluriel, ni un synonyme déjà donné.
    for formes, synonymes in (((fr, pluriel_francais(entree)), entree["sf"]),
                              ((ar, entree["pluriel_ar"]), entree["sa"])):
        vus = {cle_souple(forme) for forme in formes if forme}
        for synonyme in synonymes:
            if cle_souple(synonyme) in vus:
                signaler_le_synonyme(synonyme, "synonyme répété, ou identique au terme")
            vus.add(cle_souple(synonyme))


def verifier_le_texte_de_la_definition(entree: dict, signaler) -> None:
    """Écriture et ponctuation d'une définition, dans les deux langues."""
    texte = entree["def_fr"]
    if not texte or _ARABE.search(texte) or not texte[0].isupper() or not texte.endswith("."):
        signaler("définition française : vide, arabe, sans majuscule ou sans point final")
    if "  " in texte or " ," in texte or " ." in texte:
        signaler("définition française : espace mal placée")
    texte = entree["def_ar"]
    if not texte or _LATIN.search(texte) or not texte.endswith(".") or not _TEXTE_ARABE.fullmatch(texte):
        signaler(f"définition arabe : vide, lettres latines, signe inattendu ou sans point final : {texte}")
    if "  " in texte or " ،" in texte or " ." in texte or "," in texte or ";" in texte:
        signaler("définition arabe : ponctuation ou espace mal placée")


def pluriel_francais(entree: dict) -> str:
    """Pluriel français écrit dans le CSV : celui du lot (pf=), sinon le pluriel calculé, sinon rien."""
    if entree["pf"] == "-" or entree["codes"].endswith("p") or entree["codes"] in AUTRES_NATURES:
        return ""
    if entree["pf"]:
        return entree["pf"]
    return pluriel_fr(entree["fr"]) if entree["pluriel_ar"] else ""


def modele(entree: dict) -> Entree:
    """L'entrée d'un lot ou d'un fichier de termes, telle que l'application la lira : ses formes et sa catégorie."""
    codes_valides = _CODES_D_UN_NOM.fullmatch(entree["codes"]) or entree["codes"] in AUTRES_NATURES
    return Entree(numero=0, terme_fr=entree["fr"], terme_ar=entree["ar"], pluriel_ar=entree["pluriel_ar"],
                  pluriel_fr=pluriel_francais(entree), categorie_fr=categories(entree)[0] if codes_valides else "")


def lire_les_exemples(entrees: list[dict], erreurs: Erreurs) -> None:
    """Lit les fichiers d'exemples et range chaque phrase dans son entrée (clé « exemple »).

    Un fichier d'exemples porte le nom du lot ou du fichier de termes seuls qu'il illustre. Les phrases d'un
    fichier de termes seuls ne vont qu'aux termes de ce fichier : « en vigueur » est un adjectif dans un fichier
    et un adverbe dans un autre. Les phrases d'un lot vont aux entrées des lots, comme avant la version 0.11.
    """
    par_terme: dict[str, list[dict]] = collections.defaultdict(list)
    for entree in entrees:
        par_terme[cle_souple(entree["fr"])].append(entree)
    fichiers_de_termes = {entree["lot"] for entree in entrees if entree["seul"]}
    for fichier in sorted(EXEMPLES.glob("*.txt")):
        de_termes = fichier.name in fichiers_de_termes
        origine = f"de termes/{fichier.name}" if de_termes else "des lots"
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
            candidates = [entree for entree in par_terme.get(cle_souple(fr), [])
                          if (entree["lot"] == fichier.name if de_termes else not entree["seul"])]
            if ar:
                candidates = [entree for entree in candidates if cle_souple(entree["ar"]) == cle_souple(ar)]
            if not candidates:
                erreurs.signaler(fichier.name, numero, f"exemple d'un terme absent {origine} : {cle}")
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
    # en évidence (terme ou pluriel ; en arabe, article, particules collées et terminaisons courantes ; un
    # adjectif accordé, un verbe au passé).
    lue = modele(entree)
    for langue, nom, phrase in ((FR, "française", phrase_fr), (AR, "arabe", phrase_ar)):
        motif = motif_du_terme(lue, langue)
        if motif is None or not motif.search(phrase):
            signaler(f"la phrase {nom} ne contient pas « {lue.terme(langue)} » : {phrase}")


def lire_les_definitions(entrees: list[dict], erreurs: Erreurs) -> None:
    """Lit les fichiers de définitions des termes seuls : la définition et les synonymes de chaque terme.

    Un fichier de définitions porte le nom du fichier de termes seuls qu'il complète, et ne définit que les
    termes de ce fichier. La définition remplit les clés « def_fr » et « def_ar » de l'entrée ; les synonymes
    s'ajoutent à ceux que donne le fichier de termes.
    """
    if not DEFINITIONS.is_dir():
        return
    par_terme: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for entree in entrees:
        if entree["seul"]:
            par_terme[entree["lot"], cle_souple(entree["fr"])].append(entree)
    fichiers_de_termes = {entree["lot"] for entree in entrees if entree["seul"]}
    for fichier in sorted(DEFINITIONS.glob("*.txt")):
        # Le fichier porte le nom d'un fichier de termes : les erreurs le nomment avec son dossier.
        nom_du_fichier = f"{DEFINITIONS.name}/{fichier.name}"
        if fichier.name not in fichiers_de_termes:
            erreurs.signaler(nom_du_fichier, 0, "aucun fichier de termes seuls ne porte ce nom")
            continue
        for numero, ligne in enumerate(fichier.read_text(encoding="utf-8").splitlines(), 1):
            ligne = unicodedata.normalize("NFC", ligne.strip())
            if not ligne or ligne.startswith("#"):
                continue
            champs = [champ.strip() for champ in ligne.split(" | ")]
            if len(champs) < 3:
                erreurs.signaler(nom_du_fichier, numero, f"{len(champs)} champs au lieu de 3 au moins : {ligne[:60]}")
                continue
            cle, def_fr, def_ar, *options = champs
            fr, _, ar = (morceau.strip() for morceau in cle.partition(" = "))
            candidates = par_terme.get((fichier.name, cle_souple(fr)), [])
            if ar:
                candidates = [entree for entree in candidates if cle_souple(entree["ar"]) == cle_souple(ar)]
            if not candidates:
                erreurs.signaler(nom_du_fichier, numero,
                                 f"définition d'un terme absent de {TERMES.name}/{fichier.name} : {cle}")
                continue
            if len(candidates) > 1:
                choix = " ou ".join(f"« {fr} = {entree['ar']} »" for entree in candidates)
                erreurs.signaler(nom_du_fichier, numero, f"« {fr} » désigne plusieurs entrées : écrire {choix}")
                continue
            entree = candidates[0]
            if "origine_definition" in entree:
                erreurs.signaler(nom_du_fichier, numero, f"« {cle} » a déjà une définition")
                continue
            entree["def_fr"], entree["def_ar"] = def_fr, def_ar
            entree["origine_definition"] = f"{nom_du_fichier}:{numero}"
            for option in options:
                nom, egal, valeur = option.partition("=")
                if nom == "homographe" and valeur.strip() in (FR, AR):
                    entree.setdefault("homographes", set()).add(valeur.strip())
                    continue
                if not egal or nom not in ("sf", "sa"):
                    erreurs.signaler(nom_du_fichier, numero, f"option inconnue : {option[:40]}")
                    continue
                separateur = "،" if nom == "sa" else ","
                ajoutes = [synonyme.strip() for synonyme in valeur.split(separateur) if synonyme.strip()]
                entree[nom] = [*entree[nom], *ajoutes]
                for synonyme in ajoutes:
                    entree.setdefault("origine_des_synonymes", {})[cle_souple(synonyme)] = (nom_du_fichier, numero)


def verifier_la_definition(entree: dict, erreurs: Erreurs) -> None:
    """La définition d'un terme seul : écriture, longueur, et absence du terme lui-même dans les deux langues."""
    fichier, _, numero = entree["origine_definition"].partition(":")

    def signaler(message: str) -> None:
        erreurs.signaler(fichier, int(numero), f"« {entree['fr']} » : {message}")

    verifier_le_texte_de_la_definition(entree, signaler)
    def_fr, def_ar = entree["def_fr"], entree["def_ar"]
    if "|" in def_fr or "’" in def_fr or "ـ" in def_ar:
        signaler("définition : barre verticale, apostrophe courbe ou trait d'allongement")
    for langue, texte in (("française", def_fr), ("arabe", def_ar)):
        if len(texte) > LONGUEUR_DEFINITION:
            signaler(f"définition {langue} trop longue : {len(texte)} caractères (maximum {LONGUEUR_DEFINITION})")
    # Une définition ne reprend pas le mot qu'elle définit. Le terme y est cherché avec la règle de l'application :
    # un adjectif accordé, un verbe au participe passé et un nom au pluriel comptent aussi.
    lue = modele(entree)
    for langue, nom, texte in ((FR, "française", def_fr), (AR, "arabe", def_ar)):
        motif = motif_du_terme(lue, langue)
        contient = motif is not None and motif.search(texte) is not None
        if contient and langue not in entree.get("homographes", ()):
            signaler(f"la définition {nom} contient le terme « {lue.terme(langue)} » : {texte}")
        elif not contient and langue in entree.get("homographes", ()):
            signaler(f"option homographe={langue} inutile : la définition {nom} ne contient pas le terme")


def motif_du_present(verbe_arabe: str) -> regex.Pattern | None:
    """Motif du présent d'un verbe arabe écrit au passé : « منح » dans « يمنحها », « أبرم » dans « يبرم ».

    Sert à relire les définitions, qui sont au présent (« حماية يمنحها القانون ») alors que le glossaire écrit le
    verbe au passé. La règle est courte : préfixe du présent, « أ » initial retiré (« ألغى », « يلغي »), voyelle
    longue changée (« أجاز », « يجيز »), « و » initial tombé (« وقع », « يقع »). Elle ne connaît pas les autres
    verbes irréguliers ; la suite d'une locution verbale n'est pas cherchée.
    """
    premier = verbe_arabe.split()[0] if verbe_arabe.split() else ""
    if len(premier) < 2:
        return None
    radical = premier[1:] if premier[0] in "أإاآ" and len(premier) >= 4 else premier
    morceaux = []
    for rang, lettre in enumerate(radical):
        dernier = rang == len(radical) - 1
        if rang == 0 and lettre == "و" and len(radical) == 3:
            morceaux.append("و?")
        elif lettre in "اىي" and dernier:
            morceaux.append("[اىيو]?")
        elif lettre == "ا" and rang:
            morceaux.append("[اوي]")
        elif lettre in "أإؤئء":
            morceaux.append("[أإؤئءا]")  # « أنشأ », « ينشئ »
        else:
            morceaux.append(regex.escape(lettre))
    return regex.compile(r"(?<![\p{L}\p{M}\p{N}])[وفلس]{0,2}[يتنأ]" + "".join(morceaux)
                         + r"\p{Arabic}{0,3}(?![\p{L}\p{M}\p{N}])")


def incoherences(anciennes: list[dict], nouvelles: list[dict], des_definitions: bool = False) -> list[str]:
    """Phrases d'exemple où un autre terme du glossaire figure en français, mais pas son équivalent en arabe.

    Ce n'est pas toujours une erreur : un mot peut avoir un autre sens dans la phrase. La liste sert à relire.
    Avec ``des_definitions``, la liste porte sur les définitions des termes seuls, et non sur les phrases.
    """
    # Pour chaque terme du glossaire : le terme français, l'entrée qui sert de modèle, ses synonymes arabes.
    modeles: list[tuple[str, Entree, list[str]]] = []
    for ancienne in anciennes:
        lue = Entree(numero=0, terme_fr=ancienne["terme_fr"], terme_ar=ancienne["terme_ar"],
                     pluriel_fr=ancienne["pluriel_fr"], pluriel_ar=ancienne["pluriel_ar"],
                     categorie_fr=ancienne["categorie_fr"])
        synonymes = [s.strip() for s in ancienne["synonymes_ar"].split("|") if s.strip()]
        modeles.append((ancienne["terme_fr"], lue, synonymes))
    for entree in nouvelles:
        modeles.append((entree["fr"], modele(entree), entree["sa"]))
    motifs = []
    for terme, lue, synonymes in modeles:
        arabes = [motif_du_terme(lue, AR)] + [
            motif_du_terme(Entree(numero=0, terme_fr=terme, terme_ar=synonyme, categorie_fr=lue.categorie_fr), AR)
            for synonyme in synonymes]
        if des_definitions and nature_du_terme(lue) == VERBE:
            # Une définition est au présent : « accordée par la loi », « يمنحها القانون ».
            arabes += [motif_du_present(arabe) for arabe in (lue.terme_ar, *synonymes)]
        motifs.append((terme, lue.terme_ar, motif_du_terme(lue, FR), [m for m in arabes if m is not None]))
    remarques = []
    for entree in nouvelles:
        if des_definitions:
            if "origine_definition" not in entree:
                continue
            phrase_fr, phrase_ar, origine = entree["def_fr"], entree["def_ar"], entree["origine_definition"]
        elif "exemple" in entree:
            (phrase_fr, phrase_ar), origine = entree["exemple"], entree["origine_exemple"]
        else:
            continue
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
            remarques.append(f"{origine} « {entree['fr']} » : {' ; '.join(manques)}\n"
                             f"      {phrase_fr}\n      {phrase_ar}")
    return remarques


def categories(entree: dict) -> tuple[str, str]:
    if entree["codes"] in AUTRES_NATURES:
        francais, arabe = AUTRES_NATURES[entree["codes"]]
        return francais[" " in entree["fr"]], arabe[" " in entree["ar"]]
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


def formes_partagees(anciennes: list[dict], nouvelles: list[dict], erreurs: Erreurs) -> None:
    """Refuse un nom seul dont une forme (terme, pluriel ou synonyme) désigne aussi un autre nom.

    Les formes sont comparées comme le fait l'application : sans accents, sans hamza et sans article. Entre deux
    entrées complètes, l'application choisit d'après leur définition et leur exemple ; un terme seul n'en a pas.

    Un adjectif, un verbe ou une locution peut partager une forme avec une autre entrée : la traduction d'un
    texte ne le remplace pas, elle n'a donc pas à choisir. « عقد » est ainsi le nom « contrat » et le verbe
    « conclure » ; l'écran « Terme » propose les deux fiches.
    """
    porteurs: dict[tuple[str, str], list[tuple[int, str, dict | None, str]]] = collections.defaultdict(list)

    def noter(rang: int, libelle: str, entree: dict | None, langue: str, formes: list[str]) -> None:
        for forme in formes:
            for cle in cles_de_recherche(forme, langue) if forme else ():
                if all(autre != rang for autre, _, _, _ in porteurs[langue, cle]):
                    porteurs[langue, cle].append((rang, libelle, entree, forme))

    for rang, ancienne in enumerate(anciennes):
        libelle = f"{ancienne['terme_fr']} / {ancienne['terme_ar']}"
        for langue, suffixe in ((FR, "fr"), (AR, "ar")):
            noter(rang, libelle, None, langue, [ancienne[f"terme_{suffixe}"], ancienne[f"pluriel_{suffixe}"],
                                                *ancienne[f"synonymes_{suffixe}"].split(" | ")])
    for rang, entree in enumerate(nouvelles, len(anciennes)):
        if entree["codes"] in AUTRES_NATURES:
            continue
        libelle = f"{entree['fr']} / {entree['ar']}"
        seule = entree if entree["seul"] else None
        noter(rang, libelle, seule, FR, [entree["fr"], pluriel_francais(entree), *entree["sf"]])
        noter(rang, libelle, seule, AR, [entree["ar"], entree["pluriel_ar"], *entree["sa"]])
    deja: set[tuple[int, int]] = set()
    for (_, cle), liste in porteurs.items():
        if len(liste) < 2:
            continue
        for rang, _, entree, forme in liste:
            autres = [(autre, libelle) for autre, libelle, _, _ in liste if autre != rang]
            if entree is None or all((min(rang, autre), max(rang, autre)) in deja for autre, _ in autres):
                continue
            deja.update((min(rang, autre), max(rang, autre)) for autre, _ in autres)
            # La forme est le terme, son pluriel ou un synonyme : un synonyme venu d'un fichier de définitions est
            # signalé à sa ligne dans ce fichier.
            erreurs.signaler(*lieu_du_synonyme(entree, forme),
                             f"« {entree['fr']} » : la forme « {cle} » désigne aussi "
                             + " ; ".join(f"« {libelle} »" for _, libelle in autres))


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
    completes = lire_les_lots(erreurs)
    seuls = lire_les_lots(erreurs, seuls=True)
    nouvelles = completes + seuls
    lire_les_definitions(nouvelles, erreurs)
    for entree in nouvelles:
        verifier(entree, erreurs)
    lire_les_exemples(nouvelles, erreurs)
    # Une définition ne sert qu'une fois : deux termes qui auraient la même définition ne seraient pas distingués.
    definitions: dict[tuple[str, str], str] = {}
    for ancienne in anciennes:
        for langue, colonne in ((FR, "definition_fr"), (AR, "definition_ar")):
            if cle_phrase(ancienne[colonne]):
                definitions[langue, cle_phrase(ancienne[colonne])] = ancienne["terme_fr"]
    for entree in nouvelles:
        if "origine_definition" in entree:
            verifier_la_definition(entree, erreurs)
        if not entree["def_fr"]:
            continue
        for langue, texte in ((FR, entree["def_fr"]), (AR, entree["def_ar"])):
            cle = (langue, cle_phrase(texte))
            if cle in definitions and "origine_definition" in entree:
                fichier, ligne = entree["origine_definition"].split(":")[:2]
                erreurs.signaler(fichier, int(ligne), f"même définition que « {definitions[cle]} » : {texte}")
            definitions.setdefault(cle, entree["fr"])
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

    formes_partagees(anciennes, nouvelles, erreurs)

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
        if _CODES_D_UN_NOM.fullmatch(entree["codes"]) or entree["codes"] in AUTRES_NATURES:
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
            "source_definition": (SOURCE if not entree["seul"]
                                  else SOURCE_SEUL_DEFINI if entree["def_fr"] else SOURCE_SEUL),
            "contexte_fr": phrase_fr.replace("'", "’"), "contexte_ar": phrase_ar,
            "source_contexte": SOURCE_EXEMPLE if phrase_fr else "",
            "ressources": " | ".join(ressources),
        }
        ecrivain.writerow([valeurs[colonne] for colonne in colonnes])

    total = len(anciennes) + len(nouvelles)
    print(f"{len(anciennes)} entrées d'origine + {len(completes)} entrées des lots + {len(seuls)} termes seuls "
          f"= {total} (objectif {OBJECTIF}, reste {OBJECTIF - total})")
    sans_exemple = [entree for entree in nouvelles if "exemple" not in entree]
    manquent = collections.Counter(entree["seul"] for entree in sans_exemple)
    print(f"phrases d'exemple : {len(completes) - manquent[False]} sur {len(completes)} entrées des lots"
          + (f", {len(seuls) - manquent[True]} sur {len(seuls)} termes seuls" if seuls else "")
          + (f" ; il en manque {len(sans_exemple)} (--manquants pour la liste)" if sans_exemple else ""))
    natures = collections.Counter(categories(entree)[0].split()[0] if entree["codes"] in AUTRES_NATURES else "nom"
                                  for entree in seuls if _CODES_D_UN_NOM.fullmatch(entree["codes"])
                                  or entree["codes"] in AUTRES_NATURES)
    if seuls:
        print("termes seuls : " + ", ".join(f"{nombre} × {nature}" for nature, nombre in natures.most_common())
              + f" ; {sum(1 for entree in seuls if entree['pluriel_ar'])} avec un pluriel arabe")
        sans_definition = [entree for entree in seuls if not entree["def_fr"]]
        print(f"définitions : {len(seuls) - len(sans_definition)} sur {len(seuls)} termes seuls"
              + (f" ; il en manque {len(sans_definition)} (--manquants pour la liste)" if sans_definition else ""))
        print(f"termes seuls avec des synonymes : {sum(1 for entree in seuls if entree['sf'])} en français, "
              f"{sum(1 for entree in seuls if entree['sa'])} en arabe")
    if "--coherence" in sys.argv:
        remarques = incoherences(anciennes, nouvelles)
        print(f"\n{len(remarques)} phrase(s) à relire (terme français sans son équivalent arabe) :")
        print("\n".join(remarques))
    if "--coherence-definitions" in sys.argv:
        remarques = incoherences(anciennes, nouvelles, des_definitions=True)
        print(f"\n{len(remarques)} définition(s) à relire (terme français sans son équivalent arabe) :")
        print("\n".join(remarques))
    if "--manquants" in sys.argv:
        for lot, membres in collections.Counter(entree["lot"] for entree in sans_exemple).items():
            print(f"{membres:4d}  {lot}")
        if seuls:
            print("termes seuls sans définition :")
            for lot, membres in collections.Counter(entree["lot"] for entree in sans_definition).items():
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
        print()
        for lot, nombre in collections.Counter(e["lot"] for e in nouvelles).items():
            print(f"{nombre:4d}  {lot}")
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
        print(f"\nLe fichier CSV diffère des lots, des exemples et des définitions : {differentes} ligne(s). "
              f"L'option --ecrire le récrit ;\nune correction faite à la main dans le CSV après la "
              f"{ENTREES_D_ORIGINE}e entrée serait alors perdue.")
    else:
        print("Le fichier CSV correspond aux lots, aux exemples et aux définitions.")
    return 0


if __name__ == "__main__":
    sys.exit(construire())
