"""Langues gérées par le prototype et outils de normalisation du texte.

Pour comparer deux mots sans tenir compte des majuscules, des accents ou des
variantes d'écriture de l'arabe, on les transforme en « clés » :

* la clé stricte garde les accents français (« côte » ≠ « coté ») ;
* la clé souple les supprime et unifie les variantes arabes ;
* les clés de recherche ajoutent, pour l'arabe, la forme sans l'article « ال ».
"""

from __future__ import annotations

import unicodedata

import regex

FR = "fr"
AR = "ar"
LANGUES = (FR, AR)

#: Nom de la langue écrit dans cette langue (sélecteur de langue).
NOM_NATIF = {FR: "Français", AR: "العربية"}
#: Nom de la langue en français (messages de l'interface).
NOM_EN_FRANCAIS = {FR: "français", AR: "arabe"}
#: Code affiché dans les pastilles.
CODE = {FR: "FR", AR: "AR"}

_LETTRE_ARABE = regex.compile(r"\p{Arabic}")
_LETTRE_LATINE = regex.compile(r"\p{Latin}")
# Signes diacritiques arabes : tanwin, voyelles brèves, chadda, soukoun, alif suscrit.
_DIACRITIQUES_ARABES = regex.compile(r"[\u064B-\u065F\u0670]")
_ESPACES = regex.compile(r"\s+")
# Article défini « ال » au début d'un mot d'au moins quatre lettres.
_ARTICLE_ARABE = regex.compile(r"(?<![\p{L}\p{N}])ال(?=\p{Arabic}{2})")
# Article ou préposition élidée au début d'une expression française (« le contrat », « l'usage »).
_ARTICLE_FRANCAIS = regex.compile(r"^(?:[ld]'|(?:le|la|les|un|une|des|du)\s)(?=\p{L})")

_UNIFICATION = str.maketrans(
    {
        "\u2019": "'", "\u2018": "'", "\u02BC": "'", "`": "'", "\u00B4": "'",  # apostrophes
        "\u2010": "-", "\u2011": "-", "\u2013": "-", "\u2014": "-",  # tirets
        "\u00A0": " ", "\u202F": " ", "\u2009": " ",  # espaces insécables et fines
        "\u0640": "",  # tatwil (allongement décoratif)
        "\u200E": "", "\u200F": "",  # marques de direction
    }
)
_VARIANTES = str.maketrans(
    {
        "\u0649": "\u064A",  # alif maqsura -> ya
        "\u0629": "\u0647",  # ta marbuta -> ha
        "\u0671": "\u0627",  # alif wasla -> alif
        "œ": "oe",
        "æ": "ae",
    }
)

#: Tanwin kasra : à la fin d'un mot, il signale un nom « défectueux » (قاضٍ = القاضي).
TANWIN_KASRA = "\u064D"


def autre_langue(langue: str) -> str:
    """Renvoie l'autre langue du couple français / arabe."""
    return AR if langue == FR else FR


def est_rtl(langue: str) -> bool:
    """Indique si la langue s'écrit de droite à gauche."""
    return langue == AR


def contient_arabe(texte: str) -> bool:
    return bool(_LETTRE_ARABE.search(texte))


def contient_latin(texte: str) -> bool:
    return bool(_LETTRE_LATINE.search(texte))


def deviner_langue(texte: str) -> str | None:
    """Devine la langue d'un texte d'après son écriture (arabe ou latine)."""
    arabe = len(_LETTRE_ARABE.findall(texte))
    latin = len(_LETTRE_LATINE.findall(texte))
    if arabe == 0 and latin == 0:
        return None
    return AR if arabe > latin else FR


def cle_stricte(texte: str) -> str:
    """Clé de comparaison qui garde les accents français.

    Minuscules, apostrophes et tirets unifiés, espaces réduits, signes
    diacritiques arabes et tatwil supprimés.
    """
    texte = unicodedata.normalize("NFC", texte).casefold().translate(_UNIFICATION)
    texte = _DIACRITIQUES_ARABES.sub("", texte)
    return _ESPACES.sub(" ", texte).strip()


def cle_souple(texte: str) -> str:
    """Clé de comparaison tolérante.

    En plus de la clé stricte : accents français supprimés (« Équité » et
    « equite » donnent la même clé), hamzas ramenées à leur lettre support
    (« أهلية » et « اهلية »), ta marbuta et alif maqsura unifiés.
    """
    texte = unicodedata.normalize("NFD", cle_stricte(texte))
    texte = "".join(caractere for caractere in texte if unicodedata.category(caractere) != "Mn")
    return _ESPACES.sub(" ", texte.translate(_VARIANTES)).strip()


def sans_article_arabe(cle: str) -> str:
    """Supprime l'article défini « ال » au début de chaque mot arabe."""
    return _ARTICLE_ARABE.sub("", cle)


def sans_article_francais(cle: str) -> str:
    """Supprime l'article placé au début d'une expression française."""
    return _ARTICLE_FRANCAIS.sub("", cle)


def cles_de_recherche(texte: str, langue: str) -> tuple[str, ...]:
    """Clés souples sous lesquelles un terme ou une requête peut être reconnu.

    On ajoute à la clé souple la forme sans article : « l'usage » est reconnu
    quand le glossaire contient « usage », « العقد » quand il contient « عقد »
    et « حسن نية » quand il contient « حسن النية ». Pour un nom arabe
    défectueux écrit avec tanwin (« قاضٍ »), on ajoute aussi la forme en ي
    (« قاضي », « القاضي »).
    """
    formes = [texte]
    if langue == AR and texte.rstrip().endswith(TANWIN_KASRA):
        formes.append(texte.rstrip()[:-1] + "\u064A")
    sans_article = sans_article_arabe if langue == AR else sans_article_francais
    cles: list[str] = []
    for forme in formes:
        cle = cle_souple(forme)
        for candidate in (cle, sans_article(cle)):
            if candidate and candidate not in cles:
                cles.append(candidate)
    return tuple(cles)
