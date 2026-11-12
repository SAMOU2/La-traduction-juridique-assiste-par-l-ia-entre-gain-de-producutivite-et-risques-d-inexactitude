"""Import et export des textes : fichiers .txt, .docx et .doc (Word).

Aucune bibliothèque supplémentaire n'est nécessaire :

* un fichier .docx est une archive ZIP qui contient le texte du document au
  format XML ;
* un fichier .doc (Word 97 à 2003) est un fichier binaire « composé » : le
  texte du document y est retrouvé grâce à sa table des morceaux de texte.

``lire`` renvoie le texte d'un fichier, un paragraphe par ligne. ``ecrire``
enregistre un texte dans un fichier .txt ou .docx (l'écriture de l'ancien
format .doc n'est pas proposée). Dans un document Word, les paragraphes arabes
sont écrits de droite à gauche.
"""

from __future__ import annotations

import io
import struct
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import regex

from .glossaire import decoder
from .langues import AR, deviner_langue

#: Formats proposés dans les fenêtres « Importer » et « Exporter ».
FILTRE_IMPORT = "Textes (*.txt *.docx *.doc);;Tous les fichiers (*)"
FILTRES_EXPORT = {".docx": "Document Word (*.docx)", ".txt": "Texte brut (*.txt)"}

#: Taille maximale du texte d'un document Word, une fois décompressé (protection contre les archives piégées).
TAILLE_MAXIMALE = 64 * 1024 * 1024

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_ZIP = b"PK\x03\x04"
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_CONTROLE = regex.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
#: Caractères retirés d'un texte avant son enregistrement (un fichier XML, donc un document
#: .docx, ne peut pas les contenir).
_INTERDIT_DANS_UN_TEXTE = regex.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uFFFE\uFFFF]")
_ARABE = regex.compile(r"\p{Arabic}")
_LATIN = regex.compile(r"\p{Latin}")


class ErreurDocument(Exception):
    """Le fichier ne peut pas être lu ou écrit."""


# ------------------------------------------------------------------ lecture
def lire(chemin: str | Path) -> str:
    """Renvoie le texte d'un fichier .txt, .docx ou .doc, un paragraphe par ligne."""
    chemin = Path(chemin)
    try:
        brut = chemin.read_bytes()
    except OSError as erreur:
        raise ErreurDocument(f"Impossible de lire le fichier « {chemin.name} » : {erreur.strerror or erreur}.") \
            from erreur
    if brut.startswith(_ZIP):
        texte = _lire_docx(brut, chemin.name)
    elif brut.startswith(_OLE):
        texte = _lire_doc(brut, chemin.name)
    elif brut.startswith(b"%PDF"):
        raise ErreurDocument(f"« {chemin.name} » est un fichier PDF. Copiez son texte et collez-le dans la zone "
                             "de texte, ou enregistrez-le au format .docx ou .txt.")
    elif brut.lstrip().startswith(b"{\\rtf"):
        raise ErreurDocument(f"« {chemin.name} » est au format RTF. Ouvrez-le dans Word et enregistrez-le au "
                             "format .docx ou .txt.")
    else:
        texte, _ = decoder(brut)
        if _CONTROLE.search(texte[:4000]):
            raise ErreurDocument(f"« {chemin.name} » n'est pas un fichier de texte. "
                                 "Les formats lus sont .txt, .docx et .doc.")
    lignes = [ligne.rstrip() for ligne in texte.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lignes).strip("\n")


def _lire_docx(brut: bytes, nom: str) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(brut)) as archive:
            try:
                informations = archive.getinfo("word/document.xml")
            except KeyError:
                raise ErreurDocument(
                    f"« {nom} » n'est pas un document Word. Les formats lus sont .txt, .docx et .doc.") from None
            if informations.file_size > TAILLE_MAXIMALE:
                raise ErreurDocument(f"« {nom} » est trop volumineux pour être importé.")
            racine = ElementTree.fromstring(archive.read(informations))
    except (zipfile.BadZipFile, ElementTree.ParseError, RuntimeError, NotImplementedError) as erreur:
        raise ErreurDocument(f"« {nom} » est endommagé ou protégé : il ne peut pas être lu ({erreur}).") from erreur
    corps = racine.find(_W + "body")
    if corps is None:
        raise ErreurDocument(f"« {nom} » ne contient pas de texte.")
    return "\n".join(_paragraphes(corps))


def _paragraphes(conteneur: ElementTree.Element) -> Iterator[str]:
    """Texte des paragraphes d'un document, dans l'ordre ; une ligne de tableau donne une ligne de texte."""
    for element in conteneur:
        if element.tag == _W + "p":
            yield _texte_du_paragraphe(element)
        elif element.tag == _W + "tbl":
            for rangee in element.findall(_W + "tr"):
                yield "\t".join(" ".join(texte for texte in _paragraphes(cellule) if texte)
                                for cellule in rangee.findall(_W + "tc"))
        elif element.tag == _W + "sdt":
            contenu = element.find(_W + "sdtContent")
            if contenu is not None:
                yield from _paragraphes(contenu)
        elif element.tag in (_W + "ins", _W + "customXml", _W + "smartTag"):
            yield from _paragraphes(element)


def _texte_du_paragraphe(paragraphe: ElementTree.Element) -> str:
    morceaux: list[str] = []

    def parcourir(element: ElementTree.Element) -> None:
        for enfant in element:
            if enfant.tag == _W + "t":
                morceaux.append(enfant.text or "")
            elif enfant.tag == _W + "tab":
                morceaux.append("\t")
            elif enfant.tag in (_W + "br", _W + "cr"):
                morceaux.append("\n")
            elif enfant.tag == _W + "noBreakHyphen":
                morceaux.append("-")
            elif enfant.tag in (_W + "del", _W + "moveFrom", _W + "pPr", _W + "rPr", _MC + "Fallback"):
                continue  # texte supprimé (suivi des modifications), mise en forme, copie de secours
            else:
                parcourir(enfant)

    parcourir(paragraphe)
    return "".join(morceaux)


# ------------------------------------------------------------------ lecture de l'ancien format .doc
_CONSEIL_DOCX = ("Ouvrez-le dans Word, choisissez « Enregistrer sous », puis le type « Document Word (*.docx) », "
                 "et importez ici le fichier .docx obtenu.")
_DERNIER_SECTEUR = 0xFFFFFFFA  # au-delà : fin de chaîne, secteur libre…
_SIGNES_DE_WORD = str.maketrans({
    "\r": "\n",  # fin de paragraphe
    "\x0b": "\n", "\x0c": "\n", "\x0e": "\n",  # saut de ligne, de page, de colonne
    "\x1e": "-", "\x1f": "",  # trait d'union insécable, césure facultative
})
_FIN_DE_RANGEE = regex.compile("\x07+")


def _lire_doc(brut: bytes, nom: str) -> str:
    """Texte d'un document Word 97-2003 (.doc)."""
    try:
        flux = _flux_ole(brut)
        document = flux.get("WordDocument")
        if document is None:
            raise ErreurDocument(f"« {nom} » n'est pas un document Word. Les formats lus sont .txt, .docx et .doc.")
        identifiant, version = struct.unpack_from("<HH", document, 0)
        if identifiant != 0xA5EC or version < 0x00C1:
            if identifiant >> 8 not in (0xA5, 0xA6):
                raise ValueError("en-tête de document Word introuvable")
            raise ErreurDocument(f"« {nom} » a été créé par une version très ancienne de Word (avant Word 97).\n\n"
                                 + _CONSEIL_DOCX)
        drapeaux = struct.unpack_from("<H", document, 0x0A)[0]
        if drapeaux & 0x0100:
            raise ErreurDocument(f"« {nom} » est protégé par un mot de passe : il ne peut pas être lu.")
        table = flux["1Table" if drapeaux & 0x0200 else "0Table"]
        longueur_du_texte = struct.unpack_from("<I", document, 0x4C)[0]
        debut_clx, taille_clx = struct.unpack_from("<II", document, 0x01A2)
        texte = _texte_des_morceaux(document, table[debut_clx:debut_clx + taille_clx])
    except (struct.error, IndexError, KeyError, ValueError, OverflowError) as erreur:
        raise ErreurDocument(f"« {nom} » est endommagé : il ne peut pas être lu.\n\n" + _CONSEIL_DOCX) from erreur
    # Le corps du document vient en premier ; notes, en-têtes et pieds de page suivent.
    return _nettoyer_le_texte_de_word(texte[:longueur_du_texte])


def _texte_des_morceaux(document: bytes, clx: bytes) -> str:
    """Assemble le texte à partir de la table des morceaux (« piece table ») du document."""
    position = 0
    while clx[position] == 1:  # blocs de mise en forme, placés avant la table
        position += 3 + struct.unpack_from("<H", clx, position + 1)[0]
    if clx[position] != 2:
        raise ValueError("table des morceaux introuvable")
    taille = struct.unpack_from("<I", clx, position + 1)[0]
    table = clx[position + 5:position + 5 + taille]
    nombre = (taille - 4) // 12
    limites = struct.unpack_from(f"<{nombre + 1}I", table, 0)
    morceaux = []
    for rang in range(nombre):
        adresse = struct.unpack_from("<I", table, 4 * (nombre + 1) + 8 * rang + 2)[0]
        longueur = limites[rang + 1] - limites[rang]
        if adresse & 0x40000000:  # texte sur un octet par caractère (page de codes occidentale)
            debut = (adresse & 0x3FFFFFFF) // 2
            morceaux.append(document[debut:debut + longueur].decode("cp1252", errors="replace"))
        else:  # texte en UTF-16 : c'est le cas des documents en arabe
            debut = adresse & 0x3FFFFFFF
            morceaux.append(document[debut:debut + 2 * longueur].decode("utf-16-le", errors="replace"))
    return "".join(morceaux)


def _nettoyer_le_texte_de_word(texte: str) -> str:
    """Remplace les caractères de service de Word : fins de paragraphe, cellules de tableau, champs."""
    # Champs (liens, numéros de page, zones de formulaire…) : « \x13 code \x14 résultat \x15 », ou
    # « \x13 code \x15 » quand le champ n'a pas de résultat. On retire le code et on garde le résultat.
    # Les champs peuvent s'emboîter : la pile retient, pour chaque champ ouvert, si l'on est dans son code.
    visible: list[str] = []
    champs: list[bool] = []
    codes_ouverts = 0
    for caractere in texte:
        if caractere == "\x13":
            champs.append(True)
            codes_ouverts += 1
        elif caractere == "\x14":
            if champs and champs[-1]:
                champs[-1] = False
                codes_ouverts -= 1
        elif caractere == "\x15":
            if champs and champs.pop():
                codes_ouverts -= 1
        elif not codes_ouverts:
            visible.append(caractere)
    texte = "".join(visible).translate(_SIGNES_DE_WORD)
    # Tableaux : chaque cellule se termine par « \x07 », et chaque rangée par un « \x07 » de plus.
    texte = _FIN_DE_RANGEE.sub(lambda marques: "\t" * (len(marques.group()) - 1) + "\n"
                               if len(marques.group()) > 1 else "\t", texte)
    return _CONTROLE.sub("", texte)


def _flux_ole(brut: bytes) -> dict[str, bytes]:
    """Flux de premier niveau d'un fichier composé (format des fichiers .doc, .xls, .ppt) : nom -> contenu."""
    taille_secteur = 1 << struct.unpack_from("<H", brut, 30)[0]
    taille_mini = 1 << struct.unpack_from("<H", brut, 32)[0]
    premier_repertoire = struct.unpack_from("<I", brut, 48)[0]
    seuil_mini, premier_mini, _, premier_difat, nombre_difat = struct.unpack_from("<5I", brut, 56)
    par_secteur = taille_secteur // 4

    def secteur(numero: int) -> bytes:
        debut = (numero + 1) * taille_secteur
        if debut >= len(brut):
            raise ValueError("fichier tronqué")
        return brut[debut:debut + taille_secteur].ljust(taille_secteur, b"\x00")

    # Table d'allocation : pour chaque secteur, le numéro du secteur suivant du même flux.
    difat = list(struct.unpack_from("<109I", brut, 76))
    suivant = premier_difat
    for _ in range(nombre_difat):
        if suivant >= _DERNIER_SECTEUR:
            break
        valeurs = struct.unpack(f"<{par_secteur}I", secteur(suivant))
        difat.extend(valeurs[:-1])
        suivant = valeurs[-1]
    allocation: list[int] = []
    for numero in difat:
        if numero < _DERNIER_SECTEUR:
            allocation.extend(struct.unpack(f"<{par_secteur}I", secteur(numero)))

    def chaine(premier: int, table: list[int]) -> list[int]:
        numeros: list[int] = []
        while premier < _DERNIER_SECTEUR and len(numeros) <= len(table):
            numeros.append(premier)
            premier = table[premier]
        return numeros

    def lire(premier: int) -> bytes:
        return b"".join(secteur(numero) for numero in chaine(premier, allocation))

    repertoire = lire(premier_repertoire)
    entrees = []
    for debut in range(0, len(repertoire) - 127, 128):
        longueur_nom = struct.unpack_from("<H", repertoire, debut + 64)[0]
        nom = repertoire[debut:debut + max(0, min(longueur_nom, 64) - 2)].decode("utf-16-le", errors="replace")
        gauche, droite, enfant = struct.unpack_from("<3I", repertoire, debut + 68)
        premier, taille = struct.unpack_from("<IQ", repertoire, debut + 116)
        if taille_secteur == 512:
            taille &= 0xFFFFFFFF  # dans cette version du format, la taille tient sur quatre octets
        entrees.append((nom, repertoire[debut + 66], gauche, droite, enfant, premier, taille))

    # Les petits flux sont rangés dans le « mini-flux » de la racine, découpé en mini-secteurs.
    _, _, _, _, enfant_racine, premier_racine, taille_racine = entrees[0]
    mini_flux = lire(premier_racine)[:taille_racine]
    mini_allocation: list[int] = []
    for numero in chaine(premier_mini, allocation):
        mini_allocation.extend(struct.unpack(f"<{par_secteur}I", secteur(numero)))

    flux: dict[str, bytes] = {}
    a_visiter, vus = [enfant_racine], set()
    while a_visiter:  # entrées placées directement sous la racine
        rang = a_visiter.pop()
        if rang >= len(entrees) or rang in vus:
            continue
        vus.add(rang)
        nom, nature, gauche, droite, _, premier, taille = entrees[rang]
        a_visiter.extend((gauche, droite))
        if nature != 2:  # 2 = flux ; 1 = dossier
            continue
        if taille < seuil_mini:
            contenu = b"".join(mini_flux[numero * taille_mini:(numero + 1) * taille_mini]
                               for numero in chaine(premier, mini_allocation))
        else:
            contenu = lire(premier)
        flux[nom] = contenu[:taille]
    return flux


# ------------------------------------------------------------------ écriture
def ecrire(chemin: str | Path, texte: str, langue: str | None = None) -> None:
    """Enregistre ``texte`` dans un fichier .txt ou .docx, selon l'extension de ``chemin``.

    ``langue`` est la langue du texte ; elle fixe le sens d'écriture des
    paragraphes d'un document Word. Sans elle, le sens de chaque paragraphe
    est déduit de son contenu.
    """
    chemin = Path(chemin)
    extension = chemin.suffix.lower()
    # Un demi-caractère isolé (texte collé abîmé) ne peut pas être enregistré : il devient « � ».
    # Les caractères de contrôle sont retirés : un document Word ne peut pas en contenir.
    texte = texte.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    texte = _INTERDIT_DANS_UN_TEXTE.sub("", texte)
    try:
        if extension == ".docx":
            _ecrire_docx(chemin, texte, langue)
        elif extension == ".txt":
            # La marque d'ordre des octets (BOM) permet au Bloc-notes de reconnaître l'arabe.
            chemin.write_text(texte, encoding="utf-8-sig")
        else:
            raise ErreurDocument(f"Le format « {extension or chemin.name} » n'est pas proposé pour l'export : "
                                 "choisissez .docx ou .txt.")
    except OSError as erreur:
        raise ErreurDocument(f"Impossible d'écrire le fichier « {chemin.name} » : {erreur.strerror or erreur}.") \
            from erreur


_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
_RELATIONS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    '</Relationships>'
)
_DEBUT_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
)
# Page A4, marges de 2,5 cm.
_FIN_DOCUMENT = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" '
    'w:gutter="0"/></w:sectPr></w:body></w:document>'
)
_POLICE = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'


def _ecrire_docx(chemin: Path, texte: str, langue: str | None) -> None:
    paragraphes = [_paragraphe_docx(ligne, langue) for ligne in texte.replace("\r\n", "\n").split("\n")]
    document = _DEBUT_DOCUMENT + "".join(paragraphes) + _FIN_DOCUMENT
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _TYPES)
        archive.writestr("_rels/.rels", _RELATIONS)
        archive.writestr("word/document.xml", document)


def _paragraphe_docx(ligne: str, langue: str | None) -> str:
    de_droite_a_gauche = (langue or deviner_langue(ligne)) == AR
    proprietes = "<w:pPr>" + ("<w:bidi/>" if de_droite_a_gauche else "") + '<w:spacing w:after="160"/></w:pPr>'
    passages = "".join(_passage_docx(texte, arabe) for texte, arabe in _passages(ligne, de_droite_a_gauche))
    return f"<w:p>{proprietes}{passages}</w:p>"


def _passages(ligne: str, de_droite_a_gauche: bool) -> list[tuple[str, bool]]:
    """Découpe une ligne en passages de même écriture : (texte, vrai si le passage est en arabe).

    Les espaces et la ponctuation suivent l'écriture du mot qui les précède.
    """
    passages: list[tuple[str, bool]] = []
    courant, arabe = "", de_droite_a_gauche
    for caractere in ligne:
        if _ARABE.match(caractere):
            ecriture = True
        elif _LATIN.match(caractere):
            ecriture = False
        else:
            ecriture = arabe
        if ecriture != arabe and courant:
            passages.append((courant, arabe))
            courant = ""
        courant, arabe = courant + caractere, ecriture
    if courant:
        passages.append((courant, arabe))
    return passages


def _passage_docx(texte: str, arabe: bool) -> str:
    proprietes = (f'<w:rPr>{_POLICE}<w:sz w:val="24"/><w:szCs w:val="28"/>' + ("<w:rtl/>" if arabe else "")
                  + '<w:lang w:val="fr-FR" w:bidi="ar-DZ"/></w:rPr>')
    contenu = "<w:tab/>".join(f'<w:t xml:space="preserve">{escape(morceau)}</w:t>' if morceau else ""
                              for morceau in texte.split("\t"))
    return f"<w:r>{proprietes}{contenu}</w:r>"


def nom_d_export(source: str | Path | None, extension: str = ".docx") -> str:
    """Nom proposé pour le fichier exporté : « contrat.docx » donne « contrat_traduction.docx »."""
    radical = Path(source).stem if source else "traduction"
    return (f"{radical}_traduction" if source else radical) + extension
