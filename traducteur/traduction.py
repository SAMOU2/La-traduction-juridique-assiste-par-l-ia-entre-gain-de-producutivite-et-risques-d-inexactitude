"""Traduction d'un texte à l'aide du glossaire (écran « Traduction d'un texte »).

L'algorithme suit cinq étapes :

1. segmentation du texte en phrases ;
2. découpage de chaque phrase en mots ;
3. recherche dans le glossaire : la phrase entière parmi les exemples, puis
   les expressions les plus longues, puis les mots un par un ;
4. application des règles lexicales, grammaticales et sémantiques (voir
   ``REGLES``) ;
5. reconstruction du texte dans la langue cible, phrase par phrase.

Le résultat est une aide à la traduction, pas une traduction achevée : les
mots absents du glossaire restent écrits dans la langue source et l'ordre des
mots n'est pas modifié. Seules les phrases reprises d'un exemple du glossaire
sont des traductions complètes.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field

import regex

from .glossaire import Contexte, Entree, Glossaire
from .langues import (
    AR,
    FR,
    LANGUES,
    TANWIN_KASRA,
    autre_langue,
    cle_souple,
    cle_stricte,
    memes_accents,
    porte_des_accents,
    sans_article_arabe,
    sans_article_francais,
)
from .segmentation import PONCTUATION, Jeton, Phrase, compter, decouper_en_mots, segmenter_en_phrases
from .surlignage import positions_du_terme

# Natures des morceaux du texte traduit.
TERME = "terme"  # terme du glossaire, traduit
ATTESTE = "atteste"  # passage d'une phrase reprise d'un exemple du glossaire
SOURCE = "source"  # mot absent du glossaire : il reste dans la langue source
NEUTRE = "neutre"  # espaces, ponctuation, nombres

#: Règles appliquées pendant la traduction : identifiant -> (famille, libellé).
REGLES: dict[str, tuple[str, str]] = {
    "expression": ("lexique", "Expression de plusieurs mots reconnue en entier"),
    "synonyme": ("lexique", "Synonyme ramené au terme du glossaire"),
    "pluriel": ("grammaire", "Accord en nombre : pluriel"),
    "article": ("grammaire", "Article défini"),
    "indefini": ("grammaire", "Article indéfini"),
    "annexion": ("grammaire", "Complément du nom"),
    "possessif": ("grammaire", "Possessif"),
    "particule": ("grammaire", "Particule séparée du mot arabe"),
    "homonyme": ("sémantique", "Choix entre plusieurs équivalents d'après le contexte"),
    "phrase": ("sémantique", "Phrase reprise d'un exemple du glossaire"),
}
FAMILLES = ("lexique", "grammaire", "sémantique")

#: Nombre maximal de mots d'une expression recherchée dans le glossaire.
LONGUEUR_MAXIMALE = 8

_HORS_MOTS = regex.compile(r"[^\p{L}\p{N}]+")
_FINALES = ".!?…؟"
_PONCTUATION = {
    AR: {",": "،", ";": "؛", "?": "؟"},
    FR: {"،": ",", "؛": ";", "؟": "?", "۔": "."},
}
_CHIFFRES_ARABES = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# ------------------------------------------------------------------ français
_ARTICLES_DEFINIS = frozenset({"le", "la", "les", "l'"})
_ARTICLES_INDEFINIS = frozenset({"un", "une"})
_DE = frozenset({"de", "d'"})
#: Mots qui annoncent un nom déterminé (ils restent dans le texte : seul le nom est traduit).
_DETERMINANTS_DEFINIS = frozenset({"au", "aux", "ce", "cet", "cette", "ces"})
_DETERMINANTS_PLURIELS = frozenset({"les", "des", "aux", "ces", "ses", "leurs", "mes", "tes", "nos", "vos",
                                    "plusieurs", "quelques"})
#: Après un de ces mots, le nom est au singulier : « cours » dans « au cours de » n'est pas le pluriel de « cour ».
_DETERMINANTS_SINGULIERS = frozenset({"le", "la", "l'", "un", "une", "au", "du", "ce", "cet", "cette", "mon", "ma",
                                      "ton", "ta", "son", "sa", "notre", "votre", "leur", "chaque", "aucun", "aucune"})
_VOYELLES = frozenset("aàâäeéèêëiîïoôöuùûüyœæ")
#: Mots à « h » aspiré : pas d'élision (« le huis clos », « la hausse »).
_H_ASPIRES = ("hausse", "haut", "hasard", "harcèlement", "handicap", "hiérarchie", "honte", "hors", "huis", "huit",
              "halte", "hameau", "hangar", "héros", "heurt")
_GENRE_FEMININ = regex.compile(r"fémin|\bfém\b|\bn\.?\s?f\b|\bf\b|\bnf\b")
_GENRE_MASCULIN = regex.compile(r"mascul|\bmasc\b|\bn\.?\s?m\b|\bm\b|\bnm\b")

# ------------------------------------------------------------------ arabe
_ARTICLE = "ال"
_PARTICULES_1 = "وفبلك"
#: Mots qui commencent par « ال » sans que ce soit l'article (noms d'action de la forme « افتعال »).
_SANS_ARTICLE = frozenset({"التزام", "التزامات", "التماس", "التحاق", "التقاء", "التفات", "التباس", "التقاط"})
#: Terminaisons d'un mot arabe : (terminaison, nature).
_TERMINAISONS = (("هما", "possessif"), ("هم", "possessif"), ("هن", "possessif"), ("ها", "possessif"),
                 ("نا", "possessif"), ("كم", "possessif"), ("ان", "pluriel"), ("ين", "pluriel"),
                 ("ون", "pluriel"), ("ات", "pluriel"), ("ه", "possessif"), ("ا", "indefini"))
_PERSONNES = {"ه": "3s", "ها": "3s", "هما": "3p", "هم": "3p", "هن": "3p", "نا": "1p", "كم": "2p"}


def _cle_d_amorce(mot: str, langue: str) -> str:
    cle = cle_souple(mot)
    return sans_article_arabe(cle) if langue == AR else cle


def cle_phrase(texte: str) -> str:
    """Clé de comparaison d'une phrase : ses mots seulement, sans ponctuation, accents ni majuscules."""
    return " ".join(_HORS_MOTS.sub(" ", cle_souple(texte)).split())


@dataclass(frozen=True)
class Morceau:
    """Un morceau du texte traduit, avec sa nature (``TERME``, ``ATTESTE``, ``SOURCE`` ou ``NEUTRE``)."""

    texte: str
    nature: str
    entree: Entree | None = None


@dataclass(eq=False)
class Occurrence:
    """Un terme du glossaire relevé dans le texte source."""

    entree: Entree
    #: Toutes les entrées que la forme peut désigner (plusieurs en cas d'homonymes).
    candidats: tuple[Entree, ...]
    phrase: int  # rang de la phrase dans le texte
    premier: int  # rang du premier jeton du terme dans la phrase
    dernier: int  # rang du dernier jeton
    debut: int  # position du terme dans le texte source
    fin: int
    forme: str  # le terme tel qu'il est écrit dans le texte
    nature: str = "terme"  # « terme », « pluriel » ou « synonyme »
    pluriel: bool = False
    defini: bool = False
    indefini: bool = False
    annexe: bool = False  # premier terme d'un complément du nom (« nullité » dans « nullité du contrat »)
    complement: bool = False  # second terme (« contrat » dans « nullité du contrat »)
    particules: tuple[str, ...] = ()  # particules collées au mot arabe : و، ب، ل…
    possessif: str = ""  # pronom collé à la fin du mot arabe : ه، ها، هم…
    incertain: bool = False  # homonymes que le contexte n'a pas permis de départager
    rendu: str = ""  # le terme tel qu'il est écrit dans la traduction
    regles: list[str] = field(default_factory=list)

    @property
    def autres_candidats(self) -> tuple[Entree, ...]:
        return tuple(candidat for candidat in self.candidats if candidat is not self.entree)


@dataclass(eq=False)
class PhraseTraduite:
    """Une phrase du texte source et sa traduction."""

    source: Phrase
    jetons: list[Jeton]
    occurrences: list[Occurrence]
    morceaux: list[Morceau]
    #: Exemple du glossaire dont la phrase est reprise, s'il y en a un.
    attestation: Contexte | None = None
    mots: int = 0
    mots_reconnus: int = 0

    @property
    def texte(self) -> str:
        return "".join(morceau.texte for morceau in self.morceaux)


@dataclass(eq=False)
class TermeDetecte:
    """Une entrée du glossaire relevée dans le texte, avec toutes ses occurrences."""

    entree: Entree
    occurrences: list[Occurrence]

    @property
    def autres_candidats(self) -> tuple[Entree, ...]:
        autres: list[Entree] = []
        for occurrence in self.occurrences:
            autres.extend(candidat for candidat in occurrence.autres_candidats if candidat not in autres)
        return tuple(autres)

    @property
    def incertain(self) -> bool:
        return any(occurrence.incertain for occurrence in self.occurrences)


@dataclass(eq=False)
class Traduction:
    """Résultat de la traduction d'un texte."""

    source: str  # langue source
    cible: str  # langue cible
    texte_source: str
    phrases: list[PhraseTraduite] = field(default_factory=list)
    morceaux: list[Morceau] = field(default_factory=list)
    termes: list[TermeDetecte] = field(default_factory=list)
    mots: int = 0
    mots_reconnus: int = 0
    #: Mots absents du glossaire, dans l'ordre du texte et sans répétition.
    mots_absents: list[str] = field(default_factory=list)
    #: Nombre d'applications de chaque règle (voir ``REGLES``).
    regles: Counter = field(default_factory=Counter)

    @property
    def texte(self) -> str:
        """Le texte traduit."""
        return "".join(morceau.texte for morceau in self.morceaux)

    @property
    def occurrences(self) -> list[Occurrence]:
        return [occurrence for phrase in self.phrases for occurrence in phrase.occurrences]

    @property
    def phrases_attestees(self) -> int:
        """Nombre de phrases reprises d'un exemple du glossaire."""
        return sum(1 for phrase in self.phrases if phrase.attestation is not None)

    @property
    def phrases_a_verifier(self) -> int:
        """Parmi les phrases reprises d'un exemple, celles dont l'exemple porte la mention « à vérifier »."""
        return sum(1 for phrase in self.phrases if phrase.attestation is not None and phrase.attestation.a_verifier)

    @property
    def complete(self) -> bool:
        """Vrai si tous les mots du texte ont été reconnus."""
        return self.mots > 0 and self.mots_reconnus == self.mots

    def decompte_cible(self) -> tuple[int, int, int]:
        """Nombre de phrases, de mots et de caractères du texte traduit."""
        return compter(self.texte)

    def regles_par_famille(self) -> dict[str, list[tuple[str, int]]]:
        """Règles appliquées, rangées par famille : famille -> [(libellé, nombre)]."""
        familles: dict[str, list[tuple[str, int]]] = {famille: [] for famille in FAMILLES}
        for identifiant, (famille, libelle) in REGLES.items():
            if self.regles[identifiant]:
                familles[famille].append((libelle, self.regles[identifiant]))
        return familles


@dataclass
class _Lecture:
    """Façon dont une forme du texte est reconnue dans le glossaire."""

    entrees: list[tuple[Entree, str]]
    pluriel: bool = False
    defini: bool = False
    indefini: bool = False
    particules: tuple[str, ...] = ()
    possessif: str = ""


class Traducteur:
    """Traduit un texte à l'aide d'un glossaire."""

    def __init__(self, glossaire: Glossaire) -> None:
        self.glossaire = glossaire
        #: Phrases d'exemple du glossaire : clé de la phrase -> exemple.
        self._memoire: dict[str, dict[str, Contexte]] = {langue: {} for langue in LANGUES}
        #: Nombre de mots de la plus longue expression du glossaire, dans chaque langue.
        self._longueur = dict.fromkeys(LANGUES, 1)
        #: Premiers mots des expressions de plusieurs mots : évite de chercher une expression à chaque mot.
        self._amorces: dict[str, set[str]] = {langue: set() for langue in LANGUES}
        #: Vrai si le glossaire écrit les accents du français. Dans un texte lui aussi accentué, les
        #: accents comptent alors : « cause » n'est pas « causé », ni « condamne » « condamné ».
        self._glossaire_accentue = any(porte_des_accents(forme) for entree in glossaire.entrees
                                       for forme in (*entree.formes(FR), *entree.synonymes_fr))
        self._accents_comptent = False
        # Résultats déjà calculés (un même mot revient souvent dans un texte).
        self._lectures: dict[tuple[str, str, bool], _Lecture | None] = {}
        self._debuts: dict[tuple[str, str], bool] = {}
        self._champs: dict[tuple[Entree, str], tuple[set[str], set[str]]] = {}
        for entree in glossaire.entrees:
            for contexte in entree.contextes:
                self._memoriser(contexte)
            for langue in LANGUES:
                for forme in (*entree.formes(langue), *entree.synonymes(langue)):
                    mots = [jeton.texte for jeton in decouper_en_mots(forme) if jeton.nature != PONCTUATION]
                    self._longueur[langue] = max(self._longueur[langue], min(len(mots), LONGUEUR_MAXIMALE))
                    if len(mots) > 1:
                        self._amorces[langue].add(_cle_d_amorce(mots[0], langue))

    def _memoriser(self, contexte: Contexte) -> None:
        if not contexte.fr or not contexte.ar:
            return
        paires = [contexte]
        phrases_fr, phrases_ar = segmenter_en_phrases(contexte.fr), segmenter_en_phrases(contexte.ar)
        if len(phrases_fr) == len(phrases_ar) > 1:
            # Un exemple de plusieurs phrases : chaque phrase va avec la phrase de même rang.
            paires += [Contexte(fr=fr.texte, ar=ar.texte, source=contexte.source)
                       for fr, ar in zip(phrases_fr, phrases_ar, strict=True)]
        for paire in paires:
            for langue in LANGUES:
                cle = cle_phrase(paire.texte(langue))
                if cle:
                    self._memoire[langue].setdefault(cle, paire)

    # ------------------------------------------------------------------ traduction
    def traduire(self, texte: str, source: str) -> Traduction:
        """Traduit ``texte``, écrit dans la langue ``source``, vers l'autre langue."""
        cible = autre_langue(source)
        resultat = Traduction(source=source, cible=cible, texte_source=texte)
        # Un texte français sans aucun accent (saisie rapide, majuscules) est comparé sans les accents.
        self._accents_comptent = source == FR and self._glossaire_accentue and porte_des_accents(texte)

        # Étapes 1 à 3 : phrases, mots, recherche dans le glossaire.
        for rang, phrase in enumerate(segmenter_en_phrases(texte)):
            jetons = decouper_en_mots(phrase.texte, phrase.debut)
            occurrences = self._reperer(texte, jetons, source, rang)
            resultat.phrases.append(PhraseTraduite(phrase, jetons, occurrences, [],
                                                   attestation=self._memoire[source].get(cle_phrase(phrase.texte)),
                                                   mots=sum(1 for jeton in jetons if jeton.compte)))
        # Étape 4 : règles sémantiques (homonymes), puis règles lexicales et grammaticales.
        self._departager_les_homonymes(resultat)
        absents: dict[str, str] = {}
        position = 0
        for phrase in resultat.phrases:
            reconnus = self._appliquer_les_regles(phrase, source)
            # Étape 5 : reconstruction de la phrase.
            if phrase.attestation is not None:
                phrase.morceaux = self._reprendre_l_exemple(phrase, cible)
                phrase.mots_reconnus = phrase.mots
                resultat.regles["phrase"] += 1
                # La traduction vient de l'exemple : les règles de grammaire n'ont pas servi.
                for occurrence in phrase.occurrences:
                    occurrence.regles = [regle for regle in occurrence.regles if REGLES[regle][0] != "grammaire"]
            else:
                phrase.morceaux = self._reconstruire(texte, phrase, reconnus, source)
                phrase.mots_reconnus = sum(1 for rang, jeton in enumerate(phrase.jetons)
                                           if jeton.compte and rang in reconnus)
                for rang, jeton in enumerate(phrase.jetons):
                    if jeton.compte and rang not in reconnus:
                        absents.setdefault(cle_souple(jeton.texte), jeton.texte.lower())
            for occurrence in phrase.occurrences:
                resultat.regles.update(occurrence.regles)
            resultat.mots += phrase.mots
            resultat.mots_reconnus += phrase.mots_reconnus
            # Ce qui sépare deux phrases (espaces, retours à la ligne) est recopié tel quel.
            if phrase.source.debut > position:
                resultat.morceaux.append(Morceau(texte[position:phrase.source.debut], NEUTRE))
            resultat.morceaux.extend(phrase.morceaux)
            position = phrase.source.fin
        if position < len(texte):
            resultat.morceaux.append(Morceau(texte[position:], NEUTRE))
        resultat.mots_absents = list(absents.values())

        par_entree: dict[Entree, TermeDetecte] = {}
        for occurrence in resultat.occurrences:
            par_entree.setdefault(occurrence.entree, TermeDetecte(occurrence.entree, [])).occurrences.append(occurrence)
        resultat.termes = list(par_entree.values())
        return resultat

    # ------------------------------------------------------------------ étape 3 : recherche dans le glossaire
    def _reperer(self, texte: str, jetons: list[Jeton], langue: str, rang_phrase: int) -> list[Occurrence]:
        """Relève les termes du glossaire dans une phrase, l'expression la plus longue d'abord."""
        occurrences: list[Occurrence] = []
        rang = 0
        while rang < len(jetons):
            if not jetons[rang].est_mot:
                rang += 1
                continue
            lecture, longueur = None, 0
            maximum = self._longueur[langue] if self._commence_une_expression(jetons[rang].texte, langue) else 1
            apres_un_singulier = (langue == FR and rang > 0
                                  and _minuscule(jetons[rang - 1]) in _DETERMINANTS_SINGULIERS)
            for longueur in range(min(maximum, len(jetons) - rang), 0, -1):
                groupe = jetons[rang:rang + longueur]
                if not groupe[-1].est_mot or any(jeton.nature == PONCTUATION for jeton in groupe):
                    continue
                lecture = self._lire(texte[groupe[0].debut:groupe[-1].fin], langue)
                if lecture is not None and apres_un_singulier:
                    lecture = _au_singulier(lecture)
                if lecture is not None:
                    break
            if lecture is None:
                rang += 1
                continue
            premier, dernier = jetons[rang], jetons[rang + longueur - 1]
            entree, nature = lecture.entrees[0]
            occurrence = Occurrence(
                entree=entree, candidats=tuple(candidat for candidat, _ in lecture.entrees), phrase=rang_phrase,
                premier=rang, dernier=rang + longueur - 1, debut=premier.debut, fin=dernier.fin,
                forme=texte[premier.debut:dernier.fin], nature=nature,
                pluriel=lecture.pluriel or nature == "pluriel", defini=lecture.defini, indefini=lecture.indefini,
                particules=lecture.particules, possessif=lecture.possessif,
            )
            occurrences.append(occurrence)
            rang += longueur
        return occurrences

    def _commence_une_expression(self, mot: str, langue: str) -> bool:
        """Indique si une expression de plusieurs mots du glossaire peut commencer par ``mot``."""
        amorces = self._amorces[langue]
        if not amorces:
            return False
        if (mot, langue) not in self._debuts:
            if langue == FR:
                formes = (mot, *_singuliers(mot))
            else:
                formes = [reste for _, reste in _sans_particules(cle_stricte(mot))]
                formes += [singulier for reste in list(formes) for singulier in self._singuliers_arabes(reste)]
            self._debuts[mot, langue] = any(_cle_d_amorce(forme, langue) in amorces for forme in formes)
        return self._debuts[mot, langue]

    def _singuliers_arabes(self, mot: str) -> list[str]:
        """Singuliers d'un mot arabe que le glossaire donne comme un pluriel : « عقود » -> « عقد »."""
        return [entree.terme_ar for entree, nature in self.glossaire.reconnaitre(mot, AR)
                if nature == "pluriel" and len(entree.terme_ar.split()) == 1]

    def _pluriel_arabe(self, entree: Entree) -> str:
        """Pluriel arabe d'une entrée : celui du glossaire ou, pour une annexion, celui de son premier mot.

        « عقد الإيجار » : le premier mot n'a pas l'article et le dernier l'a, c'est une annexion.
        Seul le premier mot se met au pluriel : « عقود الإيجار ». Un nom suivi d'un adjectif
        (« القانون المدني ») n'est pas traité : l'adjectif devrait s'accorder.
        """
        if entree.pluriel_ar:
            return entree.pluriel_ar
        premier, _, suite = entree.terme_ar.partition(" ")
        if not suite or _a_l_article(premier) or not _a_l_article(suite.split()[-1]):
            return ""
        for autre in self.glossaire.trouver(premier, AR):
            if (autre.pluriel_ar and len(autre.pluriel_ar.split()) == 1
                    and cle_stricte(autre.terme_ar) == cle_stricte(premier)):
                return f"{autre.pluriel_ar} {suite}"
        return ""

    def _lire(self, forme: str, langue: str) -> _Lecture | None:
        """Cherche une forme du texte dans le glossaire, telle quelle puis sous des formes voisines."""
        cle = (forme, langue, self._accents_comptent)
        if cle not in self._lectures:
            self._lectures[cle] = self._chercher(forme, langue)
        return self._lectures[cle]

    def _chercher(self, forme: str, langue: str) -> _Lecture | None:
        if langue == FR:
            entrees = self._reconnaitre_en_francais(forme)
            if entrees:
                return _Lecture(entrees)
            for singulier in _singuliers(forme):
                entrees = self._reconnaitre_en_francais(singulier)
                if entrees:
                    return _Lecture(entrees, pluriel=True)
            return None

        forme = cle_stricte(forme)  # sans voyelles brèves ni allongement
        variantes = list(_sans_particules(forme))
        for particules, reste in variantes:
            entrees = self.glossaire.reconnaitre(reste, AR)
            if entrees:
                return _Lecture(entrees, particules=particules, defini=_est_defini(reste))
        for particules, reste in variantes:
            for terminaison, nature, radical in _sans_terminaison(reste):
                entrees = self.glossaire.reconnaitre(radical, AR)
                if entrees:
                    return _Lecture(entrees, particules=particules, defini=_est_defini(radical),
                                    pluriel=nature == "pluriel", indefini=nature == "indefini",
                                    possessif=terminaison if nature == "possessif" else "")
        # Expression dont le premier mot est au pluriel : « عقود الإيجار » = pluriel de « عقد الإيجار ».
        for particules, reste in variantes:
            premier, _, suite = reste.partition(" ")
            if not suite:
                break
            for singulier in self._singuliers_arabes(premier):
                entrees = self.glossaire.reconnaitre(f"{singulier} {suite}", AR)
                if entrees:
                    return _Lecture(entrees, particules=particules, defini=_est_defini(reste), pluriel=True)
        return None

    def _reconnaitre_en_francais(self, forme: str) -> list[tuple[Entree, str]]:
        """Entrées désignées par une forme française ; les accents comptent si le texte en porte."""
        entrees = self.glossaire.reconnaitre(forme, FR)
        if not self._accents_comptent:
            return entrees
        return [(entree, nature) for entree, nature in entrees
                if any(memes_accents(forme, reference) for reference in _formes_du_glossaire(entree, nature))]

    # ------------------------------------------------------------------ étape 4 : règles
    def _departager_les_homonymes(self, resultat: Traduction) -> None:
        """Règle sémantique : entre plusieurs entrées possibles, choisit celle que le contexte désigne."""
        source = resultat.source
        toutes = resultat.occurrences
        if not any(len(occurrence.candidats) > 1 for occurrence in toutes):
            return

        def cles(occurrence: Occurrence) -> set[str]:
            return {cle_souple(candidat.terme(source)) for candidat in occurrence.candidats}

        cles_du_texte = set().union(*(cles(occurrence) for occurrence in toutes))
        for phrase in resultat.phrases:
            mots_de_la_phrase = {cle_souple(jeton.texte) for jeton in phrase.jetons
                                 if jeton.est_mot and len(jeton.texte) > 3}
            for occurrence in phrase.occurrences:
                if len(occurrence.candidats) < 2:
                    continue
                propres = cles(occurrence)
                autres = [autre for autre in phrase.occurrences if autre is not occurrence]
                dans_la_phrase = set().union(*(cles(autre) for autre in autres)) - propres
                # Termes voisins, séparés par un mot au plus : « droit de propriété », « la loi et le droit ».
                voisins = set().union(*(cles(autre) for autre in autres if min(
                    abs(autre.premier - occurrence.dernier), abs(occurrence.premier - autre.dernier)) <= 2)) - propres
                dans_le_texte = cles_du_texte - propres
                notes = []
                for candidat in occurrence.candidats:
                    champ, mots = self._champ(candidat, source)
                    notes.append(4 * len(champ & voisins) + 2 * len(champ & dans_la_phrase)
                                 + len(champ & dans_le_texte) + len((mots - propres) & mots_de_la_phrase))
                meilleure = max(notes)
                occurrence.entree = occurrence.candidats[notes.index(meilleure)]
                if notes.count(meilleure) > 1:
                    occurrence.incertain = True
                else:
                    occurrence.regles.append("homonyme")

    def _champ(self, entree: Entree, langue: str) -> tuple[set[str], set[str]]:
        """Termes liés à une entrée et mots de sa définition et de ses exemples, dans une langue."""
        if (entree, langue) in self._champs:
            return self._champs[entree, langue]
        champ: set[str] = set()
        for terme in (*entree.termes_associes, *entree.synonymes(langue)):
            champ.add(cle_souple(terme))
            for liee in (*self.glossaire.trouver(terme, FR), *self.glossaire.trouver(terme, AR)):
                champ.add(cle_souple(liee.terme(langue)))
        textes = [entree.definition(langue), *(contexte.texte(langue) for contexte in entree.contextes)]
        mots = {cle_souple(jeton.texte) for texte in textes for jeton in decouper_en_mots(texte)
                if jeton.est_mot and len(jeton.texte) > 3}
        self._champs[entree, langue] = champ, mots
        return champ, mots

    def _appliquer_les_regles(self, phrase: PhraseTraduite, source: str) -> set[int]:
        """Règles lexicales et grammaticales d'une phrase.

        Renvoie les rangs des jetons reconnus : ceux des termes, et ceux des
        articles et des prépositions que les règles ont pris en compte.
        """
        reconnus: set[int] = set()
        for occurrence in phrase.occurrences:
            reconnus.update(range(occurrence.premier, occurrence.dernier + 1))
            if occurrence.dernier > occurrence.premier or len(occurrence.entree.terme(source).split()) > 1:
                occurrence.regles.append("expression")
            if occurrence.nature == "synonyme":
                occurrence.regles.append("synonyme")
        if source == FR:
            reconnus |= _determinants_francais(phrase.jetons, phrase.occurrences)
            precedente: Occurrence | None = None
            for occurrence in phrase.occurrences:
                occurrence.rendu = _rendre_en_arabe(occurrence, precedente if occurrence.complement else None,
                                                    self._pluriel_arabe(occurrence.entree))
                precedente = occurrence
        else:
            _annexions_arabes(phrase.occurrences)
            for occurrence in phrase.occurrences:
                occurrence.rendu = _rendre_en_francais(occurrence, self.glossaire)
        return reconnus

    # ------------------------------------------------------------------ étape 5 : reconstruction
    def _reprendre_l_exemple(self, phrase: PhraseTraduite, cible: str) -> list[Morceau]:
        """Phrase reprise d'un exemple du glossaire : sa traduction est celle de l'exemple."""
        texte = phrase.attestation.texte(cible).strip()
        finale = phrase.source.texte.rstrip()[-1:]
        if texte and texte[-1] not in _FINALES and finale and finale in _FINALES:
            texte += _PONCTUATION[cible].get(finale, finale)
        # Les équivalents des termes relevés dans la phrase source sont mis en évidence.
        reperes: list[tuple[int, int, Entree]] = []
        for entree in dict.fromkeys(occurrence.entree for occurrence in phrase.occurrences):
            reperes.extend((debut, fin, entree) for debut, fin in positions_du_terme(texte, entree, cible))
        morceaux: list[Morceau] = []
        position = 0
        for debut, fin, entree in sorted(reperes, key=lambda repere: (repere[0], -repere[1])):
            if debut < position:
                continue
            if debut > position:
                morceaux.append(Morceau(texte[position:debut], ATTESTE))
            morceaux.append(Morceau(texte[debut:fin], TERME, entree))
            position = fin
        if position < len(texte):
            morceaux.append(Morceau(texte[position:], ATTESTE))
        return morceaux

    def _reconstruire(self, texte: str, phrase: PhraseTraduite, reconnus: set[int], source: str) -> list[Morceau]:
        """Phrase traduite mot à mot : termes du glossaire traduits, autres mots laissés tels quels."""
        if not phrase.occurrences:
            return _recopier(texte, phrase)
        cible = autre_langue(source)
        par_premier = {occurrence.premier: occurrence for occurrence in phrase.occurrences}
        dans_un_terme = {rang for occurrence in phrase.occurrences
                         for rang in range(occurrence.premier, occurrence.dernier + 1)}
        morceaux: list[Morceau] = []
        espace = ""  # ce qui sépare le dernier jeton écrit du jeton suivant
        fin_precedente = phrase.source.debut
        ecrit = False  # vrai dès qu'un jeton a été écrit depuis le dernier espace retenu

        def ajouter(nouveau: Morceau) -> None:
            nonlocal espace, ecrit
            if espace and morceaux:
                morceaux.append(Morceau(espace, NEUTRE))
            morceaux.append(nouveau)
            espace, ecrit = "", True

        for rang, jeton in enumerate(phrase.jetons):
            if ecrit or not morceaux:
                espace, ecrit = texte[fin_precedente:jeton.debut], False
            fin_precedente = jeton.fin
            occurrence = par_premier.get(rang)
            if occurrence is not None:
                for particule in occurrence.particules:
                    ajouter(self._particule(particule))
                    espace = " "
                ajouter(Morceau(occurrence.rendu, TERME, occurrence.entree))
            elif rang in dans_un_terme:
                ecrit = True  # suite d'un terme déjà écrit
            elif rang in reconnus:
                continue  # article ou préposition pris en compte par une règle : rien à écrire
            elif jeton.nature == PONCTUATION:
                signe = _PONCTUATION[cible].get(jeton.texte, jeton.texte)
                if cible == AR and signe in "؛؟!:":
                    espace = ""  # pas d'espace avant ces signes en arabe
                elif cible == FR and signe in ";?!:" and morceaux:
                    espace = "\u00A0"  # espace insécable avant ces signes en français
                ajouter(Morceau(signe, NEUTRE))
            elif jeton.est_mot:
                ajouter(Morceau(jeton.texte, SOURCE))
            else:
                ajouter(Morceau(jeton.texte.translate(_CHIFFRES_ARABES) if cible == FR else jeton.texte, NEUTRE))
        if cible == AR:
            morceaux = _coller_les_particules(morceaux)
        else:
            _majuscule_initiale(morceaux)
        return morceaux

    def _particule(self, particule: str) -> Morceau:
        """Particule séparée d'un mot arabe : traduite si le glossaire la contient, sinon laissée telle quelle."""
        entrees = self.glossaire.reconnaitre(particule, AR)
        if entrees:
            return Morceau(entrees[0][0].terme_fr, TERME, entrees[0][0])
        return Morceau(particule if particule == "و" else particule + "ـ", SOURCE)


def _recopier(texte: str, phrase: PhraseTraduite) -> list[Morceau]:
    """Phrase sans aucun terme du glossaire : elle est recopiée telle quelle, ponctuation comprise."""
    morceaux: list[Morceau] = []
    position = phrase.source.debut
    for jeton in phrase.jetons:
        if jeton.debut > position:
            morceaux.append(Morceau(texte[position:jeton.debut], NEUTRE))
        morceaux.append(Morceau(jeton.texte, SOURCE if jeton.est_mot else NEUTRE))
        position = jeton.fin
    if position < phrase.source.fin:
        morceaux.append(Morceau(texte[position:phrase.source.fin], NEUTRE))
    return morceaux


# ====================================================================== règles du français vers l'arabe
def _minuscule(jeton: Jeton) -> str:
    return jeton.texte.casefold().replace("’", "'")


def _singuliers(forme: str) -> list[str]:
    """Formes au singulier possibles d'une expression française au pluriel (« contrats de vente »)."""
    choix: list[list[str]] = []
    for mot in forme.split():
        minuscule = mot.casefold()
        if len(mot) > 4 and minuscule.endswith("aux"):
            choix.append([mot[:-3] + "al", mot[:-3] + "ail", mot[:-1], mot])
        elif len(mot) > 3 and minuscule[-1] in "sx":
            choix.append([mot[:-1], mot])
        else:
            choix.append([mot])
    formes = [" ".join(mots) for mots in itertools.islice(itertools.product(*choix), 12)]
    return [candidate for candidate in formes if candidate != forme]


def _formes_du_glossaire(entree: Entree, nature: str) -> list[str]:
    """Formes françaises d'une entrée auxquelles comparer une forme du texte, selon la façon dont elle est reconnue.

    Chaque forme est donnée telle qu'elle est écrite dans le glossaire, puis sans l'article qui la précède
    parfois (« le Parlement ») : la recherche l'ignore aussi.
    """
    if nature == "synonyme":
        formes = entree.synonymes_fr
    else:
        formes = [entree.pluriel_fr] if nature == "pluriel" else [entree.terme_fr]
    return [*formes, *(sans_article_francais(cle_stricte(forme)) for forme in formes)]


def _au_singulier(lecture: _Lecture) -> _Lecture | None:
    """Lecture d'une forme placée après un déterminant singulier : les lectures au pluriel sont écartées."""
    if lecture.pluriel:
        return None
    entrees = [(entree, nature) for entree, nature in lecture.entrees if nature != "pluriel"]
    return _Lecture(entrees) if entrees else None


def _determinants_francais(jetons: list[Jeton], occurrences: list[Occurrence]) -> set[int]:
    """Règles grammaticales du français : article, complément du nom, pluriel.

    Les occurrences sont complétées sur place. Renvoie les rangs des jetons
    (articles, « de », « du », « des ») que la traduction ne recopie pas.
    """
    absorbes: set[int] = set()

    def mot(rang: int) -> str:
        return _minuscule(jetons[rang]) if 0 <= rang < len(jetons) and jetons[rang].est_mot else ""

    precedente: Occurrence | None = None
    for occurrence in occurrences:
        rang = occurrence.premier - 1
        avant = mot(rang)
        lien: list[int] = []  # jetons du lien « de », « du », « des », « de la », « de l' »
        avec_article = False
        if avant in _ARTICLES_DEFINIS:
            occurrence.defini = True
            absorbes.add(rang)
            if mot(rang - 1) in _DE:
                lien, avec_article = [rang - 1], True
        elif avant in _ARTICLES_INDEFINIS:
            occurrence.indefini = True
            absorbes.add(rang)
            occurrence.regles.append("indefini")
        elif avant in ("du", "des"):
            lien, avec_article = [rang], True
        elif avant in _DE:
            lien = [rang]
        elif avant in _DETERMINANTS_DEFINIS:
            occurrence.defini = True
        if avant in _DETERMINANTS_PLURIELS:
            occurrence.pluriel = True

        if lien and precedente is not None and precedente.dernier == lien[0] - 1:
            # « nullité du contrat » : complément du nom. En arabe, le premier nom perd son
            # article et le second est déterminé (annexion).
            absorbes.update(lien)
            precedente.annexe = True
            if "article" in precedente.regles:
                precedente.regles.remove("article")  # dans une annexion, le premier nom ne prend pas l'article
            occurrence.complement = True
            occurrence.defini = avec_article or precedente.defini
            occurrence.regles.append("annexion")
        elif avant == "du":
            occurrence.defini = True  # « du » = « de » + « le » : le mot « du » reste dans le texte
        elif avant == "des":
            occurrence.indefini = True  # « des contrats » : article indéfini pluriel
            absorbes.add(rang)
            occurrence.regles.append("indefini")
        if occurrence.defini and not occurrence.complement:
            occurrence.regles.append("article")
        precedente = occurrence
    return absorbes


def _a_l_article(mot: str) -> bool:
    """Indique si un mot arabe commence par l'article « ال »."""
    return len(mot) >= 4 and mot.startswith(_ARTICLE) and cle_stricte(mot) not in _SANS_ARTICLE


def _est_defini(forme: str) -> bool:
    return any(_a_l_article(mot) for mot in forme.split())


def _definir(terme: str, categorie: str = "") -> str:
    """Ajoute l'article « ال » à un terme arabe."""
    mots = terme.split()
    if len(mots) > 1:
        if _est_defini(terme):
            return terme  # « عقد البيع », « القانون المدني » : déjà déterminé
        if "وصفي" in categorie:  # nom et adjectif : l'article se met aux deux
            return " ".join(_definir(mot) for mot in mots)
        if "إضافي" in categorie:  # annexion : l'article se met au dernier mot
            return " ".join([*mots[:-1], _definir(mots[-1])])
        return terme
    if _a_l_article(terme):
        return terme
    if terme.endswith(TANWIN_KASRA):
        terme = terme[:-1] + "ي"  # قاضٍ -> القاضي
    return _ARTICLE + terme


def _etat_construit(terme: str) -> str:
    """Forme d'un nom arabe suivi de son complément : قاضٍ -> قاضي ; متعاقدون -> متعاقدو."""
    if terme.endswith(TANWIN_KASRA):
        return terme[:-1] + "ي"
    if terme.endswith("ون") and len(terme) > 4:
        return terme[:-1]
    return terme


def _rendre_en_arabe(occurrence: Occurrence, premier_terme: Occurrence | None, pluriel_ar: str) -> str:
    """Écrit en arabe le terme d'une occurrence relevée dans un texte français.

    ``pluriel_ar`` est le pluriel arabe du terme, vide s'il n'est pas connu : le terme reste
    alors au singulier.
    """
    entree = occurrence.entree
    terme = entree.terme_ar
    if occurrence.pluriel and pluriel_ar:
        terme = pluriel_ar
        occurrence.regles.append("pluriel")
    if occurrence.annexe and len(terme.split()) == 1:
        rendu = _etat_construit(terme)
    elif occurrence.defini:
        rendu = _definir(terme, entree.categorie_ar)
    else:
        rendu = terme
    if premier_terme is not None and len(premier_terme.rendu.split()) > 1:
        # Le premier terme est une locution (« حسن النية ») : le complément est introduit par « لـ ».
        rendu = _definir(rendu, entree.categorie_ar)
        rendu = "لل" + rendu[2:] if rendu.startswith(_ARTICLE) and _a_l_article(rendu.split()[0]) else "ل" + rendu
    return rendu


def _coller_les_particules(morceaux: list[Morceau]) -> list[Morceau]:
    """Colle une particule arabe d'une lettre (و، ب، ل…) au mot arabe qui la suit."""
    resultat: list[Morceau] = []
    rang = 0
    while rang < len(morceaux):
        morceau = morceaux[rang]
        resultat.append(morceau)
        if (morceau.nature == TERME and len(morceau.texte) == 1 and morceau.texte in _PARTICULES_1
                and rang + 2 < len(morceaux) and not morceaux[rang + 1].texte.strip()
                and morceaux[rang + 2].nature == TERME):
            rang += 1  # l'espace qui suit la particule n'est pas recopié
        rang += 1
    return resultat


# ====================================================================== règles de l'arabe vers le français
def _sans_particules(forme: str):
    """Lectures possibles du début d'un mot arabe : (particules séparées, reste)."""
    yield (), forme
    premier, _, suite = forme.partition(" ")
    suite = " " + suite if suite else ""

    def lectures(mot: str):
        if len(mot) < 3 or mot[0] not in _PARTICULES_1:
            return
        if mot.startswith("لل") and len(mot) >= 4:
            yield ("ل",), _ARTICLE + mot[2:]  # للعقد = لـ + العقد
        yield (mot[0],), mot[1:]

    for particules, reste in lectures(premier):
        yield particules, reste + suite
    if premier[:1] in "وف":
        for particules, reste in lectures(premier[1:]):
            yield (premier[0], *particules), reste + suite


def _sans_terminaison(forme: str):
    """Lectures possibles de la fin d'un mot arabe : (terminaison, nature, forme sans la terminaison)."""
    debut, _, dernier = forme.rpartition(" ")
    debut = debut + " " if debut else ""
    for terminaison, nature in _TERMINAISONS:
        if not dernier.endswith(terminaison):
            continue
        radical = dernier[:-len(terminaison)]
        if len(radical) < 3:
            continue
        yield terminaison, nature, debut + radical
        if terminaison == "ات":
            yield terminaison, nature, debut + radical + "ة"  # مسؤوليات -> مسؤولية
        elif nature == "possessif" and radical.endswith("ت"):
            yield terminaison, nature, debut + radical[:-1] + "ة"  # ملكيته -> ملكية


def _annexions_arabes(occurrences: list[Occurrence]) -> None:
    """Repère les compléments du nom : deux termes qui se suivent, le premier sans article (« بطلان العقد »)."""
    for premiere, seconde in itertools.pairwise(occurrences):
        if (seconde.premier == premiere.dernier + 1 and not premiere.defini and not premiere.possessif
                and not premiere.indefini and not seconde.particules):
            premiere.annexe = True
            seconde.complement = True
            seconde.regles.append("annexion")
    # Le premier terme est déterminé si son complément l'est : on remonte la chaîne depuis la fin.
    for premiere, seconde in reversed(list(itertools.pairwise(occurrences))):
        if premiere.annexe and seconde.complement and seconde.premier == premiere.dernier + 1:
            premiere.defini = seconde.defini or bool(seconde.possessif)


def _genre(entree: Entree, glossaire: Glossaire) -> str:
    """Genre du terme français d'une entrée : « m », « f » ou « » s'il est inconnu."""
    categorie = entree.categorie_fr.casefold()
    if _GENRE_FEMININ.search(categorie):
        return "f"
    if _GENRE_MASCULIN.search(categorie):
        return "m"
    mots = entree.terme_fr.split()
    if len(mots) > 1:
        # « contrat de vente » : le genre est celui du premier mot, s'il figure dans le glossaire.
        for autre in glossaire.trouver(mots[0], FR):
            if autre is not entree and len(autre.terme_fr.split()) == 1:
                return _genre(autre, glossaire)
    return ""


def _est_un_pluriel(entree: Entree) -> bool:
    """Indique si le terme français de l'entrée est lui-même un pluriel (« biens », « droits de l'homme »)."""
    return "plur" in entree.categorie_fr.casefold()


def _commence_par_une_voyelle(terme: str) -> bool:
    minuscule = terme.casefold()
    if minuscule[:1] == "h":
        return not minuscule.startswith(_H_ASPIRES)
    return minuscule[:1] in _VOYELLES


def _pluriel_francais(terme: str) -> str:
    """Pluriel d'un terme français absent de la colonne « pluriel_fr » (règles générales)."""
    premier, espace, suite = terme.partition(" ")
    minuscule = premier.casefold()
    if minuscule.endswith(("s", "x", "z")):
        pluriel = premier
    elif minuscule.endswith("al"):
        pluriel = premier[:-2] + "aux"
    elif minuscule.endswith(("au", "eu")):
        pluriel = premier + "x"
    else:
        pluriel = premier + "s"
    return pluriel + espace + suite


def _rendre_en_francais(occurrence: Occurrence, glossaire: Glossaire) -> str:
    """Écrit en français le terme d'une occurrence relevée dans un texte arabe."""
    entree = occurrence.entree
    terme = entree.terme_fr
    pluriel = occurrence.pluriel
    if _est_un_pluriel(entree):
        pluriel = True  # le terme du glossaire est déjà au pluriel : il n'y a pas de règle à appliquer
    elif pluriel:
        terme = entree.pluriel_fr or _pluriel_francais(terme)
        occurrence.regles.append("pluriel")
    genre = _genre(entree, glossaire)
    voyelle = _commence_par_une_voyelle(terme)

    determinant = ""
    if occurrence.possessif:
        personne = _PERSONNES[occurrence.possessif]
        if pluriel:
            determinant = {"3s": "ses ", "3p": "leurs ", "1p": "nos ", "2p": "vos "}[personne]
        elif personne == "3s":
            determinant = "son " if genre == "m" or voyelle else ("sa " if genre == "f" else "")
        else:
            determinant = {"3p": "leur ", "1p": "notre ", "2p": "votre "}[personne]
        if determinant:
            occurrence.regles.append("possessif")
    elif occurrence.defini:
        if pluriel:
            determinant = "les "
        elif voyelle:
            determinant = "l’"
        else:
            determinant = {"m": "le ", "f": "la "}.get(genre, "")
        if determinant and not occurrence.complement:
            occurrence.regles.append("article")
    elif occurrence.indefini:
        determinant = "des " if pluriel else {"m": "un ", "f": "une "}.get(genre, "")
        if determinant:
            occurrence.regles.append("indefini")

    if occurrence.complement:
        contraction = {"le ": "du ", "les ": "des "}.get(determinant)
        if contraction:
            return contraction + terme
        if determinant:
            return "de " + determinant + terme
        return ("d’" if voyelle else "de ") + terme
    if occurrence.particules:
        occurrence.regles.append("particule")
    return determinant + terme


def _majuscule_initiale(morceaux: list[Morceau]) -> None:
    """Met une majuscule au premier mot d'une phrase française, si ce mot vient du glossaire."""
    for rang, morceau in enumerate(morceaux):
        if not morceau.texte.strip():
            continue
        if morceau.nature == TERME and morceau.texte[:1].islower():
            morceaux[rang] = Morceau(morceau.texte[:1].upper() + morceau.texte[1:], TERME, morceau.entree)
        return
