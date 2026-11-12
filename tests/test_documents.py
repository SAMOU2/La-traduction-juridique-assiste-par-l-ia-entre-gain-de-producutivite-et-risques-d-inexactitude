"""Import et export des textes : fichiers .txt, .docx et .doc."""

import struct
import zipfile
from xml.etree import ElementTree

import pytest

from traducteur import documents
from traducteur.documents import ErreurDocument

TEXTE = ("العقد شريعة المتعاقدين. فلا يجوز نقضه.\n\nLe contrat (art. 106) & <la loi>\tsuite\n"
         "القاضي applique القانون؛ le droit.")


@pytest.mark.parametrize("extension", [".txt", ".docx"])
def test_un_texte_exporte_puis_importe_est_inchange(tmp_path, extension):
    fichier = tmp_path / f"traduction{extension}"
    documents.ecrire(fichier, TEXTE, "ar")
    assert documents.lire(fichier) == TEXTE


def test_le_fichier_txt_est_en_utf8_avec_marque(tmp_path):
    documents.ecrire(tmp_path / "a.txt", "عقد")
    assert (tmp_path / "a.txt").read_bytes() == b"\xef\xbb\xbf" + "عقد".encode()


@pytest.mark.parametrize(("encodage", "texte"), [("utf-16", "Le contrat عقد"), ("cp1252", "Équité, bonne foi"),
                                                 ("cp1256", "العقد شريعة المتعاقدين")])
def test_lecture_des_anciens_encodages(tmp_path, encodage, texte):
    fichier = tmp_path / "ancien.txt"
    fichier.write_bytes(texte.encode(encodage))
    assert documents.lire(fichier) == texte


def test_les_fins_de_ligne_de_windows_sont_unifiees(tmp_path):
    fichier = tmp_path / "windows.txt"
    fichier.write_bytes("Première ligne.  \r\nSeconde ligne.\r\n\r\n".encode())
    assert documents.lire(fichier) == "Première ligne.\nSeconde ligne."


def test_structure_du_document_word(tmp_path):
    """Paragraphes arabes écrits de droite à gauche ; les mots latins gardent leur sens d'écriture."""
    fichier = tmp_path / "a.docx"
    documents.ecrire(fichier, "القاضي applique القانون.\nTexte français & <balise>", None)
    with zipfile.ZipFile(fichier) as archive:
        assert set(archive.namelist()) == {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
        xml = archive.read("word/document.xml").decode("utf-8")
    premier, second = xml.split("</w:p>")[:2]
    assert "<w:bidi/>" in premier and "<w:bidi/>" not in second
    assert premier.count("<w:rtl/>") == 2  # « القاضي » et « القانون. » ; « applique » reste de gauche à droite
    assert "Texte français &amp; &lt;balise&gt;" in second


@pytest.mark.parametrize("extension", [".docx", ".txt"])
def test_les_caracteres_qui_ne_peuvent_pas_etre_enregistres(tmp_path, extension):
    """Demi-caractère isolé et caractères interdits dans un fichier XML : l'export ne doit pas échouer."""
    fichier = tmp_path / f"a{extension}"
    documents.ecrire(fichier, "contrat \ud83d fin\x01\uffff 😀", "fr")
    assert documents.lire(fichier) == "contrat \ufffd fin 😀"
    if extension == ".docx":
        with zipfile.ZipFile(fichier) as archive:
            ElementTree.fromstring(archive.read("word/document.xml"))  # le fichier XML est valide


def test_document_word_relu_par_python_docx(tmp_path):
    docx = pytest.importorskip("docx")
    fichier = tmp_path / "a.docx"
    documents.ecrire(fichier, TEXTE, "ar")
    assert [paragraphe.text for paragraphe in docx.Document(str(fichier)).paragraphs] == TEXTE.split("\n")


def test_lecture_d_un_document_ecrit_par_word(tmp_path):
    """Titres, sauts de ligne, tableaux et texte supprimé (suivi des modifications)."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    corps = (
        "<w:p><w:pPr><w:pStyle w:val='Titre1'/></w:pPr><w:r><w:t>Titre</w:t></w:r></w:p>"
        "<w:p><w:r><w:t xml:space='preserve'>Le contrat </w:t></w:r><w:del><w:r><w:delText>ancien</w:delText>"
        "</w:r></w:del><w:ins><w:r><w:t>nouveau</w:t></w:r></w:ins><w:r><w:br/><w:t>ligne</w:t><w:tab/>"
        "<w:t>fin</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>contrat</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>عقد</w:t></w:r>"
        "</w:p></w:tc></w:tr></w:tbl>"
        "<w:sdt><w:sdtContent><w:p><w:hyperlink><w:r><w:t>lien</w:t></w:r></w:hyperlink></w:p></w:sdtContent>"
        "</w:sdt><w:sectPr/>"
    )
    fichier = tmp_path / "word.docx"
    with zipfile.ZipFile(fichier, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document xmlns:w='{w}'><w:body>{corps}</w:body></w:document>")
    assert documents.lire(fichier) == "Titre\nLe contrat nouveau\nligne\tfin\ncontrat\tعقد\nlien"


@pytest.mark.parametrize(
    ("nom", "contenu", "message"),
    [
        ("abime.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(64), "endommagé"),
        ("texte.pdf", b"%PDF-1.7\n", "fichier PDF"),
        ("texte.rtf", b"{\\rtf1 texte}", "format RTF"),
        ("image.txt", b"abc\x00\x01\x02def", "n'est pas un fichier de texte"),
        ("abime.docx", b"PK\x03\x04pas une archive", "endommagé"),
    ],
)
def test_fichiers_refuses(tmp_path, nom, contenu, message):
    fichier = tmp_path / nom
    fichier.write_bytes(contenu)
    with pytest.raises(ErreurDocument, match=message):
        documents.lire(fichier)


def test_un_classeur_n_est_pas_un_document_word(tmp_path):
    fichier = tmp_path / "classeur.docx"
    with zipfile.ZipFile(fichier, "w") as archive:
        archive.writestr("xl/workbook.xml", "<a/>")
    with pytest.raises(ErreurDocument, match="n'est pas un document Word"):
        documents.lire(fichier)


# ------------------------------------------------------------------ ancien format de Word (.doc)
def fabriquer_doc(morceaux, *, corps=None, drapeaux=0, version=0x00C1, nom_du_flux="WordDocument") -> bytes:
    """Construit un petit fichier .doc (Word 97-2003) qui contient les morceaux de texte donnés.

    ``morceaux`` est une liste de couples (texte, compressé) : un morceau « compressé » est écrit sur
    un octet par caractère, les autres en UTF-16. ``corps`` est le nombre de caractères du corps du
    document (par défaut : tout le texte). Le fichier suit le format des fichiers composés : un
    en-tête, une table d'allocation, un répertoire, le flux « WordDocument » et, rangé dans le
    mini-flux, le flux « 0Table » qui contient la table des morceaux.
    """
    fin, libre = 0xFFFFFFFE, 0xFFFFFFFF
    debut_du_texte = 1024
    entete_word = bytearray(debut_du_texte)
    struct.pack_into("<HH", entete_word, 0, 0xA5EC, version)
    struct.pack_into("<H", entete_word, 0x0A, drapeaux)
    donnees, limites, adresses, position = bytearray(), [0], [], 0
    for texte, compresse in morceaux:
        adresse = debut_du_texte + len(donnees)
        if compresse:
            donnees += texte.encode("cp1252")
            adresses.append((adresse * 2) | 0x40000000)
        else:
            donnees += texte.encode("utf-16-le")
            adresses.append(adresse)
        position += len(texte)
        limites.append(position)
    struct.pack_into("<I", entete_word, 0x4C, position if corps is None else corps)
    table_des_morceaux = (b"".join(struct.pack("<I", limite) for limite in limites)
                          + b"".join(struct.pack("<HIH", 0, adresse, 0) for adresse in adresses))
    # Un bloc de mise en forme (type 1) précède la table des morceaux (type 2), comme dans un vrai fichier.
    clx = b"\x01" + struct.pack("<H", 2) + b"\x00\x00" + b"\x02" + struct.pack("<I", len(table_des_morceaux)) \
        + table_des_morceaux
    table = bytes(16) + clx
    struct.pack_into("<II", entete_word, 0x01A2, 16, len(clx))
    document = bytes(entete_word) + bytes(donnees)
    document += bytes(max(4096 - len(document), -len(document) % 512))  # 4096 octets au moins : hors du mini-flux

    secteurs_document = len(document) // 512
    mini_secteurs = -(-len(table) // 64)
    mini_flux = table.ljust(mini_secteurs * 64, b"\x00")
    mini_flux += bytes(-len(mini_flux) % 512)
    secteurs_mini = len(mini_flux) // 512
    # Secteurs : 0 = table d'allocation, 1 = répertoire, puis le document, le mini-flux, la mini-table.
    premier_document, premier_mini = 2, 2 + secteurs_document
    secteur_mini_table = premier_mini + secteurs_mini
    allocation = [0xFFFFFFFD, fin]
    allocation += [numero + 1 for numero in range(premier_document, premier_document + secteurs_document - 1)] + [fin]
    allocation += [numero + 1 for numero in range(premier_mini, premier_mini + secteurs_mini - 1)] + [fin]
    allocation += [fin]
    allocation += [libre] * (128 - len(allocation))
    mini_allocation = [*range(1, mini_secteurs), fin] + [libre] * (128 - mini_secteurs)

    def entree(nom, nature, gauche, droite, enfant, premier, taille) -> bytes:
        code = (nom + "\x00").encode("utf-16-le")
        return (code.ljust(64, b"\x00") + struct.pack("<HBB", len(code), nature, 1)
                + struct.pack("<3I", gauche, droite, enfant) + bytes(36) + struct.pack("<IQ", premier, taille))

    repertoire = (entree("Root Entry", 5, libre, libre, 1, premier_mini, mini_secteurs * 64)
                  + entree(nom_du_flux, 2, 2, libre, libre, premier_document, len(document))
                  + entree("0Table", 2, libre, libre, libre, 0, len(table))
                  + bytes(128))
    entete = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(16) + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6)
              + bytes(6) + struct.pack("<9I", 0, 1, 1, 0, 4096, secteur_mini_table, 1, fin, 0)
              + struct.pack("<109I", 0, *([libre] * 108)))
    assert len(entete) == 512
    return (entete + struct.pack("<128I", *allocation) + repertoire + document + mini_flux
            + struct.pack("<128I", *mini_allocation))


def test_lecture_d_un_document_doc(tmp_path):
    """Texte sur un octet et texte en UTF-16 (arabe), tableau, lien, notes et pied de page ignorés."""
    corps = [
        ("Le contrat – art. 106 : « équité »\r", True),
        ("العقد شريعة المتعاقدين.\r", False),
        ("terme\x07مصطلح\x07\x07contrat\x07عقد\x07\x07", False),
        ("Voir \x13 HYPERLINK \"http://www.joradp.dz\" \x14le Journal officiel\x15 ; ligne\x0bsuivante\r", True),
        # Un champ sans résultat, puis deux champs emboîtés : seul le code des champs est retiré.
        ("\x13 SEQ CHAPTER \\h \\r 1\x15Chapitre \x13 IF \x13 PAGE \x142\x15 > 1 \x14deux\x15 et fin\r", True),
    ]
    fichier = tmp_path / "ancien.doc"
    fichier.write_bytes(fabriquer_doc([*corps, ("Texte d'une note de bas de page\r", True)],
                                      corps=sum(len(texte) for texte, _ in corps)))
    assert documents.lire(fichier) == (
        "Le contrat – art. 106 : « équité »\n"
        "العقد شريعة المتعاقدين.\n"
        "terme\tمصطلح\ncontrat\tعقد\n"
        "Voir le Journal officiel ; ligne\nsuivante\n"
        "Chapitre deux et fin"
    )


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"drapeaux": 0x0100}, "protégé par un mot de passe"),
        ({"version": 0x0065}, "avant Word 97"),
        ({"nom_du_flux": "Workbook"}, "n'est pas un document Word"),
    ],
)
def test_documents_doc_refuses(tmp_path, options, message):
    fichier = tmp_path / "ancien.doc"
    fichier.write_bytes(fabriquer_doc([("Texte\r", True)], **options))
    with pytest.raises(ErreurDocument, match=message):
        documents.lire(fichier)


def test_un_fichier_doc_tronque_ne_fait_pas_planter_la_lecture(tmp_path):
    """Selon l'endroit de la coupure, le fichier est refusé ou son texte est retrouvé en entier."""
    complet = fabriquer_doc([("Le contrat fait la loi des parties.\r", True)])
    refuses = 0
    for longueur in range(8, len(complet), 61):
        fichier = tmp_path / "tronque.doc"
        fichier.write_bytes(complet[:longueur])
        try:
            assert documents.lire(fichier) == "Le contrat fait la loi des parties."
        except ErreurDocument as erreur:
            assert "endommagé" in str(erreur) or "n'est pas un document Word" in str(erreur)
            refuses += 1
    assert refuses > 50


def test_erreurs_de_lecture_et_d_ecriture(tmp_path):
    with pytest.raises(ErreurDocument, match=r"absent\.txt"):
        documents.lire(tmp_path / "absent.txt")
    with pytest.raises(ErreurDocument, match="n'est pas proposé pour l'export"):
        documents.ecrire(tmp_path / "traduction.pdf", "texte")
    with pytest.raises(ErreurDocument, match="Impossible d'écrire"):
        documents.ecrire(tmp_path / "dossier_absent" / "traduction.txt", "texte")


def test_nom_propose_pour_l_export():
    assert documents.nom_d_export("C:/textes/articles_106-107.docx") == "articles_106-107_traduction.docx"
    assert documents.nom_d_export(None, ".txt") == "traduction.txt"
