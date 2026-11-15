"""Essai de la connexion au service d'IA, en deux temps.

1. Le service répond-il ? L'application lui demande la liste de ses modèles.
2. Le modèle répond-il ? L'application lui demande de traduire un mot.

L'essai n'envoie aucun texte de l'utilisateur : la seule demande envoyée est ``DEMANDE``. Il ne
connaît ni le glossaire, ni le moteur de traduction, ni l'interface graphique.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from . import service
from .lecture import sans_reflexion

#: Les deux temps de l'essai.
SERVICE, MODELE = 1, 2
#: La demande envoyée au modèle pendant l'essai.
DEMANDE = "Traduis en arabe le mot français « contrat ». Réponds par ce seul mot, sans rien ajouter."
#: Temps laissé au service pour donner la liste de ses modèles, puis au modèle pour répondre, en secondes.
DELAI_DU_SERVICE = 20.0
DELAI_DU_MODELE = 40.0
#: Longueur maximale de la réponse demandée. Elle laisse de la place à un modèle qui réfléchit avant de répondre.
LONGUEUR_MAXIMALE = 1024
#: Nombre de caractères de la réponse montrés à l'utilisateur.
LONGUEUR_MONTREE = 80
#: Nombre de noms proches proposés quand le modèle n'est pas dans la liste du service.
NOMS_PROCHES = 3
#: Ressemblance à partir de laquelle un nom est proposé, entre 0 (rien de commun) et 1 (identique).
RESSEMBLANCE_MINIMALE = 0.6


@dataclass(frozen=True)
class Constat:
    """Ce qu'un temps de l'essai a montré."""

    #: ``SERVICE`` ou ``MODELE``.
    temps: int
    reussi: bool
    #: Phrase écrite pour l'utilisateur.
    message: str
    #: En cas d'échec : ce qui est en cause, l'un des genres de ``service.ErreurService``.
    genre: str = ""


def essayer(adresse: str, cle: str, modele: str, *, arret: Callable[[], bool] | None = None,
            delai_du_service: float = DELAI_DU_SERVICE, delai_du_modele: float = DELAI_DU_MODELE) -> Iterator[Constat]:
    """Essaie la connexion et donne le constat de chaque temps dès qu'il est connu.

    Le second temps n'est essayé que si le premier a réussi. ``arret`` est interrogée avant chaque
    envoi : dès qu'elle renvoie vrai, l'essai s'arrête.
    """
    modele = modele.strip()
    try:
        modeles = service.lister_les_modeles(adresse, cle, delai=delai_du_service, envois=1, arret=arret)
    except service.ErreurService as erreur:
        yield Constat(SERVICE, False, _echec(erreur, SERVICE), erreur.genre)
        return
    yield Constat(SERVICE, True, _le_service_repond(modeles, modele))

    try:
        # La demande la plus simple qui soit : la « température » est laissée au réglage du service, car
        # certains modèles n'acceptent pas toutes les valeurs. L'essai ne juge pas la qualité de la réponse.
        reponse = service.demander(adresse, cle, modele, [{"role": "user", "content": DEMANDE}], temperature=None,
                                   longueur_maximale=LONGUEUR_MAXIMALE, delai=delai_du_modele, envois=1, arret=arret)
    except service.ErreurService as erreur:
        yield Constat(MODELE, False, _echec(erreur, MODELE), erreur.genre)
        return
    texte = " ".join(sans_reflexion(reponse.texte).split())
    if not texte:
        yield Constat(MODELE, False, "Le modèle a répondu, mais sans texte utilisable. Réessayez, ou choisissez "
                                     "un autre modèle.", service.REPONSE)
        return
    if len(texte) > LONGUEUR_MONTREE:
        texte = texte[:LONGUEUR_MONTREE].rstrip() + "…"
    duree = f"{reponse.duree:.1f}".replace(".", ",")
    yield Constat(MODELE, True, f"Le modèle a répondu en {duree} s. Sa réponse : {texte}")


def _echec(erreur: service.ErreurService, temps: int) -> str:
    """La phrase d'un échec : celle du connecteur, sauf quand le service a tardé.

    Le connecteur conseille alors « un texte plus court ». L'essai n'envoie aucun texte de
    l'utilisateur : ce conseil ne lui servirait à rien.
    """
    if erreur.genre != service.DELAI_DEPASSE:
        return str(erreur)
    if temps == SERVICE:
        return "Le service n’a pas répondu à temps. Vérifiez la connexion à Internet, puis réessayez dans un moment."
    return ("Le modèle n’a pas répondu à temps. Il est peut-être très demandé : réessayez dans un moment, ou "
            "choisissez un autre modèle.")


def noms_proches(modele: str, modeles: list[str], nombre: int = NOMS_PROCHES) -> list[str]:
    """Les noms de la liste du service qui ressemblent le plus à ``modele``, sans tenir compte des majuscules.

    Les plus ressemblants viennent d'abord ; à ressemblance égale, l'ordre alphabétique.
    """
    cherche = modele.casefold()
    notes = []
    for nom in modeles:
        ressemblance = difflib.SequenceMatcher(None, cherche, nom.casefold()).ratio()
        if ressemblance >= RESSEMBLANCE_MINIMALE:
            notes.append((-ressemblance, nom))
    return [nom for _, nom in sorted(notes)[:nombre]]


def _le_service_repond(modeles: list[str], modele: str) -> str:
    """La phrase du premier temps : le service répond, et le modèle choisi est ou n'est pas dans sa liste."""
    if not modeles:
        return "Le service répond. Il ne donne pas la liste de ses modèles."
    message = f"Le service répond : il propose {len(modeles)} modèle{'s' if len(modeles) > 1 else ''}."
    if not modele:
        return message
    if modele in modeles:
        return f"{message} « {modele} » est dans sa liste."
    message += f" « {modele} » n’est pas dans sa liste."
    proches = noms_proches(modele, modeles)
    if proches:
        message += " Noms proches : " + ", ".join(proches) + "."
    return message
