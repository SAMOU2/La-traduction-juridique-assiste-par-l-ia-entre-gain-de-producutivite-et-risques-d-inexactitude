"""Contextes d'emploi d'un terme, cherchés dans tout le glossaire.

Le champ ④ « Contextualisation » montre d'abord les exemples de l'entrée (colonnes
``contexte_fr`` et ``contexte_ar`` de sa ligne). Quand l'entrée n'en a pas assez, on cherche
des phrases qui emploient le terme dans le reste du glossaire :

1. les exemples des autres entrées ;
2. les définitions des autres entrées.

Une phrase n'est retenue que si elle contient le terme en français **et** son équivalent en
arabe. C'est ce qui en fait un contexte dans les deux langues, et ce qui écarte les autres
sens d'un même mot (« action » : « دعوى » ou « سهم »).
"""

from __future__ import annotations

from dataclasses import dataclass

from .glossaire import Entree, Glossaire
from .langues import AR, FR
from .surlignage import motif_du_terme

#: D'où vient un contexte : de l'entrée elle-même, de l'exemple ou de la définition d'une autre entrée.
PROPRE, EXEMPLE, DEFINITION = "propre", "exemple", "definition"
#: Nombre de contextes visé pour un terme. Les exemples de l'entrée sont tous gardés, même au-delà.
NOMBRE_VISE = 2


@dataclass(frozen=True)
class Emploi:
    """Une phrase qui emploie un terme, dans les deux langues."""

    fr: str
    ar: str
    #: ``PROPRE``, ``EXEMPLE`` ou ``DEFINITION``.
    origine: str
    #: Référence citée par le glossaire pour cette phrase (un article de loi, par exemple) ; souvent vide.
    source: str
    #: L'entrée du glossaire où la phrase a été trouvée.
    entree: Entree

    def texte(self, langue: str) -> str:
        return self.fr if langue == FR else self.ar

    def provenance(self, langue: str = FR) -> str:
        """D'où vient la phrase, en clair : sa source, ou l'entrée qui la contient."""
        if self.origine == DEFINITION:
            return f"Définition de « {self.entree.terme(langue)} »"
        if self.source:
            return self.source
        return "" if self.origine == PROPRE else f"Exemple de « {self.entree.terme(langue)} »"


def emplois(glossaire: Glossaire | None, entree: Entree, nombre: int = NOMBRE_VISE) -> list[Emploi]:
    """Les contextes d'emploi d'un terme : ses exemples, complétés par ceux trouvés dans le glossaire.

    Les exemples de l'entrée viennent en premier, tous. S'il y en a moins que ``nombre``, la
    liste est complétée par des exemples, puis par des définitions d'autres entrées.
    """
    propres = [Emploi(contexte.fr, contexte.ar, PROPRE, contexte.source, entree) for contexte in entree.contextes]
    if glossaire is None or len(propres) >= nombre:
        return propres
    memoire = glossaire.__dict__.setdefault("_emplois_trouves", {})
    trouves = memoire.get(id(entree))
    if trouves is None:
        trouves = memoire[id(entree)] = _chercher(glossaire, entree)
    deja = {(emploi.fr, emploi.ar) for emploi in propres}
    resultat = list(propres)
    for emploi in trouves:
        if len(resultat) >= nombre:
            break
        if (emploi.fr, emploi.ar) not in deja:
            deja.add((emploi.fr, emploi.ar))
            resultat.append(emploi)
    return resultat


def _chercher(glossaire: Glossaire, entree: Entree) -> list[Emploi]:
    """Phrases des autres entrées qui emploient le terme dans les deux langues, les meilleures d'abord."""
    francais, arabe = motif_du_terme(entree, FR), motif_du_terme(entree, AR)
    if francais is None or arabe is None:
        return []
    domaine = entree.domaines[0] if entree.domaines else None
    exemples: list[tuple[tuple, Emploi]] = []
    definitions: list[tuple[tuple, Emploi]] = []
    for autre in glossaire.entrees:
        if autre is entree:
            continue
        # Une phrase d'un même domaine passe avant les autres ; à domaine égal, la plus courte d'abord.
        eloignement = 0 if domaine is not None and autre.domaines[:1] == [domaine] else 1
        for contexte in autre.contextes:
            if contexte.fr and contexte.ar and francais.search(contexte.fr) and arabe.search(contexte.ar):
                exemples.append(((eloignement, len(contexte.fr), autre.numero),
                                 Emploi(contexte.fr, contexte.ar, EXEMPLE, contexte.source, autre)))
        if (autre.definition_fr and autre.definition_ar and francais.search(autre.definition_fr)
                and arabe.search(autre.definition_ar)):
            definitions.append(((eloignement, len(autre.definition_fr), autre.numero),
                                Emploi(autre.definition_fr, autre.definition_ar, DEFINITION, "", autre)))
    return ([emploi for _, emploi in sorted(exemples, key=lambda element: element[0])]
            + [emploi for _, emploi in sorted(definitions, key=lambda element: element[0])])


__all__ = ["DEFINITION", "EXEMPLE", "NOMBRE_VISE", "PROPRE", "Emploi", "emplois"]
