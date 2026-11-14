"""Connecteur vers un service d'intelligence artificielle, au format « compatible OpenAI ».

Ce format est celui de NVIDIA Build et de nombreux autres services : une adresse, une clé d'accès
et un nom de modèle. Le connecteur sait faire deux choses :

* ``lister_les_modeles`` demande au service la liste de ses modèles ;
* ``demander`` lui envoie une conversation et renvoie le texte écrit par le modèle.

Il n'emploie que la bibliothèque standard de Python. Il ne connaît ni le glossaire, ni le moteur
de traduction, ni l'interface graphique.

Chaque panne devient une ``ErreurService``, dont le texte est écrit pour l'utilisateur : pas
d'Internet, adresse fausse, clé refusée, trop de demandes, service trop lent, réponse illisible.

Précautions :

* la clé ne part que par une connexion chiffrée (« https:// »), sauf vers l'ordinateur lui-même
  (un modèle installé sur le PC), et elle n'est écrite dans aucun message d'erreur ;
* le certificat du service est toujours vérifié ;
* une redirection vers une autre adresse est refusée : la clé ne la suit pas ;
* quand le service répond « trop de demandes » ou « surchargé », la demande est renvoyée après une
  attente : ``ENVOIS`` envois au plus.
"""

from __future__ import annotations

import errno
import http.client
import ipaddress
import json
import math
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime

from .. import __version__

#: Adresse proposée par défaut : celle de NVIDIA Build.
ADRESSE_PAR_DEFAUT = "https://integrate.api.nvidia.com/v1"
#: Temps laissé au service pour répondre, en secondes.
DELAI = 60.0
#: Nombre d'envois d'une même demande, au plus, quand le service demande d'attendre.
ENVOIS = 3
#: Attente la plus longue entre deux envois, en secondes.
ATTENTE_MAXIMALE = 30.0
#: Taille maximale d'une réponse, en octets (protection contre un service défaillant).
TAILLE_MAXIMALE = 8 * 1024 * 1024

# Ce qui est en cause dans une panne : les valeurs de « ErreurService.genre ».
ADRESSE = "adresse"  # adresse absente, mal écrite, ou qui n'est pas celle d'un service d'IA
CONNEXION = "connexion"  # service injoignable : pas d'Internet, connexion refusée ou coupée
DELAI_DEPASSE = "delai"  # pas de réponse à temps
CLE = "cle"  # clé absente, mal écrite ou refusée
ACCES = "acces"  # clé reconnue, mais accès refusé : crédit épuisé, droit manquant
MODELE = "modele"  # modèle absent, ou inconnu du service
DEBIT = "debit"  # trop de demandes
DEMANDE = "demande"  # demande refusée par le service : trop longue, mal comprise
PANNE = "panne"  # service en panne ou surchargé
REPONSE = "reponse"  # réponse illisible, vide ou trop longue
ARRET = "arret"  # arrêt demandé pendant la demande

#: Rôles admis dans une conversation : la consigne, la demande, une réponse précédente du modèle.
ROLES = ("system", "user", "assistant")

#: Codes de réponse après lesquels la demande est renvoyée : « trop de demandes », « surchargé ».
_A_RENVOYER = frozenset({429, 503})
#: Pannes du système qui signifient « pas de réseau ».
_SANS_RESEAU = frozenset({errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN})
#: Durée d'une tranche d'attente, en secondes : un arrêt demandé est pris en compte dans ce délai.
_TRANCHE = 0.25
#: Longueur maximale de ce qui est cité de la réponse du service dans un message d'erreur.
_LONGUEUR_DU_DETAIL = 200
_AGENT = f"TraducteurJuridique/{__version__}"

_ADRESSE_NON_VALABLE = ("L’adresse du service n’est pas valable. Elle doit ressembler à "
                        f"« {ADRESSE_PAR_DEFAUT} ».")
_ILLISIBLE = "La réponse du service est illisible. Vérifiez l’adresse du service dans « Paramètres »."
_COUPEE = ("La connexion au service a été coupée. Vérifiez la connexion à Internet, puis réessayez. Si cela se "
           "répète, un pare-feu ou le réseau bloque peut-être le service.")
_ARRETEE = "La demande a été arrêtée."


class ErreurService(Exception):
    """Le service d'IA n'a pas donné de réponse utilisable.

    Le texte de l'erreur est écrit pour l'utilisateur. ``genre`` dit ce qui est en cause : c'est
    l'une des constantes ci-dessus (``CLE``, ``CONNEXION``…). ``code`` est le code de la réponse
    du service, quand il a répondu.
    """

    def __init__(self, message: str, genre: str, code: int | None = None) -> None:
        super().__init__(message)
        self.genre = genre
        self.code = code


@dataclass(frozen=True)
class Reponse:
    """Ce que le modèle a répondu à une demande."""

    texte: str
    #: Nom du modèle qui a répondu, tel que le service le donne.
    modele: str
    #: Raison de la fin de la réponse, donnée par le service : « stop » quand le modèle a terminé.
    fin: str
    #: Temps écoulé entre le premier envoi et la réponse, attentes comprises, en secondes.
    duree: float
    #: Nombre d'envois de la demande : plus d'un quand le service a demandé d'attendre.
    envois: int

    @property
    def coupee(self) -> bool:
        """Vrai si le modèle s'est arrêté avant la fin, parce qu'il a atteint sa longueur maximale."""
        return self.fin == "length"


# ------------------------------------------------------------------ les deux demandes
def lister_les_modeles(adresse: str = ADRESSE_PAR_DEFAUT, cle: str = "", *, delai: float = DELAI,
                       envois: int = ENVOIS, attendre: Callable[[float], None] = time.sleep,
                       arret: Callable[[], bool] | None = None) -> list[str]:
    """Renvoie les noms des modèles du service, dans l'ordre alphabétique.

    La clé est facultative : NVIDIA donne cette liste sans clé. C'est donc un bon premier essai
    de l'adresse et de la connexion à Internet. Les autres paramètres sont ceux de ``demander``.
    """
    base, local = _adresse(adresse)
    cle = _cle(cle)
    code, en_tetes, contenu, _nombre = _echanger("GET", base + "/models", cle, None, local, delai, envois,
                                                 attendre, arret)
    if not 200 <= code < 300:
        raise _refus(code, en_tetes, contenu, cle)
    donnees = _json(contenu)
    liste = donnees.get("data") if isinstance(donnees, dict) else donnees
    if not isinstance(liste, list):
        raise ErreurService(_ILLISIBLE, REPONSE)
    noms = {element["id"].strip() for element in liste
            if isinstance(element, dict) and isinstance(element.get("id"), str) and element["id"].strip()}
    if liste and not noms:
        raise ErreurService(_ILLISIBLE, REPONSE)
    return sorted(noms, key=str.casefold)


def demander(adresse: str, cle: str, modele: str, messages: Sequence[Mapping[str, str]], *,
             temperature: float | None = 0.0, longueur_maximale: int | None = None, delai: float = DELAI,
             envois: int = ENVOIS, attendre: Callable[[float], None] = time.sleep,
             arret: Callable[[], bool] | None = None) -> Reponse:
    """Envoie une conversation au modèle et renvoie sa réponse.

    ``messages`` est la conversation : une suite de ``{"role": …, "content": …}``, où le rôle vaut
    « system » (la consigne), « user » (la demande) ou « assistant » (une réponse précédente).

    ``temperature`` à 0 demande au modèle sa réponse la plus régulière ; ``None`` garde le réglage
    du service. ``longueur_maximale`` limite la longueur de la réponse, comptée par le service.

    ``delai`` est le temps laissé au service pour répondre à un envoi. ``envois`` est le nombre
    d'envois au plus quand il demande d'attendre ; ``attendre`` est la fonction qui attend (les
    tests la remplacent). ``arret`` est interrogée avant chaque envoi et pendant les attentes :
    dès qu'elle renvoie vrai, la demande est abandonnée.

    Lève ``ErreurService`` si le service ne donne pas de réponse utilisable.
    """
    base, local = _adresse(adresse)
    cle = _cle(cle)
    if not cle and not local:
        raise ErreurService("Aucune clé d’accès n’est saisie. Saisissez-la dans « Paramètres ».", CLE)
    modele = modele.strip()
    if not modele:
        raise ErreurService("Aucun modèle n’est choisi. Choisissez-le dans « Paramètres ».", MODELE)
    corps: dict[str, object] = {"model": modele, "messages": _conversation(messages), "stream": False}
    if temperature is not None:
        corps["temperature"] = temperature
    if longueur_maximale is not None:
        corps["max_tokens"] = longueur_maximale
    debut = time.monotonic()
    # « json.dumps » écrit les lettres arabes et accentuées sous une forme que tout service relit (\uXXXX).
    code, en_tetes, contenu, nombre = _echanger("POST", base + "/chat/completions", cle,
                                                json.dumps(corps).encode("ascii"), local, delai, envois,
                                                attendre, arret)
    if not 200 <= code < 300:
        raise _refus(code, en_tetes, contenu, cle, modele)
    texte, fin, nom = _reponse_du_modele(contenu, cle)
    return Reponse(texte, nom or modele, fin, time.monotonic() - debut, nombre)


def contexte_tls() -> ssl.SSLContext:
    """Réglages des connexions chiffrées : ceux de Python, qui vérifient le certificat et le nom du service."""
    return ssl.create_default_context()


# ------------------------------------------------------------------ ce qui part
def _adresse(adresse: str) -> tuple[str, bool]:
    """Contrôle l'adresse du service. Renvoie l'adresse sans barre finale, et vrai si c'est l'ordinateur lui-même."""
    adresse = adresse.strip()
    if not adresse:
        raise ErreurService("Aucune adresse de service n’est indiquée. Saisissez-la dans « Paramètres ».", ADRESSE)
    # Lettres accentuées, espaces et caractères invisibles : aucune adresse de service n'en contient.
    if any(not "!" <= caractere <= "~" for caractere in adresse):
        raise ErreurService(_ADRESSE_NON_VALABLE, ADRESSE)
    try:
        morceaux = urllib.parse.urlsplit(adresse)
        hote, _port = morceaux.hostname, morceaux.port  # « port » lève ValueError s'il est mal écrit
    except ValueError as erreur:
        raise ErreurService(_ADRESSE_NON_VALABLE, ADRESSE) from erreur
    if morceaux.scheme not in ("http", "https") or not hote:
        raise ErreurService(_ADRESSE_NON_VALABLE, ADRESSE)
    if morceaux.username is not None or morceaux.password is not None:
        raise ErreurService("L’adresse du service ne doit contenir ni identifiant ni mot de passe. "
                            "La clé se saisit à part, dans « Paramètres ».", ADRESSE)
    if morceaux.query or morceaux.fragment or "?" in adresse or "#" in adresse:
        raise ErreurService("L’adresse du service ne doit contenir ni « ? » ni « # ».", ADRESSE)
    local = _est_local(hote)
    if morceaux.scheme == "http" and not local:
        raise ErreurService("L’adresse du service doit commencer par « https:// ». Avec « http:// », la clé "
                            "d’accès et le texte circuleraient sans protection.", ADRESSE)
    chemin = morceaux.path.rstrip("/")
    # Une adresse copiée d'une documentation se termine parfois par le nom de la demande : il est retiré.
    for fin in ("/chat/completions", "/models"):
        if chemin.endswith(fin):
            chemin = chemin[:-len(fin)].rstrip("/")
    return f"{morceaux.scheme}://{morceaux.netloc}{chemin}", local


def _est_local(hote: str) -> bool:
    """Vrai si ``hote`` désigne l'ordinateur lui-même : « localhost », 127.0.0.1, ::1."""
    hote = hote.lower()
    if hote == "localhost" or hote.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(hote).is_loopback
    except ValueError:
        return False


def _cle(cle: str) -> str:
    """La clé sans les espaces qui l'entourent. Refuse une clé qui ne peut pas être envoyée telle quelle."""
    cle = cle.strip()
    if any(not "!" <= caractere <= "~" for caractere in cle):
        raise ErreurService("La clé d’accès contient un caractère qui ne peut pas s’y trouver : espace, retour à "
                            "la ligne ou lettre accentuée. Copiez-la de nouveau dans « Paramètres ».", CLE)
    return cle


def _conversation(messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    """Contrôle la conversation. Une erreur ici est une erreur du programme, pas du service : ``ValueError``."""
    conversation = []
    for message in messages:
        role, contenu = message.get("role"), message.get("content")
        if role not in ROLES or not isinstance(contenu, str):
            raise ValueError(f"message de conversation mal formé : {message!r}")
        conversation.append({"role": role, "content": contenu})
    if not conversation:
        raise ValueError("la conversation est vide")
    return conversation


# ------------------------------------------------------------------ l'envoi
class _SansRedirection(urllib.request.HTTPRedirectHandler):
    """Refuse de suivre une redirection : la réponse « allez à une autre adresse » est traitée comme un refus."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noms imposés par urllib
        return None


def _ouvreur(url: str, local: bool) -> urllib.request.OpenerDirector:
    """Ce qui ouvre les connexions : proxy du système (jamais vers l'ordinateur lui-même), certificat vérifié."""
    elements: list[urllib.request.BaseHandler] = [
        urllib.request.ProxyHandler({}) if local else urllib.request.ProxyHandler(), _SansRedirection()]
    if url.startswith("https://"):  # les certificats reconnus par le système ne sont lus que s'ils servent
        elements.append(urllib.request.HTTPSHandler(context=contexte_tls()))
    return urllib.request.build_opener(*elements)


def _echanger(methode: str, url: str, cle: str, corps: bytes | None, local: bool, delai: float, envois: int,
              attendre: Callable[[float], None], arret: Callable[[], bool] | None) -> tuple[int, Message, bytes, int]:
    """Envoie la demande, et la renvoie après une attente tant que le service le demande.

    Renvoie le code, les en-têtes et le contenu de la dernière réponse, puis le nombre d'envois.
    """
    ouvreur = _ouvreur(url, local)
    envoi = 0
    while True:
        if arret is not None and arret():
            raise ErreurService(_ARRETEE, ARRET)
        envoi += 1
        code, en_tetes, contenu = _envoyer(ouvreur, methode, url, cle, corps, delai)
        if code not in _A_RENVOYER or envoi >= envois:
            return code, en_tetes, contenu, envoi
        _patienter(_attente(en_tetes.get("Retry-After"), envoi), attendre, arret)


def _envoyer(ouvreur: urllib.request.OpenerDirector, methode: str, url: str, cle: str, corps: bytes | None,
             delai: float) -> tuple[int, Message, bytes]:
    """Un envoi. Renvoie le code, les en-têtes et le contenu de la réponse, que le service accepte ou refuse."""
    en_tetes = {"Accept": "application/json", "User-Agent": _AGENT}
    if corps is not None:
        en_tetes["Content-Type"] = "application/json"
    requete = urllib.request.Request(url, data=corps, headers=en_tetes, method=methode)
    if cle:
        # « unredirected » : urllib ne recopie jamais cet en-tête vers une autre adresse.
        requete.add_unredirected_header("Authorization", f"Bearer {cle}")
    try:
        try:
            reponse = ouvreur.open(requete, timeout=delai)
        except urllib.error.HTTPError as refus:  # le service a répondu, par un code de refus
            with refus:
                return refus.code, refus.headers, _lire(refus)
        with reponse:
            return reponse.status, reponse.headers, _lire(reponse)
    except urllib.error.URLError as erreur:
        raise _injoignable(erreur.reason, delai) from erreur
    except (OSError, http.client.HTTPException, UnicodeError) as erreur:
        raise _injoignable(erreur, delai) from erreur


def _lire(reponse) -> bytes:
    contenu = reponse.read(TAILLE_MAXIMALE + 1)
    if len(contenu) > TAILLE_MAXIMALE:
        raise ErreurService("La réponse du service est trop longue pour être lue.", REPONSE)
    return contenu


def _attente(indication: str | None, envoi: int) -> float:
    """Durée de l'attente avant le prochain envoi, en secondes.

    C'est celle que le service indique (en-tête « Retry-After » : un nombre de secondes ou une
    date), sinon 2 secondes, puis 4. Elle ne dépasse jamais ``ATTENTE_MAXIMALE``.
    """
    secondes = None
    if indication and indication.strip():
        try:
            secondes = float(indication)
        except ValueError:
            try:
                moment = parsedate_to_datetime(indication)
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                secondes = (moment - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                secondes = None
    if secondes is None or not math.isfinite(secondes):
        secondes = 2.0 ** envoi
    return min(max(secondes, 0.0), ATTENTE_MAXIMALE)


def _patienter(secondes: float, attendre: Callable[[float], None], arret: Callable[[], bool] | None) -> None:
    """Attend par petites tranches, pour qu'un arrêt demandé soit pris en compte sans tarder."""
    reste = secondes
    while reste > 0:
        if arret is not None and arret():
            raise ErreurService(_ARRETEE, ARRET)
        tranche = min(reste, _TRANCHE)
        attendre(tranche)
        reste -= tranche


# ------------------------------------------------------------------ les pannes
def _injoignable(cause: object, delai: float) -> ErreurService:
    """L'erreur à signaler quand le service n'a rien répondu. ``cause`` est la panne rencontrée."""
    if isinstance(cause, ssl.SSLCertVerificationError):
        return ErreurService("La connexion sécurisée au service a été refusée : son certificat n’a pas pu être "
                             "vérifié. Vérifiez la date et l’heure de l’ordinateur, puis l’adresse du service. "
                             "Rien n’a été envoyé.", CONNEXION)
    if isinstance(cause, (ssl.SSLZeroReturnError, ssl.SSLEOFError)):  # fermée par l'autre bout, ou en chemin
        return ErreurService(_COUPEE, CONNEXION)
    if isinstance(cause, ssl.SSLError):
        return ErreurService("La connexion sécurisée au service a échoué. Vérifiez l’adresse du service dans "
                             "« Paramètres ».", CONNEXION)
    if isinstance(cause, TimeoutError):
        return ErreurService(f"Le service n’a pas répondu en {_duree(delai)}. Réessayez dans un moment, ou avec "
                             "un texte plus court.", DELAI_DEPASSE)
    if isinstance(cause, UnicodeError):  # nom de machine impossible (« https://a..b »)
        return ErreurService(_ADRESSE_NON_VALABLE, ADRESSE)
    if isinstance(cause, socket.gaierror) or getattr(cause, "errno", None) in _SANS_RESEAU:
        return ErreurService("Le service est introuvable. Vérifiez la connexion à Internet, puis l’adresse du "
                             "service dans « Paramètres ».", CONNEXION)
    if isinstance(cause, ConnectionRefusedError):
        return ErreurService("Aucun service ne répond à cette adresse. Vérifiez l’adresse du service dans "
                             "« Paramètres ».", CONNEXION)
    return ErreurService(_COUPEE, CONNEXION)


def _refus(code: int, en_tetes: Message, contenu: bytes, cle: str, modele: str = "") -> ErreurService:
    """L'erreur à signaler quand le service a répondu par un refus. ``modele`` est vide pour la liste des modèles."""
    detail = _detail(contenu, cle)
    if 300 <= code < 400:
        vers = _court(en_tetes.get("Location") or "", cle)
        return ErreurService("Le service renvoie vers une autre adresse" + (f" ({vers})" if vers else "")
                             + ". Corrigez l’adresse du service dans « Paramètres ».", ADRESSE, code)
    if code in (401, 403) and not cle:
        return ErreurService("Ce service demande une clé d’accès. Saisissez-la dans « Paramètres ».", CLE, code)
    if code == 401:
        return ErreurService("Le service a refusé la clé d’accès. Vérifiez la clé dans « Paramètres ».", CLE, code)
    if code == 402:
        return ErreurService("Le service refuse la demande : le crédit du compte est épuisé ou a expiré.",
                             ACCES, code)
    if code == 403:
        return ErreurService(_avec("Le service refuse l’accès : cette clé n’a pas le droit d’employer ce service "
                                   "ou ce modèle.", detail), ACCES, code)
    if code in (404, 405):
        if modele:
            return ErreurService(_avec(f"Le service ne connaît pas le modèle « {modele} », ou l’adresse du service "
                                       "est fausse.", detail), MODELE, code)
        return ErreurService("Cette adresse n’est pas celle d’un service d’IA : la liste des modèles y est "
                             "introuvable. Une adresse de service se termine en général par « /v1 ».", ADRESSE, code)
    if code in (408, 504, 524):
        return ErreurService("Le service a mis trop de temps à répondre. Réessayez dans un moment, ou avec un "
                             "texte plus court.", DELAI_DEPASSE, code)
    if code == 413:
        return ErreurService("Le texte envoyé est trop long pour le service. Envoyez moins de phrases à la fois.",
                             DEMANDE, code)
    if code == 429:
        return ErreurService("Le service reçoit trop de demandes. Attendez une minute, puis réessayez.", DEBIT, code)
    if code >= 500:
        return ErreurService(f"Le service est en panne ou surchargé (erreur {code}). Réessayez plus tard.",
                             PANNE, code)
    return ErreurService(_avec(f"Le service a refusé la demande (erreur {code}).", detail), DEMANDE, code)


def _avec(message: str, detail: str) -> str:
    """Le message, suivi de ce que le service a répondu, s'il a dit quelque chose de lisible."""
    return f"{message} Réponse du service : « {detail} »" if detail else message


def _detail(contenu: bytes, cle: str) -> str:
    """Ce que le service dit de son refus : une ligne courte, sans la clé. Chaîne vide s'il ne dit rien de lisible."""
    try:
        donnees = json.loads(contenu)
    except (ValueError, RecursionError):
        texte = contenu.decode("utf-8", errors="replace").strip()
        return "" if texte.startswith("<") else _court(texte, cle)  # une page web n'apprend rien
    message: object = ""
    if isinstance(donnees, dict):
        erreur = donnees.get("error")
        message = erreur.get("message") if isinstance(erreur, dict) else erreur
        for nom in ("detail", "message", "title"):
            message = message or donnees.get(nom)
    if isinstance(message, list):  # une ligne par défaut relevé dans la demande
        message = " ; ".join(str(element.get("msg", "")) if isinstance(element, dict) else str(element)
                             for element in message)
    return _court(message, cle) if isinstance(message, str) else ""


def _court(texte: str, cle: str) -> str:
    """``texte`` sur une ligne, abrégé, et sans la clé : certains services la recopient dans leur réponse."""
    texte = " ".join(texte.split())
    if cle:
        texte = texte.replace(cle, "•••")
    return texte if len(texte) <= _LONGUEUR_DU_DETAIL else texte[:_LONGUEUR_DU_DETAIL].rstrip() + "…"


def _duree(secondes: float) -> str:
    """« 60 secondes », « 1 seconde », « 0,5 seconde »."""
    return f"{secondes:g}".replace(".", ",") + (" secondes" if secondes >= 2 else " seconde")


# ------------------------------------------------------------------ ce qui revient
def _json(contenu: bytes) -> object:
    try:
        return json.loads(contenu)
    except (ValueError, RecursionError) as erreur:
        raise ErreurService(_ILLISIBLE, REPONSE) from erreur


def _reponse_du_modele(contenu: bytes, cle: str) -> tuple[str, str, str]:
    """Lit la réponse à une conversation : le texte du modèle, la raison de sa fin, le nom du modèle."""
    donnees = _json(contenu)
    choix = donnees.get("choices") if isinstance(donnees, dict) else None
    premier = choix[0] if isinstance(choix, list) and choix else None
    message = premier.get("message") if isinstance(premier, dict) else None
    if not isinstance(message, dict):
        if isinstance(donnees, dict) and donnees.get("error"):  # certains services signalent une panne ainsi
            raise ErreurService(_avec("Le service a signalé une erreur.", _detail(contenu, cle)), PANNE)
        raise ErreurService(_ILLISIBLE, REPONSE)
    texte = _texte(message.get("content"))
    fin = premier.get("finish_reason")
    fin = fin if isinstance(fin, str) else ""
    if not texte.strip():
        if fin == "length":
            raise ErreurService("Le modèle a atteint sa longueur maximale sans rien écrire d’utilisable. Envoyez "
                                "moins de phrases à la fois.", REPONSE)
        raise ErreurService("Le modèle n’a rien répondu. Réessayez, ou choisissez un autre modèle dans "
                            "« Paramètres ».", REPONSE)
    nom = donnees.get("model")
    return texte, fin, nom if isinstance(nom, str) else ""


def _texte(contenu: object) -> str:
    """Le texte d'une réponse : une chaîne, ou une suite de morceaux dont seuls les textes sont gardés."""
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        morceaux = []
        for morceau in contenu:
            if isinstance(morceau, str):
                morceaux.append(morceau)
            elif isinstance(morceau, dict) and isinstance(morceau.get("text"), str):
                morceaux.append(morceau["text"])
        return "".join(morceaux)
    return ""
