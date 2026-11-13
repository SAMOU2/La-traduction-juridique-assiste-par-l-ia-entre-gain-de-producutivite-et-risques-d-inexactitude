"""Informations sur les termes juridiques d'un texte : une carte par terme, à droite de l'écran « Texte ».

Chaque carte reprend l'enchaînement de l'écran « Terme » :

① Terme → ② Définition → ③ Équivalent → ④ Contextualisation → ⑤ Ressources

L'en-tête d'une carte donne le terme et son équivalent. Un clic ouvre la carte : les cinq
étapes s'allument l'une après l'autre, avec la définition, l'équivalent, le passage du texte
où le terme figure et toutes les références.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..contextes import PROPRE, Emploi, emplois
from ..glossaire import Glossaire
from ..langues import AR, FR, cle_souple, deviner_langue
from ..traduction import TERME, TermeDetecte, Traduction
from . import icones, theme
from .animation import Allumage
from .composants import (
    DispositionFluide,
    EtiquetteCourte,
    Numero,
    Panneau,
    ZoneDefilante,
    capitales,
    compte,
    etiquette,
    icone_fixe,
    nombre,
    paragraphe,
    pastille,
    puce_neutre,
    separateur,
)
from .dessin import abreger, dessiner_ligne, dessiner_numero, largeur_du_texte, police
from .fiche import ETAPES as CHAMPS
from .fiche import INTERLIGNE, categorie_et_pluriel, mention_a_verifier, phrase_surlignee, ressource_en_html

#: Nombre de contextes du glossaire affichés dans une carte, après le passage du texte.
EMPLOIS_AFFICHES = 2


def passage_du_terme(terme: TermeDetecte, traduction: Traduction) \
        -> tuple[tuple[str, list[tuple[int, int]]], tuple[str, list[tuple[int, int]]]]:
    """Le passage du texte qui illustre un terme : une phrase du texte source et sa traduction.

    Renvoie, pour chacune, son texte et les positions (début, fin) du terme à mettre en
    évidence. Parmi les phrases où le terme figure, on retient la première dont la traduction
    contient l'équivalent du terme ; à défaut, la première phrase.
    """
    choix = None
    for occurrence in terme.occurrences:
        phrase = traduction.phrases[occurrence.phrase]
        evidences, position = [], 0
        for morceau in phrase.morceaux:
            if morceau.nature == TERME and morceau.entree is terme.entree:
                evidences.append((position, position + len(morceau.texte)))
            position += len(morceau.texte)
        if choix is None or evidences:
            choix = (phrase, evidences)
        if evidences:
            break
    phrase, evidences_cible = choix
    debut = phrase.source.debut
    evidences_source = [(occurrence.debut - debut, occurrence.fin - debut)
                        for occurrence in phrase.occurrences if occurrence.entree is terme.entree]
    return (phrase.source.texte, evidences_source), (phrase.texte, evidences_cible)


def passage_en_html(texte: str, evidences: Sequence[tuple[int, int]], langue: str) -> str:
    """Passage du texte en HTML : les positions données sont écrites en demi-gras, en bleu."""
    morceaux, position = [], 0
    for debut, fin in sorted(evidences):
        if debut < position:
            continue
        morceaux.append(escape(texte[position:debut]))
        morceaux.append(f'<span style="color: {theme.BLEU_FONCE}; font-weight: 600;">{escape(texte[debut:fin])}</span>')
        position = fin
    morceaux.append(escape(texte[position:]))
    return paragraphe("".join(morceaux), langue, INTERLIGNE[langue])


# ====================================================================== en-tête d'une carte
class EnteteCarte(QAbstractButton):
    """En-tête d'une carte : ① le terme, sa catégorie, ses occurrences ; à droite, l'équivalent.

    L'en-tête est dessiné directement : chaque texte est abrégé à la largeur exacte de sa place.
    """

    HAUTEUR = 58

    def __init__(self, carte: CarteTerme) -> None:
        super().__init__(carte)
        self.carte = carte
        self.setFixedHeight(self.HAUTEUR)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setText(f"{carte.libelle} — {carte.equivalent}")

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(320, self.HAUTEUR)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, self.HAUTEUR)

    def places(self) -> tuple[float, float, float, float]:
        """Abscisse et largeur du terme, puis de l'équivalent."""
        gauche = 20 + 18 + 12
        droite = self.width() - 20 - 16 - 12
        libre = max(droite - gauche - 16, 40)
        part = min(max(libre * 0.56, 90), libre - 60) if libre > 150 else libre * 0.56
        return gauche, part, gauche + part + 16, libre - part

    def sous_le_terme(self) -> tuple[str, str]:
        """Sous le terme : sa catégorie et son nombre d'occurrences, tels qu'ils sont affichés."""
        carte = self.carte
        place = self.places()[1]
        de_categorie, du_nombre = self._polices_du_terme()
        separation = 3 * largeur_du_texte(" ", du_nombre) + largeur_du_texte("·", du_nombre)
        formes = [(carte.categorie, carte.occurrences), (carte.categorie, carte.occurrences_en_bref),
                  ("", carte.occurrences), ("", carte.occurrences_en_bref)]
        for categorie, occurrences in formes:
            largeur = largeur_du_texte(occurrences, du_nombre)
            if categorie:
                largeur += largeur_du_texte(categorie, de_categorie) + separation
            if largeur <= place:
                return categorie, occurrences
        return formes[-1]

    def _polices_du_terme(self):
        if self.carte.source == AR:
            return police(self.font(), 14), police(self.font(), 12)
        return police(self.font(), 12, italique=True), police(self.font(), 12)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        carte = self.carte
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        largeur, hauteur = self.width(), self.height()
        survol = self.underMouse() or self.hasFocus()
        if carte.ouverte or survol:
            peintre.fillRect(self.rect(), QColor(theme.BLEU_50 if carte.ouverte else theme.GRIS_50))
        if self.hasFocus():
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1))
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            peintre.drawRect(QRectF(0.5, 0.5, largeur - 1, hauteur - 1))
        if carte.ouverte:
            # Trait doré sur le bord gauche de la carte ouverte (il se prolonge le long de son contenu).
            peintre.fillRect(QRectF(0, 0, 3, hauteur), QColor(theme.OR))
        base = self.font()
        dessiner_numero(peintre, QPointF(20 + 9, hauteur / 2), 9, "1", police(base, 11, gras=True),
                        carte.allumage.niveau(0), carte.allumage.halo(0))
        x_terme, place_terme, x_equivalent, place_equivalent = self.places()

        # ① Le terme ; dessous, sa catégorie et son nombre d'occurrences.
        categorie, occurrences = self.sous_le_terme()
        de_categorie, du_nombre = self._polices_du_terme()
        if carte.source == AR:
            du_terme = police(base, 17, gras=True)
            dessiner_ligne(peintre, QRectF(x_terme, 0, place_terme, hauteur), abreger(carte.libelle, du_terme,
                                                                                    place_terme),
                           du_terme, theme.BLEU_FONCE, langue=AR, alignement=Qt.AlignmentFlag.AlignLeft, base=27)
            suite = " · ".join(morceau for morceau in (occurrences, categorie) if morceau)
            dessiner_ligne(peintre, QRectF(x_terme, 0, place_terme, hauteur), abreger(suite, du_nombre, place_terme),
                           du_nombre, theme.TEXTE_3, base=46)
        else:
            du_terme = police(base, 14, gras=True)
            dessiner_ligne(peintre, QRectF(x_terme, 0, place_terme, hauteur), abreger(carte.libelle, du_terme,
                                                                                    place_terme),
                           du_terme, theme.BLEU_FONCE, base=25)
            x = x_terme
            if categorie:
                dessiner_ligne(peintre, QRectF(x, 0, place_terme, hauteur), categorie, de_categorie,
                               theme.TEXTE_3, base=44)
                x += largeur_du_texte(categorie, de_categorie)
                occurrences = " · " + occurrences
            dessiner_ligne(peintre, QRectF(x, 0, place_terme, hauteur), occurrences, du_nombre, theme.TEXTE_3,
                           base=44)

        # ③ L'équivalent, aligné à droite ; dessous, sa grammaire, ou l'avertissement s'il a plusieurs sens.
        droite = Qt.AlignmentFlag.AlignRight
        de_l_equivalent = police(base, 17 if carte.cible == AR else 14, gras=True)
        dessiner_ligne(peintre, QRectF(x_equivalent, 0, place_equivalent, hauteur),
                       abreger(carte.equivalent, de_l_equivalent, place_equivalent), de_l_equivalent,
                       theme.BLEU_FONCE, langue=carte.cible, alignement=droite, base=27 if carte.cible == AR else 25)
        if carte.alerte:
            de_l_alerte = police(base, 12, gras=carte.incertain)
            dessiner_ligne(peintre, QRectF(x_equivalent, 0, place_equivalent, hauteur),
                           abreger(carte.alerte, de_l_alerte, place_equivalent), de_l_alerte,
                           theme.AMBRE if carte.incertain else theme.TEXTE_3, alignement=droite, base=44)
        elif carte.grammaire:
            de_grammaire = police(base, 13 if carte.cible == AR else 12)
            grammaire = carte.grammaire
            if carte.categorie_cible and largeur_du_texte(grammaire, de_grammaire) > place_equivalent:
                grammaire = carte.categorie_cible
            dessiner_ligne(peintre, QRectF(x_equivalent, 0, place_equivalent, hauteur),
                           abreger(grammaire, de_grammaire, place_equivalent), de_grammaire, theme.TEXTE_3,
                           langue=carte.cible, alignement=droite, base=45 if carte.cible == AR else 44)

        chevron = icones.image("chevron-h" if carte.ouverte else "chevron-b",
                               theme.BLEU if carte.ouverte else theme.TEXTE_4, 16, 1.6)
        peintre.drawPixmap(QPointF(largeur - 20 - 16, (hauteur - 16) / 2), chevron)


# ====================================================================== carte d'un terme
class CarteTerme(QWidget):
    """Les informations d'un terme relevé dans le texte : les cinq champs de l'enchaînement.

    Le contenu de la carte n'est construit qu'à sa première ouverture : un long texte peut
    contenir des centaines de termes.
    """

    #: Demande d'ouverture de la fiche complète du terme (écran « Terme »).
    fiche_demandee = Signal(object)
    #: La carte vient d'être ouverte ou refermée.
    basculee = Signal()

    def __init__(self, terme: TermeDetecte, traduction: Traduction, glossaire: Glossaire | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detecte = terme
        self.glossaire = glossaire
        entree = self.entree = terme.entree
        source = self.source = traduction.source
        cible = self.cible = traduction.cible
        self.ouverte = False

        # ① Terme
        self.libelle = entree.terme(source)
        self.categorie = entree.categorie(source)
        self.occurrences = compte(len(terme.occurrences), "occurrence")
        self.occurrences_en_bref = f"{nombre(len(terme.occurrences))} occ."
        # ② Définition, dans la langue du texte puis dans l'autre langue.
        self.definitions = [(langue, entree.definition(langue)) for langue in (source, cible)
                            if entree.definition(langue)]
        self.langue_definition, self.definition = self.definitions[0] if self.definitions else (source, "")
        #: Vrai si la définition n'est reprise d'aucune source citée.
        self.a_verifier = not entree.source_definition or mention_a_verifier(entree.source_definition) is not None
        # ③ Équivalent ; s'il y a plusieurs sens, un avertissement le signale.
        self.equivalent = entree.terme(cible)
        self.grammaire = categorie_et_pluriel(entree, cible)
        self.categorie_cible = entree.categorie(cible)
        self.autres_equivalents = list(entree.synonymes(cible))
        self.incertain = terme.incertain
        autres = " / ".join(autre.terme(cible) for autre in terme.autres_candidats)
        self.alerte = "" if not autres else (f"Ambigu : aussi « {autres} »" if terme.incertain
                                             else f"Autre sens : « {autres} »")
        # ④ Contextualisation : la phrase du texte et sa traduction, puis les contextes du glossaire.
        self.passage_source, self.passage_cible = passage_du_terme(terme, traduction)
        # Un exemple du glossaire identique au passage du texte n'est pas répété.
        passage = cle_souple(self.passage_source[0])
        self.emplois: list[Emploi] = [emploi for emploi in emplois(glossaire, entree, EMPLOIS_AFFICHES + 1)
                                      if cle_souple(emploi.texte(source)) != passage][:EMPLOIS_AFFICHES]
        # ⑤ Ressources : toutes les références de l'entrée.
        self.ressources = list(entree.ressources)

        self.allumage = Allumage(len(CHAMPS), self)
        self.allumage.change.connect(self._rafraichir)
        self.numeros: dict[int, Numero] = {}
        self.entete = EnteteCarte(self)
        self.entete.clicked.connect(lambda: self.definir_ouverte(not self.ouverte))
        self.entete.setAccessibleDescription(self.definition)
        self.corps: QWidget | None = None
        self._ensemble = QVBoxLayout(self)
        self._ensemble.setContentsMargins(0, 0, 0, 0)
        self._ensemble.setSpacing(0)
        self._ensemble.addWidget(self.entete)
        self._filet = separateur()
        self._ensemble.addWidget(self._filet)

    # ------------------------------------------------------------------ ouverture
    def etapes_renseignees(self) -> list[bool]:
        """Pour chacune des cinq étapes : vrai si elle a quelque chose à montrer pour ce terme."""
        return [True, bool(self.definition), True, True, bool(self.ressources)]

    def definir_ouverte(self, ouverte: bool, *, animer: bool = True) -> None:
        """Ouvre ou referme la carte. À l'ouverture, les étapes renseignées s'allument l'une après l'autre."""
        if ouverte == self.ouverte:
            return
        self.ouverte = ouverte
        if ouverte and self.corps is None:
            self.corps = self._construire_le_corps()
            self._ensemble.insertWidget(1, self.corps)
        if self.corps is not None:
            self.corps.setVisible(ouverte)
        self.allumage.definir(self.etapes_renseignees() if ouverte else [False] * len(CHAMPS), animer=animer)
        self.entete.update()
        self.basculee.emit()

    def _rafraichir(self) -> None:
        self.entete.update()
        for rang, numero in self.numeros.items():
            numero.definir(self.allumage.niveau(rang), self.allumage.halo(rang))

    # ------------------------------------------------------------------ contenu
    def _section(self, corps: QVBoxLayout, rang: int, mention: QWidget | None = None) -> QVBoxLayout:
        """Ajoute le titre numéroté d'un champ ; renvoie la disposition où placer son contenu."""
        ligne = QHBoxLayout()
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(6)
        numero = Numero(rang + 1, rayon=9)
        self.numeros[rang] = numero
        ligne.addWidget(numero)
        ligne.addWidget(capitales(CHAMPS[rang], "capitalesBleu" if rang == 2 else "capitales"))
        ligne.addStretch(1)
        if mention is not None:
            ligne.addWidget(mention)
        corps.addLayout(ligne)
        contenu = QVBoxLayout()
        contenu.setContentsMargins(numero.width() + 6, 0, 0, 0)
        contenu.setSpacing(0)
        corps.addLayout(contenu)
        return contenu

    def _mention_de_la_definition(self) -> QWidget | None:
        """À droite du titre « Définition » : la source citée, ou la mention « À vérifier »."""
        if not self.definition:
            return None
        mention = QWidget()
        ligne = QHBoxLayout(mention)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(5)
        if self.a_verifier:
            ligne.addWidget(icone_fixe("alerte", theme.AMBRE, 14, 1.6))
            texte = etiquette("À vérifier", "piedAlerte")
            texte.setToolTip("Définition à vérifier : elle n’est reprise d’aucune source citée.")
        else:
            ligne.addWidget(icone_fixe("document", theme.TEXTE_3, 14))
            texte = EtiquetteCourte(f"Source : {self.entree.source_definition}", "pied")
            texte.setMaximumWidth(260)
        ligne.addWidget(texte)
        return mention

    def _construire_le_corps(self) -> QWidget:
        entree, source, cible = self.entree, self.source, self.cible
        cadre = QWidget()
        corps = QVBoxLayout(cadre)
        corps.setContentsMargins(14, 2, 20, 16)
        corps.setSpacing(0)

        # ② Définition
        contenu = self._section(corps, 1, self._mention_de_la_definition())
        if not self.definitions:
            contenu.addWidget(etiquette("Aucune définition dans le glossaire.", "discret", retour_ligne=True))
        for rang, (langue, definition) in enumerate(self.definitions):
            if rang:
                contenu.addSpacing(4)
            contenu.addWidget(etiquette(paragraphe(escape(definition), langue, INTERLIGNE[langue]), "definition",
                                        langue, retour_ligne=True, selectionnable=True, riche=True))
        corps.addSpacing(8)

        # ③ Équivalent
        contenu = self._section(corps, 2)
        self.etiquette_equivalent = etiquette(paragraphe(escape(self.equivalent), cible, 34 if cible == AR else 27),
                                              "equivalentCarte", cible, retour_ligne=True, selectionnable=True,
                                              riche=True)
        contenu.addWidget(self.etiquette_equivalent)
        if self.grammaire:
            contenu.addWidget(etiquette(self.grammaire, "grammaire", cible, retour_ligne=True))
        if self.autres_equivalents:
            contenu.addSpacing(6)
            zone = QWidget()
            zone.setLayoutDirection(Qt.LayoutDirection.RightToLeft if cible == AR else Qt.LayoutDirection.LeftToRight)
            rangee = DispositionFluide(zone, 6, 6)
            for autre in self.autres_equivalents:
                rangee.addWidget(puce_neutre(autre, cible))
            contenu.addWidget(zone)
        if self.alerte:
            contenu.addSpacing(6)
            detail = ("Le contexte n’a pas permis de choisir entre les sens de ce terme : vérifiez l’équivalent."
                      if self.incertain else "Ce terme a d’autres sens dans le glossaire.")
            contenu.addWidget(etiquette(f"{self.alerte}. {detail}", "alerteCarte" if self.incertain else "discret",
                                        retour_ligne=True))
        corps.addSpacing(8)

        # ④ Contextualisation : le passage du texte, puis les contextes du glossaire
        contenu = self._section(corps, 3)
        contenu.addWidget(etiquette("Dans le texte", "sousTitre"))
        contenu.addSpacing(2)
        for langue, (texte, evidences) in ((source, self.passage_source), (cible, self.passage_cible)):
            if texte.strip():
                contenu.addWidget(etiquette(passage_en_html(texte.strip(), _decaler(texte, evidences), langue),
                                            "definition", langue, retour_ligne=True, selectionnable=True, riche=True))
        for emploi in self.emplois:
            contenu.addSpacing(10)
            provenance = emploi.provenance(source)
            titre = "Dans le glossaire" + (f" · {provenance}" if provenance else "")
            mention = EtiquetteCourte(titre, "sousTitre")
            if emploi.origine != PROPRE:
                mention.setToolTip(f"Phrase trouvée dans l’entrée « {emploi.entree.terme(source)} » du glossaire.")
            contenu.addWidget(mention)
            contenu.addSpacing(2)
            for langue in (source, cible):
                if emploi.texte(langue):
                    contenu.addWidget(etiquette(phrase_surlignee(emploi.texte(langue), entree, langue), "definition",
                                                langue, retour_ligne=True, selectionnable=True, riche=True))
        corps.addSpacing(8)

        # ⑤ Ressources : toutes les références, écrites en entier
        contenu = self._section(corps, 4)
        if not self.ressources:
            contenu.addWidget(etiquette("Aucune ressource dans le glossaire.", "discret", retour_ligne=True))
        for rang, ressource in enumerate(self.ressources):
            if rang:
                contenu.addSpacing(7)
            langue = deviner_langue(ressource) or FR
            reference = etiquette(ressource_en_html(ressource, langue), "ressource", langue, retour_ligne=True,
                                  riche=True)
            reference.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            reference.setOpenExternalLinks(True)
            contenu.addWidget(reference)

        corps.addSpacing(12)
        pied = QHBoxLayout()
        pied.setContentsMargins(36, 0, 0, 0)
        self.lien_fiche = QPushButton("Ouvrir la fiche du terme")
        self.lien_fiche.setProperty("classe", "lien")
        self.lien_fiche.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lien_fiche.setToolTip(f"Afficher « {self.libelle} » sur l’écran « Terme »")
        self.lien_fiche.clicked.connect(lambda: self.fiche_demandee.emit(self.entree))
        pied.addWidget(self.lien_fiche)
        pied.addStretch(1)
        corps.addLayout(pied)
        return cadre

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        if self.ouverte:
            # Trait doré sur le bord gauche de la carte ouverte.
            peintre = QPainter(self)
            peintre.fillRect(QRectF(0, 0, 3, self.height() - 1), QColor(theme.OR))


def _decaler(texte: str, evidences: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Positions reportées dans le texte privé de ses espaces de début."""
    retrait = len(texte) - len(texte.lstrip())
    limite = len(texte.strip())
    return [(max(debut - retrait, 0), min(fin - retrait, limite)) for debut, fin in evidences if fin - retrait > 0]


# ====================================================================== message d'un panneau vide
class MessageVide(QWidget):
    """Message centré, affiché à la place des cartes quand il n'y a aucun terme à montrer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.titre = self.texte = ""

    def definir(self, titre: str, texte: str) -> None:
        self.titre, self.texte = titre, texte
        self.setAccessibleName(titre)
        self.setAccessibleDescription(texte)
        self.update()

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        du_titre, du_texte = police(self.font(), 13, gras=True), police(self.font(), 13)
        place = self.width() - 2 * theme.MARGE
        avec_disque = self.height() >= 124
        hauteur = (40 + 14 if avec_disque else 0) + 20 + 4 + 20
        y = max((self.height() - hauteur) / 2 - 4, 4)
        if avec_disque:
            centre = QPointF(self.width() / 2, y + 20)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_100))
            peintre.drawEllipse(centre, 20, 20)
            peintre.drawPixmap(QPointF(centre.x() - 9, centre.y() - 9), icones.image("texte", theme.TEXTE_4, 18))
            y += 54
        centre_h = Qt.AlignmentFlag.AlignHCenter
        dessiner_ligne(peintre, QRectF(theme.MARGE, y, place, 20), abreger(self.titre, du_titre, place),
                       du_titre, theme.TEXTE_2, alignement=centre_h)
        dessiner_ligne(peintre, QRectF(theme.MARGE, y + 24, place, 20), abreger(self.texte, du_texte, place),
                       du_texte, theme.TEXTE_3, alignement=centre_h)


# ====================================================================== le panneau
class PanneauTermes(Panneau):
    """Les termes du glossaire relevés dans le texte, avec leurs informations."""

    #: Demande d'ouverture de la fiche d'une entrée sur l'écran « Terme ».
    ouverture = Signal(object)

    HAUTEUR_DU_TITRE = 42

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cartes: list[CarteTerme] = []
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)

        titre = QWidget()
        titre.setFixedHeight(self.HAUTEUR_DU_TITRE)
        ligne = QHBoxLayout(titre)
        ligne.setContentsMargins(20, 0, 20, 0)
        ligne.setSpacing(10)
        self.titre = etiquette("Termes juridiques détectés", "titrePanneau")
        self.nombre = pastille()
        self.aide = EtiquetteCourte("", "aidePanneau")
        self.aide.definir_texte("Cliquez sur un terme pour afficher ses informations", "Cliquez sur un terme", "")
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.bouton_tout = QPushButton("Tout développer")
        self.bouton_tout.setProperty("classe", "lien")
        self.bouton_tout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_tout.clicked.connect(self._basculer_tout)
        ligne.addWidget(self.titre)
        ligne.addWidget(self.nombre)
        ligne.addWidget(self.aide, 1)
        ligne.addWidget(self.bouton_tout)
        ensemble.addWidget(titre)
        ensemble.addWidget(separateur())

        self._liste = QWidget()
        self._colonne = QVBoxLayout(self._liste)
        self._colonne.setContentsMargins(0, 0, 0, 0)
        self._colonne.setSpacing(0)
        self._colonne.addStretch(1)
        self.defilement = ZoneDefilante()
        self.defilement.definir_contenu(self._liste)
        ensemble.addWidget(self.defilement, 1)
        self.message = MessageVide()
        ensemble.addWidget(self.message, 1)
        self.setMinimumHeight(self.HAUTEUR_DU_TITRE + 2 * EnteteCarte.HAUTEUR)
        self.afficher(None)

    # ------------------------------------------------------------------ contenu
    def afficher(self, traduction: Traduction | None, glossaire: Glossaire | None = None, *,
                 sans_glossaire: bool = False) -> None:
        """Affiche les termes relevés par une traduction ; sans traduction, un message d'attente."""
        for carte in self.cartes:
            carte.setParent(None)
            carte.deleteLater()
        self.cartes = []
        termes = traduction.termes if traduction is not None else []
        for rang, terme in enumerate(termes):
            carte = CarteTerme(terme, traduction, glossaire)
            carte.fiche_demandee.connect(self.ouverture)
            carte.basculee.connect(self._actualiser_le_bouton)
            self._colonne.insertWidget(rang, carte)
            self.cartes.append(carte)
        if sans_glossaire:
            self.message.definir("Aucun glossaire n’est chargé", "Choisissez un fichier CSV dans « Paramètres ».")
        elif traduction is None:
            self.message.definir("Les termes juridiques du texte s’afficheront ici",
                                 "Saisissez ou importez un texte, puis cliquez sur « Traduire ».")
        else:
            self.message.definir("Aucun terme du glossaire dans ce texte",
                                 "Aucun mot de ce texte ne figure parmi les termes du glossaire.")
        self.nombre.setText(nombre(len(termes)))
        self.nombre.setVisible(traduction is not None)
        self.aide.setVisible(bool(termes))
        self.bouton_tout.setVisible(len(termes) > 1)
        self.defilement.setVisible(bool(termes))
        self.message.setVisible(not termes)
        self.defilement.revenir_en_haut()
        if self.cartes:
            # Le premier terme est ouvert : ses étapes s'allument.
            self.cartes[0].definir_ouverte(True)
        self._actualiser_le_bouton()

    def lignes_affichees(self) -> list[CarteTerme]:
        """Les cartes, dans l'ordre d'apparition des termes dans le texte."""
        return list(self.cartes)

    def carte_de(self, entree) -> CarteTerme | None:
        return next((carte for carte in self.cartes if carte.entree is entree), None)

    # ------------------------------------------------------------------ ouverture des cartes
    def ouvrir(self, entree) -> bool:
        """Ouvre la carte d'un terme (les autres sont refermées) et la fait défiler jusqu'à la vue."""
        cible = self.carte_de(entree)
        if cible is None:
            return False
        for carte in self.cartes:
            if carte is not cible:
                carte.definir_ouverte(False)
        cible.definir_ouverte(True)
        QTimer.singleShot(0, lambda: self._montrer(cible))
        return True

    def _montrer(self, carte: CarteTerme) -> None:
        if carte in self.cartes:
            self._liste.layout().activate()
            self.defilement.verticalScrollBar().setValue(max(carte.y() - 8, 0))

    def tout_ouvert(self) -> bool:
        return bool(self.cartes) and all(carte.ouverte for carte in self.cartes)

    def definir_tout(self, ouvert: bool) -> None:
        """Ouvre ou referme toutes les cartes d'un coup (sans animation)."""
        for carte in self.cartes:
            carte.definir_ouverte(ouvert, animer=False)
        if not ouvert:
            self.defilement.revenir_en_haut()

    def _basculer_tout(self) -> None:
        self.definir_tout(not self.tout_ouvert())

    def _actualiser_le_bouton(self) -> None:
        self.bouton_tout.setText("Tout réduire" if self.tout_ouvert() else "Tout développer")


__all__ = ["EMPLOIS_AFFICHES", "CarteTerme", "EnteteCarte", "MessageVide", "PanneauTermes", "passage_du_terme",
           "passage_en_html"]
