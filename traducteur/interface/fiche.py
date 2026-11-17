"""La fiche d'un terme : le terme et son équivalent, côte à côte dans un seul panneau.

Les autres informations de l'entrée (définition, contextualisation, ressources, synonymes, termes
associés, expressions) ne sont pas dans la fiche : le menu « Plus de détails » les affiche à la
demande (voir ``details.py``). Chacune est une « colonne », comme le terme et l'équivalent : un
corps, construit à partir d'une entrée du glossaire et du sens de traduction, et un pied.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from html import escape

import regex
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..contextes import DEFINITION, PROPRE, Emploi, emplois
from ..glossaire import Entree, Glossaire, mention_a_verifier
from ..langues import AR, FR, NOM_EN_FRANCAIS, autre_langue, deviner_langue
from ..surlignage import positions_du_terme
from . import icones, theme
from .composants import (
    ESPACE_INVISIBLE,
    DispositionColonnes,
    DispositionFluide,
    EtiquetteCourte,
    Panneau,
    TermeAjuste,
    ZoneDefilante,
    bornes_des_colonnes,
    capitales,
    compte,
    direction,
    etiquette,
    icone_fixe,
    infobulle,
    mention_a_controler,
    nombre,
    paragraphe,
    puce,
    puce_neutre,
    rond,
    separateur,
    vider,
)
from .dessin import abreger, dessiner_ligne, largeur_du_texte, police

#: Les deux colonnes de la fiche : le terme, dans la langue source, et son équivalent, dans la langue cible.
COLONNES = ("Terme", "Équivalent")
#: Largeurs relatives des deux colonnes.
PROPORTIONS = (1, 1)
#: Largeur minimale de la fiche.
LARGEUR_MINIMALE = 560
HAUTEUR_ONGLETS, HAUTEUR_PIED = 38, 44
#: Hauteur du corps de la fiche dans la fenêtre de référence (1440 × 860), et hauteur minimale.
HAUTEUR_DU_CORPS, HAUTEUR_MINIMALE_DU_CORPS = 196, 132
#: Hauteur de la ligne du terme et de celle de l'équivalent : la même, pour que les deux mots soient
#: écrits à la même hauteur dans les deux colonnes, quelle que soit la taille de leurs caractères.
HAUTEUR_DU_TERME = 78
#: Espace entre la légende d'une colonne (« FRANÇAIS · SOURCE ») et le terme.
ESPACE_SOUS_LA_LEGENDE = 10

#: Hauteur des lignes d'un paragraphe, selon la langue.
INTERLIGNE = {FR: 22, AR: 30}

_ADRESSE = regex.compile(r"(?:https?://|www\.)[^\s<>«»]+[^\s<>«».,;:!?)]")
#: Marge au-dessus du message d'un champ vide, la même dans toutes les colonnes.
_MARGE_HAUTE_DU_MESSAGE = 20


# ====================================================================== fonctions d'affichage
def categorie_et_pluriel(entree: Entree, langue: str) -> str:
    """« nom masculin · pl. contrats » ou « اسم مذكر، ج. عقود »."""
    categorie, pluriel = entree.categorie(langue), entree.pluriel(langue)
    if langue == AR:
        return "، ".join(morceau for morceau in (categorie, f"ج. {pluriel}" if pluriel else "") if morceau)
    return " · ".join(morceau for morceau in (categorie, f"pl. {pluriel}" if pluriel else "") if morceau)


def equivalent_a_verifier(entree: Entree) -> str | None:
    """Détail de la mention « à vérifier » qui porte sur l'équivalent d'une entrée ; ``None`` sans mention.

    Sans définition, une mention « à vérifier » écrite dans la colonne « source_definition » porte
    sur l'équivalent : c'est le cas des termes seuls du glossaire fourni, marqués « à vérifier
    (équivalent d'exemple) ». Le détail rendu est alors « équivalent d'exemple ».
    """
    if entree.definition_fr or entree.definition_ar:
        return None
    return mention_a_verifier(entree.source_definition)


def _categorie_en_html(entree: Entree, langue: str) -> str:
    """La catégorie et le pluriel ; en français, la catégorie est en italique."""
    if langue == AR:
        return escape(categorie_et_pluriel(entree, AR))
    categorie, pluriel = entree.categorie(FR), entree.pluriel(FR)
    morceaux = ([f"<i>{escape(categorie)}</i>"] if categorie else []) + ([f"pl. {escape(pluriel)}"] if pluriel else [])
    return " · ".join(morceaux)


def phrase_surlignee(phrase: str, entree: Entree, langue: str) -> str:
    """Phrase d'exemple en HTML, le terme de l'entrée mis en évidence."""
    morceaux, position = [], 0
    for debut, fin in positions_du_terme(phrase, entree, langue):
        morceaux.append(escape(phrase[position:debut]))
        morceaux.append(f'<span style="color: {theme.BLEU_FONCE}; font-weight: 600;">'
                        f"{escape(phrase[debut:fin])}</span>")
        position = fin
    morceaux.append(escape(phrase[position:]))
    return paragraphe("".join(morceaux), langue, INTERLIGNE[langue])


def ressource_en_html(ressource: str, langue: str) -> str:
    """Référence en HTML : première partie en demi-gras, la suite en gris, adresses web cliquables."""
    virgule = "،" if langue == AR else ","
    titre, separation, suite = ressource.partition(virgule)
    if not separation or _ADRESSE.search(titre):
        titre, suite = "", ressource
    taille_titre, ligne_titre, ligne_suite = (15, 26, 23) if langue == AR else (13, 19, 18)
    html = ""
    if titre:
        html += paragraphe(f'<span style="color: {theme.TEXTE}; font-size: {taille_titre}px; font-weight: 600;">'
                           f"{escape(titre.strip())}</span>", langue, ligne_titre)
    if suite.strip():
        html += paragraphe(_avec_liens(suite.strip()), langue, ligne_suite)
    return html


def _avec_liens(texte: str) -> str:
    morceaux, position = [], 0
    for trouve in _ADRESSE.finditer(texte):
        adresse = trouve.group()
        cible = adresse if adresse.startswith("http") else "https://" + adresse
        # Une longue adresse peut passer à la ligne après chaque « / ».
        visible = escape(adresse).replace("/", "/" + ESPACE_INVISIBLE)
        morceaux.append(escape(texte[position:trouve.start()]))
        morceaux.append(f'<a href="{escape(cible, quote=True)}" style="color: {theme.BLEU}; '
                        f'text-decoration: none;">{visible}&nbsp;↗</a>')
        position = trouve.end()
    morceaux.append(escape(texte[position:]))
    return "".join(morceaux)


def _tailles_du_terme(terme: str, langue: str, role: str) -> tuple[int, int]:
    """Tailles maximale et minimale des caractères d'un terme affiché en grand.

    Les termes longs sont écrits plus petit ; l'équivalent (``role`` « cible ») est écrit plus
    grand que le terme, et l'arabe un peu plus grand que le français.
    """
    if role == "cible":
        paliers = (((8, 58), (16, 42), (28, 32), (999, 26)) if langue == AR
                   else ((10, 44), (18, 32), (30, 25), (999, 21)))
    else:
        paliers = ((10, 48), (18, 36), (999, 28)) if langue == AR else ((12, 40), (22, 30), (999, 24))
    maximale = next(taille for limite, taille in paliers if len(terme) <= limite)
    return maximale, min(maximale, 16 if langue == AR else 14)


# ====================================================================== onglets des sens
class Onglet(QAbstractButton):
    """Onglet d'un sens du terme : « Sens 1 », l'équivalent, le premier domaine."""

    def __init__(self, rang: int, entree: Entree, source: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entree = entree
        self._cible = autre_langue(source)
        self.numero = f"Sens {rang}"
        self.equivalent = entree.terme(self._cible)
        self.domaine = entree.domaines[0] if entree.domaines else ""
        self.setText(f"{self.numero} : {self.equivalent}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip("Afficher la fiche de ce sens")

    def _polices(self) -> tuple[QFont, QFont, QFont]:
        return (police(self.font(), 13, gras=True), police(self.font(), 15 if self._cible == AR else 13, gras=True),
                police(self.font(), 13))

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        numero, equivalent, domaine = self._polices()
        largeur = 12 + largeur_du_texte(self.numero, numero) + 8 + largeur_du_texte(self.equivalent, equivalent) + 12
        if self.domaine:
            largeur += 8 + largeur_du_texte(self.domaine, domaine)
        return QSize(round(largeur) + 1, 26)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        choisi = self.isChecked()
        cadre = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if choisi:
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1))
            peintre.setBrush(QColor(theme.SURFACE))
            peintre.drawRoundedRect(cadre, 7, 7)
        elif self.underMouse() or self.hasFocus():
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.GRIS_200))
            peintre.drawRoundedRect(cadre, 7, 7)
        numero, equivalent, domaine = self._polices()
        x = 12.0
        for texte, police_du_texte, couleur, langue in (
                (self.numero, numero, theme.TEXTE if choisi else theme.TEXTE_3, FR),
                (self.equivalent, equivalent, theme.BLEU_FONCE if choisi else theme.TEXTE_2, self._cible),
                (self.domaine, domaine, theme.TEXTE_3, FR)):
            if not texte:
                continue
            largeur = largeur_du_texte(texte, police_du_texte) + 1
            dessiner_ligne(peintre, QRectF(x, 0, largeur, self.height()), texte, police_du_texte, couleur,
                           langue=langue, alignement=Qt.AlignmentFlag.AlignLeft, base=17.5)
            x += largeur + 7


class BandeDesSens(QWidget):
    """Bande d'onglets affichée en haut de la fiche quand le terme a plusieurs sens dans le glossaire."""

    #: Un onglet a été choisi ; le signal porte l'entrée du glossaire.
    sens_choisi = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(HAUTEUR_ONGLETS)
        self.onglets: list[Onglet] = []
        self._groupe = QButtonGroup(self)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(16, 0, theme.MARGE, 1)
        ligne.setSpacing(6)
        self._zone = QHBoxLayout()
        self._zone.setSpacing(6)
        ligne.addLayout(self._zone)
        ligne.addSpacing(30)
        # L'avertissement est aligné à droite ; il raccourcit, puis disparaît, quand la place manque.
        self.avertissement = EtiquetteCourte("", "alerteSens")
        self.avertissement.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.avertissement.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ligne.addWidget(self.avertissement, 1)
        # Le signe précède le texte : il est placé juste devant lui (voir « _placer_le_signe »).
        self._signe = icone_fixe("alerte", theme.AMBRE, 14, 1.6)
        self._signe.setParent(self)
        # Le texte choisit sa forme (longue, courte…) quand sa largeur change : le signe est alors replacé.
        self.avertissement.installEventFilter(self)

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.fillRect(self.rect(), QColor(theme.GRIS_50))
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer_le_signe()

    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802
        if objet is self.avertissement and evenement.type() == QEvent.Type.Resize:
            # Le texte n'a pas encore pris sa nouvelle forme : le signe est replacé juste après.
            QTimer.singleShot(0, self, self._placer_le_signe)
        return False

    def afficher(self, sens: Sequence[Entree], courant: Entree | None, source: str) -> None:
        """Affiche un onglet par sens ; la bande est cachée s'il n'y a qu'un sens."""
        for onglet in self.onglets:
            self._groupe.removeButton(onglet)
        vider(self._zone)
        self.onglets = []
        if len(sens) < 2 or courant is None:
            self.hide()
            return
        for rang, entree in enumerate(sens, start=1):
            onglet = Onglet(rang, entree, source)
            onglet.setChecked(entree is courant)
            onglet.clicked.connect(lambda _=False, choisi=entree: self.sens_choisi.emit(choisi))
            self._groupe.addButton(onglet)
            self._zone.addWidget(onglet)
            self.onglets.append(onglet)
        self.avertissement.definir_texte(
            f"« {courant.terme(source)} » a {len(sens)} sens dans le glossaire : "
            "choisissez celui qui convient au texte.",
            f"{len(sens)} sens dans le glossaire : choisissez celui qui convient.", f"{len(sens)} sens", "")
        self.show()
        self._placer_le_signe()

    def _placer_le_signe(self) -> None:
        """Place le signe d'avertissement juste devant le texte, lui-même aligné à droite."""
        texte = self.avertissement.text()
        self._signe.setVisible(bool(texte))
        if texte:
            largeur = self.avertissement.fontMetrics().horizontalAdvance(texte)
            x = self.avertissement.geometry().right() - largeur - 7 - self._signe.width()
            self._signe.move(max(x, 0), (self.height() - self._signe.height()) // 2)


# ====================================================================== colonnes de la fiche
class Colonne(QObject):
    """Un champ de la fiche : un corps, placé dans la zone défilante, et un pied."""

    #: Demande d'ouverture d'une autre entrée du glossaire (clic sur une puce).
    entree_demandee = Signal(object)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)

    #: Marge au-dessus du premier élément du corps.
    marge_haute = 16

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.entree: Entree | None = None
        self.source = FR
        self.corps = QWidget()
        self.disposition = QVBoxLayout(self.corps)
        self.disposition.setSpacing(0)
        self._reserve = -1
        self.definir_reserve(0)
        self.pied = QWidget()
        self.ligne_du_pied = QHBoxLayout(self.pied)
        self.ligne_du_pied.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        self.ligne_du_pied.setSpacing(7)

    def widgets(self) -> tuple[QWidget, QWidget]:
        """Le corps et le pied de la colonne."""
        return self.corps, self.pied

    # ------------------------------------------------------------------ hauteur
    def hauteur_naturelle(self, largeur: int) -> int:
        """Hauteur qu'il faut au contenu de la colonne, pour une largeur donnée."""
        return self.disposition.heightForWidth(largeur) - self._reserve

    def definir_reserve(self, reserve: int) -> None:
        """Laisse ``reserve`` pixels vides au bas de la colonne (voir ``Fiche._centrer_dans_la_vue``)."""
        reserve = max(reserve, 0)
        if reserve != self._reserve:
            self._reserve = reserve
            self.disposition.setContentsMargins(theme.MARGE, self.marge_haute, theme.MARGE, 16 + reserve)

    # ------------------------------------------------------------------ affichage
    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str) -> None:
        """Affiche une entrée du glossaire (rien si ``entree`` est vide)."""
        self.glossaire, self.entree, self.source = glossaire, entree, source
        vider(self.disposition)
        vider(self.ligne_du_pied)
        self.corps.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        if entree is not None:
            self.remplir(entree, source, autre_langue(source))

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        """Construit le contenu de la colonne (à définir dans chaque colonne)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ outils communs
    def _rubrique(self, titre: str) -> QLabel:
        """Petit titre en capitales (« DOMAINE », « SYNONYMES »…), précédé d'un espace."""
        self.disposition.addSpacing(18)
        label = capitales(titre)
        self.disposition.addWidget(label)
        self.disposition.addSpacing(6)
        return label

    def _rangee_de_puces(self, puces: Sequence[QWidget], *, centre: bool = False, espace: int = 6) -> QWidget:
        conteneur = QWidget()
        rangee = DispositionFluide(conteneur, espace, espace, centre=centre)
        for element in puces:
            rangee.addWidget(element)
        self.disposition.addWidget(conteneur)
        return conteneur

    def _puce_de_terme(self, texte: str, langue: str | None = None, *, grande: bool = False) -> QWidget:
        """Puce d'un terme : cliquable si ce terme est une autre entrée du glossaire.

        ``langue`` est la langue du terme quand elle est connue (un synonyme) ; sinon elle est
        déduite de son écriture (un terme associé peut être écrit dans l'une ou l'autre langue).
        """
        ecriture = langue or deviner_langue(texte) or FR
        autre = None
        if self.glossaire is not None:
            autre = self.glossaire.par_terme(texte, ecriture)
            if autre is None and langue is None:
                autre = self.glossaire.par_terme(texte, autre_langue(ecriture))
        if autre is None or autre is self.entree:
            return puce_neutre(texte, ecriture, hauteur=30 if grande else theme.HAUTEUR_PUCE, grande=grande)
        bouton = (puce(texte, ecriture, classe="puceExemple", hauteur=30, info="Ouvrir cette entrée du glossaire")
                  if grande else puce(texte, ecriture, info="Ouvrir cette entrée du glossaire"))
        bouton.clicked.connect(lambda _=False, cible=autre: self.entree_demandee.emit(cible))
        return bouton

    def _vide(self, nom_icone: str, titre: str, texte: str) -> None:
        """Message centré, affiché quand le glossaire ne donne rien pour ce champ."""
        # Les colonnes n'ont pas la même marge haute : ce complément met leurs messages à la même hauteur.
        self.disposition.addSpacing(_MARGE_HAUTE_DU_MESSAGE - self.marge_haute)
        self.disposition.addStretch(2)
        self.disposition.addWidget(rond("rondVide", 40, nom_icone, theme.TEXTE_4, 18), 0,
                                   Qt.AlignmentFlag.AlignHCenter)
        self.disposition.addSpacing(14)
        for contenu, classe in ((titre, "videTitre"), (texte, "videTexte")):
            label = etiquette(contenu, classe, retour_ligne=True)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.disposition.addWidget(label)
            self.disposition.addSpacing(6)
        self.disposition.addStretch(3)

    def _lien_du_pied(self, texte: str, action, texte_confirme: str) -> QPushButton:
        """Lien du pied de la colonne ; son libellé confirme brièvement l'action."""
        bouton = QPushButton(texte)
        bouton.setProperty("classe", "lien")
        bouton.setIcon(icones.icone("copier", theme.BLEU, 16))
        bouton.setIconSize(QSize(16, 16))
        bouton.setCursor(Qt.CursorShape.PointingHandCursor)

        # Le libellé d'origine revient après un court instant.
        retour = QTimer(bouton)
        retour.setSingleShot(True)
        retour.setInterval(1600)
        retour.timeout.connect(lambda: bouton.setText(texte))

        def executer() -> None:
            action()
            bouton.setText(texte_confirme)
            retour.start()

        bouton.clicked.connect(executer)
        return bouton


class ColonneTerme(Colonne):
    """Le terme recherché, dans la langue source : sa catégorie grammaticale et son domaine."""

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        centre = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        legende = capitales(f"{NOM_EN_FRANCAIS[source]} · source")
        legende.setAlignment(centre)
        corps.addWidget(legende)
        corps.addSpacing(ESPACE_SOUS_LA_LEGENDE)
        terme = entree.terme(source)
        self.terme = TermeAjuste(terme, "terme", source, *_tailles_du_terme(terme, source, "source"), centre=True)
        if source == FR:
            police_du_terme = QFont(self.terme.font())
            police_du_terme.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.4)
            self.terme.setFont(police_du_terme)
        # Le terme est centré dans une ligne de hauteur fixe : il est écrit à la hauteur de son équivalent.
        self.terme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.terme.setMinimumHeight(HAUTEUR_DU_TERME)
        corps.addWidget(self.terme)
        categorie = _categorie_en_html(entree, source)
        if categorie:
            corps.addSpacing(2)
            corps.addWidget(etiquette(paragraphe(categorie, source, 24 if source == AR else 18, centre=True),
                                      "categorie", source, retour_ligne=True, riche=True))
        if entree.domaines:
            corps.addSpacing(6)
            domaine = etiquette(" › ".join(entree.domaines), "domaine", retour_ligne=True)
            domaine.setAlignment(centre)
            corps.addWidget(domaine)
        corps.addStretch(1)

        # Pied : rang de l'entrée dans le glossaire, et passage à l'entrée voisine.
        entrees = self.glossaire.entrees if self.glossaire is not None else [entree]
        self.ligne_du_pied.addWidget(icone_fixe("fiche", theme.TEXTE_3))
        self.rang = EtiquetteCourte("", "pied")
        self.rang.definir_texte(f"Entrée {nombre(entree.numero)} sur {nombre(len(entrees))}",
                                f"{nombre(entree.numero)} / {nombre(len(entrees))}")
        self.ligne_du_pied.addWidget(self.rang, 1)
        voisines = QHBoxLayout()
        voisines.setSpacing(4)
        self.bouton_precedent = self._bouton_voisin("chevron-g", "Entrée précédente du glossaire",
                                                    entrees[entree.numero - 2] if entree.numero > 1 else None)
        self.bouton_suivant = self._bouton_voisin("chevron-d", "Entrée suivante du glossaire",
                                                  entrees[entree.numero] if entree.numero < len(entrees) else None)
        voisines.addWidget(self.bouton_precedent)
        voisines.addWidget(self.bouton_suivant)
        self.ligne_du_pied.addLayout(voisines)

    def _bouton_voisin(self, nom_icone: str, info: str, voisine: Entree | None) -> QToolButton:
        bouton = QToolButton()
        bouton.setProperty("classe", "voisine")
        bouton.setIcon(icones.icone(nom_icone, theme.TEXTE_2, 12, 1.7, couleur_inactive=theme.TEXTE_4))
        bouton.setIconSize(QSize(12, 12))
        bouton.setFixedSize(26, 26)
        bouton.setToolTip(info)
        bouton.setEnabled(voisine is not None)
        if voisine is not None:
            bouton.setCursor(Qt.CursorShape.PointingHandCursor)
            bouton.clicked.connect(lambda _=False, cible=voisine: self.entree_demandee.emit(cible))
        return bouton


class ColonneDefinition(Colonne):
    """La définition du terme dans les deux langues, avec sa source."""

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        if not entree.definition_fr and not entree.definition_ar:
            # Sans définition, une mention « à vérifier » du glossaire porte sur l'équivalent : la colonne
            # de l'équivalent l'affiche (voir ``ColonneEquivalent``).
            self._vide("livre", "Aucune définition pour ce terme", "Le glossaire n’en donne pas encore.")
            return
        for rang, langue in enumerate((source, cible)):
            if rang:
                corps.addSpacing(16)
                corps.addWidget(separateur())
                corps.addSpacing(10)
            corps.addWidget(capitales("Français") if langue == FR else etiquette("العربية", "langueBloc", AR))
            corps.addSpacing(3)
            definition = entree.definition(langue)
            if definition:
                corps.addWidget(etiquette(paragraphe(escape(definition), langue, INTERLIGNE[langue]), "definition",
                                          langue, retour_ligne=True, selectionnable=True, riche=True))
            else:
                corps.addWidget(etiquette(f"Pas de définition en {NOM_EN_FRANCAIS[langue]} dans le glossaire.",
                                          "discret", retour_ligne=True))
        corps.addStretch(1)

        # Pied : la source de la définition, ou la mention « À vérifier » (une définition sans source
        # citée est à vérifier).
        if entree.source_definition:
            detail = mention_a_verifier(entree.source_definition)
            explication = "Cette définition n’est pas reprise d’un texte officiel : vérifiez-la avant de la citer."
        else:
            detail = "source non indiquée"
            explication = ("Le glossaire n’indique pas la source de cette définition : "
                           "vérifiez-la avant de la citer.")
        if detail is not None:
            self._pied_a_verifier(detail, explication)
            return
        mention = QHBoxLayout()
        mention.setSpacing(4)
        self.ligne_du_pied.addWidget(icone_fixe("document", theme.TEXTE_3))
        mention.addWidget(etiquette("Source :", "pied"))
        self.source_de_la_definition = EtiquetteCourte(entree.source_definition, "piedFort")
        mention.addWidget(self.source_de_la_definition, 1)
        self.ligne_du_pied.addLayout(mention, 1)

    def _pied_a_verifier(self, detail: str, explication: str) -> None:
        """Pied du champ : la mention « À vérifier », son détail (« définition d'exemple ») et son infobulle."""
        mention = QHBoxLayout()
        mention.setSpacing(4)
        self.ligne_du_pied.addWidget(icone_fixe("alerte", theme.AMBRE, 16, 1.6))
        a_verifier = etiquette("À vérifier", "piedAlerte")
        a_verifier.setToolTip(infobulle(explication))
        mention.addWidget(a_verifier)
        self.source_de_la_definition = EtiquetteCourte("", "pied")
        if detail:
            self.source_de_la_definition.definir_texte(f"· {detail}", "")
        mention.addWidget(self.source_de_la_definition, 1)
        self.ligne_du_pied.addLayout(mention, 1)


class ColonneEquivalent(Colonne):
    """L'équivalent du terme dans la langue cible, et ses autres équivalents.

    Au pied : la mention « À vérifier » quand le glossaire la porte sur l'équivalent lui-même,
    puis le lien qui copie l'équivalent.
    """

    #: Infobulle de la mention « À vérifier ».
    EXPLICATION = ("Cet équivalent n’est repris d’aucun texte officiel ni d’aucun dictionnaire : "
                   "vérifiez-le avant de l’employer.")

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        centre = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        legende = capitales(f"{NOM_EN_FRANCAIS[cible]} · cible", "capitalesBleu")
        legende.setAlignment(centre)
        corps.addWidget(legende)
        corps.addSpacing(ESPACE_SOUS_LA_LEGENDE)
        equivalent = entree.terme(cible)
        self.terme = TermeAjuste(equivalent, "equivalent", cible, *_tailles_du_terme(equivalent, cible, "cible"),
                                 centre=True)
        self.terme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.terme.setMinimumHeight(HAUTEUR_DU_TERME)
        corps.addWidget(self.terme)
        grammaire = categorie_et_pluriel(entree, cible)
        if grammaire:
            corps.addSpacing(2)
            label = etiquette(grammaire, "grammaire", cible, retour_ligne=True)
            label.setAlignment(centre)
            corps.addWidget(label)
        autres = entree.synonymes(cible)
        if autres:
            # Sur une ligne : le titre, puis les autres équivalents.
            corps.addSpacing(10)
            titre = capitales("Autre équivalent" if len(autres) == 1 else "Autres équivalents")
            titre.setFixedHeight(26)
            titre.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._rangee_de_puces([titre, *(self._puce_d_equivalent(autre, cible) for autre in autres)], centre=True,
                                  espace=8)
        corps.addStretch(1)

        def copier() -> None:
            QGuiApplication.clipboard().setText(equivalent)
            self.message.emit(f"Équivalent copié : {equivalent}")

        #: La mention « À vérifier », quand le glossaire la porte sur l'équivalent (``None`` sinon).
        self.mention: QWidget | None = None
        detail = equivalent_a_verifier(entree)
        if detail is not None:
            self.mention = mention_a_controler(self.EXPLICATION, detail)
        if self.mention is not None:
            self.ligne_du_pied.addWidget(self.mention, 1)
        else:
            self.ligne_du_pied.addStretch(1)
        self.bouton_copier = self._lien_du_pied("Copier l’équivalent", copier, "Équivalent copié")
        self.ligne_du_pied.addWidget(self.bouton_copier)

    def _puce_d_equivalent(self, texte: str, cible: str) -> QWidget:
        """Puce d'un autre équivalent : cliquable s'il est le terme d'une entrée du glossaire."""
        element = self._puce_de_terme(texte, cible)
        element.setFixedHeight(26)
        return element


class LienCourt(QPushButton):
    """Lien sur une ligne : un libellé trop long est abrégé par « … » (le texte complet reste dans l'infobulle)."""

    def __init__(self, texte: str, classe: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.texte_complet = texte
        self.setProperty("classe", classe)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._abreger()

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        self.ensurePolished()
        return QSize(self.fontMetrics().horizontalAdvance(self.texte_complet) + 18, 20)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(40, 20)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._abreger()

    def _abreger(self) -> None:
        self.ensurePolished()
        visible = self.fontMetrics().elidedText(self.texte_complet, Qt.TextElideMode.ElideRight,
                                                max(self.width() - 16, 0))
        # Dans le libellé d'un bouton, « & » annonce un raccourci clavier : on le double pour l'afficher.
        self.setText(visible.replace("&", "&&"))


class LigneDeProvenance(QWidget):
    """Au-dessus d'une phrase trouvée dans une autre entrée : le lien vers cette entrée, puis « À vérifier ».

    Le lien passe d'abord. Quand la place manque, la mention se réduit à son icône ; ensuite
    seulement, le lien est abrégé.
    """

    ECART, ICONE, HAUTEUR = 8, 14, 20

    def __init__(self, lien: LienCourt, explication: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lien = lien
        lien.setParent(self)
        #: L'icône et les mots de la mention ; ``None`` si la phrase cite sa source.
        self.icone: QLabel | None = None
        self.mots: QLabel | None = None
        if explication:
            self.icone = icone_fixe("alerte", theme.AMBRE, self.ICONE, 1.6)
            self.mots = etiquette("À vérifier", "piedAlerte")
            for element in (self.icone, self.mots):
                element.setParent(self)
                element.setToolTip(infobulle(explication))
        self.setFixedHeight(self.HAUTEUR)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def a_verifier(self) -> bool:
        return self.icone is not None

    def _largeur_des_mots(self) -> int:
        self.mots.ensurePolished()
        return self.mots.sizeHint().width()

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        largeur = self.lien.sizeHint().width()
        if self.icone is not None:
            largeur += self.ECART + self.ICONE + 5 + self._largeur_des_mots()
        return QSize(largeur, self.HAUTEUR)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        largeur = self.lien.minimumSizeHint().width()
        return QSize(largeur + (self.ECART + self.ICONE if self.icone is not None else 0), self.HAUTEUR)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer()

    def showEvent(self, evenement) -> None:  # noqa: N802
        super().showEvent(evenement)
        self._placer()

    def _placer(self) -> None:
        complet = self.lien.sizeHint().width()
        if self.icone is None:
            self.lien.setGeometry(0, 0, min(complet, self.width()), self.HAUTEUR)
            return
        mots = self._largeur_des_mots()
        avec_les_mots = complet + self.ECART + self.ICONE + 5 + mots <= self.width()
        reste = self.width() - self.ECART - self.ICONE - (5 + mots if avec_les_mots else 0)
        self.lien.setGeometry(0, 0, min(complet, max(reste, self.lien.minimumSizeHint().width())), self.HAUTEUR)
        depart = self.lien.width() + self.ECART
        self.icone.move(depart, (self.HAUTEUR - self.ICONE) // 2)
        self.mots.setVisible(avec_les_mots)
        self.mots.setGeometry(depart + self.ICONE + 5, 0, mots, self.HAUTEUR)


class ColonneContexte(Colonne):
    """Contextualisation : des phrases qui emploient le terme, dans les deux langues ; le terme y est mis en évidence.

    Les exemples de l'entrée viennent d'abord. S'il en manque, la colonne les complète par des
    phrases d'autres entrées du glossaire (exemples, définitions) qui emploient le terme : voir
    ``traducteur.contextes``.

    Au-dessus de chaque phrase : la source que cite le glossaire, ou la mention « À vérifier »
    quand la phrase n'est reprise d'aucun texte.
    """

    marge_haute = 18
    #: Infobulles de la mention « À vérifier », pour une phrase d'exemple et pour une définition.
    EXPLICATION_EXEMPLE = ("Cette phrase a été rédigée pour montrer l’emploi du terme. Elle n’est pas reprise d’un "
                           "texte officiel : vérifiez-la avant de la citer.")
    EXPLICATION_DEFINITION = "Cette définition n’est pas reprise d’un texte officiel : vérifiez-la avant de la citer."

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: Les contextes affichés.
        self.emplois: list[Emploi] = []

    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str) -> None:
        self.emplois = emplois(glossaire, entree) if entree is not None else []
        super().afficher(glossaire, entree, source)

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        if not self.emplois:
            self._vide("bulle", "Aucun exemple pour ce terme",
                       "Aucune phrase du glossaire n’emploie encore ce terme.")
            return
        for rang, emploi in enumerate(self.emplois):
            if rang:
                corps.addSpacing(14)
                corps.addWidget(separateur())
                corps.addSpacing(16)
            provenance = emploi.provenance(source)
            explication = (self.EXPLICATION_DEFINITION if emploi.origine == DEFINITION
                           else self.EXPLICATION_EXEMPLE)
            if emploi.origine != PROPRE:
                # La phrase vient d'une autre entrée : le lien ouvre cette entrée.
                lien = LienCourt(provenance, "sourceLien")
                lien.setFixedHeight(20)
                lien.setToolTip(infobulle(f"Phrase trouvée dans l’entrée « {emploi.entree.terme(source)} » : "
                                          "cliquez pour ouvrir cette entrée."))
                lien.clicked.connect(lambda _=False, cible=emploi.entree: self.entree_demandee.emit(cible))
                corps.addWidget(LigneDeProvenance(lien, explication if emploi.a_verifier else ""))
                corps.addSpacing(5)
            elif provenance:
                reference = etiquette(provenance, "sourceExemple")
                reference.setFixedHeight(20)
                reference.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                corps.addWidget(reference, 0, Qt.AlignmentFlag.AlignRight if deviner_langue(provenance) == AR
                                else Qt.AlignmentFlag.AlignLeft)
                corps.addSpacing(5)
            elif emploi.a_verifier:
                corps.addWidget(mention_a_controler(explication, emploi.detail_a_verifier))
                corps.addSpacing(5)
            for langue in (source, cible):
                phrase = emploi.texte(langue)
                if phrase:
                    corps.addWidget(etiquette(phrase_surlignee(phrase, entree, langue), "definition", langue,
                                              retour_ligne=True, selectionnable=True, riche=True))
                    corps.addSpacing(2)
        corps.addStretch(1)
        propres = sum(1 for emploi in self.emplois if emploi.origine == PROPRE)
        trouves = len(self.emplois) - propres
        if not trouves:
            bilan = (f"{compte(propres, 'exemple')} dans le glossaire",)
        elif not propres:
            bilan = (f"{compte(trouves, 'contexte trouvé', 'contextes trouvés')} dans le glossaire",
                     compte(trouves, "contexte trouvé", "contextes trouvés"))
        else:
            bilan = (f"{compte(propres, 'exemple')} · {compte(trouves, 'autre emploi', 'autres emplois')} "
                     "dans le glossaire", f"{compte(propres, 'exemple')} · {compte(trouves, 'autre', 'autres')}")
        self.ligne_du_pied.addWidget(icone_fixe("texte", theme.TEXTE_3))
        mention = EtiquetteCourte("", "pied")
        mention.definir_texte(*bilan)
        self.ligne_du_pied.addWidget(mention, 1)


class ColonneRessources(Colonne):
    """Les références à consulter et à citer : textes de loi, dictionnaires, sites officiels."""

    marge_haute = 15

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        if not entree.ressources:
            self._vide("ouvrages", "Aucune ressource pour ce terme",
                       "Le glossaire ne cite pas encore de référence.")
            return
        for rang, ressource in enumerate(entree.ressources):
            if rang:
                corps.addSpacing(8)
                corps.addWidget(separateur())
                corps.addSpacing(8)
            langue = deviner_langue(ressource) or FR
            label = etiquette(ressource_en_html(ressource, langue), "ressource", langue, retour_ligne=True, riche=True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setOpenExternalLinks(True)
            corps.addWidget(label)
        corps.addStretch(1)

        references = "\n".join(entree.ressources)

        def copier() -> None:
            QGuiApplication.clipboard().setText(references)
            self.message.emit("Références copiées dans le presse-papiers")

        self.bouton_copier = self._lien_du_pied("Copier les références", copier, "Références copiées")
        self.ligne_du_pied.addWidget(self.bouton_copier)
        self.ligne_du_pied.addStretch(1)


class ColonneTermesLies(Colonne):
    """Des termes liés au terme affiché, en puces : synonymes, termes associés.

    Une puce bleue est une autre entrée du glossaire : un clic l'ouvre. Une puce grise est un
    terme que le glossaire cite sans lui donner d'entrée.
    """

    marge_haute = 20
    #: Message affiché quand le glossaire ne donne aucun terme : icône, titre, texte.
    ICONE, TITRE_VIDE, TEXTE_VIDE = "", "", ""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: Les puces affichées, dans l'ordre du glossaire.
        self.puces: list[QWidget] = []

    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str) -> None:
        self.puces = []
        super().afficher(glossaire, entree, source)

    def termes(self, entree: Entree, source: str) -> list[tuple[str, str | None]]:
        """Les termes à afficher : (terme, langue) ; la langue est ``None`` quand elle est à deviner."""
        raise NotImplementedError

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        termes = self.termes(entree, source)
        if not termes:
            self._vide(self.ICONE, self.TITRE_VIDE, self.TEXTE_VIDE)
            return
        self.puces = [self._puce_de_terme(texte, langue, grande=True) for texte, langue in termes]
        self._rangee_de_puces(self.puces, espace=8)
        self.disposition.addStretch(1)
        # Pied : ce que veulent dire les deux couleurs de puces.
        ouvrables = sum(1 for element in self.puces if isinstance(element, QPushButton))
        legende = EtiquetteCourte("", "pied")
        if ouvrables == len(self.puces):
            legende.definir_texte("Cliquez sur un terme pour ouvrir son entrée dans le glossaire",
                                  "Cliquez sur un terme pour ouvrir son entrée", "")
        elif ouvrables:
            legende.definir_texte("En bleu : une entrée du glossaire, à ouvrir d’un clic · en gris : un terme "
                                  "sans entrée", "En bleu : une entrée du glossaire, à ouvrir d’un clic", "")
        else:
            legende.definir_texte("Ces termes n’ont pas encore d’entrée dans le glossaire", "")
        self.ligne_du_pied.addWidget(icone_fixe("information", theme.TEXTE_3))
        self.ligne_du_pied.addWidget(legende, 1)


class ColonneSynonymes(ColonneTermesLies):
    """Les synonymes du terme, dans la langue source."""

    ICONE, TITRE_VIDE, TEXTE_VIDE = "equivalence", "Aucun synonyme pour ce terme", "Le glossaire n’en donne pas."

    def termes(self, entree: Entree, source: str) -> list[tuple[str, str | None]]:
        return [(synonyme, source) for synonyme in entree.synonymes(source)]

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        # Des synonymes arabes se suivent de droite à gauche.
        self.corps.setLayoutDirection(direction(source))
        super().remplir(entree, source, cible)


class ColonneAssocies(ColonneTermesLies):
    """Les termes associés au terme : ceux qu'on rencontre avec lui dans les mêmes textes."""

    ICONE, TITRE_VIDE, TEXTE_VIDE = "liens", "Aucun terme associé", "Le glossaire n’en cite pas pour ce terme."

    def termes(self, entree: Entree, source: str) -> list[tuple[str, str | None]]:
        return [(associe, None) for associe in entree.termes_associes]


class ColonneExpressions(Colonne):
    """Les autres entrées trouvées par la recherche : expressions qui contiennent le terme, termes proches.

    Le contenu ne vient pas de l'entrée affichée mais de la recherche en cours : ``definir`` le
    reçoit, avant ``afficher``.
    """

    #: Demande d'affichage d'une entrée de la liste (la recherche en cours est conservée).
    ouverture = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: Titre de la liste : « Expressions avec « contrat » », « Autres résultats pour « contra » »…
        self.titre = ""
        self._entrees: list[Entree] = []
        self.grille: GrilleEntrees | None = None
        # La grille va d'un bord à l'autre : ses filets rejoignent ceux du panneau.
        self.disposition.setContentsMargins(0, 0, 0, 0)

    def definir_reserve(self, reserve: int) -> None:
        """La liste n'a pas de marge : rien à réserver."""

    def definir(self, titre: str, entrees: Sequence[Entree]) -> None:
        """Fixe le titre et le contenu de la liste, affichés au prochain appel de ``afficher``."""
        self.titre, self._entrees = titre, list(entrees)

    def entrees(self) -> list[Entree]:
        return list(self._entrees)

    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str) -> None:
        self.grille = None
        super().afficher(glossaire, entree, source)

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        if not self._entrees:
            self._vide("liste", "Aucune expression avec ce terme",
                       "Aucune autre entrée du glossaire ne contient ce terme.")
            return
        self.grille = GrilleEntrees()
        self.grille.definir(self._entrees)
        self.grille.ouverture.connect(self.ouverture)
        self.disposition.addWidget(self.grille)
        self.disposition.addStretch(1)
        aide = EtiquetteCourte("", "pied")
        aide.definir_texte("Cliquez sur une ligne pour ouvrir sa fiche", "")
        self.ligne_du_pied.addWidget(icone_fixe("information", theme.TEXTE_3))
        self.ligne_du_pied.addWidget(aide, 1)


# ====================================================================== la fiche
class Fiche(Panneau):
    """Le terme et son équivalent, côte à côte dans un seul panneau.

    De haut en bas : les onglets des sens (si le terme en a plusieurs), le corps des deux
    colonnes (il défile d'un bloc si la hauteur manque) et leur pied. Les autres informations
    de l'entrée sont dans le menu « Plus de détails » : voir ``details.py``.
    """

    #: Demande d'ouverture d'une autre entrée du glossaire (clic sur une puce ou sur une flèche de la fiche).
    entree_demandee = Signal(object)
    #: Un autre sens du terme a été choisi par son onglet.
    sens_choisi = Signal(object)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)

    #: Rayon du rond dessiné entre les deux colonnes : sa flèche va du terme vers l'équivalent.
    RAYON_DE_LA_FLECHE = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.entree: Entree | None = None
        self.source = FR
        self.setMinimumWidth(LARGEUR_MINIMALE)

        self.onglets = BandeDesSens()
        self.onglets.sens_choisi.connect(self.sens_choisi)
        self.onglets.hide()
        self.colonne_terme = ColonneTerme(self)
        self.colonne_equivalent = ColonneEquivalent(self)
        self.colonnes: list[Colonne] = [self.colonne_terme, self.colonne_equivalent]

        self._rangee = QWidget()
        corps = DispositionColonnes(self._rangee, PROPORTIONS)
        pieds = QWidget()
        pieds.setFixedHeight(HAUTEUR_PIED)
        dans_les_pieds = DispositionColonnes(pieds, PROPORTIONS)
        for colonne in self.colonnes:
            colonne.entree_demandee.connect(self.entree_demandee)
            colonne.message.connect(self.message)
            corps.addWidget(colonne.corps)
            dans_les_pieds.addWidget(colonne.pied)
        self.defilement = ZoneDefilante()
        self.defilement.definir_contenu(self._rangee)
        self.defilement.setMinimumHeight(HAUTEUR_MINIMALE_DU_CORPS)
        self.defilement.viewport().installEventFilter(self)

        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        ensemble.addWidget(self.onglets)
        ensemble.addWidget(self.defilement, 1)
        ensemble.addWidget(pieds)

    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str,
                 sens: Sequence[Entree] = ()) -> None:
        """Affiche une entrée. ``sens`` : les entrées qui ont le même terme (un onglet chacune)."""
        self.glossaire, self.entree, self.source = glossaire, entree, source
        for colonne in self.colonnes:
            colonne.afficher(glossaire, entree, source)
        self.onglets.afficher(sens, entree, source)
        self.defilement.revenir_en_haut()
        self._centrer_dans_la_vue()
        self.update()

    # ------------------------------------------------------------------ hauteurs
    def eventFilter(self, objet, evenement) -> bool:  # noqa: N802 (nom imposé par Qt)
        if objet is self.defilement.viewport() and evenement.type() == QEvent.Type.Resize:
            self._centrer_dans_la_vue()
        return False

    def _hauteurs_naturelles(self, largeur: int) -> list[int]:
        """Hauteur qu'il faut à chaque colonne, pour une fiche de ``largeur`` pixels."""
        bornes = bornes_des_colonnes(max(largeur, LARGEUR_MINIMALE), PROPORTIONS)
        return [colonne.hauteur_naturelle(bornes[rang + 1] - bornes[rang])
                for rang, colonne in enumerate(self.colonnes)]

    def _centrer_dans_la_vue(self) -> None:
        """Limite la hauteur utile de chaque colonne à la partie visible du corps.

        Les deux colonnes défilent d'un bloc : elles ont la hauteur de la plus haute. Leur
        contenu est centré en hauteur ; il serait placé au milieu de cette hauteur, parfois hors
        de la vue. Le bas de chaque colonne reçoit donc une réserve vide : son contenu se place
        dans la partie visible, ou dans la hauteur qu'il lui faut si elle est plus grande.
        """
        visible = self.defilement.viewport().height()
        naturelles = self._hauteurs_naturelles(self.width())
        rangee = max(visible, *naturelles)
        for colonne, naturelle in zip(self.colonnes, naturelles, strict=True):
            colonne.definir_reserve(rangee - max(visible, naturelle))

    def _hauteur_fixe(self) -> int:
        """Hauteur de tout ce qui entoure le corps : onglets, pied."""
        return (HAUTEUR_ONGLETS if not self.onglets.isHidden() else 0) + HAUTEUR_PIED

    def hauteur_de_reference(self) -> int:
        """Hauteur de la fiche dans la fenêtre de référence."""
        return self._hauteur_fixe() + HAUTEUR_DU_CORPS

    def hauteur_minimale(self) -> int:
        return self._hauteur_fixe() + HAUTEUR_MINIMALE_DU_CORPS

    def hauteur_du_contenu(self, largeur: int) -> int:
        """Hauteur qu'il faut à la fiche pour afficher ses deux colonnes sans défilement."""
        return self._hauteur_fixe() + max(self._hauteurs_naturelles(largeur))

    # ------------------------------------------------------------------ dessin
    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().paintEvent(evenement)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        milieu = bornes_des_colonnes(self.width(), PROPORTIONS)[1]
        haut = self.defilement.y()
        pied = self.height() - HAUTEUR_PIED
        # L'équivalent est mis en avant : fond teinté, filet bleu en haut.
        peintre.fillRect(milieu, haut, self.width() - milieu, self.height() - haut, QColor(theme.BLEU_50))
        peintre.fillRect(milieu, haut, self.width() - milieu, 3, QColor(theme.BLEU))
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, pied, milieu, pied)
        peintre.setPen(QColor(theme.BLEU_100))
        peintre.drawLine(milieu, pied, self.width(), pied)
        peintre.drawLine(milieu, haut, milieu, self.height())
        if self.entree is not None and pied - haut >= 4 * self.RAYON_DE_LA_FLECHE:
            # Entre les deux colonnes : du terme vers son équivalent.
            centre = QPointF(milieu + 0.5, (haut + pied) / 2)
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1))
            peintre.setBrush(QColor(theme.SURFACE))
            peintre.drawEllipse(centre, self.RAYON_DE_LA_FLECHE, self.RAYON_DE_LA_FLECHE)
            peintre.drawPixmap(QPointF(centre.x() - 7, centre.y() - 7), icones.image("fleche", theme.BLEU, 14, 1.6))


# ====================================================================== listes d'entrées
class CelluleEntree(QAbstractButton):
    """Une entrée de la liste : le terme français à gauche, le terme arabe à droite."""

    def __init__(self, entree: Entree, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entree = entree
        self.marge_gauche = self.marge_droite = 16
        #: Place gardée devant le terme français (pour un signe, par exemple).
        self.retrait = 0
        self._francais = self._arabe = ""
        self._necessaire: tuple[tuple, float] | None = None
        self.setText(f"{entree.terme_fr} — {entree.terme_ar}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def _polices(self) -> tuple[QFont, QFont]:
        return police(self.font(), 13), police(self.font(), 15)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self.ajuster()

    #: Écart gardé entre les deux termes, et part de la case que le terme arabe peut occuper.
    ECART = 20
    PART_DE_L_ARABE = 0.55

    def ajuster(self) -> None:
        """Abrège les deux termes à la largeur de la case ; l'infobulle donne alors les termes entiers."""
        francais, arabe = self._polices()
        place = self.width() - self.marge_gauche - self.retrait - self.marge_droite
        # L'arabe garde sa largeur, dans la limite de la moitié de la case ; le français prend le reste.
        largeur_arabe = min(largeur_du_texte(self.entree.terme_ar, arabe) + 2, max(place * self.PART_DE_L_ARABE, 40))
        self._arabe = abreger(self.entree.terme_ar, arabe, largeur_arabe)
        self._francais = abreger(self.entree.terme_fr, francais,
                                 place - largeur_du_texte(self._arabe, arabe) - self.ECART)
        abrege = (self._francais, self._arabe) != (self.entree.terme_fr, self.entree.terme_ar)
        self.setToolTip(infobulle(f"{self.entree.terme_fr} — {self.entree.terme_ar}") if abrege else "")

    def textes_affiches(self) -> tuple[str, str]:
        return self._francais, self._arabe

    def largeur_necessaire(self) -> float:
        """Largeur de case à partir de laquelle les deux termes sont écrits en entier, où que soit la case."""
        cle = (self.font().key(), self.retrait)
        if self._necessaire is None or self._necessaire[0] != cle:
            francais, arabe = self._polices()
            largeur_arabe = largeur_du_texte(self.entree.terme_ar, arabe)
            place = max(largeur_du_texte(self.entree.terme_fr, francais) + largeur_arabe + self.ECART,
                        (largeur_arabe + 2) / self.PART_DE_L_ARABE)
            # Les cases du bord ont la marge la plus large : c'est elle qui est comptée.
            self._necessaire = (cle, math.ceil(place) + 1 + self.retrait + 2 * theme.MARGE)
        return self._necessaire[1]

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        survol = self.underMouse() or self.hasFocus()
        if survol:
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1) if self.hasFocus() else Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.BLEU_50))
            peintre.drawRoundedRect(QRectF(6.5, 4.5, self.width() - 13, self.height() - 8), 6, 6)
        francais, arabe = self._polices()
        gauche = self.marge_gauche + self.retrait
        cadre = QRectF(gauche, 0, self.width() - gauche - self.marge_droite, self.height())
        dessiner_ligne(peintre, cadre, self._francais, francais, theme.BLEU_FONCE if survol else theme.TEXTE,
                       base=22.8)
        dessiner_ligne(peintre, cadre, self._arabe, arabe, theme.BLEU_FONCE if survol else theme.TEXTE_2,
                       langue=AR, base=23.2)


class GrilleEntrees(QWidget):
    """Grille des entrées : quatre colonnes au plus, des lignes de hauteur régulière.

    Le nombre de colonnes dépend de la largeur de la grille et de la longueur des termes : de
    longues expressions sont rangées sur moins de colonnes, pour être écrites en entier.
    """

    #: Demande d'ouverture d'une entrée (clic sur une case).
    ouverture = Signal(object)

    HAUTEUR_DE_LIGNE = 36
    #: Largeur minimale d'une case : la grille n'a jamais plus de colonnes que cette largeur n'en permet.
    LARGEUR_DE_CASE = 250
    #: Part des cases dont les deux termes doivent être écrits en entier. En dessous, la grille prend une colonne
    #: de moins. Les quelques termes plus longs que les autres sont abrégés ; leur infobulle les donne en entier.
    PART_ENTIERE = 0.9

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cellules: list[CelluleEntree] = []
        regle = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        regle.setHeightForWidth(True)
        self.setSizePolicy(regle)

    def definir(self, elements: Sequence, fabrique: Callable[..., CelluleEntree] = CelluleEntree) -> None:
        """Remplit la grille : une case par élément.

        ``fabrique`` construit la case d'un élément ; par défaut, les éléments sont des entrées
        du glossaire. La case porte l'entrée qu'un clic ouvre (attribut ``entree``).
        """
        for cellule in self.cellules:
            cellule.setParent(None)
            cellule.deleteLater()
        self.cellules = []
        for element in elements:
            cellule = fabrique(element, self)
            cellule.clicked.connect(lambda _=False, cible=cellule.entree: self.ouverture.emit(cible))
            cellule.show()
            self.cellules.append(cellule)
        self._placer()
        self.updateGeometry()
        self.update()

    def colonnes(self, largeur: int | None = None) -> int:
        """Le plus grand nombre de colonnes qui laisse presque toutes les cases écrites en entier."""
        largeur = self.width() if largeur is None else largeur
        possibles = max(1, min(4, largeur // self.LARGEUR_DE_CASE))
        if possibles > 1:
            necessaires = [cellule.largeur_necessaire() for cellule in self.cellules]
            for colonnes in range(possibles, 1, -1):
                entieres = sum(1 for necessaire in necessaires if necessaire <= largeur // colonnes)
                if entieres >= self.PART_ENTIERE * len(necessaires):
                    return colonnes
        return 1

    def cases_abregees(self) -> int:
        """Nombre de cases dont un terme est abrégé."""
        return sum(1 for cellule in self.cellules
                   if cellule.textes_affiches() != (cellule.entree.terme_fr, cellule.entree.terme_ar))

    def rangees(self, largeur: int | None = None) -> int:
        return -(-len(self.cellules) // self.colonnes(largeur))

    def hasHeightForWidth(self) -> bool:  # noqa: N802 (nom imposé par Qt)
        return True

    def heightForWidth(self, largeur: int) -> int:  # noqa: N802
        return self.rangees(largeur) * self.HAUTEUR_DE_LIGNE

    def sizeHint(self) -> QSize:  # noqa: N802
        largeur = self.width() if self.width() > self.LARGEUR_DE_CASE else 4 * self.LARGEUR_DE_CASE
        return QSize(largeur, self.heightForWidth(largeur))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.LARGEUR_DE_CASE, self.HAUTEUR_DE_LIGNE)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer()

    def _placer(self) -> None:
        colonnes = self.colonnes()
        bornes = bornes_des_colonnes(self.width(), [1] * colonnes)
        for rang, cellule in enumerate(self.cellules):
            rangee, colonne = divmod(rang, colonnes)
            # Les cases du bord reprennent la marge du panneau.
            cellule.marge_gauche = theme.MARGE if colonne == 0 else 16
            cellule.marge_droite = theme.MARGE if colonne == colonnes - 1 else 16
            cellule.setGeometry(bornes[colonne], rangee * self.HAUTEUR_DE_LIGNE,
                                bornes[colonne + 1] - bornes[colonne], self.HAUTEUR_DE_LIGNE)
            cellule.ajuster()

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setPen(QColor(theme.FILET_DOUX))
        colonnes = self.colonnes()
        for borne in bornes_des_colonnes(self.width(), [1] * colonnes)[1:-1]:
            peintre.drawLine(borne, 0, borne, self.height())
        for rangee in range(1, self.rangees()):
            peintre.drawLine(0, rangee * self.HAUTEUR_DE_LIGNE, self.width(), rangee * self.HAUTEUR_DE_LIGNE)
