"""La fiche d'un terme : les cinq champs de l'enchaînement, côte à côte dans un seul panneau.

① Terme → ② Définition → ③ Équivalent → ④ Contextualisation → ⑤ Ressources

Chaque champ est une colonne de la fiche : un corps, construit à partir d'une entrée du
glossaire et du sens de traduction, et un pied. Sous la fiche, ``ListeEntrees`` présente les
autres entrées trouvées par la recherche.
"""

from __future__ import annotations

from collections.abc import Sequence
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

from ..contextes import PROPRE, Emploi, emplois
from ..glossaire import Entree, Glossaire
from ..langues import AR, FR, NOM_EN_FRANCAIS, autre_langue, cle_souple, deviner_langue
from ..surlignage import positions_du_terme
from . import icones, theme
from .animation import Allumage
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
    nombre,
    paragraphe,
    pastille,
    puce,
    puce_neutre,
    rond,
    separateur,
    vider,
)
from .dessin import abreger, dessiner_ligne, dessiner_numero, largeur_du_texte, melanger, police

#: Les cinq champs de l'enchaînement.
ETAPES = ("Terme", "Définition", "Équivalent", "Contextualisation", "Ressources")
#: Largeurs relatives des cinq colonnes (celles de la proposition, pour une fiche de 1 392 pixels).
PROPORTIONS = (272, 292, 264, 292, 272)
#: En dessous de cette largeur, la fiche garde sa largeur et défile horizontalement.
LARGEUR_MINIMALE = 960
HAUTEUR_ONGLETS, HAUTEUR_ENTETE, HAUTEUR_PIED = 38, 50, 44
#: Hauteur du corps de la fiche dans la fenêtre de référence (1440 × 860), et hauteur minimale.
HAUTEUR_DU_CORPS, HAUTEUR_MINIMALE_DU_CORPS = 336, 150

#: Hauteur des lignes d'un paragraphe, selon la langue.
INTERLIGNE = {FR: 22, AR: 30}

_ADRESSE = regex.compile(r"(?:https?://|www\.)[^\s<>«»]+[^\s<>«».,;:!?)]")
_A_VERIFIER = "a verifier"
#: Marge au-dessus du message d'un champ vide, la même dans toutes les colonnes.
_MARGE_HAUTE_DU_MESSAGE = 20


# ====================================================================== fonctions d'affichage
def categorie_et_pluriel(entree: Entree, langue: str) -> str:
    """« nom masculin · pl. contrats » ou « اسم مذكر، ج. عقود »."""
    categorie, pluriel = entree.categorie(langue), entree.pluriel(langue)
    if langue == AR:
        return "، ".join(morceau for morceau in (categorie, f"ج. {pluriel}" if pluriel else "") if morceau)
    return " · ".join(morceau for morceau in (categorie, f"pl. {pluriel}" if pluriel else "") if morceau)


def _categorie_en_html(entree: Entree, langue: str) -> str:
    """La catégorie et le pluriel ; en français, la catégorie est en italique."""
    if langue == AR:
        return escape(categorie_et_pluriel(entree, AR))
    categorie, pluriel = entree.categorie(FR), entree.pluriel(FR)
    morceaux = ([f"<i>{escape(categorie)}</i>"] if categorie else []) + ([f"pl. {escape(pluriel)}"] if pluriel else [])
    return " · ".join(morceaux)


def mention_a_verifier(source: str) -> str | None:
    """Détail d'une source de définition qui commence par « à vérifier » ; ``None`` pour une vraie source.

    « à vérifier (définition d'exemple) » donne « définition d'exemple ».
    """
    if not cle_souple(source).startswith(_A_VERIFIER):
        return None
    return source[len(_A_VERIFIER):].strip(" :·,;-–—()")


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
        paliers = ((10, 40), (18, 30), (999, 24)) if langue == AR else ((12, 34), (22, 26), (999, 21))
    maximale = next(taille for limite, taille in paliers if len(terme) <= limite)
    return maximale, min(maximale, 16 if langue == AR else 14)


# ====================================================================== en-tête : les cinq étapes
class EnteteEtapes(QWidget):
    """Les cinq étapes de l'enchaînement, numérotées et reliées par des flèches.

    Chaque étape est placée au début de sa colonne. ``legendes`` ajoute une ligne sous chaque
    titre : pour chaque étape, les formes du texte, de la plus longue à la plus courte.

    Une étape est éteinte (grise) ou allumée (dorée). ``allumer`` allume, l'une après l'autre,
    les étapes que le glossaire renseigne pour le terme affiché.
    """

    def __init__(self, legendes: Sequence[Sequence[str]] = (), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.titres = list(ETAPES)
        self._legendes = [tuple(formes) for formes in legendes]
        self.setFixedHeight(80 if legendes else HAUTEUR_ENTETE)
        self.setAccessibleName(" → ".join(ETAPES))
        self.allumage = Allumage(len(ETAPES), self)
        self.allumage.change.connect(self.update)

    def allumer(self, etapes: Sequence[bool], *, animer: bool = True) -> None:
        """Allume les étapes renseignées (vrai), dans l'ordre ; les autres restent éteintes."""
        self.allumage.definir(etapes, animer=animer)
        allumees = [titre for titre, allumee in zip(ETAPES, etapes, strict=True) if allumee]
        self.setAccessibleDescription("Étapes renseignées : " + ", ".join(allumees) if allumees else "")

    def etapes_allumees(self) -> list[bool]:
        """Pour chaque étape : vrai si elle est allumée (ou le sera à la fin de l'animation)."""
        return self.allumage.allumees()

    def legendes_affichees(self) -> list[str]:
        """La légende de chaque étape, dans la forme qui tient dans sa colonne."""
        bornes = bornes_des_colonnes(self.width(), PROPORTIONS)
        police_legende = police(self.font(), 12)
        resultat = []
        for rang, formes in enumerate(self._legendes):
            place = bornes[rang + 1] - bornes[rang] - theme.MARGE - 31 - 8
            resultat.append(next((forme for forme in formes if largeur_du_texte(forme, police_legende) <= place),
                                 abreger(formes[-1], police_legende, place)))
        return resultat

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        bornes = bornes_des_colonnes(self.width(), PROPORTIONS)
        milieu = 29 if self._legendes else HAUTEUR_ENTETE / 2
        police_titre = police(self.font(), 14, gras=True)
        police_numero = police(self.font(), 12, gras=True)
        legendes = self.legendes_affichees()
        for rang, titre in enumerate(ETAPES):
            gauche = bornes[rang] + theme.MARGE
            accent = rang == 2  # l'équivalent est le champ mis en avant
            niveau = self.allumage.niveau(rang)
            dessiner_numero(peintre, QPointF(gauche + 11, milieu), 11, str(rang + 1), police_numero, niveau,
                            self.allumage.halo(rang))

            x_titre = gauche + 31
            place = bornes[rang + 1] - x_titre - 4
            titre = abreger(titre, police_titre, place)
            dessiner_ligne(peintre, QRectF(x_titre, milieu - 12, place, 24), titre, police_titre,
                           melanger(theme.TEXTE_3, theme.BLEU_FONCE if accent else theme.TEXTE, niveau).name())
            if legendes:
                dessiner_ligne(peintre, QRectF(x_titre, milieu + 12, place, 20), legendes[rang],
                               police(self.font(), 12), theme.TEXTE_3)
            if rang < len(ETAPES) - 1:
                # Flèche vers l'étape suivante : du titre jusqu'au numéro de la colonne voisine. Elle
                # se colore quand l'étape suivante s'allume.
                debut = x_titre + largeur_du_texte(titre, police_titre) + 14
                fin = bornes[rang + 1] + theme.MARGE - 14
                if fin - debut >= 12:
                    stylo = QPen(melanger("#CBD3DF", theme.OR_FONCE, self.allumage.niveau(rang + 1)), 1.25)
                    stylo.setCapStyle(Qt.PenCapStyle.RoundCap)
                    stylo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    peintre.setPen(stylo)
                    peintre.drawLine(QPointF(debut, milieu), QPointF(fin, milieu))
                    peintre.drawLine(QPointF(fin - 4.5, milieu - 4), QPointF(fin, milieu))
                    peintre.drawLine(QPointF(fin - 4.5, milieu + 4), QPointF(fin, milieu))


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

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        peintre = QPainter(self)
        peintre.fillRect(self.rect(), QColor(theme.GRIS_50))
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer_le_signe()

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

    def _rangee_de_puces(self, puces: Sequence[QWidget], *, centre: bool = False) -> QWidget:
        conteneur = QWidget()
        rangee = DispositionFluide(conteneur, 6, 6, centre=centre)
        for element in puces:
            rangee.addWidget(element)
        self.disposition.addWidget(conteneur)
        return conteneur

    def _puce_de_terme(self, texte: str, langue: str | None = None) -> QWidget:
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
            return puce_neutre(texte, ecriture)
        bouton = puce(texte, ecriture, info="Ouvrir cette entrée du glossaire")
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
    """① Le terme recherché : catégorie grammaticale, domaine, synonymes et termes associés."""

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        # En arabe, toute la colonne s'aligne à droite, comme le terme.
        self.corps.setLayoutDirection(direction(source))
        corps = self.disposition
        corps.addWidget(capitales(f"{NOM_EN_FRANCAIS[source]} · source"))
        corps.addSpacing(2)
        terme = entree.terme(source)
        self.terme = TermeAjuste(terme, "terme", source, *_tailles_du_terme(terme, source, "source"))
        if source == FR:
            police_du_terme = QFont(self.terme.font())
            police_du_terme.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.4)
            self.terme.setFont(police_du_terme)
        corps.addWidget(self.terme)
        categorie = _categorie_en_html(entree, source)
        if categorie:
            corps.addSpacing(2)
            corps.addWidget(etiquette(paragraphe(categorie, source, 24 if source == AR else 18), "categorie", source,
                                      retour_ligne=True, riche=True))
        if entree.domaines:
            self._rubrique("Domaine")
            corps.addWidget(etiquette(" › ".join(entree.domaines), "domaine", retour_ligne=True))
        synonymes = entree.synonymes(source)
        if synonymes:
            self._rubrique("Synonyme" if len(synonymes) == 1 else "Synonymes")
            self._rangee_de_puces([self._puce_de_terme(synonyme, source) for synonyme in synonymes])
        if entree.termes_associes:
            self._rubrique("Terme associé" if len(entree.termes_associes) == 1 else "Termes associés")
            self._rangee_de_puces([self._puce_de_terme(associe) for associe in entree.termes_associes])
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
    """② La définition du terme dans les deux langues, avec sa source."""

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        if not entree.definition_fr and not entree.definition_ar:
            self._vide("document", "Aucune définition pour ce terme",
                       "Ajoutez-la dans les colonnes definition_fr et definition_ar du fichier CSV, "
                       "puis rechargez le glossaire (F5).")
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

        # Pied : la source de la définition, ou la mention « À vérifier » (comme dans le tableau
        # de l'écran « Texte », une définition sans source citée est à vérifier).
        if entree.source_definition:
            detail = mention_a_verifier(entree.source_definition)
            explication = "Cette définition n’est pas reprise d’un texte officiel : vérifiez-la avant de la citer."
        else:
            detail = "source non indiquée"
            explication = ("Le glossaire n’indique pas la source de cette définition : "
                           "vérifiez-la avant de la citer.")
        mention = QHBoxLayout()
        mention.setSpacing(4)
        if detail is None:
            self.ligne_du_pied.addWidget(icone_fixe("document", theme.TEXTE_3))
            mention.addWidget(etiquette("Source :", "pied"))
            self.source_de_la_definition = EtiquetteCourte(entree.source_definition, "piedFort")
        else:
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
    """③ L'équivalent du terme dans la langue cible, et ses autres équivalents."""

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        centre = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        legende = capitales(f"{NOM_EN_FRANCAIS[cible]} · cible", "capitalesBleu")
        legende.setAlignment(centre)
        corps.addWidget(legende)
        corps.addStretch(1)
        equivalent = entree.terme(cible)
        self.terme = TermeAjuste(equivalent, "equivalent", cible, *_tailles_du_terme(equivalent, cible, "cible"),
                                 centre=True)
        corps.addWidget(self.terme)
        grammaire = categorie_et_pluriel(entree, cible)
        if grammaire:
            corps.addSpacing(4)
            label = etiquette(grammaire, "grammaire", cible, retour_ligne=True)
            label.setAlignment(centre)
            corps.addWidget(label)
        autres = entree.synonymes(cible)
        if autres:
            corps.addSpacing(16)
            filet = separateur("separateurBleu")
            filet.setFixedWidth(56)
            corps.addWidget(filet, 0, Qt.AlignmentFlag.AlignHCenter)
            corps.addSpacing(16)
            titre = capitales("Autre équivalent" if len(autres) == 1 else "Autres équivalents")
            titre.setAlignment(centre)
            corps.addWidget(titre)
            corps.addSpacing(8)
            self._rangee_de_puces([self._puce_d_equivalent(autre, cible) for autre in autres], centre=True)
        corps.addStretch(1)

        def copier() -> None:
            QGuiApplication.clipboard().setText(equivalent)
            self.message.emit(f"Équivalent copié : {equivalent}")

        self.bouton_copier = self._lien_du_pied("Copier l’équivalent", copier, "Équivalent copié")
        self.ligne_du_pied.addStretch(1)
        self.ligne_du_pied.addWidget(self.bouton_copier)
        self.ligne_du_pied.addStretch(1)

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


class ColonneContexte(Colonne):
    """④ Des phrases qui emploient le terme, dans les deux langues ; le terme y est mis en évidence.

    Les exemples de l'entrée viennent d'abord. S'il en manque, la colonne les complète par des
    phrases d'autres entrées du glossaire (exemples, définitions) qui emploient le terme : voir
    ``traducteur.contextes``.
    """

    marge_haute = 18

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
            self._vide("texte", "Aucun exemple pour ce terme",
                       "Ajoutez-en dans les colonnes contexte_fr et contexte_ar du fichier CSV, "
                       "puis rechargez le glossaire (F5).")
            return
        for rang, emploi in enumerate(self.emplois):
            if rang:
                corps.addSpacing(14)
                corps.addWidget(separateur())
                corps.addSpacing(16)
            provenance = emploi.provenance(source)
            if provenance and emploi.origine == PROPRE:
                reference = etiquette(provenance, "sourceExemple")
                reference.setFixedHeight(20)
                reference.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
                corps.addWidget(reference, 0, Qt.AlignmentFlag.AlignRight if deviner_langue(provenance) == AR
                                else Qt.AlignmentFlag.AlignLeft)
                corps.addSpacing(5)
            elif provenance:
                # La phrase vient d'une autre entrée : le lien ouvre cette entrée.
                lien = LienCourt(provenance, "sourceLien")
                lien.setFixedHeight(20)
                lien.setToolTip(infobulle(f"Phrase trouvée dans l’entrée « {emploi.entree.terme(source)} » : "
                                          "cliquez pour ouvrir cette entrée."))
                lien.clicked.connect(lambda _=False, cible=emploi.entree: self.entree_demandee.emit(cible))
                corps.addWidget(lien, 0, Qt.AlignmentFlag.AlignLeft)
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
    """⑤ Les références à consulter et à citer : textes de loi, dictionnaires, sites officiels."""

    marge_haute = 15

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        corps = self.disposition
        if not entree.ressources:
            self._vide("document", "Aucune ressource pour ce terme",
                       "Ajoutez-en dans la colonne ressources du fichier CSV, puis rechargez le glossaire (F5).")
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


# ====================================================================== la fiche
class Fiche(Panneau):
    """Les cinq champs d'une entrée du glossaire, dans un seul panneau.

    De haut en bas : les onglets des sens (si le terme en a plusieurs), l'en-tête des cinq
    étapes, le corps des cinq colonnes (il défile d'un bloc si la hauteur manque) et leur pied.
    """

    #: Demande d'ouverture d'une autre entrée du glossaire (clic sur une puce de la fiche).
    entree_demandee = Signal(object)
    #: Un autre sens du terme a été choisi par son onglet.
    sens_choisi = Signal(object)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.entree: Entree | None = None
        self.source = FR
        self.setMinimumWidth(LARGEUR_MINIMALE)

        self.onglets = BandeDesSens()
        self.onglets.sens_choisi.connect(self.sens_choisi)
        self.onglets.hide()
        self.entete = EnteteEtapes()
        self.colonne_terme = ColonneTerme(self)
        self.colonne_definition = ColonneDefinition(self)
        self.colonne_equivalent = ColonneEquivalent(self)
        self.colonne_contexte = ColonneContexte(self)
        self.colonne_ressources = ColonneRessources(self)
        self.colonnes: list[Colonne] = [self.colonne_terme, self.colonne_definition, self.colonne_equivalent,
                                        self.colonne_contexte, self.colonne_ressources]

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
        ensemble.addWidget(self.entete)
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
        self.entete.allumer(self.etapes_renseignees())
        self.update()

    def etapes_renseignees(self) -> list[bool]:
        """Pour chacune des cinq étapes : vrai si le glossaire la renseigne pour l'entrée affichée."""
        entree = self.entree
        if entree is None:
            return [False] * len(ETAPES)
        return [True, bool(entree.definition_fr or entree.definition_ar), True,
                bool(self.colonne_contexte.emplois), bool(entree.ressources)]

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

        Les cinq colonnes défilent d'un bloc : elles ont toutes la hauteur de la plus haute.
        Un contenu centré en hauteur (l'équivalent, le message d'un champ vide) serait placé
        au milieu de cette hauteur, parfois hors de la vue. Le bas de chaque colonne reçoit
        donc une réserve vide : son contenu se place dans la partie visible, ou dans la
        hauteur qu'il lui faut si elle est plus grande.
        """
        visible = self.defilement.viewport().height()
        naturelles = self._hauteurs_naturelles(self.width())
        rangee = max(visible, *naturelles)
        for colonne, naturelle in zip(self.colonnes, naturelles, strict=True):
            colonne.definir_reserve(rangee - max(visible, naturelle))

    def _hauteur_fixe(self) -> int:
        """Hauteur de tout ce qui entoure le corps : onglets, en-tête, pied."""
        return (HAUTEUR_ONGLETS if not self.onglets.isHidden() else 0) + HAUTEUR_ENTETE + HAUTEUR_PIED

    def hauteur_de_reference(self) -> int:
        """Hauteur de la fiche dans la fenêtre de référence."""
        return self._hauteur_fixe() + HAUTEUR_DU_CORPS

    def hauteur_minimale(self) -> int:
        return self._hauteur_fixe() + HAUTEUR_MINIMALE_DU_CORPS

    def hauteur_du_contenu(self, largeur: int) -> int:
        """Hauteur qu'il faut à la fiche pour afficher ses cinq colonnes sans défilement."""
        return self._hauteur_fixe() + max(self._hauteurs_naturelles(largeur))

    # ------------------------------------------------------------------ dessin
    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().paintEvent(evenement)
        peintre = QPainter(self)
        bornes = bornes_des_colonnes(self.width(), PROPORTIONS)
        haut = self.entete.y()
        sous_entete = haut + HAUTEUR_ENTETE
        pied = self.height() - HAUTEUR_PIED
        # Le champ 3 (l'équivalent) est mis en avant : fond teinté, filet bleu en haut.
        peintre.fillRect(bornes[2], haut, bornes[3] - bornes[2], self.height() - haut, QColor(theme.BLEU_50))
        peintre.fillRect(bornes[2], haut, bornes[3] - bornes[2], 3, QColor(theme.BLEU))
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, sous_entete, self.width(), sous_entete)
        peintre.drawLine(0, pied, self.width(), pied)
        for rang in range(1, len(PROPORTIONS)):
            peintre.setPen(QColor(theme.BLEU_100 if rang in (2, 3) else theme.FILET_DOUX))
            peintre.drawLine(bornes[rang], sous_entete, bornes[rang], self.height())


# ====================================================================== autres entrées trouvées
class CelluleEntree(QAbstractButton):
    """Une entrée de la liste : le terme français à gauche, le terme arabe à droite."""

    def __init__(self, entree: Entree, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entree = entree
        self.marge_gauche = self.marge_droite = 16
        self._francais = self._arabe = ""
        self.setText(f"{entree.terme_fr} — {entree.terme_ar}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def _polices(self) -> tuple[QFont, QFont]:
        return police(self.font(), 13), police(self.font(), 15)

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self.ajuster()

    def ajuster(self) -> None:
        """Abrège les deux termes à la largeur de la case ; l'infobulle donne alors les termes entiers."""
        francais, arabe = self._polices()
        place = self.width() - self.marge_gauche - self.marge_droite
        # L'arabe garde sa largeur, dans la limite de la moitié de la case ; le français prend le reste.
        largeur_arabe = min(largeur_du_texte(self.entree.terme_ar, arabe) + 2, max(place * 0.55, 40))
        self._arabe = abreger(self.entree.terme_ar, arabe, largeur_arabe)
        self._francais = abreger(self.entree.terme_fr, francais,
                                 place - largeur_du_texte(self._arabe, arabe) - 20)
        abrege = (self._francais, self._arabe) != (self.entree.terme_fr, self.entree.terme_ar)
        self.setToolTip(infobulle(f"{self.entree.terme_fr} — {self.entree.terme_ar}") if abrege else "")

    def textes_affiches(self) -> tuple[str, str]:
        return self._francais, self._arabe

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        survol = self.underMouse() or self.hasFocus()
        if survol:
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1) if self.hasFocus() else Qt.PenStyle.NoPen)
            peintre.setBrush(QColor(theme.BLEU_50))
            peintre.drawRoundedRect(QRectF(6.5, 4.5, self.width() - 13, self.height() - 8), 6, 6)
        francais, arabe = self._polices()
        cadre = QRectF(self.marge_gauche, 0, self.width() - self.marge_gauche - self.marge_droite, self.height())
        dessiner_ligne(peintre, cadre, self._francais, francais, theme.BLEU_FONCE if survol else theme.TEXTE,
                       base=22.8)
        dessiner_ligne(peintre, cadre, self._arabe, arabe, theme.BLEU_FONCE if survol else theme.TEXTE_2,
                       langue=AR, base=23.2)


class GrilleEntrees(QWidget):
    """Grille des entrées : quatre colonnes au plus, des lignes de hauteur régulière."""

    #: Demande d'ouverture d'une entrée (clic sur une case).
    ouverture = Signal(object)

    HAUTEUR_DE_LIGNE = 36
    #: Largeur minimale d'une case : le nombre de colonnes en dépend.
    LARGEUR_DE_CASE = 250

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cellules: list[CelluleEntree] = []
        regle = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        regle.setHeightForWidth(True)
        self.setSizePolicy(regle)

    def definir(self, entrees: Sequence[Entree]) -> None:
        for cellule in self.cellules:
            cellule.setParent(None)
            cellule.deleteLater()
        self.cellules = []
        for entree in entrees:
            cellule = CelluleEntree(entree, self)
            cellule.clicked.connect(lambda _=False, cible=entree: self.ouverture.emit(cible))
            cellule.show()
            self.cellules.append(cellule)
        self._placer()
        self.updateGeometry()
        self.update()

    def colonnes(self, largeur: int | None = None) -> int:
        largeur = self.width() if largeur is None else largeur
        return max(1, min(4, largeur // self.LARGEUR_DE_CASE))

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


class ListeEntrees(Panneau):
    """Panneau placé sous la fiche : les autres entrées du glossaire trouvées par la recherche."""

    #: Demande d'affichage d'une entrée de la liste.
    ouverture = Signal(object)

    HAUTEUR_DU_TITRE = 40
    #: Espace laissé sous la dernière ligne.
    MARGE_BASSE = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        titre = QWidget()
        titre.setFixedHeight(self.HAUTEUR_DU_TITRE)
        ligne = QHBoxLayout(titre)
        ligne.setContentsMargins(theme.MARGE, 0, theme.MARGE, 0)
        ligne.setSpacing(12)
        self.titre = EtiquetteCourte("", "titrePanneau")
        self.nombre = pastille()
        self.aide = EtiquetteCourte("", "aidePanneau")
        self.aide.definir_texte("Cliquez sur une ligne pour ouvrir sa fiche", "")
        self.aide.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.aide.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        ligne.addWidget(self.titre)
        ligne.addWidget(self.nombre)
        ligne.addWidget(self.aide, 1)
        ensemble.addWidget(titre)

        self.grille = GrilleEntrees()
        self.grille.ouverture.connect(self.ouverture)
        self.defilement = ZoneDefilante()
        self.defilement.definir_contenu(self.grille)
        ensemble.addWidget(self.defilement, 1)

    def definir(self, titre: str, entrees: Sequence[Entree]) -> None:
        """Remplit la liste ; le panneau n'a pas lieu d'être affiché si ``entrees`` est vide."""
        self.titre.definir_texte(titre)
        self.nombre.setText(nombre(len(entrees)))
        self.grille.definir(entrees)
        self.defilement.revenir_en_haut()

    def entrees(self) -> list[Entree]:
        return [cellule.entree for cellule in self.grille.cellules]

    def hauteur_naturelle(self, largeur: int) -> int:
        """Hauteur du panneau quand toutes les lignes sont visibles."""
        if not self.grille.cellules:
            return 0
        return self.HAUTEUR_DU_TITRE + self.grille.heightForWidth(largeur) + self.MARGE_BASSE

    def hauteur_minimale(self) -> int:
        """Le titre et deux lignes."""
        return self.HAUTEUR_DU_TITRE + 2 * GrilleEntrees.HAUTEUR_DE_LIGNE + self.MARGE_BASSE

    def paintEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().paintEvent(evenement)
        peintre = QPainter(self)
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(0, self.HAUTEUR_DU_TITRE, self.width(), self.HAUTEUR_DU_TITRE)
