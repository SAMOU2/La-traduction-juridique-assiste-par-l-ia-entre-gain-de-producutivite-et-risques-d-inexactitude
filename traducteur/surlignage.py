"""Repérage d'un terme du glossaire dans une phrase d'exemple.

Sert à mettre le terme en évidence dans le champ « Contextualisation », et à chercher dans le glossaire les
phrases qui emploient un terme. Le repérage est volontairement large, car la phrase appartient déjà à l'entrée :

* en français, on accepte le terme, son pluriel et un « s » final ;
* en arabe, on accepte les particules collées au mot (و، ف، ب، ل، ك), l'article
  (ال، لل), les terminaisons courantes (duel, pluriel, pronoms) et les
  variantes d'écriture de la hamza : « عقد » est repéré dans « العقد » et
  « طرف » dans « الطرفان ».

Un mot qui n'est pas un nom change de forme dans une phrase. La catégorie de l'entrée dit comment :

* un adjectif s'accorde : « protégé » est repéré dans « protégées », « محمي » dans « المحمية » ;
* un verbe est écrit à l'infinitif en français et au passé en arabe. Il est repéré à l'infinitif et au participe
  passé (« abroger » dans « a abrogé »), et en arabe au passé, au masculin comme au féminin (« نشر » dans
  « نشرت »). Dans une locution verbale, quelques mots peuvent séparer le verbe de la suite : « mettre en
  demeure » dans « a mis le débiteur en demeure », « رفع دعوى » dans « رفع المدعي دعوى » ;
* une locution qui finit par « à », « de » ou « que » se contracte avec le mot qui suit (« conformément au »,
  « en vertu du », « à moins qu'il ») ; en arabe, une particule d'une lettre se colle au mot qui suit
  (« طبقا ل » dans « طبقا للقانون »).
"""

from __future__ import annotations

import regex

from .glossaire import Entree
from .langues import AR, FR, TANWIN_KASRA, cle_stricte

#: Natures d'un terme, lues dans sa catégorie grammaticale française. Une entrée sans catégorie est un nom.
NOM, ADJECTIF, VERBE, INVARIABLE = "nom", "adjectif", "verbe", "invariable"
# Les mêmes catégories que ``traducteur.traduction.se_remplace_dans_un_texte`` : un nom est remplacé dans la
# traduction d'un texte, les autres mots ne le sont pas.
_NATURE_DE_NOM = regex.compile(r"\bnom|\bsubst|\bn\b|\bn[mf]\b")
_AUTRES_NATURES = (
    (ADJECTIF, regex.compile(r"\b(?:adjecti|particip)|\badj\b")),
    (VERBE, regex.compile(r"\bverb|\bv\b")),
    (INVARIABLE, regex.compile(r"\b(?:adverb|pr[ée]positi|conjoncti)|\b(?:adv|pr[ée]p|conj)\b")),
)

_DIACRITIQUES = r"[\u064B-\u065F\u0670\u0640]*"
_PARTICULES = r"[وفبلك]{0,2}"
_ARTICLE = r"(?:ال|لل)?"
_TERMINAISONS = r"(?:ا|ان|ين|ون|ات|ي|ه|ها|هم|هما|هن|نا|كم)?"
#: Terminaisons d'un adjectif arabe : féminin, duel, pluriel, cas direct, pronom ; « صافٍ » fait « صافية ».
_ACCORDS = r"(?:ة|ا|ات|ان|ين|ون|تان|تين|ي|ية|يا|ه|ها|هم|هما|هن)?"
_LIMITE_GAUCHE = r"(?<![\p{L}\p{M}\p{N}])"
_LIMITE_DROITE = r"(?![\p{L}\p{M}\p{N}])"
#: Mots qui peuvent séparer le verbe d'une locution verbale de sa suite : trois au plus, sans ponctuation.
_ECART = {FR: r"(?P<ecart>(?:\s+[^\s.,;:!?()«»]+){0,3}?)", AR: r"(?P<ecart>(?:\s+[\p{L}\p{M}]+){0,3}?)"}
_CLASSES_ARABES = {
    **dict.fromkeys("أإؤئء", "[أإؤئءا]"),
    **dict.fromkeys("اآٱ", "[اأإآٱ]"),
    **dict.fromkeys("يى", "[يى]"),
    **dict.fromkeys("ةه", "[ةهت]"),
}
#: « ذو أهلية » : le premier mot change avec le cas, le genre et le nombre.
_POSSESSEURS = "(?:ذو|ذا|ذي|ذات|ذوو|ذوي)"

# ------------------------------------------------------------------ français
#: Dernier mot d'une locution, et les formes qu'il prend devant le mot qui suit (« en vertu du », « à moins qu'il »).
_CONTRACTIONS = {
    "de": rf"(?:(?:de|du|des){_LIMITE_DROITE}|d['’])",
    "à": rf"(?:à|au|aux){_LIMITE_DROITE}",
    "que": rf"(?:que{_LIMITE_DROITE}|qu['’])",
}
#: Mots d'une locution adjectivale qui ne s'accordent pas (« susceptible d'appel », « non bâti »).
_MOTS_FIGES = frozenset({"à", "au", "aux", "de", "du", "des", "en", "par", "pour", "sous", "sur", "sans", "non", "et",
                         "ou", "la", "le", "les", "ci-après", "quasi"})
#: Féminin d'un adjectif d'après sa terminaison, de la plus précise à la plus générale. Sinon : un « e » de plus.
_FEMININS = (
    ("teur", ("trice", "teuse")), ("ieur", ("ieure",)), ("majeur", ("majeure",)), ("mineur", ("mineure",)),
    ("meilleur", ("meilleure",)), ("eur", ("euse",)), ("eux", ("euse",)), ("el", ("elle",)), ("eil", ("eille",)),
    ("nul", ("nulle",)), ("éen", ("éenne",)), ("ien", ("ienne",)), ("on", ("onne",)), ("er", ("ère",)),
    ("bref", ("brève",)), ("if", ("ive",)), ("f", ("ve",)), ("et", ("ette", "ète")), ("gu", ("guë", "güe")),
    ("ong", ("ongue",)), ("c", ("que",)), ("ès", ("esse",)), ("s", ("se", "sse")), ("û", ("ue",)),
)
#: Participes passés qui ne suivent aucune des terminaisons ci-dessous.
_PARTICIPES = {
    "être": "été", "avoir": "eu", "naître": "né", "mourir": "mort", "nuire": "nui", "luire": "lui",
    "suffire": "suffi", "rire": "ri", "sourire": "souri", "devoir": "dû", "pouvoir": "pu", "savoir": "su",
    "vouloir": "voulu", "valoir": "valu", "prévaloir": "prévalu", "falloir": "fallu", "boire": "bu",
    "croire": "cru", "lire": "lu", "élire": "élu", "réélire": "réélu", "relire": "relu", "plaire": "plu",
    "déplaire": "déplu", "taire": "tu", "vivre": "vécu", "survivre": "survécu", "résoudre": "résolu",
    "coudre": "cousu", "clore": "clos", "asseoir": "assis", "surseoir": "sursis", "échoir": "échu",
    "déchoir": "déchu", "inclure": "inclus", "fuir": "fui",
}
#: Terminaisons de l'infinitif et du participe passé, de la plus précise à la plus générale.
_TERMINAISONS_DU_PARTICIPE = (
    ("prendre", "pris"), ("indre", "int"), ("soudre", "sous"), ("ndre", "ndu"), ("rdre", "rdu"),
    ("mettre", "mis"), ("battre", "battu"), ("ompre", "ompu"), ("vaincre", "vaincu"), ("clure", "clu"),
    ("aître", "u"), ("uire", "uit"), ("crire", "crit"), ("dire", "dit"), ("faire", "fait"), ("traire", "trait"),
    ("suivre", "suivi"), ("quérir", "quis"), ("venir", "venu"), ("tenir", "tenu"), ("courir", "couru"),
    ("vrir", "vert"), ("frir", "fert"), ("cevoir", "çu"), ("mouvoir", "mu"), ("voir", "vu"),
    ("er", "é"), ("ir", "i"), ("re", "u"),
)


def nature_du_terme(entree: Entree) -> str:
    """Nature du terme d'une entrée : ``NOM``, ``ADJECTIF``, ``VERBE`` ou ``INVARIABLE``."""
    categorie = entree.categorie_fr.casefold()
    if _NATURE_DE_NOM.search(categorie):
        return NOM
    return next((nature for nature, motif in _AUTRES_NATURES if motif.search(categorie)), NOM)


def participe_passe(infinitif: str) -> str | None:
    """Participe passé d'un verbe français (« permettre » : « permis ») ; ``None`` si ce n'est pas un infinitif."""
    verbe = infinitif.casefold()
    if verbe in _PARTICIPES:
        return _PARTICIPES[verbe]
    for fin, participe in _TERMINAISONS_DU_PARTICIPE:
        if verbe.endswith(fin) and len(verbe) > len(fin):
            return verbe[:-len(fin)] + participe
        if verbe == fin and len(fin) > 2:  # « faire », « prendre », « mettre », « voir »
            return participe
    return None


def accords(adjectif: str) -> list[str]:
    """Formes d'un adjectif français : masculin, féminin et leurs pluriels (« légal », « légale », « légaux »…)."""
    mot = adjectif.casefold()
    if mot.endswith("e"):
        feminins = [mot]
    else:
        feminins = next(([mot[:-len(fin)] + feminin for feminin in fins] for fin, fins in _FEMININS
                         if mot.endswith(fin)), [mot + "e"])
    if mot.endswith(("s", "x")):
        pluriels = [mot]
    elif mot.endswith("al"):
        pluriels = [mot[:-2] + "aux", mot + "s"]
    elif mot.endswith("û"):
        pluriels = [mot[:-1] + "us"]
    else:
        pluriels = [mot + ("x" if mot.endswith("eau") else "s")]
    return list(dict.fromkeys([mot, *feminins, *pluriels, *(feminin + "s" for feminin in feminins)]))


def _litteral(texte: str) -> str:
    """Un mot français rendu en expression : l'apostrophe et le trait d'union s'écrivent de plusieurs façons."""
    morceaux = []
    for caractere in texte:
        if caractere in "'’":
            morceaux.append("['’]")
        elif caractere in "-‑":
            morceaux.append("[-‑]")
        else:
            morceaux.append(regex.escape(caractere))
    return "".join(morceaux)


def _choix(formes: list[str]) -> str:
    """Expression qui accepte une des formes, la plus longue d'abord."""
    formes = sorted(dict.fromkeys(formes), key=len, reverse=True)
    return _litteral(formes[0]) if len(formes) == 1 else "(?:" + "|".join(map(_litteral, formes)) + ")"


def _suite_francaise(mots: list[str], nature: str) -> str:
    """Les mots d'un terme français, jusqu'à la limite de droite ; le dernier se contracte ou s'accorde."""
    morceaux = []
    for rang, mot in enumerate(mots):
        dernier, minuscules = rang == len(mots) - 1, mot.casefold()
        contracte = dernier and minuscules in _CONTRACTIONS
        fige = minuscules in _MOTS_FIGES or "'" in mot or "’" in mot
        # Dans une locution adjectivale, chaque mot peut s'accorder (« certifiées conformes »).
        morceau = _choix(accords(mot)) if nature == ADJECTIF and not fige and not contracte else _litteral(mot)
        if not dernier:
            morceaux.append(morceau)
        elif contracte:
            morceaux.append(_CONTRACTIONS[minuscules])
        elif minuscules.endswith(("'à", "’à")):  # « jusqu'à » : « jusqu'au », « jusqu'aux »
            morceaux.append(_litteral(mot[:-1]) + _CONTRACTIONS["à"])
        else:
            # Un nom prend un « s » ; un adjectif est déjà accordé, un verbe et une locution ne changent pas.
            morceaux.append(morceau + ("s?" if nature == NOM else "") + _LIMITE_DROITE)
    return r"\s+".join(morceaux)


def _verbe_francais(mots: list[str]) -> str:
    """Un verbe ou une locution verbale : l'infinitif ou le participe passé, puis la suite de la locution."""
    pronom = ""
    if mots[0].casefold() == "se" and len(mots) > 1:
        mots = mots[1:]
        pronom = "se"
    elif mots[0].casefold().startswith(("s'", "s’")) and len(mots[0]) > 2:
        mots = [mots[0][2:], *mots[1:]]
        pronom = "se"
    verbe, suite = mots[0], mots[1:]
    formes = _litteral(verbe)
    participe = participe_passe(verbe)
    if participe:
        formes = f"(?:{formes}|{_litteral(participe)}(?:e|s|es)?)"
    if pronom:
        # « s'engager », « s'est engagé », « se sont engagés », « ne s'est pas engagé ».
        formes = r"(?:se\s+|s['’])(?:\p{L}+\s+){0,2}?" + formes
    if not suite:
        return formes + _LIMITE_DROITE
    return f"(?P<verbe>{formes}){_ECART[FR]}\\s+(?P<suite>{_suite_francaise(suite, VERBE)})"


def _motif_francais(forme: str, nature: str = NOM) -> str:
    mots = forme.split()
    if not mots:
        return ""
    return _verbe_francais(mots) if nature == VERBE else _suite_francaise(mots, nature)


# ------------------------------------------------------------------ arabe
def _lettres_arabes(mot: str) -> str:
    return _DIACRITIQUES.join(_CLASSES_ARABES.get(lettre, regex.escape(lettre)) for lettre in mot)


def _mot_arabe(mot: str) -> str:
    """Un mot arabe, avec ou sans article."""
    variantes = [_lettres_arabes(mot)]
    if mot.startswith("ال") and len(mot) >= 4:
        # « ال » est le plus souvent l'article (القانون), mais il peut aussi
        # appartenir au mot (التزام) : on accepte les deux lectures.
        variantes.append(_lettres_arabes(mot[2:]))
    return _ARTICLE + "(?:" + "|".join(variantes) + ")"


def _mots_arabes(forme: str) -> list[tuple[str, bool]]:
    """Les mots d'une forme arabe, sans signes ; pour chacun, vrai s'il s'écrit avec un tanwin kasra (« مرقٍ »)."""
    mots = [(cle_stricte(mot), mot.endswith(TANWIN_KASRA)) for mot in forme.split()]
    return [(mot, defectueux) for mot, defectueux in mots if mot]


def _suite_arabe(mots: list[tuple[str, bool]], nature: str, apres_un_mot: bool = False) -> str:
    """Les mots d'un terme arabe, jusqu'à la limite de droite ; une particule finale se colle au mot qui suit.

    ``apres_un_mot`` : ces mots suivent le verbe d'une locution, le premier n'est donc pas le début du terme.
    """
    morceaux = []
    for rang, (mot, defectueux) in enumerate(mots):
        dernier = rang == len(mots) - 1
        if dernier and len(mot) == 1 and (rang or apres_un_mot):
            # « طبقا ل », « أخل ب » : la particule et le mot qui la porte (« للقانون », « بالتزامه »).
            morceaux.append(_lettres_arabes(mot) + r"[\p{L}\p{M}]+")
        elif nature == ADJECTIF:
            morceau = _POSSESSEURS if mot == "ذو" else _mot_arabe(mot)
            morceaux.append(morceau + _DIACRITIQUES + _ACCORDS + _DIACRITIQUES + (_LIMITE_DROITE if dernier else ""))
        elif dernier:
            morceaux.append(_mot_arabe(mot) + _DIACRITIQUES + _TERMINAISONS + _DIACRITIQUES + _LIMITE_DROITE)
        elif nature == NOM:
            # Un mot qui n'est pas le dernier : le « ي » d'un nom défectueux qui porte l'article (« المرقي
            # العقاري »), ou l'alif du cas direct (« تدبيرا مؤقتا »).
            morceaux.append(_mot_arabe(mot) + _DIACRITIQUES + ("(?:ي|يا)?" if defectueux else "ا?") + _DIACRITIQUES)
        else:
            morceaux.append(_mot_arabe(mot))
    return r"\s+".join(morceaux)


def _verbe_arabe(mots: list[tuple[str, bool]]) -> str:
    """Un verbe au passé, masculin ou féminin (« نشر », « نشرت » ; « ألغى », « ألغت »), puis la suite de la locution."""
    verbe, suite = mots[0][0], mots[1:]
    if len(verbe) > 2 and verbe[-1] in "ىا":
        # La lettre faible finale tombe devant la marque du féminin.
        formes = _lettres_arabes(verbe[:-1]) + _DIACRITIQUES + "(?:" + _lettres_arabes(verbe[-1]) + "|ت)"
    else:
        formes = _lettres_arabes(verbe) + _DIACRITIQUES + "ت?"
    formes += _DIACRITIQUES
    if not suite:
        return formes + _TERMINAISONS + _DIACRITIQUES + _LIMITE_DROITE
    return f"(?P<verbe>{formes}){_ECART[AR]}\\s+(?P<suite>{_suite_arabe(suite, VERBE, apres_un_mot=True)})"


def _motif_arabe(forme: str, nature: str = NOM) -> str:
    mots = _mots_arabes(forme)
    if not mots:
        return ""
    return _PARTICULES + (_verbe_arabe(mots) if nature == VERBE else _suite_arabe(mots, nature))


# ------------------------------------------------------------------ repérage
def motif_du_terme(entree: Entree, langue: str) -> regex.Pattern | None:
    """Expression qui repère le terme de ``entree`` (ou son pluriel) dans une phrase ; ``None`` sans terme."""
    construire = _motif_arabe if langue == AR else _motif_francais
    nature = nature_du_terme(entree)
    formes = sorted(entree.formes(langue), key=len, reverse=True)
    motifs = [motif for motif in (construire(forme, nature) for forme in formes) if motif]
    if not motifs:
        return None
    return regex.compile(_LIMITE_GAUCHE + "(?:" + "|".join(motifs) + ")", regex.IGNORECASE)


def positions_du_terme(phrase: str, entree: Entree, langue: str) -> list[tuple[int, int]]:
    """Positions (début, fin) des occurrences du terme de ``entree`` dans ``phrase``.

    Une locution verbale dont le verbe est séparé de la suite donne deux passages : le verbe, puis la suite.
    """
    expression = motif_du_terme(entree, langue)
    if expression is None:
        return []
    positions: list[tuple[int, int]] = []
    for trouve in expression.finditer(phrase):
        if trouve.groupdict().get("ecart"):
            # Le premier passage part du début du mot : en arabe, une particule peut être collée au verbe.
            positions.extend(((trouve.start(), trouve.end("verbe")), trouve.span("suite")))
        else:
            positions.append(trouve.span())
    return positions
