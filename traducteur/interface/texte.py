"""Écran de traduction d'un texte (écran 2 de la maquette).

Deux zones de texte côte à côte (texte source, texte traduit), la bande des
cinq étapes de l'algorithme, puis le tableau des termes du glossaire relevés
dans le texte, avec pour chacun l'enchaînement de l'écran de recherche :
terme, définition, équivalent, contextualisation, ressources.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QKeySequence,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import documents
from ..glossaire import Entree, Glossaire
from ..langues import (
    AR,
    CODE,
    FR,
    NOM_EN_FRANCAIS,
    NOM_NATIF,
    autre_langue,
    contient_arabe,
    contient_latin,
    deviner_langue,
)
from ..segmentation import compter
from ..surlignage import positions_du_terme
from ..traduction import SOURCE, TERME, TermeDetecte, Traducteur, Traduction
from . import icones, theme
from .cartes import categorie_et_pluriel, phrase_surlignee, ressource_en_html
from .composants import (
    DROITE,
    MARQUE_RTL,
    EtiquetteCourte,
    direction,
    etiquette,
    icone_fixe,
    infobulle,
    pastille_langue,
    vider,
)

#: Texte proposé par « Insérer un exemple » : les articles 106 et 107 du Code civil (phrases reprises
#: des exemples du glossaire fourni), puis une phrase qui n'y figure pas, traduite mot à mot.
EXEMPLES = {
    FR: ("Le contrat fait la loi des parties. Il ne peut être révoqué, ni modifié que de leur consentement mutuel "
         "ou pour les causes prévues par la loi. Le contrat doit être exécuté conformément à son contenu, et de "
         "bonne foi. Il oblige le contractant, non seulement à ce qui y est exprimé, mais encore à tout ce que la "
         "loi, l’usage et l’équité considèrent comme une suite nécessaire de ce contrat d’après la nature de "
         "l’obligation.\nLa nullité du contrat de vente protège l’acheteur."),
    AR: ("العقد شريعة المتعاقدين. فلا يجوز نقضه، ولا تعديله إلا باتفاق الطرفين، أو للأسباب التي يقررها القانون. "
         "يجب تنفيذ العقد طبقا لما اشتمل عليه وبحسن نية. ولا يقتصر العقد على إلزام المتعاقد بما ورد فيه فحسب، "
         "بل يتناول أيضا ما هو من مستلزماته وفقا للقانون، والعرف، والعدالة، بحسب طبيعة الالتزام.\n"
         "بطلان عقد البيع يحمي المشتري."),
}

_ROLES = {
    "source": {FR: "texte source", AR: "النص المصدر"},
    "cible": {FR: "texte traduit", AR: "النص المترجم"},
}
_INVITES = {
    FR: "Saisissez, collez ou importez le texte à traduire…",
    AR: "أدخل النص المراد ترجمته أو الصقه أو استورده…",
}
_AUCUN_GLOSSAIRE = "Aucun glossaire n’est chargé : ouvrez un fichier CSV (menu Fichier → Ouvrir un glossaire)."
#: Rappel affiché sous une traduction partielle : forme longue, forme courte, puis rien si la place manque.
_AIDE_GRIS = ("En gris : mots absents du glossaire, à traduire", "En gris : mots à traduire", "")

#: Les cinq étapes de l'algorithme : (titre, titre court, description, description courte).
#: La description est affichée avant la traduction ; les formes courtes servent quand la place manque.
ETAPES = (
    ("Segmentation en phrases", "Segmentation", "le texte est découpé en phrases", "phrase par phrase"),
    ("Découpage en mots", "Découpage", "chaque phrase est découpée en mots", "mot par mot"),
    ("Recherche dans le CSV", "Recherche", "phrases, expressions et mots du glossaire", "dans le glossaire"),
    ("Règles linguistiques", "Règles", "lexique, grammaire, sémantique", "3 familles"),
    ("Reconstruction", "Reconstruction", "paragraphe et ponctuation", "du paragraphe"),
)
#: Colonnes du tableau des termes et largeurs relatives (celles de la maquette).
COLONNES = (("Terme", 200), ("Définition", 390), ("Équivalent", 180), ("Contextualisation", 380), ("Ressources", 242))

#: Hauteur d'une ligne des zones de texte, en pixels, selon la langue. Une hauteur fixe garde des
#: lignes régulières quand une même ligne mêle des mots français et des mots arabes.
INTERLIGNE = {FR: 28, AR: 34}
_LONGUEUR_DEFINITION = 170
#: Longueur maximale d'un exemple dans le tableau (l'arabe est écrit plus grand).
_LONGUEUR_EXEMPLE = {FR: 110, AR: 90}
#: Couleur des mots absents du glossaire dans le texte traduit.
_GRIS = "#8A97AA"


def _nombre(valeur: int, singulier: str, pluriel: str | None = None) -> str:
    """« 1 phrase », « 4 phrases », « 2 480 mots »."""
    nombre = f"{valeur:,}".replace(",", "\u202f")
    return f"{nombre} {singulier if valeur < 2 else (pluriel or singulier + 's')}"


def _decompte(phrases: int, mots: int, caracteres: int) -> tuple[str, str, str]:
    """Décompte d'un texte, du plus long au plus court : « 4 phrases · 76 mots · 422 caractères », …, « 76 mots »."""
    elements = (_nombre(phrases, "phrase"), _nombre(mots, "mot"), _nombre(caracteres, "caractère"))
    return " · ".join(elements), " · ".join(elements[:2]), elements[1]


def _abrege(texte: str, longueur: int) -> str:
    """Coupe un texte trop long à la fin d'un mot et ajoute « … »."""
    if len(texte) <= longueur:
        return texte
    coupe = texte.rfind(" ", 0, longueur)
    return texte[:coupe if coupe > longueur // 2 else longueur].rstrip(" ,;:،؛") + "…"


def _extrait(phrase: str, entree: Entree, langue: str) -> str:
    """Passage d'une phrase d'exemple autour du terme : « … pour les causes prévues par la loi. »"""
    longueur = _LONGUEUR_EXEMPLE[langue]
    if len(phrase) <= longueur:
        return phrase
    positions = positions_du_terme(phrase, entree, langue)
    centre = (positions[0][0] + positions[0][1]) // 2 if positions else 0
    debut = max(0, min(centre - longueur // 2, len(phrase) - longueur))
    fin = min(len(phrase), debut + longueur)
    if debut > 0:
        espace = phrase.find(" ", debut)
        debut = espace + 1 if 0 <= espace < centre else debut
    if fin < len(phrase):
        espace = phrase.rfind(" ", debut, fin)
        fin = espace if espace > centre else fin
    return ("… " if debut > 0 else "") + phrase[debut:fin].strip() + (" …" if fin < len(phrase) else "")


def _filet() -> QFrame:
    filet = QFrame()
    filet.setObjectName("filetPanneau")
    filet.setFixedHeight(1)
    return filet


def _repeindre(widget: QWidget) -> None:
    """Applique de nouveau la feuille de style après le changement d'une propriété."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


# ====================================================================== zones de texte
class PanneauTexte(QFrame):
    """Une zone de texte encadrée : en-tête (langue), texte, pied (décompte et boutons)."""

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panneauTexte")
        self.role = role
        self.langue = FR
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(1, 1, 1, 1)
        ensemble.setSpacing(0)

        self.entete = QWidget()
        self.entete.setFixedHeight(46)
        ligne = QHBoxLayout(self.entete)
        ligne.setContentsMargins(20, 0, 16, 0)
        ligne.setSpacing(8)
        self.pastille = pastille_langue(FR)
        self.nom = etiquette("", "titrePanneau")
        self.legende = etiquette("", "sousTitrePanneau")
        ligne.addWidget(self.pastille)
        ligne.addWidget(self.nom)
        ligne.addWidget(self.legende)
        ligne.addStretch(1)
        #: Emplacement libre à la fin de l'en-tête (fichier importé, état de la traduction).
        self.complement = QHBoxLayout()
        self.complement.setSpacing(8)
        ligne.addLayout(self.complement)
        ensemble.addWidget(self.entete)
        ensemble.addWidget(_filet())

        self.zone = QTextEdit()
        self.zone.setObjectName("zoneTexte")
        self.zone.setFrameShape(QFrame.Shape.NoFrame)
        self.zone.setAcceptRichText(False)
        self.zone.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.zone.document().setDocumentMargin(18)
        self.zone.setMinimumHeight(60)
        ensemble.addWidget(self.zone, 1)
        ensemble.addWidget(_filet())

        cadre_du_pied = QWidget()
        cadre_du_pied.setFixedHeight(52)
        self.pied = QHBoxLayout(cadre_du_pied)
        self.pied.setContentsMargins(20, 0, 16, 0)
        self.pied.setSpacing(8)
        ensemble.addWidget(cadre_du_pied)
        self.definir_langue(FR)

    def definir_langue(self, langue: str) -> None:
        """Fixe la langue du panneau : libellés de l'en-tête et sens d'écriture du texte."""
        self.langue = langue
        self.pastille.setText(CODE[langue])
        self.nom.setText(NOM_NATIF[langue])
        self.legende.setText(_ROLES[self.role][langue])
        self.entete.setLayoutDirection(direction(langue))
        self.zone.setLayoutDirection(direction(langue))
        option = self.zone.document().defaultTextOption()
        option.setTextDirection(direction(langue))
        self.zone.document().setDefaultTextOption(option)
        if self.zone.property("arabe") != (langue == AR):
            self.zone.setProperty("arabe", langue == AR)
            _repeindre(self.zone)
        self.appliquer_l_interligne()

    def appliquer_l_interligne(self) -> None:
        """Espace les lignes du texte (à refaire après chaque remplacement du texte)."""
        curseur = QTextCursor(self.zone.document())
        curseur.select(QTextCursor.SelectionType.Document)
        mise_en_forme = QTextBlockFormat()
        mise_en_forme.setLineHeight(INTERLIGNE[self.langue], QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        curseur.mergeBlockFormat(mise_en_forme)

    def orienter_les_paragraphes(self) -> None:
        """Écrit dans son propre sens un paragraphe resté entièrement dans l'autre langue.

        Dans une traduction partielle, un paragraphe dont aucun mot n'a été traduit ne contient
        que l'écriture de l'autre langue. Affiché dans le sens d'écriture du panneau, il aurait
        son point final du mauvais côté.
        """
        dans_la_langue, dans_l_autre = ((contient_arabe, contient_latin) if self.langue == AR
                                        else (contient_latin, contient_arabe))
        sens_inverse = direction(autre_langue(self.langue))
        bloc = self.zone.document().begin()
        while bloc.isValid():
            texte = bloc.text()
            if dans_l_autre(texte) and not dans_la_langue(texte):
                mise_en_forme = QTextBlockFormat()
                mise_en_forme.setLayoutDirection(sens_inverse)
                QTextCursor(bloc).mergeBlockFormat(mise_en_forme)
            bloc = bloc.next()


# ====================================================================== étapes de l'algorithme
class Etape(QWidget):
    """Une étape de l'algorithme : numéro, titre et résultat de l'étape.

    Le titre et le résultat ont une forme longue et une forme courte ; la forme
    courte est affichée quand la forme longue ne tient pas dans la largeur
    (c'est ``EtiquetteCourte`` qui choisit).
    """

    def __init__(self, numero: int, titre: str, titre_court: str, description: str, description_courte: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.description = description
        self._titres = (titre, titre_court)
        self._descriptions = (description, description_courte or description)
        self._resultats = self._descriptions
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(10)
        self.numero = QLabel(str(numero))
        self.numero.setProperty("classe", "numeroEtape")
        self.numero.setProperty("faite", False)
        self.numero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.numero.setFixedSize(26, 26)
        ligne.addWidget(self.numero)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(1)
        self.titre = EtiquetteCourte("", "titreEtape")
        self.titre.definir_texte(titre, titre_court)
        self.detail = EtiquetteCourte(description, "detailEtape")
        colonne.addStretch(1)
        colonne.addWidget(self.titre)
        colonne.addWidget(self.detail)
        colonne.addStretch(1)
        ligne.addLayout(colonne, 1)
        # L'infobulle est celle de l'étape entière, pas celle de chaque étiquette.
        for label in (self.numero, self.titre, self.detail):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.afficher(None)

    def afficher(self, resultat: str | None, court: str = "", explication: str = "") -> None:
        """Affiche le résultat de l'étape ; ``None`` remet la description d'origine.

        ``court`` est la forme abrégée du résultat (« 31 sur 41 » pour « 31 mots trouvés sur 41 »).
        """
        self._resultats = self._descriptions if resultat is None else (resultat, court or resultat)
        if self.numero.property("faite") != (resultat is not None):
            self.numero.setProperty("faite", resultat is not None)
            _repeindre(self.numero)
        self.detail.definir_texte(*self._resultats)
        lignes = [self._titres[0], self._resultats[0], *([explication] if explication else [])]
        self.setToolTip("<qt>" + "<br>".join(escape(ligne).replace("\n", "<br>") for ligne in lignes) + "</qt>")

    def resultat(self) -> str:
        """Le résultat de l'étape, dans sa forme longue."""
        return self._resultats[0]

    def largeur_minimale(self) -> int:
        """Largeur qu'il faut à l'étape pour afficher son titre et son résultat dans leur forme courte."""
        largeurs = []
        for label, (_, court) in ((self.titre, self._titres), (self.detail, self._resultats)):
            label.ensurePolished()
            largeurs.append(label.fontMetrics().horizontalAdvance(court))
        return self.numero.width() + self.layout().spacing() + max(largeurs)


class BandeEtapes(QFrame):
    """Bande des cinq étapes : segmentation, découpage, recherche, règles, reconstruction."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bandeEtapes")
        self.setFixedHeight(60)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(18, 0, 18, 0)
        ligne.setSpacing(8)
        self.etapes: list[Etape] = []
        self.chevrons: list[QLabel] = []
        for rang, (titre, titre_court, description, description_courte) in enumerate(ETAPES):
            if rang:
                self.chevrons.append(icone_fixe("chevron", "#B4C1D8", 18))
                ligne.addWidget(self.chevrons[-1])
            etape = Etape(rang + 1, titre, titre_court, description, description_courte)
            self.etapes.append(etape)
            ligne.addWidget(etape, 1)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self._placer_les_chevrons()

    def _placer_les_chevrons(self) -> None:
        """Retire les chevrons quand, avec eux, la forme courte des étapes ne tient plus dans la bande.

        La décision ne dépend que de la largeur de la bande et des textes, jamais de la place
        qu'occupent les étapes : afficher ou retirer les chevrons ne la remet donc pas en cause.
        """
        disposition = self.layout()
        marges = disposition.contentsMargins()
        largeur = self.width() - marges.left() - marges.right() - disposition.spacing() * (len(self.etapes) - 1)
        chevrons = sum(chevron.width() + disposition.spacing() for chevron in self.chevrons)
        par_etape = (largeur - chevrons) // len(self.etapes)
        visibles = all(etape.largeur_minimale() <= par_etape for etape in self.etapes)
        for chevron in self.chevrons:
            chevron.setVisible(visibles)

    def afficher(self, traduction: Traduction | None) -> None:
        self._afficher(traduction)
        self._placer_les_chevrons()

    def _afficher(self, traduction: Traduction | None) -> None:
        if traduction is None:
            for etape in self.etapes:
                etape.afficher(None)
            return
        phrases = len(traduction.phrases)
        self.etapes[0].afficher(_nombre(phrases, "phrase détectée", "phrases détectées"), _nombre(phrases, "phrase"))
        self.etapes[1].afficher(_nombre(traduction.mots, "mot"))
        absents = ""
        if traduction.mots_absents:
            visibles = traduction.mots_absents[:40]
            absents = ("Mots absents du glossaire : " + ", ".join(visibles)
                       + ("…" if len(traduction.mots_absents) > len(visibles) else "."))
        trouves = "trouvé" if traduction.mots_reconnus < 2 else "trouvés"
        self.etapes[2].afficher(f"{_nombre(traduction.mots_reconnus, 'mot')} {trouves} sur {traduction.mots}",
                                f"{traduction.mots_reconnus} sur {traduction.mots}", absents)
        regles = sum(traduction.regles.values())
        details = []
        for famille, lignes in traduction.regles_par_famille().items():
            details.extend(f"{famille.capitalize()} — {libelle} : {nombre}" for libelle, nombre in lignes)
        self.etapes[3].afficher(_nombre(regles, "règle appliquée", "règles appliquées") if regles
                                else "aucune règle appliquée", _nombre(regles, "règle"), "\n".join(details))
        reprises = traduction.phrases_attestees
        self.etapes[4].afficher(
            _nombre(phrases, "phrase reconstruite", "phrases reconstruites"), _nombre(phrases, "phrase"),
            f"{_nombre(reprises, 'phrase reprise', 'phrases reprises')} des exemples du glossaire, "
            f"{_nombre(phrases - reprises, 'phrase traduite', 'phrases traduites')} mot à mot.")


# ====================================================================== tableau des termes
class LigneTerme(QFrame):
    """Une ligne du tableau : terme, définition, équivalent, contextualisation, ressources."""

    ouverture = Signal(object)

    def __init__(self, terme: TermeDetecte, traduction: Traduction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ligneTerme")
        self.terme = terme
        entree, source, cible = terme.entree, traduction.source, traduction.cible
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        self.cellules: list[QVBoxLayout] = []
        for rang, (_, largeur) in enumerate(COLONNES):
            cadre = QFrame()
            cadre.setObjectName("celluleTerme")
            cadre.setProperty("derniere", rang == len(COLONNES) - 1)
            cadre.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            cellule = QVBoxLayout(cadre)
            cellule.setContentsMargins(20, 11, 12, 11)
            cellule.setSpacing(3)
            self.cellules.append(cellule)
            ligne.addWidget(cadre, largeur)

        # 1. Terme
        self.bouton = QPushButton(entree.terme(source).replace("&", "&&"))
        self.bouton.setProperty("classe", "lienTerme")
        self.bouton.setProperty("arabe", source == AR)
        self.bouton.setLayoutDirection(direction(source))
        self.bouton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton.setToolTip("Afficher la fiche de ce terme")
        self.bouton.clicked.connect(lambda: self.ouverture.emit(entree))
        self.cellules[0].addWidget(self.bouton)
        occurrences = _nombre(len(terme.occurrences), "occurrence")
        categorie = entree.categorie(source)
        if source == AR:
            # La catégorie arabe et le nombre d'occurrences, écrit en français, sont sur deux lignes.
            if categorie:
                self.cellules[0].addWidget(etiquette(categorie, "celluleDetail", AR, retour_ligne=True))
            label = etiquette(occurrences, "celluleDetail")
            label.setAlignment(DROITE | Qt.AlignmentFlag.AlignTop)
            self.cellules[0].addWidget(label)
        else:
            self.cellules[0].addWidget(etiquette(f"{categorie} · {occurrences}" if categorie else occurrences,
                                                 "celluleDetail", FR, retour_ligne=True))

        # 2. Définition
        definition = entree.definition(source)
        if definition:
            label = etiquette(_abrege(definition, _LONGUEUR_DEFINITION),
                              "celluleArabe" if source == AR else "celluleTexte", source, retour_ligne=True)
            if len(definition) > _LONGUEUR_DEFINITION:
                label.setToolTip(infobulle(definition))
            self.cellules[1].addWidget(label)
        else:
            self.cellules[1].addWidget(etiquette("—", "celluleDetail"))

        # 3. Équivalent
        self.cellules[2].addWidget(etiquette(
            entree.terme(cible), "celluleEquivalentArabe" if cible == AR else "celluleEquivalent", cible,
            retour_ligne=True, selectionnable=True))
        detail = categorie_et_pluriel(entree, cible)
        if detail:
            self.cellules[2].addWidget(etiquette(detail, "celluleDetail", cible, retour_ligne=True))
        autres = " / ".join(autre.terme(cible) for autre in terme.autres_candidats)
        if autres:
            texte = f"Ambigu : aussi « {autres} »" if terme.incertain else f"Autre sens : « {autres} »"
            self.cellules[2].addWidget(etiquette(texte, "celluleAlerte" if terme.incertain else "celluleDetail",
                                                 retour_ligne=True))

        # 4. Contextualisation : un exemple du glossaire, sinon la phrase du texte où figure le terme.
        phrase_du_texte = traduction.phrases[terme.occurrences[0].phrase]
        exemple = phrase_du_texte.attestation or (entree.contextes[0] if entree.contextes else None)
        if exemple is not None and exemple.texte(source):
            for langue in (source, cible):
                if exemple.texte(langue):
                    self.cellules[3].addWidget(etiquette(
                        phrase_surlignee(_extrait(exemple.texte(langue), entree, langue), entree, langue),
                        "celluleArabe" if langue == AR else "celluleTexte", langue, retour_ligne=True, riche=True))
        else:
            self.cellules[3].addWidget(etiquette(
                phrase_surlignee(_extrait(phrase_du_texte.source.texte, entree, source), entree, source),
                "celluleArabe" if source == AR else "celluleTexte", source, retour_ligne=True, riche=True))

        # 5. Ressources : la première référence, et le nombre des autres.
        if entree.ressources:
            premiere = entree.ressources[0]
            langue = deviner_langue(premiere) or FR
            label = etiquette(ressource_en_html(premiere, langue), "celluleArabe" if langue == AR else "celluleTexte",
                              langue, retour_ligne=True, riche=True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setOpenExternalLinks(True)
            self.cellules[4].addWidget(label)
            if len(entree.ressources) > 1:
                reste = len(entree.ressources) - 1
                self.cellules[4].addWidget(etiquette(
                    "+ 1 autre référence" if reste == 1 else f"+ {reste} autres références", "celluleDetail"))
        else:
            self.cellules[4].addWidget(etiquette("—", "celluleDetail"))
        for cellule in self.cellules:
            cellule.addStretch(1)


class PanneauTermes(QFrame):
    """Tableau des termes du glossaire relevés dans le texte."""

    ouverture = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panneauTermes")
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(1, 1, 1, 1)
        ensemble.setSpacing(0)

        titre = QWidget()
        titre.setFixedHeight(44)
        ligne = QHBoxLayout(titre)
        ligne.setContentsMargins(20, 0, 16, 0)
        ligne.setSpacing(12)
        ligne.addWidget(etiquette("Termes juridiques détectés", "titreTermes"))
        self.resume = EtiquetteCourte("", "decompte")
        ligne.addWidget(self.resume, 1)
        ensemble.addWidget(titre)

        entete = QFrame()
        entete.setObjectName("enteteTermes")
        entete.setFixedHeight(32)
        colonnes = QHBoxLayout(entete)
        colonnes.setContentsMargins(0, 0, 10, 0)  # largeur de la barre de défilement des lignes
        colonnes.setSpacing(0)
        for rang, (nom, largeur) in enumerate(COLONNES):
            cellule = QWidget()
            cellule.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            dans_la_cellule = QHBoxLayout(cellule)
            dans_la_cellule.setContentsMargins(20, 0, 8, 0)
            dans_la_cellule.setSpacing(8)
            numero = QLabel(str(rang + 1))
            numero.setProperty("classe", "numeroColonne")
            numero.setAlignment(Qt.AlignmentFlag.AlignCenter)
            numero.setFixedSize(16, 16)
            dans_la_cellule.addWidget(numero)
            dans_la_cellule.addWidget(EtiquetteCourte(nom.upper(), "titreColonne"), 1)
            colonnes.addWidget(cellule, largeur)
        ensemble.addWidget(entete)

        self.defilement = QScrollArea()
        self.defilement.setObjectName("defilementTermes")
        self.defilement.setWidgetResizable(True)
        self.defilement.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.defilement.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        contenu = QWidget()
        contenu.setObjectName("lignesTermes")
        self.lignes = QVBoxLayout(contenu)
        self.lignes.setContentsMargins(0, 0, 0, 0)
        self.lignes.setSpacing(0)
        self.defilement.setWidget(contenu)
        ensemble.addWidget(self.defilement, 1)
        self.setMinimumHeight(132)
        self.afficher(None)

    def afficher(self, traduction: Traduction | None) -> None:
        vider(self.lignes)
        if traduction is None or not traduction.termes:
            self.resume.definir_texte("" if traduction is None else "aucun terme du glossaire dans ce texte")
            message = etiquette(
                "Les termes du glossaire relevés dans le texte s’afficheront ici après la traduction."
                if traduction is None else "Aucun terme du glossaire n’a été relevé dans ce texte.",
                "discret", retour_ligne=True)
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setContentsMargins(20, 18, 20, 18)
            self.lignes.addWidget(message)
        else:
            self.resume.definir_texte(f"{_nombre(len(traduction.termes), 'terme')} · "
                                      "cliquez sur un terme pour afficher sa fiche")
            for terme in traduction.termes:
                ligne = LigneTerme(terme, traduction)
                ligne.ouverture.connect(self.ouverture)
                self.lignes.addWidget(ligne)
        self.lignes.addStretch(1)
        self.defilement.verticalScrollBar().setValue(0)

    def lignes_affichees(self) -> list[LigneTerme]:
        return [self.lignes.itemAt(rang).widget() for rang in range(self.lignes.count())
                if isinstance(self.lignes.itemAt(rang).widget(), LigneTerme)]


# ====================================================================== l'écran
class PageTexte(QWidget):
    """L'écran de traduction d'un texte."""

    #: Le sens de traduction a changé ; le signal porte la nouvelle langue source.
    sens_change = Signal(str)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)
    #: Demande d'affichage de la fiche d'une entrée du glossaire (écran de recherche).
    entree_demandee = Signal(object)
    #: Une traduction vient d'être affichée ou effacée.
    traduction_changee = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.traducteur: Traducteur | None = None
        self.traduction: Traduction | None = None
        self.source = FR
        #: Fichier d'où vient le texte source, s'il a été importé.
        self.fichier: Path | None = None
        self._modification_interne = False

        page = QVBoxLayout(self)
        page.setContentsMargins(24, 18, 24, 16)
        page.setSpacing(14)

        # ---------------------------------------------------------- texte source
        self.panneau_source = PanneauTexte("source")
        self.zone_source = self.panneau_source.zone
        self.zone_source.textChanged.connect(self._texte_modifie)
        self.lien_exemple = QPushButton("Insérer un exemple")
        self.lien_exemple.setProperty("classe", "lien")
        self.lien_exemple.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lien_exemple.setToolTip("Remplir la zone avec un texte d’exemple (articles 106 et 107 du Code civil)")
        self.lien_exemple.clicked.connect(self.inserer_un_exemple)
        self.panneau_source.complement.addWidget(self.lien_exemple)
        self.fichier_importe = self._creer_le_rappel_du_fichier()
        self.panneau_source.complement.addWidget(self.fichier_importe)

        self.decompte_source = EtiquetteCourte("", "decompte")
        self.bouton_effacer = QPushButton("Effacer")
        self.bouton_effacer.setProperty("classe", "secondaire")
        self.bouton_effacer.setFixedHeight(36)
        self.bouton_effacer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_effacer.clicked.connect(self.effacer)
        self.bouton_traduire = QPushButton("Traduire")
        self.bouton_traduire.setProperty("classe", "principal")
        self.bouton_traduire.setIcon(icones.icone("echange", "#FFFFFF", 18))
        self.bouton_traduire.setFixedHeight(36)
        self.bouton_traduire.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_traduire.setToolTip("Traduire le texte (Ctrl+Entrée)")
        self.bouton_traduire.clicked.connect(self.traduire)
        self.panneau_source.pied.addWidget(self.decompte_source, 1)
        self.panneau_source.pied.addWidget(self.bouton_effacer)
        self.panneau_source.pied.addWidget(self.bouton_traduire)

        # ---------------------------------------------------------- texte traduit
        self.panneau_cible = PanneauTexte("cible")
        self.zone_cible = self.panneau_cible.zone
        self.zone_cible.setReadOnly(True)
        self.zone_cible.setPlaceholderText("La traduction s’affichera ici.")
        self.etat = QLabel()
        self.etat.setProperty("classe", "badge")
        self.etat.setFixedHeight(26)
        self.panneau_cible.complement.addWidget(self.etat)

        self.bouton_copier = QPushButton("Copier")
        self.bouton_copier.setProperty("classe", "secondaire")
        self.bouton_copier.setIcon(icones.icone("copier", theme.BLEU_FONCE, 18))
        self.bouton_copier.setFixedHeight(36)
        self.bouton_copier.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_copier.setToolTip("Copier la traduction dans le presse-papiers")
        self.bouton_copier.clicked.connect(self.copier)
        self._retour_copier = QTimer(self)
        self._retour_copier.setSingleShot(True)
        self._retour_copier.setInterval(1600)
        self._retour_copier.timeout.connect(lambda: self.bouton_copier.setText("Copier"))
        # Ce rappel ne reçoit que la place laissée par le décompte ; il disparaît si elle ne suffit pas.
        self.aide = EtiquetteCourte("", "aide")
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.decompte_cible = EtiquetteCourte("", "decompte")
        self.decompte_cible.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.panneau_cible.pied.addWidget(self.bouton_copier)
        self.panneau_cible.pied.addWidget(self.aide, 1)
        self.panneau_cible.pied.addWidget(self.decompte_cible)

        textes = QHBoxLayout()
        textes.setSpacing(24)
        textes.addWidget(self.panneau_source, 1)
        textes.addWidget(self.panneau_cible, 1)
        page.addLayout(textes, 5)

        # ---------------------------------------------------------- étapes et termes
        self.bande = BandeEtapes()
        page.addWidget(self.bande)
        self.termes = PanneauTermes()
        self.termes.ouverture.connect(self.entree_demandee)
        page.addWidget(self.termes, 4)

        raccourci = QShortcut(QKeySequence("Ctrl+Return"), self)
        raccourci.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        raccourci.activated.connect(self.traduire)
        self._decompte_differe = QTimer(self)
        self._decompte_differe.setSingleShot(True)
        self._decompte_differe.setInterval(200)
        self._decompte_differe.timeout.connect(self._afficher_le_decompte_source)

        self._appliquer_sens()
        self._afficher(None)

    def _creer_le_rappel_du_fichier(self) -> QFrame:
        """Étiquette « fichier importé » de l'en-tête : nom du fichier et bouton pour l'oublier."""
        cadre = QFrame()
        cadre.setObjectName("fichierImporte")
        cadre.setFixedHeight(28)
        cadre.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        ligne = QHBoxLayout(cadre)
        ligne.setContentsMargins(10, 0, 5, 0)
        ligne.setSpacing(6)
        ligne.addWidget(icone_fixe("fichier", theme.BLEU, 16))
        self.nom_du_fichier = EtiquetteCourte("", "nomFichier")
        self.nom_du_fichier.setMaximumWidth(190)
        ligne.addWidget(self.nom_du_fichier)
        fermer = QToolButton()
        fermer.setObjectName("fermerFichier")
        fermer.setIcon(icones.icone("croix", theme.TEXTE_3, 12, 2.6))
        fermer.setFixedSize(18, 18)
        fermer.setCursor(Qt.CursorShape.PointingHandCursor)
        fermer.setToolTip("Effacer le texte importé")
        fermer.clicked.connect(self.effacer)
        ligne.addWidget(fermer)
        cadre.hide()
        return cadre

    # ------------------------------------------------------------------ glossaire et sens
    @property
    def cible(self) -> str:
        return autre_langue(self.source)

    def definir_glossaire(self, glossaire: Glossaire | None) -> None:
        """Change de glossaire ; la traduction affichée est refaite avec le nouveau glossaire."""
        self.glossaire = glossaire
        self.traducteur = Traducteur(glossaire) if glossaire is not None and len(glossaire) else None
        if self.traduction is not None:
            self.traduire(deviner=False)
        else:
            self._afficher(None)

    def definir_sens(self, source: str) -> None:
        """Fixe la langue source (l'autre langue devient la langue cible)."""
        if source == self.source:
            return
        self.source = source
        self._appliquer_sens()
        self._afficher(None)
        self.sens_change.emit(source)

    def inverser(self) -> None:
        """Inverse le sens de traduction. Le texte source est conservé ; la traduction est effacée."""
        self.definir_sens(autre_langue(self.source))

    def _appliquer_sens(self) -> None:
        self.panneau_source.definir_langue(self.source)
        self.panneau_cible.definir_langue(self.cible)
        self.zone_source.setPlaceholderText(_INVITES[self.source])

    # ------------------------------------------------------------------ texte source
    def texte(self) -> str:
        """Le texte source, tel qu'il est saisi."""
        return self.zone_source.toPlainText()

    def definir_texte(self, texte: str, fichier: Path | None = None) -> None:
        """Remplace le texte source (texte importé ou exemple)."""
        self._modification_interne = True
        try:
            self.zone_source.setPlainText(texte)
            self.panneau_source.appliquer_l_interligne()
        finally:
            self._modification_interne = False
        self.fichier = fichier
        self._afficher(None)

    def inserer_un_exemple(self) -> None:
        self.definir_texte(EXEMPLES[self.source])
        self.zone_source.setFocus()

    def effacer(self) -> None:
        """Vide le texte source et la traduction."""
        self.definir_texte("")
        self.zone_source.setFocus()

    def _texte_modifie(self) -> None:
        self._decompte_differe.start()
        if self._modification_interne:
            return
        self.lien_exemple.setVisible(not self.texte().strip() and self.fichier is None)
        if self.traduction is not None and self.traduction.texte_source != self.texte():
            # Le texte ne correspond plus à la traduction affichée.
            self.zone_source.setExtraSelections([])
            self._definir_etat("Texte modifié", "attente",
                               "Le texte source a changé : cliquez sur « Traduire » pour mettre la traduction à jour.")

    def _afficher_le_decompte_source(self) -> None:
        self.decompte_source.definir_texte(*_decompte(*compter(self.texte())))

    # ------------------------------------------------------------------ traduction
    def traduire(self, *, deviner: bool = True) -> None:
        """Traduit le texte source et affiche le résultat.

        Si le texte est écrit dans l'autre langue, le sens de traduction est
        d'abord inversé (comme sur l'écran de recherche).

        ``deviner`` ne peut être donné que par son nom : un bouton relié à cette
        méthode lui passerait sinon son état (« coché » ou non) à la place.
        """
        texte = self.texte()
        if not texte.strip():
            self._afficher(None)
            self.message.emit("Saisissez, collez ou importez d’abord un texte à traduire.")
            return
        if self.traducteur is None:
            self._afficher(None)
            self.message.emit(_AUCUN_GLOSSAIRE)
            return
        if deviner:
            langue = deviner_langue(texte)
            if langue is not None and langue != self.source:
                self.definir_sens(langue)
                self.message.emit(f"Texte écrit en {NOM_EN_FRANCAIS[langue]} : le sens de traduction a été inversé.")
        self._afficher(self.traducteur.traduire(texte, self.source))
        resultat = self.traduction
        self.message.emit(f"Traduction : {_nombre(resultat.mots_reconnus, 'mot')} sur {resultat.mots} "
                          f"{'trouvé' if resultat.mots_reconnus < 2 else 'trouvés'} dans le glossaire.")

    def _afficher(self, traduction: Traduction | None) -> None:
        """Affiche une traduction, ou l'état initial si ``traduction`` est vide."""
        self.traduction = traduction
        self._afficher_le_decompte_source()
        self.lien_exemple.setVisible(not self.texte().strip() and self.fichier is None)
        self.fichier_importe.setVisible(self.fichier is not None)
        if self.fichier is not None:
            self.nom_du_fichier.definir_texte(self.fichier.name)
            self.fichier_importe.setToolTip(infobulle(f"Texte importé depuis {self.fichier}"))
        self.bande.afficher(traduction)
        self.termes.afficher(traduction)
        self.bouton_copier.setEnabled(traduction is not None)
        if traduction is None:
            self.zone_source.setExtraSelections([])
            self.zone_cible.clear()
            self.decompte_cible.definir_texte("")
            self.aide.definir_texte("")
            if self.traducteur is None:
                self._definir_etat("Aucun glossaire", "partiel", _AUCUN_GLOSSAIRE)
            else:
                self._definir_etat("", "attente")
        else:
            self._surligner_les_termes(traduction)
            self.zone_cible.setHtml(self._html(traduction))
            self.panneau_cible.appliquer_l_interligne()
            self.panneau_cible.orienter_les_paragraphes()
            self.decompte_cible.definir_texte(*_decompte(*traduction.decompte_cible()))
            restants = traduction.mots - traduction.mots_reconnus
            if traduction.complete:
                self._definir_etat("Traduction terminée", "termine",
                                   "Tous les mots du texte ont été trouvés dans le glossaire.")
                self.aide.definir_texte("")
            elif not traduction.mots_reconnus:
                self._definir_etat("Aucun mot trouvé", "partiel",
                                   "Aucun mot de ce texte ne figure dans le glossaire : le texte est recopié tel quel.")
                self.aide.definir_texte(*_AIDE_GRIS)
            else:
                self._definir_etat(
                    "Traduction partielle", "partiel",
                    f"{_nombre(restants, 'mot')} sur {traduction.mots} ne "
                    f"{'figure' if restants < 2 else 'figurent'} pas dans le glossaire : "
                    f"{'il reste' if restants < 2 else 'ils restent'} à traduire.")
                self.aide.definir_texte(*_AIDE_GRIS)
        self.traduction_changee.emit()

    def _definir_etat(self, texte: str, etat: str, explication: str = "") -> None:
        self.etat.setText(texte)
        self.etat.setVisible(bool(texte))
        self.etat.setToolTip(infobulle(explication))
        if self.etat.property("etat") != etat:
            self.etat.setProperty("etat", etat)
            _repeindre(self.etat)

    def _surligner_les_termes(self, traduction: Traduction) -> None:
        """Colore, dans le texte source, les termes trouvés dans le glossaire."""
        texte = traduction.texte_source
        # Qt compte les positions en unités UTF-16 : un caractère hors du plan de base en occupe deux.
        decalages = [rang for rang, caractere in enumerate(texte) if ord(caractere) > 0xFFFF]

        def position(indice: int) -> int:
            return indice + sum(1 for rang in decalages if rang < indice)

        couleur = QTextCharFormat()
        couleur.setForeground(QColor(theme.AMBRE))
        selections = []
        for occurrence in traduction.occurrences:
            curseur = QTextCursor(self.zone_source.document())
            curseur.setPosition(position(occurrence.debut))
            curseur.setPosition(position(occurrence.fin), QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = curseur
            selection.format = couleur
            selections.append(selection)
        self.zone_source.setExtraSelections(selections)

    def _html(self, traduction: Traduction) -> str:
        """Texte traduit : termes du glossaire en couleur, mots non traduits en gris."""
        morceaux = []
        for morceau in traduction.morceaux:
            texte = escape(morceau.texte)
            if morceau.nature == TERME:
                texte = f'<span style="color: {theme.AMBRE};">{texte}</span>'
            elif morceau.nature == SOURCE:
                texte = f'<span style="color: {_GRIS};">{texte}</span>'
            morceaux.append(texte)
        sens = "rtl" if traduction.cible == AR else "ltr"
        marque = MARQUE_RTL if traduction.cible == AR else ""
        return f'<div dir="{sens}" style="white-space: pre-wrap;">{marque}{"".join(morceaux)}</div>'

    # ------------------------------------------------------------------ presse-papiers et fichiers
    def copier(self) -> None:
        """Copie la traduction dans le presse-papiers."""
        if self.traduction is None:
            return
        QGuiApplication.clipboard().setText(self.traduction.texte)
        self.bouton_copier.setText("Copié")
        self._retour_copier.start()
        self.message.emit("Traduction copiée dans le presse-papiers")

    def importer(self, chemin: str | Path | None = None) -> bool:
        """Importe un fichier .txt, .docx ou .doc dans la zone source, puis le traduit."""
        if chemin is None:
            depart = str(self.fichier.parent) if self.fichier is not None else ""
            chemin, _ = QFileDialog.getOpenFileName(self, "Importer un texte", depart, documents.FILTRE_IMPORT)
            if not chemin:
                return False
        try:
            texte = documents.lire(chemin)
        except documents.ErreurDocument as erreur:
            self._avertir("Import impossible", str(erreur))
            return False
        if not texte.strip():
            self._avertir("Import impossible", f"« {Path(chemin).name} » ne contient pas de texte.")
            return False
        self.definir_texte(texte, Path(chemin))
        self.traduire()
        return True

    def exporter(self, chemin: str | Path | None = None) -> bool:
        """Enregistre la traduction dans un fichier .docx ou .txt."""
        if self.traduction is None:
            self.message.emit("Il n’y a pas encore de traduction à exporter.")
            return False
        if chemin is None:
            # À côté du fichier importé ; sinon dans le dossier « Documents ».
            documents_de_l_utilisateur = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation)
            dossier = self.fichier.parent if self.fichier is not None else Path(documents_de_l_utilisateur
                                                                                 or Path.home())
            propose = dossier / documents.nom_d_export(self.fichier)
            chemin, filtre = QFileDialog.getSaveFileName(self, "Exporter la traduction", str(propose),
                                                         ";;".join(documents.FILTRES_EXPORT.values()))
            if not chemin:
                return False
            if not Path(chemin).suffix:
                # Aucune extension saisie : on prend celle du format choisi dans la fenêtre.
                extension = next((ext for ext, nom in documents.FILTRES_EXPORT.items() if nom == filtre), ".docx")
                chemin += extension
        try:
            documents.ecrire(chemin, self.traduction.texte, self.traduction.cible)
        except documents.ErreurDocument as erreur:
            self._avertir("Export impossible", str(erreur))
            return False
        self.message.emit(f"Traduction enregistrée : {Path(chemin).name}")
        return True

    def _avertir(self, titre: str, texte: str) -> None:
        boite = QMessageBox(QMessageBox.Icon.Warning, titre, texte, QMessageBox.StandardButton.Ok, self)
        boite.setTextFormat(Qt.TextFormat.PlainText)
        boite.exec()
