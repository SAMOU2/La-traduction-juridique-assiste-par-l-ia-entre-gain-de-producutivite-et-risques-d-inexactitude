"""Menu « Plus de détails » de l'écran « Terme » : un cercle par information, autour du terme.

La fiche n'affiche que le terme et son équivalent (voir ``fiche.py``). Le reste de l'entrée est
rangé dans ce menu : la définition, les phrases d'exemple (contextualisation), les ressources,
les expressions qui contiennent le terme, ses termes associés et ses synonymes.

Le menu est une roue : le terme au centre, un cercle par information autour de lui (trois à
gauche, trois à droite), chacun relié au centre par un trait. Un cercle est coloré quand le
glossaire renseigne l'information, gris sinon. Un clic sur un cercle affiche l'information à
droite de la roue ; un second clic, ou un clic sur le centre, la referme. L'information choisie
reste choisie d'un terme à l'autre.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QLineF, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..glossaire import Entree, Glossaire
from ..langues import AR, FR
from . import icones, theme
from .animation import Allumage
from .composants import (
    EtiquetteCourte,
    Panneau,
    ZoneDefilante,
    etiquette,
    infobulle,
    nombre,
    pastille,
    rond,
    separateur,
)
from .dessin import couper_en_lignes, dessiner_ligne, largeur_du_texte, melanger, police
from .fiche import (
    HAUTEUR_PIED,
    Colonne,
    ColonneAssocies,
    ColonneContexte,
    ColonneDefinition,
    ColonneExpressions,
    ColonneRessources,
    ColonneSynonymes,
)


@dataclass(frozen=True)
class Detail:
    """Une information du menu : son nom, son icône, sa couleur, ce que disent ses infobulles."""

    cle: str
    titre: str
    #: Nom plus court, écrit à côté du cercle quand la roue est étroite.
    titre_court: str
    icone: str
    couleur: str
    #: Infobulle du cercle quand le glossaire renseigne l'information, et quand il ne la renseigne pas.
    info: str
    info_vide: str


#: Les informations du menu, dans l'ordre des cercles : du haut de la roue, à gauche, puis dans le sens des
#: aiguilles d'une montre.
DETAILS = (
    Detail("definition", "Définition", "Définition", "livre", theme.DETAIL_VERT,
           "La définition du terme, en français et en arabe",
           "Le glossaire ne donne pas de définition pour ce terme"),
    Detail("contexte", "Contextualisation", "Contexte", "bulle", theme.DETAIL_ROUGE,
           "Des phrases qui emploient le terme, dans les deux langues",
           "Aucune phrase du glossaire n’emploie ce terme"),
    Detail("ressources", "Ressources", "Ressources", "ouvrages", theme.DETAIL_VIOLET,
           "Les textes de loi, les ouvrages et les sites à consulter et à citer",
           "Le glossaire ne cite pas de référence pour ce terme"),
    Detail("expressions", "Expressions", "Expressions", "liste", theme.DETAIL_ROSE,
           "Les autres entrées du glossaire trouvées par la recherche",
           "La recherche n’a trouvé aucune autre entrée du glossaire"),
    Detail("associes", "Termes associés", "Associés", "liens", theme.DETAIL_ORANGE,
           "Les termes qu’on rencontre avec celui-ci",
           "Le glossaire ne cite pas de terme associé"),
    Detail("synonymes", "Synonymes", "Synonymes", "equivalence", theme.DETAIL_CYAN,
           "Les synonymes du terme, dans la même langue",
           "Le glossaire ne donne pas de synonyme pour ce terme"),
)
PAR_CLE = {detail.cle: detail for detail in DETAILS}
CLES = tuple(PAR_CLE)


def medaillon(detail: Detail, diametre: int, allume: bool = True) -> QPixmap:
    """Petite image du cercle d'une information : son icône dans un anneau de sa couleur.

    Le cercle est gris si ``allume`` est faux.
    """
    ecran = QGuiApplication.primaryScreen()
    rapport = ecran.devicePixelRatio() if ecran is not None else 1.0
    image = QPixmap(round(diametre * rapport), round(diametre * rapport))
    image.setDevicePixelRatio(rapport)
    image.fill(Qt.GlobalColor.transparent)
    couleur = detail.couleur if allume else theme.TEXTE_4
    peintre = QPainter(image)
    peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
    epaisseur = max(diametre / 11, 1.5)
    peintre.setPen(QPen(QColor(couleur if allume else theme.DETAIL_ETEINT), epaisseur))
    peintre.setBrush(QColor(theme.SURFACE))
    rayon = (diametre - epaisseur) / 2
    peintre.drawEllipse(QPointF(diametre / 2, diametre / 2), rayon, rayon)
    cote = round(diametre * 0.52)
    peintre.drawPixmap(QPointF((diametre - cote) / 2, (diametre - cote) / 2),
                       icones.image(detail.icone, couleur, cote, 1.5))
    peintre.end()
    return image


# ====================================================================== un cercle de la roue
class BoutonDetail(QAbstractButton):
    """Un cercle du menu : l'icône d'une information dans un anneau de couleur, son nom à côté.

    Le cercle est coloré quand le glossaire renseigne l'information, gris sinon ; une pastille
    donne alors le nombre d'éléments (« 23 » expressions). Le cercle choisi est teinté et entouré
    d'un halo. La roue fixe la place du cercle et celle de son nom (voir ``RoueDesDetails``).
    """

    def __init__(self, detail: Detail, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detail = detail
        #: Vrai si le glossaire renseigne l'information pour le terme affiché.
        self.disponible = False
        #: Nombre d'éléments de l'information (0 : pas de pastille).
        self.nombre = 0
        #: Le nom écrit à côté du cercle (sa forme longue ou sa forme courte).
        self.libelle = detail.titre
        #: Niveau d'allumage (0 : gris, 1 : coloré) et halo passager, pendant l'animation.
        self.niveau, self.halo = 0.0, 0.0
        # Place du cercle et de son nom, dans les coordonnées du bouton : la roue les fixe.
        self.centre = QPointF(0.0, 0.0)
        self.rayon = 25.0
        self.cadre_du_libelle = QRectF()
        self.alignement = Qt.AlignmentFlag.AlignHCenter
        self.taille_du_libelle = 12
        self.setCheckable(True)
        self.setText(detail.titre)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        # Le clavier atteint le cercle par la touche Tab ; un clic ne lui laisse pas d'anneau de curseur.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def definir(self, disponible: bool, nombre_d_elements: int = 0) -> None:
        """Dit si le glossaire renseigne l'information, et combien d'éléments elle compte."""
        self.disponible, self.nombre = disponible, nombre_d_elements if disponible else 0
        detail = self.detail
        self.setAccessibleName(detail.titre)
        self.setAccessibleDescription(detail.info if disponible else detail.info_vide)
        self.setToolTip(infobulle(detail.info if disponible else detail.info_vide))
        self.update()

    def hitButton(self, point) -> bool:  # noqa: N802 (nom imposé par Qt)
        """Le cercle et son nom répondent au clic, pas le reste du rectangle du bouton."""
        return (QLineF(QPointF(point), self.centre).length() <= self.rayon + 4
                or self.cadre_du_libelle.adjusted(-3, -3, 3, 3).contains(QPointF(point)))

    def couleur(self) -> QColor:
        """Couleur de l'anneau : celle de l'information, à la mesure de son allumage ; grise sinon."""
        return melanger(theme.DETAIL_ETEINT, self.detail.couleur, self.niveau if self.disponible else 0.0)

    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        echelle = self.rayon / RoueDesDetails.RAYON_D_UN_CERCLE
        choisi, survol = self.isChecked(), self.underMouse()
        couleur = self.couleur()
        allume = self.disponible and self.niveau > 0.0

        # Halo : celui du cercle choisi, ou celui, passager, du cercle qui s'allume.
        halo = 1.0 if choisi else self.halo
        if halo > 0.0:
            lueur = QColor(couleur)
            lueur.setAlphaF(0.20 * halo)
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(lueur)
            rayon_du_halo = self.rayon + RoueDesDetails.HALO * echelle
            peintre.drawEllipse(self.centre, rayon_du_halo, rayon_du_halo)

        # L'anneau : épais et coloré, ou fin et gris quand le glossaire n'a rien.
        epaisseur = (5.5 if choisi else 4.6 if survol else 4.0) * echelle if allume else 1.5
        fond = QColor(theme.SURFACE)
        if choisi or survol:
            fond = melanger(theme.SURFACE, couleur.name(), 0.16 if choisi else 0.08)
        peintre.setPen(QPen(couleur, epaisseur))
        peintre.setBrush(fond)
        peintre.drawEllipse(self.centre, self.rayon - epaisseur / 2, self.rayon - epaisseur / 2)
        if self.hasFocus():
            peintre.setPen(QPen(QColor(theme.BLEU_200), 1.5))
            peintre.setBrush(Qt.BrushStyle.NoBrush)
            peintre.drawEllipse(self.centre, self.rayon + 3, self.rayon + 3)

        # L'icône, au centre.
        cote = max(round(18 * echelle), 9)
        teinte = melanger(theme.TEXTE_4, self.detail.couleur, self.niveau).name() if self.disponible else theme.TEXTE_4
        peintre.drawPixmap(QPointF(self.centre.x() - cote / 2, self.centre.y() - cote / 2),
                           icones.image(self.detail.icone, teinte, cote, 1.5))

        # La pastille du nombre d'éléments, en haut à droite du cercle.
        if self.nombre and allume:
            texte = nombre(self.nombre) if self.nombre < 1000 else "999+"
            police_du_nombre = police(self.font(), 10, gras=True)
            hauteur = 15.0
            largeur = max(hauteur, largeur_du_texte(texte, police_du_nombre) + 8)
            cadre = QRectF(self.centre.x() + self.rayon * 0.62 - largeur / 2 + 3,
                           self.centre.y() - self.rayon * 0.62 - hauteur / 2 - 3, largeur, hauteur)
            peintre.setPen(QPen(QColor(theme.SURFACE), 1.5))
            peintre.setBrush(couleur)
            peintre.drawRoundedRect(cadre, hauteur / 2, hauteur / 2)
            dessiner_ligne(peintre, cadre, texte, police_du_nombre, theme.SURFACE,
                           alignement=Qt.AlignmentFlag.AlignHCenter)

        # Le nom de l'information.
        police_du_libelle = police(self.font(), self.taille_du_libelle, gras=self.disponible)
        teinte = theme.TEXTE_4 if not self.disponible else theme.MARINE if choisi or survol else theme.TEXTE_2
        dessiner_ligne(peintre, self.cadre_du_libelle, self.libelle, police_du_libelle, teinte,
                       alignement=self.alignement)


# ====================================================================== la roue
class RoueDesDetails(QWidget):
    """Le menu en roue : le terme au centre, un cercle par information autour de lui.

    La roue se dessine à la taille qu'elle reçoit : dans une petite fenêtre, les cercles
    rétrécissent et les noms trop longs prennent leur forme courte.
    """

    #: Un cercle a été cliqué. Le signal porte la clé de l'information à afficher (« definition »…),
    #: ou une chaîne vide quand l'information affichée est à refermer.
    choisi = Signal(str)

    #: Dimensions de la roue à l'échelle 1 : distance du centre de la roue au centre d'un cercle,
    #: rayon du disque central, rayon d'un cercle, largeur du halo du cercle choisi.
    RAYON_DE_L_ORBITE, RAYON_DU_CENTRE, RAYON_D_UN_CERCLE, HALO = 106.0, 50.0, 25.0, 6.0
    #: Espace entre un cercle et son nom, hauteur de la ligne du nom, marge autour de la roue.
    ECART_DU_LIBELLE, HAUTEUR_DU_LIBELLE, MARGE = 8, 18, 4
    #: Hauteur laissée libre en haut de la roue (le panneau y écrit le titre du menu) et en bas.
    RESERVE_HAUTE, RESERVE_BASSE = 34, 8
    #: Écrit au centre quand le terme n'y tient pas en entier.
    REPERE_DU_CENTRE = "TERME"
    ECHELLE_MINIMALE, ECHELLE_MAXIMALE = 0.42, 1.25

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.boutons: dict[str, BoutonDetail] = {}
        for detail in DETAILS:
            bouton = BoutonDetail(detail, self)
            bouton.clicked.connect(lambda _=False, cle=detail.cle: self._cliquer(cle))
            self.boutons[detail.cle] = bouton
        #: Le terme écrit au centre, et sa langue.
        self.terme, self.langue = "", FR
        #: Clé de l'information choisie (vide : aucune).
        self.detail = ""
        #: Noms des cercles : pour chaque clé, la forme longue et la forme courte.
        self._libelles = {detail.cle: (detail.titre, detail.titre_court) for detail in DETAILS}
        #: Échelle du dessin et centre de la roue, calculés à chaque changement de taille.
        self.echelle = 1.0
        self.centre = QPointF(0.0, 0.0)
        self.allumage = Allumage(len(DETAILS), self)
        self.allumage.change.connect(self._rafraichir)
        self.setMouseTracking(True)
        self.setAccessibleName("Plus de détails")
        self._placer()

    # ------------------------------------------------------------------ contenu
    def definir(self, etats: Mapping[str, tuple[bool, int]], terme: str, langue: str,
                libelles: Mapping[str, tuple[str, str]] | None = None) -> None:
        """Décrit le terme affiché : pour chaque information, si le glossaire la renseigne et combien d'éléments.

        ``libelles`` change le nom de certains cercles (forme longue, forme courte) : le cercle des
        expressions s'appelle « Autres résultats » quand la recherche a trouvé autre chose.
        """
        self.terme, self.langue = terme, langue
        for detail in DETAILS:
            self._libelles[detail.cle] = (libelles or {}).get(detail.cle, (detail.titre, detail.titre_court))
            disponible, elements = etats.get(detail.cle, (False, 0))
            self.boutons[detail.cle].definir(disponible, elements)
        self._placer()
        # Les cercles renseignés s'allument l'un après l'autre.
        self.allumage.definir([self.boutons[cle].disponible for cle in CLES])
        self.update()

    def choisir(self, cle: str) -> None:
        """Marque le cercle de l'information affichée (aucun si ``cle`` est vide)."""
        self.detail = cle if cle in self.boutons else ""
        for autre, bouton in self.boutons.items():
            bouton.setChecked(autre == self.detail)
        self.update()

    def etats(self) -> dict[str, bool]:
        """Pour chaque information : vrai si son cercle est coloré."""
        return {cle: bouton.disponible for cle, bouton in self.boutons.items()}

    def libelles_affiches(self) -> list[str]:
        """Le nom écrit à côté de chaque cercle, dans l'ordre des cercles."""
        return [bouton.libelle for bouton in self.boutons.values()]

    def _cliquer(self, cle: str) -> None:
        """Un clic sur le cercle choisi referme son information ; sur un autre cercle, il l'affiche."""
        nouveau = "" if cle == self.detail else cle
        self.choisir(nouveau)
        self.choisi.emit(nouveau)

    def _rafraichir(self) -> None:
        for rang, cle in enumerate(CLES):
            bouton = self.boutons[cle]
            bouton.niveau, bouton.halo = self.allumage.niveau(rang), self.allumage.halo(rang)
            bouton.update()
        self.update()

    # ------------------------------------------------------------------ mise en place
    @staticmethod
    def directions() -> list[tuple[float, float]]:
        """Direction de chaque cercle depuis le centre.

        Les cercles sont répartis de part et d'autre du centre : le premier est en haut à gauche,
        les suivants tournent à droite. Aucun cercle n'est au-dessus ni au-dessous du centre : la
        roue emploie toute la hauteur du panneau, et chaque nom s'écrit à côté de son cercle.
        """
        pas = 2 * math.pi / len(DETAILS)
        return [(math.sin((rang - 0.5) * pas), -math.cos((rang - 0.5) * pas)) for rang in range(len(DETAILS))]

    def sizeHint(self) -> QSize:  # noqa: N802 (nom imposé par Qt)
        return QSize(460, 330)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(260, 170)

    def resizeEvent(self, evenement) -> None:  # noqa: N802
        super().resizeEvent(evenement)
        self._placer()

    def _placer(self) -> None:
        """Calcule l'échelle de la roue, puis place chaque cercle et son nom.

        Le nom d'un cercle est écrit du côté opposé au centre : à gauche des cercles de gauche,
        à droite des cercles de droite. La roue prend la plus grande échelle que permettent la
        hauteur du panneau et sa largeur, noms compris, puis elle est centrée dans cette largeur.
        """
        directions = self.directions()
        orbite, cercle = self.RAYON_DE_L_ORBITE, self.RAYON_D_UN_CERCLE
        ecart, marge = self.ECART_DU_LIBELLE, self.MARGE
        demi_hauteur = max(abs(dy) for _, dy in directions) * orbite + cercle + self.HALO
        en_hauteur = (self.height() - self.RESERVE_HAUTE - self.RESERVE_BASSE) / (2 * demi_hauteur)
        libre = self.width() - 2 * marge
        police_du_libelle = police(self.font(), 12, gras=True)

        # De chaque côté du centre, un cercle occupe : sa distance au centre et son rayon, qui suivent
        # l'échelle, puis l'écart et la largeur de son nom, qui ne la suivent pas. L'échelle que permet
        # la largeur est la plus petite de celles que permet chaque paire (cercle de gauche, cercle de droite).
        # Les noms longs sont gardés s'ils laissent à la roue (presque) l'échelle que la hauteur permet.
        a_gauche: list[tuple[float, float]] = []
        a_droite: list[tuple[float, float]] = []
        libelles: list[str] = []
        largeurs: list[float] = []
        en_largeur = 0.0
        for forme in (0, 1):
            libelles = [self._libelles[cle][forme] for cle in CLES]
            largeurs = [largeur_du_texte(libelle, police_du_libelle) + 2 for libelle in libelles]
            cotes = [(abs(dx) * orbite + cercle, largeur + ecart)
                     for (dx, _), largeur in zip(directions, largeurs, strict=True)]
            a_gauche = [cote for cote, (dx, _) in zip(cotes, directions, strict=True) if dx < 0] or [(cercle, 0.0)]
            a_droite = [cote for cote, (dx, _) in zip(cotes, directions, strict=True) if dx >= 0] or [(cercle, 0.0)]
            en_largeur = min((libre - fixe_g - fixe_d) / (pente_g + pente_d)
                             for pente_g, fixe_g in a_gauche for pente_d, fixe_d in a_droite)
            if en_largeur >= 0.92 * min(en_hauteur, self.ECHELLE_MAXIMALE):
                break
        echelle = min(max(min(en_hauteur, en_largeur), self.ECHELLE_MINIMALE), self.ECHELLE_MAXIMALE)
        gauche = max(pente * echelle + fixe for pente, fixe in a_gauche)
        droite = max(pente * echelle + fixe for pente, fixe in a_droite)
        self.echelle = echelle
        # Centrée dans la largeur ; en hauteur, au milieu du panneau, ou plus bas si le titre du menu l'exige.
        self.centre = QPointF((self.width() - gauche - droite) / 2 + gauche,
                              max(self.height() / 2, self.RESERVE_HAUTE + demi_hauteur * echelle))

        rayon, hauteur = cercle * echelle, float(self.HAUTEUR_DU_LIBELLE)
        for cle, (dx, dy), libelle, largeur in zip(CLES, directions, libelles, largeurs, strict=True):
            bouton = self.boutons[cle]
            x, y = self.centre.x() + dx * orbite * echelle, self.centre.y() + dy * orbite * echelle
            if dx >= 0:
                cadre = QRectF(x + rayon + ecart, y - hauteur / 2, largeur, hauteur)
                alignement = Qt.AlignmentFlag.AlignLeft
            else:
                cadre = QRectF(x - rayon - ecart - largeur, y - hauteur / 2, largeur, hauteur)
                alignement = Qt.AlignmentFlag.AlignRight
            # Le bouton couvre le cercle (avec la place de son halo) et son nom.
            halo = rayon + self.HALO * echelle + 2
            contour = QRectF(x - halo, y - halo, 2 * halo, 2 * halo).united(cadre.adjusted(-2, -2, 2, 2))
            contour = contour.toAlignedRect()
            bouton.libelle, bouton.rayon, bouton.alignement = libelle, rayon, alignement
            bouton.taille_du_libelle = 12
            bouton.centre = QPointF(x - contour.x(), y - contour.y())
            bouton.cadre_du_libelle = cadre.translated(-contour.x(), -contour.y())
            bouton.setGeometry(contour)
            bouton.update()
        self.update()

    def cadre_du_libelle(self, cle: str) -> QRectF:
        """Place du nom d'un cercle, dans les coordonnées de la roue."""
        bouton = self.boutons[cle]
        return bouton.cadre_du_libelle.translated(bouton.x(), bouton.y())

    # ------------------------------------------------------------------ le centre
    def _sur_le_centre(self, point) -> bool:
        return QLineF(QPointF(point), self.centre).length() <= self.RAYON_DU_CENTRE * self.echelle

    def info_du_centre(self) -> str:
        """Infobulle du disque central : ce qu'un clic y fait, ou le terme s'il n'a pas pu y être écrit."""
        if self.detail:
            return "Refermer l’information affichée"
        return infobulle(self.terme) if self.terme and not self.lignes_du_centre()[0] else ""

    def mouseMoveEvent(self, evenement) -> None:  # noqa: N802
        # Le centre referme l'information affichée : il ne répond au clic que s'il y en a une.
        sur_le_centre = self._sur_le_centre(evenement.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if sur_le_centre and self.detail
                       else Qt.CursorShape.ArrowCursor)
        self.setToolTip(self.info_du_centre() if sur_le_centre else "")
        super().mouseMoveEvent(evenement)

    def mouseReleaseEvent(self, evenement) -> None:  # noqa: N802
        if (evenement.button() == Qt.MouseButton.LeftButton and self.detail
                and self._sur_le_centre(evenement.position())):
            self.choisir("")
            self.choisi.emit("")
        super().mouseReleaseEvent(evenement)

    def lignes_du_centre(self) -> tuple[list[str], int]:
        """Le terme, coupé en lignes qui tiennent dans le disque central, et la taille de ses caractères.

        Les caractères diminuent tant que le terme ne tient pas. L'arabe est écrit un peu plus
        grand que le français. Si le terme ne tient pas en entier, même à la plus petite taille,
        la liste est vide : le disque porte alors le seul mot « TERME » (voir ``paintEvent``). Un
        terme abrégé (« respons… ») se lirait mal, et le terme est écrit en grand dans la fiche.
        """
        rayon = self.RAYON_DU_CENTRE * self.echelle
        agrandi = 1.2 if self.langue == AR else 1.0
        taille = 11
        for taille_latine, nombre_de_lignes, part in ((16, 2, 1.5), (14, 2, 1.5), (12, 3, 1.42), (11, 3, 1.42)):
            taille = round(taille_latine * agrandi)
            police_du_terme = police(self.font(), taille, gras=True)
            # Pas plus de lignes que le disque n'en contient.
            permises = max(min(nombre_de_lignes, int(1.2 * rayon // (taille + 4))), 1)
            lignes, abrege = couper_en_lignes(self.terme, police_du_terme, rayon * part, permises)
            # Un mot plus large que la ligne n'est pas coupé : il déborderait du disque.
            if not abrege and all(largeur_du_texte(ligne, police_du_terme) <= 1.64 * rayon for ligne in lignes):
                return lignes, taille
        return [], taille

    # ------------------------------------------------------------------ dessin
    def paintEvent(self, evenement) -> None:  # noqa: N802
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing)
        echelle, centre = self.echelle, self.centre
        rayon_du_centre = self.RAYON_DU_CENTRE * echelle
        orbite = rayon_du_centre + 9 * echelle

        # 1. Autour du centre, un anneau fin : les traits en partent.
        peintre.setPen(QPen(QColor(theme.FILET), 1))
        peintre.setBrush(Qt.BrushStyle.NoBrush)
        peintre.drawEllipse(centre, orbite, orbite)

        # 2. Du centre vers chaque cercle : un point sur l'anneau, puis un trait fléché, de la couleur du cercle.
        fin = (self.RAYON_DE_L_ORBITE - self.RAYON_D_UN_CERCLE - 8) * echelle
        pointe = 5 * echelle
        for cle, (dx, dy) in zip(CLES, self.directions(), strict=True):
            bouton = self.boutons[cle]
            choisi = cle == self.detail
            couleur = bouton.couleur()
            depart = QPointF(centre.x() + dx * orbite, centre.y() + dy * orbite)
            arrivee = QPointF(centre.x() + dx * fin, centre.y() + dy * fin)
            stylo = QPen(couleur, 2.0 if choisi else 1.25)
            stylo.setCapStyle(Qt.PenCapStyle.RoundCap)
            peintre.setPen(stylo)
            if fin - orbite >= 6:
                peintre.drawLine(depart, arrivee)
                for cote in (-1, 1):
                    angle = math.atan2(dy, dx) + math.pi + cote * 0.5
                    peintre.drawLine(arrivee, QPointF(arrivee.x() + pointe * math.cos(angle),
                                                      arrivee.y() + pointe * math.sin(angle)))
            peintre.setPen(Qt.PenStyle.NoPen)
            peintre.setBrush(couleur)
            peintre.drawEllipse(depart, 2.6 * echelle, 2.6 * echelle)

        # 3. Le disque central : une ombre légère, un anneau bleu, le terme.
        peintre.setPen(Qt.PenStyle.NoPen)
        for decalage, opacite in ((3.0, 0.05), (1.5, 0.07)):
            ombre = QColor(theme.MARINE)
            ombre.setAlphaF(opacite)
            peintre.setBrush(ombre)
            peintre.drawEllipse(QPointF(centre.x(), centre.y() + decalage * echelle),
                                rayon_du_centre + decalage * 0.4, rayon_du_centre + decalage * 0.4)
        epaisseur = 7 * echelle
        peintre.setPen(QPen(QColor(theme.BLEU), epaisseur))
        peintre.setBrush(QColor(theme.SURFACE))
        peintre.drawEllipse(centre, rayon_du_centre - epaisseur / 2, rayon_du_centre - epaisseur / 2)
        lignes, taille = self.lignes_du_centre()
        largeur = 2 * rayon_du_centre
        if lignes:
            police_du_terme = police(self.font(), taille, gras=True)
            interligne = taille + 4.0
            haut = centre.y() - interligne * len(lignes) / 2
            for rang, ligne in enumerate(lignes):
                dessiner_ligne(peintre, QRectF(centre.x() - largeur / 2, haut + rang * interligne, largeur, interligne),
                               ligne, police_du_terme, theme.MARINE, langue=self.langue,
                               alignement=Qt.AlignmentFlag.AlignHCenter)
        elif self.terme:
            # Le terme ne tient pas dans le disque : un simple repère, écrit comme les légendes de la fiche.
            police_du_repere = police(self.font(), 10, gras=True, espacement=0.6)
            if largeur_du_texte(self.REPERE_DU_CENTRE, police_du_repere) <= 1.7 * rayon_du_centre:
                dessiner_ligne(peintre, QRectF(centre.x() - largeur / 2, centre.y() - 8, largeur, 16),
                               self.REPERE_DU_CENTRE, police_du_repere, theme.TEXTE_3,
                               alignement=Qt.AlignmentFlag.AlignHCenter)


# ====================================================================== à droite de la roue
class Invite(QWidget):
    """Affichée à droite de la roue tant qu'aucun cercle n'est choisi : ce que le menu propose pour ce terme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(theme.MARGE, 12, theme.MARGE, 12)
        colonne.setSpacing(0)
        colonne.addStretch(4)
        colonne.addWidget(rond("rondVide", 40, "information", theme.TEXTE_4, 18), 0, Qt.AlignmentFlag.AlignHCenter)
        colonne.addSpacing(14)
        self.titre = etiquette("", "videTitre", retour_ligne=True)
        self.texte = etiquette("", "videTexte", retour_ligne=True)
        for label in (self.titre, self.texte):
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            colonne.addWidget(label)
            colonne.addSpacing(6)
        colonne.addStretch(5)

    def definir(self, titre: str, texte: str) -> None:
        self.titre.setText(titre)
        self.texte.setText(texte)
        self.setAccessibleName(titre)
        self.setAccessibleDescription(texte)


class PanneauDetails(Panneau):
    """Le menu « Plus de détails » et, à sa droite, l'information choisie.

    Le panneau construit les six informations de l'entrée affichée, mais n'en montre qu'une à
    la fois : celle dont le cercle est choisi. Sans cercle choisi, une invitation la remplace.
    """

    #: Demande d'ouverture d'une autre entrée du glossaire (clic sur une puce, sur le lien d'une phrase).
    entree_demandee = Signal(object)
    #: Demande d'affichage d'une autre entrée trouvée par la recherche (clic sur une ligne de la liste).
    ouverture = Signal(object)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)
    #: L'information affichée a changé ; le signal porte sa clé (vide : aucune).
    detail_change = Signal(str)

    #: Hauteurs du panneau : celle sous laquelle la fiche lui cède de la place, et la hauteur minimale.
    HAUTEUR_CONFORTABLE, HAUTEUR_MINIMALE = 270, 170
    HAUTEUR_ENTETE = 44
    #: Largeur donnée au menu : une part de la largeur du panneau, entre deux limites.
    PART_DU_MENU, LARGEUR_MINIMALE_DU_MENU, LARGEUR_MAXIMALE_DU_MENU = 0.38, 360, 500

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.entree: Entree | None = None
        self.source = FR
        #: Clé de l'information affichée (vide : aucune).
        self.detail = ""
        #: Information que l'utilisateur a choisie : elle reste affichée d'un terme à l'autre.
        self._voulu = ""
        #: Nom du cercle des autres entrées trouvées : « Expressions » ou « Autres résultats ».
        self._libelle_des_autres = ("Expressions", "Expressions")

        self.colonne_definition = ColonneDefinition(self)
        self.colonne_contexte = ColonneContexte(self)
        self.colonne_ressources = ColonneRessources(self)
        self.colonne_expressions = ColonneExpressions(self)
        self.colonne_associes = ColonneAssocies(self)
        self.colonne_synonymes = ColonneSynonymes(self)
        self.colonnes: dict[str, Colonne] = {
            "definition": self.colonne_definition, "contexte": self.colonne_contexte,
            "ressources": self.colonne_ressources, "expressions": self.colonne_expressions,
            "associes": self.colonne_associes, "synonymes": self.colonne_synonymes}
        for colonne in self.colonnes.values():
            colonne.entree_demandee.connect(self.entree_demandee)
            colonne.message.connect(self.message)
        self.colonne_expressions.ouverture.connect(self.ouverture)

        # ---------------------------------------------------------- à gauche : le menu
        # La roue occupe toute la hauteur du panneau. Le titre du menu est posé sur son coin, en haut à
        # gauche : la roue garde cette place libre (voir ``RoueDesDetails.RESERVE_HAUTE``).
        self.roue = RoueDesDetails()
        self.roue.choisi.connect(self.choisir)
        self._menu = QWidget()
        dans_le_menu = QVBoxLayout(self._menu)
        dans_le_menu.setContentsMargins(8, 0, 8, 0)
        dans_le_menu.addWidget(self.roue)
        self.titre = etiquette("Plus de détails", "titrePanneau")
        self.titre.setParent(self._menu)
        self.titre.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.titre.move(theme.MARGE, 12)
        self.titre.raise_()

        # ---------------------------------------------------------- à droite : l'invitation, ou l'information
        self.invite = Invite()
        entete = QWidget()
        entete.setFixedHeight(self.HAUTEUR_ENTETE)
        ligne = QHBoxLayout(entete)
        ligne.setContentsMargins(theme.MARGE, 0, 12, 0)
        ligne.setSpacing(10)
        self.medaillon = QLabel()
        self.medaillon.setFixedSize(24, 24)
        self.titre_du_detail = EtiquetteCourte("", "titrePanneau")
        self.nombre = pastille()
        self.bouton_fermer = QToolButton()
        self.bouton_fermer.setProperty("classe", "voisine")
        self.bouton_fermer.setIcon(icones.icone("croix", theme.TEXTE_2, 12, 1.7))
        self.bouton_fermer.setIconSize(QSize(12, 12))
        self.bouton_fermer.setFixedSize(26, 26)
        self.bouton_fermer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bouton_fermer.setToolTip("Refermer cette information")
        self.bouton_fermer.setAccessibleName("Refermer cette information")
        self.bouton_fermer.clicked.connect(lambda: self.choisir(""))
        ligne.addWidget(self.medaillon)
        ligne.addWidget(self.titre_du_detail)
        ligne.addWidget(self.nombre)
        ligne.addStretch(1)
        ligne.addWidget(self.bouton_fermer)

        # Une page par information : son corps, qui défile, puis son pied.
        self.pages = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        self._defilements: dict[str, ZoneDefilante] = {}
        self._pieds: dict[str, tuple[QWidget, QWidget]] = {}
        for cle, colonne in self.colonnes.items():
            page = QWidget()
            dans_la_page = QVBoxLayout(page)
            dans_la_page.setContentsMargins(0, 0, 0, 0)
            dans_la_page.setSpacing(0)
            defilement = ZoneDefilante()
            defilement.definir_contenu(colonne.corps)
            filet = separateur()
            colonne.pied.setFixedHeight(HAUTEUR_PIED)
            dans_la_page.addWidget(defilement, 1)
            dans_la_page.addWidget(filet)
            dans_la_page.addWidget(colonne.pied)
            self.pages.addWidget(page)
            self._pages[cle], self._defilements[cle], self._pieds[cle] = page, defilement, (filet, colonne.pied)
        self.vue = QWidget()
        dans_la_vue = QVBoxLayout(self.vue)
        dans_la_vue.setContentsMargins(0, 0, 0, 0)
        dans_la_vue.setSpacing(0)
        dans_la_vue.addWidget(entete)
        dans_la_vue.addWidget(separateur())
        dans_la_vue.addWidget(self.pages, 1)

        self.pile = QStackedWidget()
        self.pile.addWidget(self.invite)
        self.pile.addWidget(self.vue)
        ensemble = QHBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(0)
        ensemble.addWidget(self._menu)
        ensemble.addWidget(self.pile, 1)
        self.setMinimumHeight(self.HAUTEUR_MINIMALE)
        self._ajuster_le_menu()
        self.afficher(None, None, FR)

    # ------------------------------------------------------------------ contenu
    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str, *,
                 titre_des_autres: str = "", autres: Sequence[Entree] = (),
                 libelle_des_autres: tuple[str, str] = ("Expressions", "Expressions"),
                 suggestion: str = "") -> None:
        """Affiche les informations d'une entrée.

        ``autres`` : les autres entrées trouvées par la recherche, avec le titre de leur liste et
        le nom de leur cercle. ``suggestion`` : l'information à montrer d'office quand
        l'utilisateur n'en a choisi aucune (la liste des résultats d'une recherche approchée).
        """
        self.glossaire, self.entree, self.source = glossaire, entree, source
        self._libelle_des_autres = libelle_des_autres
        self.colonne_expressions.definir(titre_des_autres, autres)
        for cle, colonne in self.colonnes.items():
            colonne.afficher(glossaire, entree, source)
            filet, pied = self._pieds[cle]
            renseigne = colonne.ligne_du_pied.count() > 0
            filet.setVisible(renseigne)
            pied.setVisible(renseigne)
        self.roue.definir(self.etats(), entree.terme(source) if entree is not None else "", source,
                          {"expressions": libelle_des_autres})
        self._montrer(self._voulu or suggestion)

    def etats(self) -> dict[str, tuple[bool, int]]:
        """Pour chaque information : vrai si le glossaire la renseigne pour l'entrée affichée, et son nombre d'éléments.

        La définition ne se compte pas : son nombre est toujours 0.
        """
        entree = self.entree
        if entree is None:
            return dict.fromkeys(CLES, (False, 0))
        nombres = {
            "definition": 0,
            "contexte": len(self.colonne_contexte.emplois),
            "ressources": len(entree.ressources),
            "expressions": len(self.colonne_expressions.entrees()),
            "associes": len(entree.termes_associes),
            "synonymes": len(entree.synonymes(self.source)),
        }
        etats = {cle: (bool(elements), elements) for cle, elements in nombres.items()}
        etats["definition"] = (bool(entree.definition_fr or entree.definition_ar), 0)
        return etats

    def renseignes(self) -> list[str]:
        """Les clés des informations que le glossaire renseigne pour l'entrée affichée, dans l'ordre des cercles."""
        etats = self.etats()
        return [cle for cle in CLES if etats[cle][0]]

    def choisir(self, cle: str) -> None:
        """Affiche une information, à la demande de l'utilisateur (aucune si ``cle`` est vide).

        Ce choix est gardé : la même information sera affichée pour les termes suivants.
        """
        self._voulu = cle if cle in self.colonnes else ""
        self._montrer(self._voulu)

    def _montrer(self, cle: str) -> None:
        self.detail = cle if self.entree is not None and cle in self.colonnes else ""
        self.roue.choisir(self.detail)
        if not self.detail:
            self._composer_l_invite()
            self.pile.setCurrentWidget(self.invite)
        else:
            detail = PAR_CLE[self.detail]
            disponible, elements = self.etats()[self.detail]
            self.medaillon.setPixmap(medaillon(detail, 24, disponible))
            if self.detail == "expressions":
                # La liste porte son propre titre : « Expressions avec « contrat » », « Autres résultats pour… ».
                titre = self.colonne_expressions.titre or self._libelle_des_autres[0]
            else:
                titre = detail.titre
            self.titre_du_detail.definir_texte(titre)
            self.nombre.setText(nombre(elements))
            self.nombre.setVisible(elements > 0)
            self.pages.setCurrentWidget(self._pages[self.detail])
            self._defilements[self.detail].revenir_en_haut()
            self.pile.setCurrentWidget(self.vue)
        self.detail_change.emit(self.detail)

    def _composer_l_invite(self) -> None:
        """L'invitation nomme les informations que le glossaire renseigne pour ce terme."""
        noms = {detail.cle: detail.titre for detail in DETAILS} | {"expressions": self._libelle_des_autres[0]}
        renseignes = [noms[cle].lower() for cle in self.renseignes()]
        if renseignes:
            self.invite.definir("Plus de détails sur ce terme",
                                "Cliquez sur un cercle coloré : " + ", ".join(renseignes) + ".")
        else:
            self.invite.definir("Le glossaire ne donne que l’équivalent de ce terme",
                                "Il n’a pour lui ni définition, ni phrase d’exemple, ni référence.")

    # ------------------------------------------------------------------ mise en place
    def _ajuster_le_menu(self) -> None:
        largeur = round(self.width() * self.PART_DU_MENU)
        self._menu.setFixedWidth(min(max(largeur, self.LARGEUR_MINIMALE_DU_MENU), self.LARGEUR_MAXIMALE_DU_MENU))
        # Le titre prend la largeur de son texte, une fois le style de la fenêtre appliqué.
        self.titre.ensurePolished()
        self.titre.adjustSize()

    def resizeEvent(self, evenement) -> None:  # noqa: N802 (nom imposé par Qt)
        super().resizeEvent(evenement)
        self._ajuster_le_menu()

    def showEvent(self, evenement) -> None:  # noqa: N802
        super().showEvent(evenement)
        self._ajuster_le_menu()

    def paintEvent(self, evenement) -> None:  # noqa: N802
        super().paintEvent(evenement)
        peintre = QPainter(self)
        peintre.setPen(QColor(theme.FILET_DOUX))
        peintre.drawLine(self._menu.width(), 0, self._menu.width(), self.height())


__all__ = ["CLES", "DETAILS", "PAR_CLE", "BoutonDetail", "Detail", "Invite", "PanneauDetails", "RoueDesDetails",
           "medaillon"]
