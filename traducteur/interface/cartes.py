"""Les cinq champs de l'écran de recherche.

Terme → Définition → Équivalent → Contextualisation → Ressources : chaque
champ est une « carte » (titre numéroté, contenu défilant, pied). Les cartes
reçoivent une entrée du glossaire et le sens de traduction, puis construisent
leur contenu.
"""

from __future__ import annotations

from html import escape

import regex
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..glossaire import Entree, Glossaire
from ..langues import AR, FR, NOM_EN_FRANCAIS, NOM_NATIF, autre_langue, deviner_langue
from ..surlignage import positions_du_terme
from . import icones, theme
from .composants import (
    ESPACE_INVISIBLE,
    MARQUE_RTL,
    DispositionFluide,
    EtiquetteCourte,
    Fleche,
    LigneCliquable,
    TermeAjuste,
    direction,
    etiquette,
    icone_fixe,
    pastille_langue,
    puce,
    puce_fixe,
    separateur,
    vider,
)

#: Largeur minimale d'une carte, en pixels. Les cinq cartes tiennent côte à côte
#: dans une fenêtre de 1 080 pixels de large ; en dessous, la rangée défile.
LARGEUR_MINIMALE = 190

_ADRESSE = regex.compile(r"(?:https?://|www\.)[^\s<>«»]+[^\s<>«».,;:!?)]")


def _tailles_du_terme(terme: str, langue: str) -> tuple[int, int]:
    """Tailles maximale et minimale des caractères d'un terme affiché en grand.

    Les termes longs sont écrits plus petit ; l'arabe est écrit un peu plus
    grand que le français, comme dans la maquette.
    """
    grande, moyenne, petite, minimale = (44, 32, 26, 16) if langue == AR else (36, 27, 22, 13)
    if len(terme) <= 12:
        return grande, minimale
    return (moyenne if len(terme) <= 22 else petite), minimale


def _legende(langue: str, role: str) -> str:
    """« Langue source : français », « اللغة الهدف: العربية »…"""
    if langue == AR:
        return ("اللغة المصدر: " if role == "source" else "اللغة الهدف: ") + NOM_NATIF[AR]
    return f"Langue {role} : {NOM_EN_FRANCAIS[FR]}"


def _categorie(entree: Entree, langue: str) -> str:
    """« nom masculin · pl. contrats » ou « اسم مذكر، ج. عقود »."""
    categorie, pluriel = entree.categorie(langue), entree.pluriel(langue)
    if langue == AR:
        return "، ".join(morceau for morceau in (categorie, f"ج. {pluriel}" if pluriel else "") if morceau)
    return " · ".join(morceau for morceau in (categorie, f"pl. {pluriel}" if pluriel else "") if morceau)


class Carte(QWidget):
    """Un champ de l'enchaînement : titre numéroté, carte au contenu défilant, pied."""

    #: Demande d'ouverture d'une autre entrée du glossaire (clic sur une puce ou une expression).
    entree_demandee = Signal(object)
    #: Message court à afficher dans la barre d'état.
    message = Signal(str)

    numero = 0
    titre = ""
    #: Texte affiché tant qu'aucun terme n'est sélectionné.
    presentation = ""

    def __init__(self, parent: QWidget | None = None, *, derniere: bool = False, accent: bool = False) -> None:
        super().__init__(parent)
        self.glossaire: Glossaire | None = None
        self.entree: Entree | None = None
        self.source = FR

        ensemble = QVBoxLayout(self)
        ensemble.setContentsMargins(0, 0, 0, 0)
        ensemble.setSpacing(10)

        # Titre numéroté, suivi d'une flèche vers le champ suivant.
        en_tete = QHBoxLayout()
        en_tete.setContentsMargins(0, 0, 0, 0)
        en_tete.setSpacing(10)
        numero = QLabel(str(self.numero))
        numero.setProperty("classe", "numero")
        numero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        numero.setFixedSize(26, 26)
        en_tete.addWidget(numero)
        en_tete.addWidget(etiquette(self.titre, "titreCarte"))
        if derniere:
            en_tete.addStretch(1)
        else:
            en_tete.addWidget(Fleche(), 1)
        ensemble.addLayout(en_tete)

        # Carte : contenu défilant et pied.
        self.cadre = QFrame()
        self.cadre.setObjectName("carte")
        self.cadre.setProperty("accent", accent)
        dans_le_cadre = QVBoxLayout(self.cadre)
        bord = 2 if accent else 1
        dans_le_cadre.setContentsMargins(bord, bord, bord, bord)
        dans_le_cadre.setSpacing(0)

        self.defilement = QScrollArea()
        self.defilement.setObjectName("corpsCarte")
        self.defilement.setWidgetResizable(True)
        self.defilement.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # La place de la barre de défilement est toujours réservée : la largeur du
        # contenu ne change pas quand la barre apparaît. Sans rien à faire défiler,
        # son curseur est invisible.
        self.defilement.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.defilement.verticalScrollBar().rangeChanged.connect(self._signaler_le_defilement)
        self._signaler_le_defilement(0, 0)
        contenu = QWidget()
        contenu.setObjectName("contenuCarte")
        self.corps = QVBoxLayout(contenu)
        self.corps.setContentsMargins(16, 16, 6, 12)
        self.corps.setSpacing(10)
        self.defilement.setWidget(contenu)
        dans_le_cadre.addWidget(self.defilement, 1)

        cadre_du_pied = QFrame()
        cadre_du_pied.setObjectName("piedCarte")
        cadre_du_pied.setFixedHeight(44)
        self.pied = QHBoxLayout(cadre_du_pied)
        self.pied.setContentsMargins(16, 0, 16, 0)
        self.pied.setSpacing(8)
        dans_le_cadre.addWidget(cadre_du_pied)

        ensemble.addWidget(self.cadre, 1)
        self.setMinimumWidth(LARGEUR_MINIMALE)
        self.afficher(None, None, FR)

    # ------------------------------------------------------------------ affichage
    def afficher(self, glossaire: Glossaire | None, entree: Entree | None, source: str) -> None:
        """Affiche une entrée du glossaire, ou la présentation du champ si ``entree`` est vide."""
        self.glossaire, self.entree, self.source = glossaire, entree, source
        vider(self.corps)
        vider(self.pied)
        if entree is None:
            self.corps.addWidget(etiquette(self.presentation, "discret", retour_ligne=True))
        else:
            self.remplir(entree, source, autre_langue(source))
        self.corps.addStretch(1)
        self.defilement.verticalScrollBar().setValue(0)

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        """Construit le contenu de la carte (à définir dans chaque carte)."""
        raise NotImplementedError

    def _signaler_le_defilement(self, minimum: int, maximum: int) -> None:
        """Rend le curseur de la barre de défilement visible seulement s'il y a quelque chose à faire défiler."""
        barre = self.defilement.verticalScrollBar()
        inactive = maximum <= minimum
        if barre.property("inactive") != inactive:
            barre.setProperty("inactive", inactive)
            barre.style().unpolish(barre)
            barre.style().polish(barre)
            barre.update()

    # ------------------------------------------------------------------ outils communs
    def _rubrique(self, titre: str) -> None:
        """Petit titre en capitales (« DOMAINE », « SYNONYMES »…)."""
        self.corps.addSpacing(4)
        self.corps.addWidget(etiquette(titre.upper(), "rubrique"))

    def _rangee_de_puces(self, puces: list[QWidget], langue: str = FR) -> None:
        conteneur = QWidget()
        conteneur.setLayoutDirection(direction(langue))
        rangee = DispositionFluide(conteneur, 6, 6)
        for element in puces:
            rangee.addWidget(element)
        self.corps.addWidget(conteneur)

    def _puce_de_terme(self, texte: str, langue: str) -> QWidget:
        """Puce d'un terme : cliquable si ce terme est une autre entrée du glossaire."""
        autre = self._entree_du_terme(texte)
        if autre is None or autre is self.entree:
            return puce_fixe(texte)
        bouton = puce(self.glossaire.libelle(autre, langue), "puceGrise", info="Ouvrir cette entrée du glossaire")
        bouton.clicked.connect(lambda _=False, cible=autre: self.entree_demandee.emit(cible))
        return bouton

    def _entree_du_terme(self, texte: str) -> Entree | None:
        """Entrée du glossaire dont le terme (français ou arabe) est ``texte``."""
        if self.glossaire is None:
            return None
        langue = deviner_langue(texte) or FR
        return self.glossaire.par_terme(texte, langue) or self.glossaire.par_terme(texte, autre_langue(langue))

    def _pied_texte(self, nom_icone: str, texte: str) -> None:
        self.pied.addWidget(icone_fixe(nom_icone, theme.TEXTE_4, 16))
        self.pied.addWidget(EtiquetteCourte(texte, "pied"), 1)

    def _pied_lien(self, texte: str, action, texte_confirme: str) -> QPushButton:
        """Lien du pied de carte ; son libellé confirme brièvement l'action."""
        bouton = QPushButton(texte)
        bouton.setProperty("classe", "lien")
        bouton.setIcon(icones.icone("copier", theme.BLEU_FONCE, 16))
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
        self.pied.addWidget(bouton)
        self.pied.addStretch(1)
        return bouton


class CarteTerme(Carte):
    numero = 1
    titre = "Terme"
    presentation = ("Le terme recherché, avec sa catégorie grammaticale, son domaine, ses synonymes "
                    "et les termes associés.")

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        self.corps.addWidget(_panneau_du_terme(entree, source, "source", "terme", accent=False))

        if entree.domaines:
            self._rubrique("Domaine")
            self._rangee_de_puces([puce_fixe(domaine) for domaine in entree.domaines])
        if entree.synonymes(source):
            self._rubrique("Synonymes")
            self._rangee_de_puces([self._puce_de_synonyme(synonyme, source) for synonyme in entree.synonymes(source)],
                                  source)
        if entree.termes_associes:
            self._rubrique("Termes associés")
            self._rangee_de_puces([self._puce_de_terme(terme, source) for terme in entree.termes_associes], source)

        total = len(self.glossaire) if self.glossaire is not None else entree.numero
        self._pied_texte("tableau", f"Entrée n° {entree.numero} sur {total} du glossaire")

    def _puce_de_synonyme(self, synonyme: str, langue: str) -> QWidget:
        autre = self.glossaire.par_terme(synonyme, langue) if self.glossaire is not None else None
        if autre is None or autre is self.entree:
            return puce_fixe(synonyme)
        bouton = puce(synonyme, "puceGrise", info="Ouvrir cette entrée du glossaire")
        bouton.clicked.connect(lambda _=False, cible=autre: self.entree_demandee.emit(cible))
        return bouton


class CarteDefinition(Carte):
    numero = 2
    titre = "Définition"
    presentation = "La définition du terme dans les deux langues, avec sa source."

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        if not entree.definition_fr and not entree.definition_ar:
            self.corps.addWidget(etiquette("Aucune définition dans le glossaire pour ce terme.", "discret",
                                           retour_ligne=True))
            return
        for rang, langue in enumerate((source, cible)):
            if rang:
                self.corps.addSpacing(4)
                self.corps.addWidget(separateur())
                self.corps.addSpacing(4)
            bloc = QWidget()
            bloc.setLayoutDirection(direction(langue))
            ligne = QHBoxLayout(bloc)
            ligne.setContentsMargins(0, 0, 0, 0)
            ligne.setSpacing(8)
            ligne.addWidget(pastille_langue(langue))
            ligne.addWidget(etiquette(NOM_NATIF[langue], "legendeLangue"))
            ligne.addStretch(1)
            self.corps.addWidget(bloc)
            definition = entree.definition(langue)
            if definition:
                self.corps.addWidget(etiquette(definition, "texteArabe" if langue == AR else "texte", langue,
                                               retour_ligne=True, selectionnable=True))
            else:
                self.corps.addWidget(etiquette(f"Pas de définition en {NOM_EN_FRANCAIS[langue]} dans le glossaire.",
                                               "discret", retour_ligne=True))
        if entree.source_definition:
            self._pied_texte("livre", f"Source : {entree.source_definition}")


class CarteEquivalent(Carte):
    numero = 3
    titre = "Équivalent"
    presentation = ("L'équivalent du terme dans la langue cible et les expressions du glossaire "
                    "qui contiennent ce terme.")

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        self.corps.addWidget(_panneau_du_terme(entree, cible, "cible", "equivalent", accent=True))

        expressions = self.glossaire.expressions(entree, source) if self.glossaire is not None else []
        if expressions:
            self._rubrique("Expressions")
            liste = QVBoxLayout()
            liste.setSpacing(0)
            for expression in expressions:
                # Le français reste à gauche et l'arabe à droite, quel que soit le sens de traduction.
                ligne = LigneCliquable()
                ligne.setToolTip("Ouvrir cette entrée du glossaire")
                ligne.disposition.addWidget(etiquette(expression.terme_fr, "expression", FR, retour_ligne=True), 3)
                ligne.disposition.addWidget(etiquette(expression.terme_ar, "expressionArabe", AR, retour_ligne=True), 2)
                ligne.cliquee.connect(lambda autre=expression: self.entree_demandee.emit(autre))
                liste.addWidget(ligne)
            self.corps.addLayout(liste)

        equivalent = entree.terme(cible)

        def copier() -> None:
            QGuiApplication.clipboard().setText(equivalent)
            self.message.emit(f"Équivalent copié : {equivalent}")

        self._pied_lien("Copier l’équivalent", copier, "Équivalent copié")


class CarteContexte(Carte):
    numero = 4
    titre = "Contextualisation"
    presentation = "Des exemples d'emploi du terme dans les deux langues ; le terme y est mis en évidence."

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        if not entree.contextes:
            self.corps.addWidget(etiquette("Aucun exemple dans le glossaire pour ce terme.", "discret",
                                           retour_ligne=True))
            return
        for contexte in entree.contextes:
            cadre = QFrame()
            cadre.setObjectName("exemple")
            bloc = QVBoxLayout(cadre)
            bloc.setContentsMargins(12, 12, 12, 12)
            bloc.setSpacing(8)
            if contexte.source:
                ligne = QHBoxLayout()
                ligne.addWidget(etiquette(contexte.source, "sourceExemple"))
                ligne.addStretch(1)
                bloc.addLayout(ligne)
            for langue in (source, cible):
                phrase = contexte.texte(langue)
                if phrase:
                    label = etiquette(_phrase_surlignee(phrase, entree, langue),
                                      "texteArabe" if langue == AR else "texte", langue,
                                      retour_ligne=True, selectionnable=True, riche=True)
                    bloc.addWidget(label)
            self.corps.addWidget(cadre)
        nombre = len(entree.contextes)
        self._pied_texte("texte", f"{nombre} exemple{'s' if nombre > 1 else ''} dans le glossaire")


class CarteRessources(Carte):
    numero = 5
    titre = "Ressources"
    presentation = "Les références à consulter et à citer : textes de loi, dictionnaires, sites officiels."

    def remplir(self, entree: Entree, source: str, cible: str) -> None:
        if not entree.ressources:
            self.corps.addWidget(etiquette("Aucune ressource dans le glossaire pour ce terme.", "discret",
                                           retour_ligne=True))
            return
        for rang, ressource in enumerate(entree.ressources):
            if rang:
                self.corps.addWidget(separateur())
            langue = deviner_langue(ressource) or FR
            bloc = QWidget()
            bloc.setLayoutDirection(direction(langue))
            ligne = QHBoxLayout(bloc)
            ligne.setContentsMargins(0, 2, 0, 2)
            ligne.setSpacing(10)
            vignette = QFrame()
            vignette.setObjectName("vignette")
            vignette.setFixedSize(32, 32)
            dans_la_vignette = QHBoxLayout(vignette)
            dans_la_vignette.setContentsMargins(0, 0, 0, 0)
            dans_la_vignette.addWidget(icone_fixe(_icone_de_ressource(ressource), theme.BLEU_FONCE, 18),
                                       0, Qt.AlignmentFlag.AlignCenter)
            ligne.addWidget(vignette, 0, Qt.AlignmentFlag.AlignTop)
            label = etiquette(_ressource_en_html(ressource, langue), "ressourceArabe" if langue == AR else "ressource",
                              langue, retour_ligne=True, riche=True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setOpenExternalLinks(True)
            ligne.addWidget(label, 1)
            self.corps.addWidget(bloc)

        references = "\n".join(entree.ressources)

        def copier() -> None:
            QGuiApplication.clipboard().setText(references)
            self.message.emit("Références copiées dans le presse-papiers")

        self._pied_lien("Copier les références", copier, "Références copiées")


# ---------------------------------------------------------------------- fonctions d'affichage
def _panneau_du_terme(entree: Entree, langue: str, role: str, classe: str, *, accent: bool) -> QFrame:
    """Encadré qui présente un terme en grand : langue, terme, catégorie grammaticale."""
    panneau = QFrame()
    panneau.setObjectName("panneau")
    panneau.setProperty("accent", accent)
    panneau.setLayoutDirection(direction(langue))
    bloc = QVBoxLayout(panneau)
    bloc.setContentsMargins(14, 12, 14, 14)
    bloc.setSpacing(6)

    ligne = QHBoxLayout()
    ligne.setSpacing(8)
    ligne.addWidget(pastille_langue(langue), 0, Qt.AlignmentFlag.AlignTop)
    ligne.addWidget(etiquette(_legende(langue, role), "legendeLangue", langue, retour_ligne=True), 1)
    bloc.addLayout(ligne)

    terme = entree.terme(langue)
    bloc.addWidget(TermeAjuste(terme, classe, langue, *_tailles_du_terme(terme, langue)))

    categorie = _categorie(entree, langue)
    if categorie:
        bloc.addWidget(etiquette(categorie, "categorie", langue, retour_ligne=True))
    return panneau


def _phrase_surlignee(phrase: str, entree: Entree, langue: str) -> str:
    """Phrase d'exemple en HTML, le terme de l'entrée mis en évidence."""
    morceaux, position = [], 0
    for debut, fin in positions_du_terme(phrase, entree, langue):
        morceaux.append(escape(phrase[position:debut]))
        morceaux.append(f'<span style="color: {theme.AMBRE}; font-weight: 600;">{escape(phrase[debut:fin])}</span>')
        position = fin
    morceaux.append(escape(phrase[position:]))
    return _paragraphe("".join(morceaux), langue)


def _paragraphe(html: str, langue: str) -> str:
    if langue == AR:
        return f'<p dir="rtl" align="right" style="margin: 0;">{MARQUE_RTL}{html}</p>'
    return f'<p dir="ltr" align="left" style="margin: 0;">{html}</p>'


def _ressource_en_html(ressource: str, langue: str) -> str:
    """Référence en HTML : première partie en gras, adresses web cliquables."""
    virgule = "،" if langue == AR else ","
    titre, separation, suite = ressource.partition(virgule)
    if not separation or _ADRESSE.search(titre):
        titre, suite = "", ressource
    html = ""
    if titre:
        html += f'<span style="color: {theme.TEXTE}; font-weight: 600;">{escape(titre.strip())}</span><br>'
    html += _avec_liens(suite.strip())
    return _paragraphe(html, langue)


def _avec_liens(texte: str) -> str:
    morceaux, position = [], 0
    for trouve in _ADRESSE.finditer(texte):
        adresse = trouve.group()
        cible = adresse if adresse.startswith("http") else "https://" + adresse
        # Une longue adresse peut passer à la ligne après chaque « / ».
        visible = escape(adresse).replace("/", "/" + ESPACE_INVISIBLE)
        morceaux.append(escape(texte[position:trouve.start()]))
        morceaux.append(f'<a href="{escape(cible, quote=True)}" style="color: {theme.BLEU_FONCE};">{visible}</a>')
        position = trouve.end()
    morceaux.append(escape(texte[position:]))
    return "".join(morceaux)


def _icone_de_ressource(ressource: str) -> str:
    """Choisit l'icône d'une référence d'après les mots qu'elle contient."""
    texte = ressource.casefold()
    if any(mot in texte for mot in ("journal officiel", "joradp", "الجريدة الرسمية")):
        return "fichier"
    if any(mot in texte for mot in ("code", "loi ", "ordonnance", "décret", "القانون", "الأمر", "قانون")):
        return "institution"
    return "livre"
