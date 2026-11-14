"""Connecteur vers le service d'IA (``traducteur/ia/service.py``).

Aucun test ne joint Internet. Un « faux service », lancé par les tests sur l'ordinateur lui-même,
joue chaque cas : réponse normale, clé refusée, trop de demandes, lenteur, réponse illisible. Une
connexion vers une autre machine fait échouer le test.
"""

import collections
import errno
import json
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import RACINE

from traducteur import __version__
from traducteur.ia import service as connecteur
from traducteur.ia.service import ErreurService, demander, lister_les_modeles

CLE = "nvapi-cle-d-essai-123"
MODELE = "essai/modele-1"
CONVERSATION = [{"role": "system", "content": "Traduis en arabe, en langue juridique."},
                {"role": "user", "content": "Le contrat fait la loi des parties."}]
TRADUCTION = "العقد شريعة المتعاقدين."
#: Adresse d'un service qui n'existe pas (les noms en « .example » sont réservés aux exemples).
AILLEURS = "https://service.example/v1"


def en_json(objet) -> bytes:
    return json.dumps(objet).encode("utf-8")


def reponse_du_modele(contenu=TRADUCTION, fin="stop", modele=MODELE) -> dict:
    """Ce qu'un service renvoie quand le modèle a répondu."""
    return {"id": "essai-1", "object": "chat.completion", "model": modele,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": contenu}, "finish_reason": fin}]}


LISTE_DES_MODELES = {"object": "list", "data": [{"id": "essai/modele-2", "object": "model"},
                                                {"id": MODELE, "object": "model"}]}


# ------------------------------------------------------------------ le faux service
@dataclass
class Demande:
    """Une demande reçue par le faux service."""

    methode: str
    chemin: str
    en_tetes: dict[str, str]  # noms en minuscules
    corps: bytes

    @property
    def json(self) -> dict:
        return json.loads(self.corps)


@dataclass
class Prevue:
    """Une réponse prévue par le test."""

    code: int = 200
    corps: bytes = b""
    en_tetes: dict[str, str] = field(default_factory=dict)
    attente: float = 0.0  # secondes de silence avant de répondre
    couper: bool = False  # raccrocher sans rien répondre


class _Gestionnaire(BaseHTTPRequestHandler):
    def _repondre(self) -> None:
        faux: FauxService = self.server.faux
        longueur = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(longueur) if longueur else b""
        faux.recues.append(Demande(self.command, self.path, {nom.lower(): valeur for nom, valeur in
                                                             self.headers.items()}, corps))
        prevue = faux.prevues.popleft() if faux.prevues else faux.reponse_normale(self.path)
        if prevue.attente:
            time.sleep(prevue.attente)
        if prevue.couper:
            return
        self.send_response(prevue.code)
        for nom, valeur in prevue.en_tetes.items():
            self.send_header(nom, valeur)
        self.send_header("Content-Length", str(len(prevue.corps)))
        self.end_headers()
        self.wfile.write(prevue.corps)

    do_GET = do_POST = _repondre  # noqa: N815 (noms imposés par http.server)

    def log_message(self, *arguments) -> None:  # pas de journal dans la sortie des tests
        pass


class _Serveur(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address) -> None:  # un client parti avant la réponse : sans importance
        pass


class FauxService:
    """Un service d'IA de comédie, sur l'ordinateur lui-même.

    Il renvoie les réponses prévues par le test, dans l'ordre, et note chaque demande reçue. Sans
    réponse prévue, il répond comme un vrai service : la liste des modèles, ou la réponse du modèle.
    """

    def __init__(self, certificat: tuple[str, str] | None = None) -> None:
        self.recues: list[Demande] = []
        self.prevues: collections.deque[Prevue] = collections.deque()
        self.serveur = _Serveur(("127.0.0.1", 0), _Gestionnaire)
        self.serveur.faux = self
        self.protocole = "http"
        if certificat is not None:
            contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            contexte.load_cert_chain(*certificat)
            self.serveur.socket = contexte.wrap_socket(self.serveur.socket, server_side=True)
            self.protocole = "https"
        threading.Thread(target=self.serveur.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    @property
    def port(self) -> int:
        return self.serveur.server_address[1]

    @property
    def adresse(self) -> str:
        return f"{self.protocole}://127.0.0.1:{self.port}/v1"

    def prevoir(self, code: int = 200, corps=b"", en_tetes: dict[str, str] | None = None, attente: float = 0.0,
                couper: bool = False) -> None:
        """Prévoit la prochaine réponse. ``corps`` est écrit en JSON s'il n'est pas déjà une suite d'octets."""
        if not isinstance(corps, bytes):
            corps = en_json(corps)
        self.prevues.append(Prevue(code, corps, dict(en_tetes or {}), attente, couper))

    @staticmethod
    def reponse_normale(chemin: str) -> Prevue:
        if chemin.endswith("/models"):
            return Prevue(200, en_json(LISTE_DES_MODELES), {"Content-Type": "application/json"})
        return Prevue(200, en_json(reponse_du_modele()), {"Content-Type": "application/json"})

    def arreter(self) -> None:
        self.serveur.shutdown()
        self.serveur.server_close()


@pytest.fixture
def service():
    faux = FauxService()
    yield faux
    faux.arreter()


@pytest.fixture(autouse=True)
def rien_ne_sort(monkeypatch):
    """Aucun test ne joint Internet : une connexion vers une autre machine fait échouer le test.

    L'échec est une ``AssertionError`` : le connecteur ne la prend pas pour une panne de réseau.
    """
    vraie_connexion, vraie_recherche = socket.socket.connect, socket.getaddrinfo

    def connecter(prise, destination):
        assert isinstance(destination, tuple) and destination[0] in ("127.0.0.1", "::1"), \
            f"connexion tentée vers {destination!r}"
        return vraie_connexion(prise, destination)

    def chercher(hote, *arguments, **options):
        assert hote in ("127.0.0.1", "::1", "localhost"), f"nom cherché sur le réseau : {hote!r}"
        return vraie_recherche(hote, *arguments, **options)

    monkeypatch.setattr(socket.socket, "connect", connecter)
    monkeypatch.setattr(socket, "getaddrinfo", chercher)
    for nom in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(nom, raising=False)
        monkeypatch.delenv(nom.upper(), raising=False)


def refus(genre: str, *morceaux: str, code: int | None = None):
    """Attend une ``ErreurService`` de ce genre, dont le message contient ces morceaux et jamais la clé."""
    return _Refus(genre, morceaux, code)


class _Refus:
    def __init__(self, genre: str, morceaux: tuple[str, ...], code: int | None) -> None:
        self.genre, self.morceaux, self.code = genre, morceaux, code
        self.attente = pytest.raises(ErreurService)

    def __enter__(self):
        self.capture = self.attente.__enter__()
        return self.capture

    def __exit__(self, *arguments) -> bool:
        resultat = self.attente.__exit__(*arguments)
        erreur = self.capture.value
        message = str(erreur)
        assert erreur.genre == self.genre, f"{erreur.genre} : {message}"
        assert erreur.code == self.code, f"code {erreur.code} : {message}"
        for morceau in self.morceaux:
            assert morceau in message, message
        assert CLE not in message and CLE not in repr(erreur)
        assert message.endswith((".", "»", "…")), message
        return resultat


# ------------------------------------------------------------------ l'adresse
def test_l_adresse_par_defaut_est_celle_de_nvidia():
    assert connecteur.ADRESSE_PAR_DEFAUT == "https://integrate.api.nvidia.com/v1"
    assert (connecteur.DELAI, connecteur.ENVOIS) == (60.0, 3)


@pytest.mark.parametrize("adresse", [
    "", "   ", "integrate.api.nvidia.com/v1", "ftp://service.example/v1", "file:///etc/passwd", "https://",
    "https://service .example/v1", "https://service.example:abc/v1", "https://exémple.example/v1",
    "https://service.example/v1\nX-Autre: 1", "https://[::1/v1"])
def test_une_adresse_absente_ou_mal_ecrite_est_refusee_sans_connexion(adresse):
    for essai in (lambda: lister_les_modeles(adresse), lambda: demander(adresse, CLE, MODELE, CONVERSATION)):
        with refus(connecteur.ADRESSE):
            essai()


@pytest.mark.parametrize("adresse, morceau", [
    ("https://utilisateur:secret@service.example/v1", "ni identifiant ni mot de passe"),
    ("https://service.example/v1?version=2", "« ? »"),
    ("https://service.example/v1#haut", "« # »"),
    ("https://service.example/v1?", "« ? »"),
])
def test_une_adresse_qui_contient_autre_chose_qu_une_adresse_est_refusee(adresse, morceau):
    with refus(connecteur.ADRESSE, morceau):
        demander(adresse, CLE, MODELE, CONVERSATION)


def test_sans_https_rien_ne_part_vers_une_autre_machine():
    """La clé et le texte ne circulent pas sans protection : l'adresse est refusée avant toute connexion."""
    for essai in (lambda: lister_les_modeles("http://service.example/v1", CLE),
                  lambda: demander("http://service.example/v1", CLE, MODELE, CONVERSATION)):
        with refus(connecteur.ADRESSE, "« https:// »", "sans protection"):
            essai()


@pytest.mark.parametrize("ecriture", [
    "{base}", "  {base}  ", "{base}/", "{base}//", "{base}/chat/completions", "{base}/models", "{base}/models/"])
def test_l_adresse_est_nettoyee(service, ecriture):
    """Espaces autour, barre finale, nom de la demande recopié d'une documentation : l'adresse reste comprise."""
    adresse = ecriture.format(base=service.adresse)
    assert lister_les_modeles(adresse) == [MODELE, "essai/modele-2"]
    assert demander(adresse, CLE, MODELE, CONVERSATION).texte == TRADUCTION
    assert [(demande.methode, demande.chemin) for demande in service.recues] == [
        ("GET", "/v1/models"), ("POST", "/v1/chat/completions")]


def test_l_ordinateur_lui_meme_est_joint_par_son_nom(service):
    """« http:// » est admis vers l'ordinateur lui-même : un modèle installé sur le PC n'a pas de certificat."""
    assert lister_les_modeles(f"http://localhost:{service.port}/v1") == [MODELE, "essai/modele-2"]


# ------------------------------------------------------------------ la liste des modèles
def test_la_liste_des_modeles(service):
    service.prevoir(corps={"object": "list", "data": [{"id": "b/modele"}, {"id": "A/modele"}, {"id": "b/modele"},
                                                      {"id": " c/modele "}, {"id": ""}, {"nom": "sans id"}]})
    assert lister_les_modeles(service.adresse) == ["A/modele", "b/modele", "c/modele"]
    demande, = service.recues
    assert (demande.methode, demande.chemin, demande.corps) == ("GET", "/v1/models", b"")
    assert "authorization" not in demande.en_tetes  # sans clé, comme chez NVIDIA
    assert demande.en_tetes["accept"] == "application/json"
    assert demande.en_tetes["user-agent"] == f"TraducteurJuridique/{__version__}"


def test_la_liste_des_modeles_avec_la_cle(service):
    lister_les_modeles(service.adresse, CLE)
    assert service.recues[0].en_tetes["authorization"] == f"Bearer {CLE}"


@pytest.mark.parametrize("corps, attendu", [({"data": []}, []), ([{"id": "seul/modele"}], ["seul/modele"])])
def test_la_liste_des_modeles_vide_ou_sans_enveloppe(service, corps, attendu):
    service.prevoir(corps=corps)
    assert lister_les_modeles(service.adresse) == attendu


@pytest.mark.parametrize("corps", [b"<html><body>Bienvenue</body></html>", b"", {"data": "modele"},
                                   {"data": [{"nom": "sans id"}]}, "une phrase", 12])
def test_une_liste_des_modeles_illisible(service, corps):
    service.prevoir(corps=corps)
    with refus(connecteur.REPONSE, "illisible", "« Paramètres »"):
        lister_les_modeles(service.adresse)


def test_une_adresse_qui_n_est_pas_celle_d_un_service_d_ia(service):
    service.prevoir(404, b"<html>Page introuvable</html>")
    with refus(connecteur.ADRESSE, "« /v1 »", code=404):
        lister_les_modeles(service.adresse, CLE)


# ------------------------------------------------------------------ une demande au modèle
def test_une_demande_au_modele(service):
    reponse = demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert (reponse.texte, reponse.modele, reponse.fin, reponse.envois) == (TRADUCTION, MODELE, "stop", 1)
    assert not reponse.coupee and 0 <= reponse.duree < 5
    demande, = service.recues
    assert (demande.methode, demande.chemin) == ("POST", "/v1/chat/completions")
    assert demande.json == {"model": MODELE, "messages": CONVERSATION, "stream": False, "temperature": 0.0}
    assert demande.en_tetes["authorization"] == f"Bearer {CLE}"
    assert demande.en_tetes["content-type"] == "application/json"
    assert demande.en_tetes["accept"] == "application/json"
    assert demande.en_tetes["user-agent"] == f"TraducteurJuridique/{__version__}"


def test_un_texte_arabe_fait_l_aller_et_le_retour(service):
    conversation = [{"role": "user", "content": "تُرجم إلى الفرنسية : العقد شريعة المتعاقدين. « é à ç œ »"}]
    service.prevoir(corps=reponse_du_modele("Le contrat fait la loi des parties. « é à ç œ » ١٠٦"))
    reponse = demander(service.adresse, CLE, MODELE, conversation)
    assert reponse.texte == "Le contrat fait la loi des parties. « é à ç œ » ١٠٦"
    assert service.recues[0].json["messages"] == conversation
    assert service.recues[0].corps.isascii()  # lettres arabes et accentuées écrites en \uXXXX


def test_les_reglages_de_la_demande(service):
    demander(service.adresse, CLE, f"  {MODELE} ", CONVERSATION, temperature=None, longueur_maximale=256)
    assert service.recues[0].json == {"model": MODELE, "messages": CONVERSATION, "stream": False, "max_tokens": 256}


def test_le_nom_du_modele_est_celui_que_le_service_donne(service):
    service.prevoir(corps=reponse_du_modele(modele="essai/modele-1-2026-11"))
    assert demander(service.adresse, CLE, MODELE, CONVERSATION).modele == "essai/modele-1-2026-11"
    sans_nom = reponse_du_modele()
    del sans_nom["model"]
    service.prevoir(corps=sans_nom)
    assert demander(service.adresse, CLE, MODELE, CONVERSATION).modele == MODELE


def test_une_reponse_en_plusieurs_morceaux(service):
    service.prevoir(corps=reponse_du_modele([{"type": "text", "text": "العقد "}, {"type": "image", "url": "…"},
                                             "شريعة ", {"type": "text", "text": "المتعاقدين."}]))
    assert demander(service.adresse, CLE, MODELE, CONVERSATION).texte == TRADUCTION


def test_une_reponse_coupee_est_signalee(service):
    service.prevoir(corps=reponse_du_modele("العقد شريعة", fin="length"))
    reponse = demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert reponse.texte == "العقد شريعة" and reponse.fin == "length" and reponse.coupee


@pytest.mark.parametrize("contenu", [None, "", "  \n ", [], [{"type": "image"}]])
def test_un_modele_qui_ne_repond_rien(service, contenu):
    service.prevoir(corps=reponse_du_modele(contenu))
    with refus(connecteur.REPONSE, "rien répondu"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    service.prevoir(corps=reponse_du_modele(contenu, fin="length"))
    with refus(connecteur.REPONSE, "longueur maximale", "moins de phrases"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


@pytest.mark.parametrize("corps", [
    b"<html><body>Bienvenue</body></html>", b"", b"{", b"\xff\xfe\x00\x01", [], {}, {"choices": []},
    {"choices": [{}]}, {"choices": [{"message": "du texte"}]}, {"choices": "du texte"}, "du texte"])
def test_une_reponse_illisible(service, corps):
    service.prevoir(corps=corps)
    with refus(connecteur.REPONSE, "illisible", "« Paramètres »"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


def test_une_panne_annoncee_dans_une_reponse_acceptee(service):
    """Certains services répondent « 200 » et écrivent leur panne dans la réponse."""
    service.prevoir(corps={"error": {"message": "The model is overloaded."}})
    with refus(connecteur.PANNE, "a signalé une erreur", "« The model is overloaded. »"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


def test_une_reponse_trop_longue(service, monkeypatch):
    monkeypatch.setattr(connecteur, "TAILLE_MAXIMALE", 1000)
    service.prevoir(corps=reponse_du_modele("ا" * 2000))
    with refus(connecteur.REPONSE, "trop longue"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert demander(service.adresse, CLE, MODELE, CONVERSATION).texte == TRADUCTION  # sous la limite : lue


# ------------------------------------------------------------------ les refus du service
@pytest.mark.parametrize("code, genre, morceau", [
    (401, connecteur.CLE, "a refusé la clé"),
    (402, connecteur.ACCES, "crédit"),
    (403, connecteur.ACCES, "refuse l’accès"),
    (404, connecteur.MODELE, f"« {MODELE} »"),
    (405, connecteur.MODELE, f"« {MODELE} »"),
    (408, connecteur.DELAI_DEPASSE, "trop de temps"),
    (413, connecteur.DEMANDE, "trop long"),
    (400, connecteur.DEMANDE, "(erreur 400)"),
    (418, connecteur.DEMANDE, "(erreur 418)"),
    (422, connecteur.DEMANDE, "(erreur 422)"),
    (500, connecteur.PANNE, "(erreur 500)"),
    (502, connecteur.PANNE, "(erreur 502)"),
    (504, connecteur.DELAI_DEPASSE, "trop de temps"),
    (524, connecteur.DELAI_DEPASSE, "trop de temps"),
])
def test_un_refus_du_service(service, code, genre, morceau):
    service.prevoir(code, {"error": {"message": "Refused."}})
    with refus(genre, morceau, code=code):
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert len(service.recues) == 1  # un refus n'est pas renvoyé


def test_la_cle_refusee(service):
    service.prevoir(401, {"status": 401, "title": "Unauthorized", "detail": f"Bad key: {CLE}"})
    with refus(connecteur.CLE, "Vérifiez la clé dans « Paramètres »", code=401) as capture:
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert "Bad key" not in str(capture.value)  # ce message se suffit : rien n'est cité du service


@pytest.mark.parametrize("code", [401, 403])
def test_un_service_qui_demande_une_cle_alors_qu_aucune_n_est_saisie(service, code):
    """Sans clé, le message ne dit pas « clé refusée » : il demande de la saisir."""
    for essai in (lambda: lister_les_modeles(service.adresse),
                  lambda: demander(service.adresse, "", MODELE, CONVERSATION)):
        service.prevoir(code, {"error": {"message": "Missing bearer token"}})
        with refus(connecteur.CLE, "Ce service demande une clé", "Saisissez-la dans « Paramètres »", code=code):
            essai()


@pytest.mark.parametrize("corps, cite", [
    ({"error": {"message": "Unknown parameter:  'temperatur'.\n", "type": "invalid_request_error"}},
     "« Unknown parameter: 'temperatur'. »"),
    ({"error": "Model is loading"}, "« Model is loading »"),
    ({"status": 400, "title": "Bad Request", "detail": "Inference error"}, "« Inference error »"),
    ({"detail": [{"loc": ["body", "model"], "msg": "field required"}, {"msg": "value is not a valid list"}]},
     "« field required ; value is not a valid list »"),
    ({"message": "Not allowed"}, "« Not allowed »"),
    ({"title": "Bad Request"}, "« Bad Request »"),
    (b"Requete refusee", "« Requete refusee »"),
])
def test_ce_que_le_service_dit_de_son_refus_est_cite(service, corps, cite):
    service.prevoir(400, corps)
    with refus(connecteur.DEMANDE, "Le service a refusé la demande (erreur 400). Réponse du service : " + cite,
               code=400):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


@pytest.mark.parametrize("corps", [b"<html><body><h1>400 Bad Request</h1></body></html>", b"", {"error": 12},
                                   {"error": {"code": 7}}, [1, 2], {"detail": {"motif": "x"}}])
def test_un_refus_sans_explication_lisible(service, corps):
    service.prevoir(400, corps)
    with refus(connecteur.DEMANDE, code=400) as capture:
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert str(capture.value) == "Le service a refusé la demande (erreur 400)."


def test_la_cle_n_est_jamais_recopiee_dans_un_message(service):
    """Certains services recopient la clé dans leur refus : elle est masquée."""
    service.prevoir(403, {"error": {"message": f"Key {CLE} is not allowed to use this model."}})
    with refus(connecteur.ACCES, "« Key ••• is not allowed to use this model. »", code=403):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


def test_une_longue_explication_est_abregee(service):
    service.prevoir(400, {"error": {"message": "mot " * 200}})
    with refus(connecteur.DEMANDE, code=400) as capture:
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    message = str(capture.value)
    assert message.endswith("mot mot… »") and len(message) < 300


def test_le_modele_inconnu_du_service(service):
    service.prevoir(404, {"status": 404, "title": "Not Found", "detail": "Function not found for account"})
    with refus(connecteur.MODELE, f"ne connaît pas le modèle « {MODELE} »", "« Function not found for account »",
               code=404):
        demander(service.adresse, CLE, MODELE, CONVERSATION)


def test_une_redirection_n_est_pas_suivie(service):
    """Le service répond « allez à une autre adresse » : la clé et le texte n'y vont pas."""
    autre = FauxService()
    try:
        for code in (301, 302, 303, 307, 308):
            service.prevoir(code, en_tetes={"Location": f"{autre.adresse}/chat/completions"})
            with refus(connecteur.ADRESSE, f"vers une autre adresse ({autre.adresse}/chat/completions)",
                       "Corrigez l’adresse", code=code):
                demander(service.adresse, CLE, MODELE, CONVERSATION)
        service.prevoir(302, en_tetes={"Location": f"{autre.adresse}/models"})
        with refus(connecteur.ADRESSE, "vers une autre adresse", code=302):
            lister_les_modeles(service.adresse, CLE)
        assert autre.recues == [] and len(service.recues) == 6
    finally:
        autre.arreter()


# ------------------------------------------------------------------ trop de demandes
def attentes_notees() -> tuple[list[float], object]:
    """Une fausse attente : elle note les durées demandées et ne fait pas attendre le test."""
    durees: list[float] = []
    return durees, durees.append


@pytest.mark.parametrize("indication, attendue", [
    ("2", 2.0), ("1.5", 1.5), (None, 2.0), ("0", 0.0), ("-3", 0.0), ("3600", 30.0), ("bientôt", 2.0), ("nan", 2.0),
    ("Wed, 21 Oct 2015 07:28:00 GMT", 0.0), ("Wed, 21 Oct 2099 07:28:00 GMT", 30.0)])
def test_trop_de_demandes_la_demande_est_renvoyee_apres_l_attente_indiquee(service, indication, attendue):
    service.prevoir(429, {"error": {"message": "Too many requests"}},
                    en_tetes={"Retry-After": indication} if indication is not None else None)
    durees, attendre = attentes_notees()
    reponse = demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre)
    assert (reponse.texte, reponse.envois) == (TRADUCTION, 2)
    assert sum(durees) == pytest.approx(attendue) and all(0 < duree <= 0.25 for duree in durees)
    assert len(service.recues) == 2 and service.recues[0].corps == service.recues[1].corps


def test_sans_indication_l_attente_double(service):
    service.prevoir(429)
    service.prevoir(429)
    durees, attendre = attentes_notees()
    assert demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre).envois == 3
    assert sum(durees) == pytest.approx(2.0 + 4.0)


def test_trop_de_demandes_trois_envois_au_plus(service):
    for _ in range(4):
        service.prevoir(429, en_tetes={"Retry-After": "1"})
    durees, attendre = attentes_notees()
    with refus(connecteur.DEBIT, "trop de demandes", "Attendez une minute", code=429):
        demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre)
    assert len(service.recues) == 3 and sum(durees) == pytest.approx(2.0)  # pas d'attente après le dernier envoi


def test_un_service_surcharge_est_reessaye_lui_aussi(service):
    service.prevoir(503, b"Service Unavailable")
    durees, attendre = attentes_notees()
    assert demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre).envois == 2
    for _ in range(3):
        service.prevoir(503)
    with refus(connecteur.PANNE, "(erreur 503)", code=503):
        demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre)
    assert len(service.recues) == 2 + 3 and sum(durees) == pytest.approx(2.0 + 2.0 + 4.0)


def test_un_seul_envoi_quand_on_le_demande(service):
    service.prevoir(429)
    durees, attendre = attentes_notees()
    with refus(connecteur.DEBIT, code=429):
        demander(service.adresse, CLE, MODELE, CONVERSATION, envois=1, attendre=attendre)
    assert len(service.recues) == 1 and durees == []


def test_la_liste_des_modeles_est_renvoyee_elle_aussi(service):
    service.prevoir(429, en_tetes={"Retry-After": "1"})
    durees, attendre = attentes_notees()
    assert lister_les_modeles(service.adresse, attendre=attendre) == [MODELE, "essai/modele-2"]
    assert sum(durees) == pytest.approx(1.0) and len(service.recues) == 2


# ------------------------------------------------------------------ lenteur et pannes de connexion
def test_un_service_trop_lent(service):
    service.prevoir(attente=1.5, corps=reponse_du_modele())
    debut = time.monotonic()
    with refus(connecteur.DELAI_DEPASSE, "n’a pas répondu en 0,3 seconde", "texte plus court"):
        demander(service.adresse, CLE, MODELE, CONVERSATION, delai=0.3)
    assert time.monotonic() - debut < 1.2
    assert len(service.recues) == 1  # une demande restée sans réponse n'est pas renvoyée


def test_le_delai_ordinaire_est_ecrit_en_clair():
    assert str(connecteur._injoignable(TimeoutError(), connecteur.DELAI)).startswith(
        "Le service n’a pas répondu en 60 secondes.")


def test_aucun_service_a_cette_adresse():
    with socket.socket() as prise:  # un port libre : personne n'y écoute une fois la prise refermée
        prise.bind(("127.0.0.1", 0))
        port = prise.getsockname()[1]
    with refus(connecteur.CONNEXION, "Aucun service ne répond à cette adresse"):
        demander(f"http://127.0.0.1:{port}/v1", CLE, MODELE, CONVERSATION)


def test_sans_internet_le_nom_du_service_est_introuvable(monkeypatch):
    def introuvable(*arguments, **options):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", introuvable)
    for essai in (lambda: lister_les_modeles(AILLEURS), lambda: demander(AILLEURS, CLE, MODELE, CONVERSATION)):
        with refus(connecteur.CONNEXION, "introuvable", "connexion à Internet"):
            essai()


@pytest.mark.parametrize("numero", [errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN])
def test_sans_reseau(monkeypatch, numero):
    def injoignable(prise, destination):
        raise OSError(numero, "réseau injoignable")

    monkeypatch.setattr(socket, "getaddrinfo", lambda *arguments, **options: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))])
    monkeypatch.setattr(socket.socket, "connect", injoignable)
    with refus(connecteur.CONNEXION, "introuvable", "connexion à Internet"):
        demander(AILLEURS, CLE, MODELE, CONVERSATION)


def test_une_connexion_coupee(service):
    service.prevoir(couper=True)
    with refus(connecteur.CONNEXION, "a été coupée"):
        demander(service.adresse, CLE, MODELE, CONVERSATION)
    assert len(service.recues) == 1


@pytest.mark.parametrize("panne", [
    ConnectionResetError(errno.ECONNRESET, "Connection reset by peer"),
    ssl.SSLZeroReturnError(6, "TLS/SSL connection has been closed (EOF)"),
    ssl.SSLEOFError(8, "EOF occurred in violation of protocol"),
    urllib.error.URLError(ssl.SSLZeroReturnError(6, "TLS/SSL connection has been closed (EOF)")),
    OSError("panne inconnue")])
def test_une_connexion_coupee_en_chemin(monkeypatch, panne):
    """Un pare-feu ou un réseau qui bloque le service ferme la connexion : ce n'est pas une adresse fausse."""
    monkeypatch.setattr(connecteur, "_ouvreur", lambda url, local: _OuvreurEnPanne(panne))
    with refus(connecteur.CONNEXION, "a été coupée", "connexion à Internet", "un pare-feu ou le réseau"):
        demander(AILLEURS, CLE, MODELE, CONVERSATION)


def test_une_connexion_chiffree_vers_un_service_qui_ne_l_est_pas(service):
    """« https:// » vers un service qui répond en clair : la connexion échoue, et la demande n'est pas partie."""
    with refus(connecteur.CONNEXION, "connexion sécurisée", "a échoué"):
        demander(service.adresse.replace("http://", "https://"), CLE, MODELE, CONVERSATION)
    assert service.recues == []


def test_un_nom_de_machine_impossible():
    with refus(connecteur.ADRESSE, "n’est pas valable"):
        connecteur._envoyer(_OuvreurEnPanne(UnicodeError("label empty or too long")), "GET", AILLEURS, "", None, 1)


class _OuvreurEnPanne:
    """Un ouvreur de connexions qui échoue toujours de la même façon."""

    def __init__(self, panne: Exception) -> None:
        self.panne = panne

    def open(self, requete, timeout=None):
        raise self.panne


# ------------------------------------------------------------------ le certificat du service
def test_le_certificat_et_le_nom_du_service_sont_verifies():
    contexte = connecteur.contexte_tls()
    assert contexte.verify_mode == ssl.CERT_REQUIRED and contexte.check_hostname


def test_un_certificat_refuse_est_explique(monkeypatch):
    panne = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
    monkeypatch.setattr(connecteur, "_ouvreur", lambda url, local: _OuvreurEnPanne(panne))
    with refus(connecteur.CONNEXION, "certificat", "la date et l’heure", "Rien n’a été envoyé."):
        demander(AILLEURS, CLE, MODELE, CONVERSATION)


def fabriquer_un_certificat(dossier, noms: str) -> tuple[str, str]:
    """Fabrique un certificat d'essai, valable pour ``noms``, qu'aucune autorité ne signe : (certificat, clé)."""
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("commande « openssl » absente : pas de certificat d'essai")
    fichier, cle = dossier / "certificat.pem", dossier / "cle.pem"
    fabrication = subprocess.run(
        [openssl, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-days", "2",
         "-keyout", str(cle), "-out", str(fichier), "-subj", "/CN=essai", "-addext", f"subjectAltName={noms}"],
        capture_output=True)
    if fabrication.returncode != 0:
        pytest.skip("cette version d'« openssl » ne fabrique pas le certificat d'essai")
    return str(fichier), str(cle)


@pytest.fixture(scope="session")
def certificat(tmp_path_factory) -> tuple[str, str]:
    """Un certificat d'essai fait pour l'ordinateur lui-même."""
    return fabriquer_un_certificat(tmp_path_factory.mktemp("certificat"), "DNS:localhost,IP:127.0.0.1")


@pytest.fixture
def service_chiffre(certificat):
    faux = FauxService(certificat)
    yield faux
    faux.arreter()


def test_un_service_au_certificat_inconnu_est_refuse(service_chiffre):
    """Essai réel : la connexion chiffrée est refusée, et ni la clé ni le texte ne partent."""
    assert service_chiffre.adresse.startswith("https://")
    for essai in (lambda: lister_les_modeles(service_chiffre.adresse, CLE),
                  lambda: demander(service_chiffre.adresse, CLE, MODELE, CONVERSATION)):
        with refus(connecteur.CONNEXION, "certificat", "Rien n’a été envoyé."):
            essai()
    assert service_chiffre.recues == []


def test_un_service_au_certificat_reconnu_est_accepte(service_chiffre, certificat, monkeypatch):
    """Essai réel d'une connexion chiffrée : le certificat d'essai est reconnu, le temps du test."""
    monkeypatch.setattr(connecteur, "contexte_tls", lambda: ssl.create_default_context(cafile=certificat[0]))
    assert lister_les_modeles(service_chiffre.adresse) == [MODELE, "essai/modele-2"]
    assert demander(service_chiffre.adresse, CLE, MODELE, CONVERSATION).texte == TRADUCTION
    assert service_chiffre.recues[1].en_tetes["authorization"] == f"Bearer {CLE}"


def test_le_nom_du_service_est_verifie_lui_aussi(tmp_path, monkeypatch):
    """Essai réel : un certificat reconnu, mais fait pour une autre machine, est refusé."""
    certificat = fabriquer_un_certificat(tmp_path, "DNS:autre.example")
    faux = FauxService(certificat)
    try:
        monkeypatch.setattr(connecteur, "contexte_tls", lambda: ssl.create_default_context(cafile=certificat[0]))
        with refus(connecteur.CONNEXION, "certificat", "Rien n’a été envoyé."):
            demander(faux.adresse, CLE, MODELE, CONVERSATION)
        assert faux.recues == []
    finally:
        faux.arreter()


# ------------------------------------------------------------------ la clé
def test_sans_cle_rien_ne_part_vers_un_service_distant():
    with refus(connecteur.CLE, "Aucune clé", "« Paramètres »"):
        demander(AILLEURS, "  ", MODELE, CONVERSATION)


def test_un_modele_installe_sur_l_ordinateur_n_a_pas_besoin_de_cle(service):
    assert demander(service.adresse, "", MODELE, CONVERSATION).texte == TRADUCTION
    assert "authorization" not in service.recues[0].en_tetes


@pytest.mark.parametrize("cle", ["nvapi-abc def", "nvapi-abc\ndef", "nvapi-abc\r\nX-Autre: 1", "nvapi-clé",
                                 "nvapi-\u200babc", "nvapi-abc\x00"])
def test_une_cle_mal_copiee_est_refusee_sans_connexion(service, cle):
    for essai in (lambda: lister_les_modeles(service.adresse, cle),
                  lambda: demander(service.adresse, cle, MODELE, CONVERSATION)):
        with pytest.raises(ErreurService) as capture:
            essai()
        assert capture.value.genre == connecteur.CLE and "Copiez-la de nouveau" in str(capture.value)
        assert cle not in str(capture.value)
    assert service.recues == []


def test_les_espaces_autour_de_la_cle_sont_retires(service):
    demander(service.adresse, f"  {CLE}\n", MODELE, CONVERSATION)
    assert service.recues[0].en_tetes["authorization"] == f"Bearer {CLE}"


# ------------------------------------------------------------------ le modèle et la conversation
@pytest.mark.parametrize("modele", ["", "   "])
def test_sans_modele_rien_ne_part(service, modele):
    with refus(connecteur.MODELE, "Aucun modèle", "« Paramètres »"):
        demander(service.adresse, CLE, modele, CONVERSATION)
    assert service.recues == []


@pytest.mark.parametrize("conversation", [
    [], [{"role": "utilisateur", "content": "Bonjour"}], [{"role": "user"}], [{"content": "Bonjour"}],
    [{"role": "user", "content": None}], [{"role": "user", "content": ["Bonjour"]}]])
def test_une_conversation_mal_formee_est_une_erreur_du_programme(service, conversation):
    with pytest.raises(ValueError, match="conversation"):
        demander(service.adresse, CLE, MODELE, conversation)
    assert service.recues == []


def test_la_conversation_envoyee_ne_contient_que_les_roles_et_les_textes(service):
    conversation = [{"role": "system", "content": "Consigne", "note": "privée"},
                    {"role": "user", "content": "Demande"}, {"role": "assistant", "content": "Réponse"},
                    {"role": "user", "content": ""}]
    demander(service.adresse, CLE, MODELE, conversation)
    assert service.recues[0].json["messages"] == [
        {"role": "system", "content": "Consigne"}, {"role": "user", "content": "Demande"},
        {"role": "assistant", "content": "Réponse"}, {"role": "user", "content": ""}]


# ------------------------------------------------------------------ l'arrêt
def test_un_arret_demande_avant_l_envoi(service):
    with refus(connecteur.ARRET, "a été arrêtée"):
        demander(service.adresse, CLE, MODELE, CONVERSATION, arret=lambda: True)
    with refus(connecteur.ARRET):
        lister_les_modeles(service.adresse, arret=lambda: True)
    assert service.recues == []


def test_un_arret_demande_pendant_l_attente(service):
    for _ in range(3):
        service.prevoir(429, en_tetes={"Retry-After": "20"})
    durees, attendre = attentes_notees()
    reponses = iter([False, False, False, True])  # avant l'envoi, puis au début de chaque tranche d'attente
    with refus(connecteur.ARRET, "a été arrêtée"):
        demander(service.adresse, CLE, MODELE, CONVERSATION, attendre=attendre, arret=lambda: next(reponses))
    assert len(service.recues) == 1 and sum(durees) == pytest.approx(0.5)


# ------------------------------------------------------------------ le proxy
def test_l_ordinateur_lui_meme_est_joint_sans_proxy(service, monkeypatch):
    """Le proxy du système sert pour Internet. Il ne sert jamais pour un modèle installé sur le PC."""
    for nom in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(nom, "http://127.0.0.1:9")  # un proxy qui n'existe pas
    assert lister_les_modeles(service.adresse) == [MODELE, "essai/modele-2"]
    assert demander(service.adresse, CLE, MODELE, CONVERSATION).texte == TRADUCTION


# ------------------------------------------------------------------ l'indépendance
def test_le_connecteur_ne_charge_ni_le_moteur_ni_l_interface():
    """Seule la bibliothèque standard de Python est employée : ni Qt, ni « regex », ni le reste de l'application."""
    script = ("import sys, traducteur.ia.service; "
              "print(sorted(nom for nom in sys.modules if nom.split('.')[0] in ('PySide6', 'regex', 'traducteur')))")
    sortie = subprocess.run([sys.executable, "-c", script], cwd=RACINE, capture_output=True, text=True, check=True)
    assert sortie.stdout.strip() == "['traducteur', 'traducteur.ia', 'traducteur.ia.service']"
