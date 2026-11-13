"""Lecture du glossaire CSV et recherche des termes.

Le fichier CSV contient une ligne par terme. Deux colonnes seulement sont
obligatoires : le terme français (``terme_fr``) et le terme arabe
(``terme_ar``). Les autres colonnes sont facultatives ; elles alimentent les
champs Terme, Définition, Équivalent, Contextualisation et Ressources.

Le lecteur est volontairement tolérant, pour accepter un fichier enregistré
depuis Excel ou LibreOffice sans préparation particulière :

* le séparateur (``;``, ``,`` ou tabulation) et l'encodage sont détectés ;
* plusieurs noms sont acceptés pour une même colonne (voir ``COLONNES``) ;
* un fichier sans ligne d'en-tête est accepté : la colonne arabe et la colonne
  française sont alors repérées d'après leur écriture.
"""

from __future__ import annotations

import csv
import difflib
import io
from dataclasses import dataclass, field
from pathlib import Path

import regex

from .langues import (
    AR,
    FR,
    LANGUES,
    autre_langue,
    cle_souple,
    cle_stricte,
    cles_de_recherche,
    contient_arabe,
    sans_article_arabe,
)

#: Séparateur des valeurs multiples à l'intérieur d'une cellule (« a | b | c »).
SEPARATEUR_LISTE = "|"

#: Colonnes reconnues : nom officiel -> autres noms acceptés dans l'en-tête.
#: Les majuscules, les accents, les espaces et la ponctuation sont ignorés :
#: « Terme (FR) » et « terme_fr » désignent la même colonne.
COLONNES: dict[str, tuple[str, ...]] = {
    "terme_fr": ("fr", "français", "terme français", "mot français", "mot_fr", "terme", "mot", "french"),
    "terme_ar": ("ar", "arabe", "terme arabe", "mot arabe", "mot_ar", "équivalent", "équivalent_ar",
                 "traduction", "arabic", "العربية", "عربي", "المصطلح", "المقابل"),
    "categorie_fr": ("catégorie", "catégorie grammaticale", "nature", "nature_fr"),
    "categorie_ar": ("nature_ar", "النوع"),
    "pluriel_fr": ("pluriel",),
    "pluriel_ar": ("الجمع",),
    "domaine": ("domaines",),
    "synonymes_fr": ("synonymes", "synonyme", "synonyme_fr"),
    "synonymes_ar": ("synonyme_ar", "المرادفات"),
    "termes_associes": ("termes associés", "associés", "voir aussi"),
    "definition_fr": ("définition", "def_fr"),
    "definition_ar": ("def_ar", "التعريف"),
    "source_definition": ("source définition", "source_def"),
    "contexte_fr": ("contexte", "contextes_fr", "exemple_fr", "exemples_fr", "exemple", "exemples"),
    "contexte_ar": ("contextes_ar", "exemple_ar", "exemples_ar", "السياق"),
    "source_contexte": ("source contexte", "source_exemple", "sources_contexte"),
    "ressources": ("ressource", "références", "référence", "sources", "المراجع"),
}
COLONNES_OBLIGATOIRES = ("terme_fr", "terme_ar")

_NON_ALPHANUM = regex.compile(r"[^\p{L}\p{N}]+")
_LATIN = regex.compile(r"\p{Latin}")
_SUITE_ARABE = regex.compile(r"\p{Arabic}{2,}")
#: Début, sans accents ni majuscules, d'une source qui annonce un texte à vérifier.
_A_VERIFIER = "a verifier"


#: Premiers octets des fichiers .xlsx / .ods (archive ZIP) et .xls (ancien format d'Office).
_SIGNATURES_DE_CLASSEUR = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")

_CONSEIL_UTF8 = ("Si les mots arabes apparaissent sous forme de « ??? » dans le fichier, "
                 "enregistrez-le de nouveau au format « CSV UTF-8 ».")


class ErreurGlossaire(Exception):
    """Le fichier CSV ne peut pas être utilisé comme glossaire."""


def _cle_colonne(nom: str) -> str:
    return _NON_ALPHANUM.sub("", cle_souple(nom))


_ALIAS: dict[str, str] = {}
for _nom, _autres in COLONNES.items():
    for _alias in (_nom, *_autres):
        _ALIAS.setdefault(_cle_colonne(_alias), _nom)


def _liste(valeur: str) -> list[str]:
    """Découpe une cellule à valeurs multiples (« a | b | c »)."""
    return [morceau.strip() for morceau in valeur.split(SEPARATEUR_LISTE) if morceau.strip()]


def _mot_entier(cle: str) -> regex.Pattern:
    """Motif qui reconnaît ``cle`` comme mot (ou groupe de mots) entier."""
    return regex.compile(rf"(?<![\p{{L}}\p{{N}}]){regex.escape(cle)}(?![\p{{L}}\p{{N}}])")


def mention_a_verifier(source: str) -> str | None:
    """Détail d'une source qui commence par « à vérifier » ; ``None`` pour une vraie source.

    Le glossaire fourni écrit « à vérifier (définition d'exemple) » ou « à vérifier (phrase
    d'exemple) » à la place d'une source quand le texte n'est repris d'aucun ouvrage :
    la fonction rend alors « définition d'exemple » ou « phrase d'exemple ».
    """
    if not cle_souple(source).startswith(_A_VERIFIER):
        return None
    return source[len(_A_VERIFIER):].strip(" :·,;-–—()")


@dataclass(frozen=True)
class Contexte:
    """Un exemple d'emploi du terme, dans les deux langues, avec sa source."""

    fr: str = ""
    ar: str = ""
    source: str = ""

    def texte(self, langue: str) -> str:
        return self.fr if langue == FR else self.ar

    @property
    def a_verifier(self) -> bool:
        """Vrai si la source de l'exemple commence par « à vérifier » : la phrase n'est reprise d'aucun texte."""
        return mention_a_verifier(self.source) is not None


@dataclass(eq=False)
class Entree:
    """Une ligne du glossaire."""

    numero: int  # rang de l'entrée dans le glossaire (la première porte le n° 1)
    terme_fr: str
    terme_ar: str
    categorie_fr: str = ""
    categorie_ar: str = ""
    pluriel_fr: str = ""
    pluriel_ar: str = ""
    domaines: list[str] = field(default_factory=list)
    synonymes_fr: list[str] = field(default_factory=list)
    synonymes_ar: list[str] = field(default_factory=list)
    termes_associes: list[str] = field(default_factory=list)
    definition_fr: str = ""
    definition_ar: str = ""
    source_definition: str = ""
    contextes: list[Contexte] = field(default_factory=list)
    ressources: list[str] = field(default_factory=list)

    # Accès « par langue », pour traiter les deux sens de traduction de la même façon.
    def terme(self, langue: str) -> str:
        return self.terme_fr if langue == FR else self.terme_ar

    def categorie(self, langue: str) -> str:
        return self.categorie_fr if langue == FR else self.categorie_ar

    def pluriel(self, langue: str) -> str:
        return self.pluriel_fr if langue == FR else self.pluriel_ar

    def definition(self, langue: str) -> str:
        return self.definition_fr if langue == FR else self.definition_ar

    def synonymes(self, langue: str) -> list[str]:
        return self.synonymes_fr if langue == FR else self.synonymes_ar

    def formes(self, langue: str) -> list[str]:
        """Formes écrites du terme dans une langue : le terme, puis son pluriel."""
        return [forme for forme in (self.terme(langue), self.pluriel(langue)) if forme]


def _creer_entree(numero: int, valeurs: dict[str, str]) -> Entree:
    """Construit une entrée à partir du contenu d'une ligne, rangé par nom de colonne."""
    # Exemples : le n-ième exemple français va avec le n-ième exemple arabe et la n-ième source.
    contextes_fr, contextes_ar = _liste(valeurs["contexte_fr"]), _liste(valeurs["contexte_ar"])
    sources = _liste(valeurs["source_contexte"])
    contextes = [
        Contexte(
            fr=contextes_fr[rang] if rang < len(contextes_fr) else "",
            ar=contextes_ar[rang] if rang < len(contextes_ar) else "",
            source=sources[rang] if rang < len(sources) else "",
        )
        for rang in range(max(len(contextes_fr), len(contextes_ar)))
    ]
    return Entree(
        numero=numero,
        terme_fr=valeurs["terme_fr"],
        terme_ar=valeurs["terme_ar"],
        categorie_fr=valeurs["categorie_fr"],
        categorie_ar=valeurs["categorie_ar"],
        pluriel_fr=valeurs["pluriel_fr"],
        pluriel_ar=valeurs["pluriel_ar"],
        domaines=_liste(valeurs["domaine"]),
        synonymes_fr=_liste(valeurs["synonymes_fr"]),
        synonymes_ar=_liste(valeurs["synonymes_ar"]),
        termes_associes=_liste(valeurs["termes_associes"]),
        definition_fr=valeurs["definition_fr"],
        definition_ar=valeurs["definition_ar"],
        source_definition=valeurs["source_definition"],
        contextes=contextes,
        ressources=_liste(valeurs["ressources"]),
    )


def decoder(brut: bytes) -> tuple[str, str]:
    """Décode le contenu d'un fichier et renvoie le texte avec le nom de l'encodage."""
    if brut.startswith(b"\xef\xbb\xbf"):
        return brut[3:].decode("utf-8", errors="replace"), "UTF-8"
    if brut.startswith((b"\xff\xfe", b"\xfe\xff")):
        return brut.decode("utf-16", errors="replace"), "UTF-16"
    try:
        return brut.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        pass
    # Anciens fichiers « CSV » d'Excel : page de codes arabe de Windows, sinon occidentale.
    try:
        texte = brut.decode("cp1256")
        if _SUITE_ARABE.search(texte):
            return texte, "Windows-1256"
    except UnicodeDecodeError:
        pass
    return brut.decode("cp1252", errors="replace"), "Windows-1252"


def detecter_separateur(texte: str) -> str:
    """Devine le séparateur de colonnes : ``;``, tabulation ou ``,``.

    Le bon séparateur est celui qui découpe les premières lignes en un même
    nombre de colonnes, supérieur à un.
    """
    debut = "\n".join(texte.splitlines()[:25])
    meilleur, meilleur_score = ";", (0, 0)
    for separateur in (";", "\t", ","):
        try:
            lignes = [ligne for ligne in csv.reader(io.StringIO(debut), delimiter=separateur) if ligne]
        except csv.Error:
            continue
        if not lignes or len(lignes[0]) < 2:
            continue
        largeur = len(lignes[0])
        score = (sum(1 for ligne in lignes if len(ligne) == largeur), largeur)
        if score > meilleur_score:
            meilleur, meilleur_score = separateur, score
    return meilleur


class Glossaire:
    """Le glossaire chargé en mémoire, avec ses index de recherche."""

    def __init__(self, entrees: list[Entree], chemin: Path | None = None, encodage: str = "UTF-8",
                 separateur: str = ";", colonnes: list[str] | None = None,
                 colonnes_ignorees: list[str] | None = None, lignes_ignorees: int = 0) -> None:
        self.entrees = entrees
        self.chemin = chemin
        self.encodage = encodage
        self.separateur = separateur
        #: Colonnes reconnues dans le fichier, dans l'ordre du fichier.
        self.colonnes = colonnes or list(COLONNES_OBLIGATOIRES)
        #: En-têtes du fichier qui ne correspondent à aucune colonne connue.
        self.colonnes_ignorees = colonnes_ignorees or []
        #: Nombre de lignes écartées (terme français ou terme arabe manquant).
        self.lignes_ignorees = lignes_ignorees
        self._strict: dict[str, dict[str, list[Entree]]] = {langue: {} for langue in LANGUES}
        self._souple: dict[str, dict[str, list[Entree]]] = {langue: {} for langue in LANGUES}
        self._cles_du_terme: dict[str, dict[Entree, tuple[str, ...]]] = {langue: {} for langue in LANGUES}
        self._cles_des_synonymes: dict[str, dict[Entree, frozenset[str]]] = {langue: {} for langue in LANGUES}
        self._par_synonyme: dict[str, dict[str, list[Entree]]] = {langue: {} for langue in LANGUES}
        self._indexer()

    # ------------------------------------------------------------------ lecture
    @classmethod
    def charger(cls, chemin: str | Path) -> Glossaire:
        """Lit un fichier CSV et construit le glossaire."""
        chemin = Path(chemin)
        try:
            brut = chemin.read_bytes()
        except OSError as erreur:
            raise ErreurGlossaire(
                f"Impossible de lire le fichier « {chemin.name} » : {erreur.strerror or erreur}."
            ) from erreur
        if brut.startswith(_SIGNATURES_DE_CLASSEUR):
            raise ErreurGlossaire(
                f"« {chemin.name} » est un classeur de tableur (Excel ou LibreOffice), pas un fichier CSV.\n\n"
                "Ouvrez-le dans le tableur, enregistrez-le au format « CSV UTF-8 », "
                "puis ouvrez ici le fichier .csv obtenu."
            )
        texte, encodage = decoder(brut)
        return cls.depuis_texte(texte, chemin=chemin, encodage=encodage)

    @classmethod
    def depuis_texte(cls, texte: str, chemin: Path | None = None, encodage: str = "UTF-8") -> Glossaire:
        """Construit le glossaire à partir du contenu d'un fichier CSV."""
        separateur = detecter_separateur(texte)
        try:
            lignes = [ligne for ligne in csv.reader(io.StringIO(texte, newline=""), delimiter=separateur)
                      if any(cellule.strip() for cellule in ligne)]
        except csv.Error as erreur:
            raise ErreurGlossaire(f"Le fichier n'est pas un fichier CSV lisible ({erreur}).") from erreur
        if not lignes:
            raise ErreurGlossaire("Le fichier est vide.")

        # La première ligne est un en-tête si on y reconnaît au moins deux noms
        # de colonnes, dont une colonne de termes. Une seule cellule reconnue ne
        # suffit pas : « mot » peut aussi être le premier terme du glossaire.
        premiere = lignes[0]
        reconnues: dict[str, int] = {}
        for index, cellule in enumerate(premiere):
            nom = _ALIAS.get(_cle_colonne(cellule))
            if nom and nom not in reconnues:
                reconnues[nom] = index
        a_en_tete = len(reconnues) >= 2 and any(nom in reconnues for nom in COLONNES_OBLIGATOIRES)
        donnees = lignes[1:] if a_en_tete else lignes
        positions: dict[str, int] = dict(reconnues) if a_en_tete else {}
        # Sans en-tête reconnu, la première ligne est peut-être un en-tête aux noms
        # inconnus : on ne la compte pas pour repérer les colonnes de termes.
        echantillon = donnees if a_en_tete or len(donnees) == 1 else donnees[1:]
        cls._reperer_les_colonnes_de_termes(echantillon, positions)
        if not a_en_tete:
            index_ar = positions["terme_ar"]
            if index_ar >= len(premiere) or not contient_arabe(premiere[index_ar]):
                # Pas d'arabe dans la colonne arabe de la première ligne : c'est
                # un en-tête dont les noms ne sont pas tous connus.
                a_en_tete = True
                donnees = lignes[1:]
                for nom, index in reconnues.items():
                    if nom not in positions and index not in positions.values():
                        positions[nom] = index
        ignorees = ([cellule.strip() for index, cellule in enumerate(premiere)
                     if cellule.strip() and index not in positions.values()] if a_en_tete else [])

        entrees: list[Entree] = []
        lignes_ignorees = 0
        for ligne in donnees:
            # Contenu de la ligne, rangé par nom de colonne ; une colonne absente du fichier vaut "".
            valeurs = dict.fromkeys(COLONNES, "")
            valeurs.update({nom: ligne[index].strip() for nom, index in positions.items() if index < len(ligne)})
            if not valeurs["terme_fr"] or not valeurs["terme_ar"]:
                lignes_ignorees += 1
                continue
            entrees.append(_creer_entree(len(entrees) + 1, valeurs))
        if not entrees:
            raise ErreurGlossaire("Aucune ligne ne contient à la fois un terme français et un terme arabe.")
        if not any(contient_arabe(entree.terme_ar) for entree in entrees):
            raise ErreurGlossaire(
                "La colonne des termes arabes ne contient aucun mot écrit en arabe.\n\n" + _CONSEIL_UTF8)
        return cls(entrees, chemin=chemin, encodage=encodage, separateur=separateur,
                   colonnes=sorted(positions, key=positions.get), colonnes_ignorees=ignorees,
                   lignes_ignorees=lignes_ignorees)

    @staticmethod
    def _reperer_les_colonnes_de_termes(lignes: list[list[str]], positions: dict[str, int]) -> None:
        """Repère la colonne arabe et la colonne française d'après leur écriture.

        Sert quand le fichier n'a pas d'en-tête, ou quand l'en-tête ne nomme pas
        les deux colonnes de termes. ``positions`` est complété sur place.
        """
        if all(nom in positions for nom in COLONNES_OBLIGATOIRES):
            return
        echantillon = lignes[:200]
        largeur = max((len(ligne) for ligne in echantillon), default=0)
        libres = [index for index in range(largeur) if index not in positions.values()]

        def proportion(index: int, test) -> float:
            cellules = [ligne[index] for ligne in echantillon if index < len(ligne) and ligne[index].strip()]
            return sum(1 for contenu in cellules if test(contenu)) / len(cellules) if cellules else 0.0

        def est_francais(contenu: str) -> bool:
            return bool(_LATIN.search(contenu)) and not contient_arabe(contenu)

        if "terme_ar" not in positions:
            arabes = [index for index in libres if proportion(index, contient_arabe) >= 0.6]
            if arabes:
                positions["terme_ar"] = arabes[0]
                libres.remove(arabes[0])
        if "terme_fr" not in positions:
            latines = [index for index in libres if proportion(index, est_francais) >= 0.6]
            if latines:
                positions["terme_fr"] = latines[0]
        manquantes = [nom for nom in COLONNES_OBLIGATOIRES if nom not in positions]
        if manquantes:
            raise ErreurGlossaire(
                "Colonne introuvable : " + " et ".join(manquantes) + ".\n\n"
                "Le fichier doit contenir une colonne de termes français (terme_fr) et une colonne "
                "de termes arabes (terme_ar). " + _CONSEIL_UTF8
            )

    # ------------------------------------------------------------------ index
    def _indexer(self) -> None:
        for entree in self.entrees:
            for langue in LANGUES:
                self._cles_du_terme[langue][entree] = cles_de_recherche(entree.terme(langue), langue)
                self._cles_des_synonymes[langue][entree] = frozenset(
                    cle for synonyme in entree.synonymes(langue) for cle in cles_de_recherche(synonyme, langue)
                )
                for cle in self._cles_des_synonymes[langue][entree]:
                    self._ajouter(self._par_synonyme[langue], cle, entree)
                for forme in entree.formes(langue):
                    self._ajouter(self._strict[langue], cle_stricte(forme), entree)
                    for cle in cles_de_recherche(forme, langue):
                        self._ajouter(self._souple[langue], cle, entree)

    @staticmethod
    def _ajouter(index: dict[str, list[Entree]], cle: str, entree: Entree) -> None:
        entrees = index.setdefault(cle, [])
        if entree not in entrees:
            entrees.append(entree)

    def __len__(self) -> int:
        return len(self.entrees)

    @property
    def nom(self) -> str:
        """Nom du fichier chargé."""
        return self.chemin.name if self.chemin else "glossaire"

    # ------------------------------------------------------------------ recherche
    def trouver(self, forme: str, langue: str) -> list[Entree]:
        """Entrées dont le terme (ou son pluriel) est exactement ``forme``.

        La comparaison stricte (accents respectés) passe avant la comparaison
        souple. Les entrées sont renvoyées dans l'ordre du fichier.
        """
        trouvees = self._strict[langue].get(cle_stricte(forme))
        if trouvees:
            return list(trouvees)
        resultat: list[Entree] = []
        for cle in cles_de_recherche(forme, langue):
            for entree in self._souple[langue].get(cle, ()):
                if entree not in resultat:
                    resultat.append(entree)
        return sorted(resultat, key=lambda entree: entree.numero)

    def reconnaitre(self, forme: str, langue: str) -> list[tuple[Entree, str]]:
        """Entrées désignées par une forme relevée dans un texte, avec la façon dont elles sont reconnues.

        La forme est comparée au terme de chaque entrée (``"terme"``), à son
        pluriel (``"pluriel"``) et, si rien ne correspond, à ses synonymes
        (``"synonyme"``). Contrairement à ``trouver``, un article français
        placé devant la forme n'est pas ignoré : la traduction d'un texte le
        traite à part. L'article arabe, collé au mot, est ignoré.
        """
        trouvees = list(self._strict[langue].get(cle_stricte(forme), ()))
        cle = cle_souple(forme)
        cles = (cle, sans_article_arabe(cle)) if langue == AR else (cle,)
        if not trouvees:
            for candidate in cles:
                for entree in self._souple[langue].get(candidate, ()):
                    if entree not in trouvees:
                        trouvees.append(entree)
        if trouvees:
            trouvees.sort(key=lambda entree: entree.numero)
            return [(entree, "terme" if any(candidate in self._cles_du_terme[langue][entree] for candidate in cles)
                     else "pluriel") for entree in trouvees]
        synonymes: list[Entree] = []
        for candidate in cles:
            for entree in self._par_synonyme[langue].get(candidate, ()):
                if entree not in synonymes:
                    synonymes.append(entree)
        return [(entree, "synonyme") for entree in sorted(synonymes, key=lambda entree: entree.numero)]

    def par_terme(self, terme: str, langue: str) -> Entree | None:
        """Première entrée dont le terme (ou son pluriel) est exactement ``terme``."""
        trouvees = self.trouver(terme, langue)
        return trouvees[0] if trouvees else None

    def chercher(self, requete: str, langue: str) -> list[Entree]:
        """Entrées qui correspondent à la requête, les plus pertinentes d'abord.

        Ordre de pertinence :

        0. le terme (ou son pluriel) est exactement la requête ;
        1. le terme commence par la requête ;
        2. le terme contient la requête comme mot entier ;
        3. la requête est un synonyme du terme.
        """
        cles = cles_de_recherche(requete, langue)
        if not cles:
            return []
        motifs = [_mot_entier(cle) for cle in cles]
        rangs: dict[Entree, int] = dict.fromkeys(self.trouver(requete, langue), 0)
        for entree in self.entrees:
            if entree in rangs:
                continue
            cles_du_terme = self._cles_du_terme[langue][entree]
            if any(terme.startswith(cle) for terme in cles_du_terme for cle in cles):
                rangs[entree] = 1
            elif any(motif.search(terme) for terme in cles_du_terme for motif in motifs):
                rangs[entree] = 2
            elif any(cle in self._cles_des_synonymes[langue][entree] for cle in cles):
                rangs[entree] = 3
        return sorted(rangs, key=lambda entree: (rangs[entree], len(entree.terme(langue)), entree.numero))

    def propositions(self, requete: str, langue: str, limite: int = 5) -> list[Entree]:
        """Termes dont l'écriture est proche de la requête (faute de frappe probable)."""
        par_cle: dict[str, Entree] = {}
        for entree in self.entrees:
            for cle in self._cles_du_terme[langue][entree]:
                par_cle.setdefault(cle, entree)
        resultat: list[Entree] = []
        for cle in cles_de_recherche(requete, langue):
            for proche in difflib.get_close_matches(cle, list(par_cle), n=limite, cutoff=0.75):
                if par_cle[proche] not in resultat:
                    resultat.append(par_cle[proche])
        return resultat[:limite]

    def expressions(self, entree: Entree, langue: str) -> list[Entree]:
        """Autres entrées dont le terme contient celui de ``entree`` (« contrat de vente »…)."""
        motifs = [_mot_entier(cle) for cle in self._cles_du_terme[langue][entree]]
        trouvees = [
            autre for autre in self.entrees
            if autre is not entree
            and cle_souple(autre.terme(langue)) != cle_souple(entree.terme(langue))
            and any(motif.search(cle) for cle in self._cles_du_terme[langue][autre] for motif in motifs)
        ]
        return sorted(trouvees, key=lambda autre: (len(autre.terme(langue)), autre.numero))

    def homonymes(self, entree: Entree, langue: str) -> list[Entree]:
        """Entrées qui ont exactement le même terme que ``entree`` dans une langue."""
        return [autre for autre in self._strict[langue].get(cle_stricte(entree.terme(langue)), ())
                if cle_stricte(autre.terme(langue)) == cle_stricte(entree.terme(langue))]

    def libelle(self, entree: Entree, langue: str) -> str:
        """Terme de l'entrée, suivi de son équivalent entre parenthèses s'il a des homonymes.

        « droit » figure deux fois dans le glossaire d'exemple : les libellés
        « droit (حق) » et « droit (قانون) » permettent de distinguer les deux entrées.
        """
        terme = entree.terme(langue)
        if len(self.homonymes(entree, langue)) > 1:
            return f"{terme} ({entree.terme(autre_langue(langue))})"
        return terme
