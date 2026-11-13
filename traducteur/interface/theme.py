"""Couleurs, palette et feuille de style de l'interface.

Les valeurs sont celles de la proposition d'interface (dossier ``maquette/proposition``).
Les tailles de caractères sont données en pixels entiers : les demi-pixels des dessins
(13,5 px, 16,5 px…) sont arrondis.
"""

from PySide6.QtGui import QColor, QPalette

# ------------------------------------------------------------------ couleurs
FOND = "#F4F6F9"
SURFACE = "#FFFFFF"
FILET = "#E1E6EE"
FILET_DOUX = "#EDF0F5"
TEXTE = "#101828"  # texte principal
TEXTE_2 = "#344054"  # texte courant secondaire
TEXTE_3 = "#667085"  # légendes
TEXTE_4 = "#98A2B3"  # texte estompé
BLEU = "#2251CC"
BLEU_FONCE = "#1A3FA6"
BLEU_PRESSE = "#163690"
BLEU_50 = "#F1F5FF"
BLEU_100 = "#DFE8FF"
BLEU_200 = "#C2D3FF"
AMBRE = "#B54708"
AMBRE_50 = "#FFFAEB"
AMBRE_200 = "#FEDF89"
VERT = "#067647"
VERT_50 = "#ECFDF3"
VERT_200 = "#ABEFC6"
VERT_VIF = "#12B76A"
MARINE = "#0F1F3D"
GRIS_50 = "#F7F9FB"
GRIS_100 = "#F0F3F7"
GRIS_200 = "#E6EAF0"
GRIS_300 = "#CDD3DD"
#: Colonne « Équivalent » du tableau des termes : teinte au repos.
TEINTE_TABLEAU = "#F7F9FF"

# ------------------------------------------------------------------ dimensions communes
#: Marge entre le bord de la fenêtre et les panneaux, et marge intérieure des panneaux.
MARGE = 24
#: Rayon des angles des panneaux.
RAYON = 12
#: Largeur réservée à une barre de défilement verticale.
LARGEUR_BARRE = 10
#: Hauteur des puces. Le rayon des angles ne doit pas dépasser la moitié de la hauteur,
#: sinon Qt dessine des angles droits.
HAUTEUR_PUCE = 24


def palette() -> QPalette:
    """Palette claire de l'application : les couleurs ne dépendent pas du thème du système."""
    couleurs = QPalette()
    for role, couleur in (
            (QPalette.ColorRole.Window, FOND),
            (QPalette.ColorRole.WindowText, TEXTE),
            (QPalette.ColorRole.Base, SURFACE),
            (QPalette.ColorRole.AlternateBase, GRIS_50),
            (QPalette.ColorRole.Text, TEXTE),
            (QPalette.ColorRole.Button, SURFACE),
            (QPalette.ColorRole.ButtonText, TEXTE_2),
            (QPalette.ColorRole.BrightText, SURFACE),
            (QPalette.ColorRole.Highlight, BLEU),
            (QPalette.ColorRole.HighlightedText, SURFACE),
            (QPalette.ColorRole.Link, BLEU),
            (QPalette.ColorRole.LinkVisited, BLEU_FONCE),
            (QPalette.ColorRole.ToolTipBase, MARINE),
            (QPalette.ColorRole.ToolTipText, SURFACE),
            (QPalette.ColorRole.PlaceholderText, TEXTE_4),
            (QPalette.ColorRole.Light, SURFACE),
            (QPalette.ColorRole.Midlight, GRIS_100),
            (QPalette.ColorRole.Mid, FILET),
            (QPalette.ColorRole.Dark, GRIS_300),
            (QPalette.ColorRole.Shadow, TEXTE_4)):
        couleurs.setColor(role, QColor(couleur))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        couleurs.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXTE_4))
    return couleurs


def appliquer(application) -> None:
    """Prépare l'application : style « Fusion » de Qt et palette claire.

    L'interface est dessinée par sa feuille de style. Le style « Fusion » lui donne le même
    rendu sur tous les systèmes : les styles propres à Windows ou à macOS dessinent à leur
    façon certains éléments (menus, cadres, barres de défilement).
    """
    application.setStyle("Fusion")
    application.setPalette(palette())


FEUILLE_DE_STYLE = f"""
#centre {{ background: {FOND}; }}
#zoneDefilante {{ background: transparent; border: none; }}
#separateur {{ background: {FILET_DOUX}; border: none; }}
#separateurBleu {{ background: {BLEU_200}; border: none; }}
#filetVertical {{ background: {FILET}; border: none; }}

/* ---------- Barre de menus ; à droite, le glossaire chargé ---------- */
#barreMenus {{ background: {SURFACE}; border: none; border-bottom: 1px solid {FILET}; }}
QMenuBar {{ background: transparent; border: none; color: {TEXTE_2}; font-size: 13px; }}
QMenuBar::item {{ background: transparent; padding: 6px 11px; border-radius: 6px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {GRIS_100}; color: {TEXTE}; }}
QMenu {{
    background: {SURFACE}; color: {TEXTE}; border: 1px solid {FILET}; padding: 6px; font-size: 13px;
}}
QMenu::item {{ background: transparent; padding: 7px 28px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {BLEU_50}; color: {BLEU_FONCE}; }}
QMenu::item:disabled {{ color: {TEXTE_4}; }}
QMenu::separator {{ height: 1px; background: {FILET_DOUX}; margin: 5px 6px; }}
QMenu::indicator {{ width: 14px; height: 14px; margin-left: 6px; }}
#indicateurGlossaire {{
    background: {GRIS_50}; border: 1px solid {FILET}; border-radius: 12px; padding: 0; text-align: left;
}}
#indicateurGlossaire:hover, #indicateurGlossaire:pressed, #indicateurGlossaire:focus {{
    background: {GRIS_100}; border-color: {GRIS_300};
}}
#indicateurGlossaire::menu-indicator {{ image: none; width: 0; height: 0; }}
#pointGlossaire {{ background: {VERT_VIF}; border: none; border-radius: 3px; }}
#pointGlossaire[absent="true"] {{ background: {AMBRE}; }}
QLabel[classe="glossaireNom"] {{ color: {TEXTE}; font-size: 12px; font-weight: 600; }}
QLabel[classe="glossaireDetail"] {{ color: {TEXTE_3}; font-size: 12px; }}

/* ---------- Barre d'outils : écran, sens de traduction ---------- */
#selecteurMode {{ background: {GRIS_200}; border: none; border-radius: 10px; }}
QPushButton[classe="mode"] {{
    background: transparent; border: none; border-radius: 7px;
    color: {TEXTE_3}; font-size: 14px; font-weight: 600; padding: 0 6px;
}}
QPushButton[classe="mode"]:hover {{ color: {TEXTE_2}; }}
QPushButton[classe="mode"]:checked {{ background: {SURFACE}; color: {BLEU_FONCE}; }}
QPushButton[classe="mode"]:focus {{ color: {BLEU_FONCE}; }}
#sens {{ background: {SURFACE}; border: 1px solid {FILET}; border-radius: 10px; }}
QLabel[classe="langueSens"] {{ color: {TEXTE}; font-size: 14px; font-weight: 600; }}
QLabel[classe="langueSens"][arabe="true"] {{ font-size: 16px; }}
#boutonInverser {{
    background: transparent; border: none; border-top-right-radius: 9px; border-bottom-right-radius: 9px;
}}
#boutonInverser:hover, #boutonInverser:focus {{ background: {BLEU_50}; }}
#boutonInverser:pressed {{ background: {BLEU_100}; }}
QLabel[classe="aideOutils"] {{ color: {TEXTE_3}; font-size: 12px; }}

/* ---------- Barre de recherche ---------- */
#champRecherche {{
    background: transparent; border: none; color: {TEXTE}; font-size: 16px; padding: 0;
    selection-background-color: {BLEU}; selection-color: {SURFACE};
}}
QLabel[classe="resumeRecherche"] {{ color: {TEXTE_3}; font-size: 13px; }}
#effacerRecherche {{ background: {GRIS_100}; border: none; border-radius: 9px; }}
#effacerRecherche:hover, #effacerRecherche:focus {{ background: {FILET}; }}

/* ---------- Boutons ---------- */
QPushButton[classe="principal"] {{
    background: {BLEU}; color: {SURFACE}; border: none; border-radius: 8px;
    padding: 0 16px; font-size: 14px; font-weight: 600;
}}
QPushButton[classe="principal"]:hover, QPushButton[classe="principal"]:focus {{ background: {BLEU_FONCE}; }}
QPushButton[classe="principal"]:pressed {{ background: {BLEU_PRESSE}; }}
QPushButton[classe="principal"]:disabled {{ background: {BLEU_200}; }}
QPushButton[classe="contour"] {{
    background: {SURFACE}; color: {TEXTE_2}; border: 1px solid {FILET}; border-radius: 8px;
    padding: 0 14px; font-size: 13px; font-weight: 600;
}}
QPushButton[classe="contour"]:hover {{ background: {GRIS_50}; border-color: {GRIS_300}; }}
QPushButton[classe="contour"]:focus {{ border-color: {BLEU_200}; }}
QPushButton[classe="contour"]:pressed {{ background: {GRIS_100}; }}
QPushButton[classe="contour"]:disabled {{ color: {TEXTE_4}; background: {GRIS_50}; }}
QPushButton[classe="lien"] {{
    background: transparent; border: none; color: {BLEU};
    font-size: 13px; font-weight: 600; text-align: left; padding: 2px 0;
}}
QPushButton[classe="lien"]:hover, QPushButton[classe="lien"]:focus {{
    color: {BLEU_FONCE}; text-decoration: underline;
}}
QPushButton[classe="lien"]:disabled {{ color: {TEXTE_4}; }}
QToolButton[classe="voisine"] {{ background: {SURFACE}; border: 1px solid {FILET}; border-radius: 6px; }}
QToolButton[classe="voisine"]:hover {{ background: {GRIS_50}; border-color: {GRIS_300}; }}
QToolButton[classe="voisine"]:focus {{ border-color: {BLEU_200}; }}
QToolButton[classe="voisine"]:pressed {{ background: {GRIS_100}; }}
QToolButton[classe="voisine"]:disabled {{ background: {GRIS_50}; }}

/* ---------- Puces et pastilles ---------- */
QPushButton[classe="puce"] {{
    background: {BLEU_50}; color: {BLEU_FONCE}; border: 1px solid {BLEU_100}; border-radius: 6px;
    padding: 0 9px; font-size: 13px;
}}
QPushButton[classe="puce"][arabe="true"] {{ font-size: 14px; }}
QPushButton[classe="puce"]:hover, QPushButton[classe="puce"]:focus {{
    background: {BLEU_100}; border-color: {BLEU_200};
}}
QLabel[classe="puceNeutre"] {{
    background: {GRIS_50}; color: {TEXTE_3}; border: 1px solid {FILET}; border-radius: 6px;
    padding: 0 9px; font-size: 13px;
}}
QLabel[classe="puceNeutre"][arabe="true"] {{ font-size: 14px; }}
QPushButton[classe="puceExemple"] {{
    background: {BLEU_50}; color: {BLEU_FONCE}; border: 1px solid {BLEU_100}; border-radius: 8px;
    padding: 0 13px; font-size: 14px;
}}
QPushButton[classe="puceExemple"][arabe="true"] {{ font-size: 16px; }}
QPushButton[classe="puceExemple"]:hover, QPushButton[classe="puceExemple"]:focus {{
    background: {BLEU_100}; border-color: {BLEU_200};
}}
QLabel[classe="pastille"] {{
    background: {GRIS_100}; color: {TEXTE_2}; border-radius: 9px; padding: 0 6px;
    font-size: 11px; font-weight: 600;
}}

/* ---------- Titres et légendes des panneaux ---------- */
QLabel[classe="capitales"] {{ color: {TEXTE_3}; font-size: 11px; font-weight: 600; }}
QLabel[classe="capitalesBleu"] {{ color: {BLEU}; font-size: 11px; font-weight: 600; }}
QLabel[classe="titrePanneau"] {{ color: {TEXTE}; font-size: 14px; font-weight: 600; }}
QLabel[classe="aidePanneau"] {{ color: {TEXTE_3}; font-size: 12px; }}
QLabel[classe="legende"] {{ color: {TEXTE_3}; font-size: 12px; }}
QLabel[classe="discret"] {{ color: {TEXTE_3}; font-size: 13px; }}

/* ---------- Fiche d'un terme ---------- */
#bandeSens {{ background: {GRIS_50}; border: none; border-bottom: 1px solid {FILET_DOUX}; }}
QLabel[classe="alerteSens"] {{ color: {AMBRE}; font-size: 12px; }}
QLabel[classe="terme"] {{ color: {MARINE}; font-weight: 600; }}
QLabel[classe="equivalent"] {{ color: {BLEU_FONCE}; font-weight: 600; }}
QLabel[classe="categorie"] {{ color: {TEXTE_3}; font-size: 13px; }}
QLabel[classe="categorie"][arabe="true"] {{ font-size: 15px; }}
QLabel[classe="grammaire"] {{ color: {TEXTE_2}; font-size: 13px; }}
QLabel[classe="grammaire"][arabe="true"] {{ font-size: 15px; }}
QLabel[classe="domaine"] {{ color: {TEXTE_2}; font-size: 13px; }}
QLabel[classe="langueBloc"] {{ color: {TEXTE_3}; font-size: 13px; }}
QLabel[classe="definition"] {{ color: {TEXTE}; font-size: 14px; }}
QLabel[classe="definition"][arabe="true"] {{ font-size: 17px; }}
QLabel[classe="sourceExemple"] {{
    background: {GRIS_100}; color: {TEXTE_2}; border-radius: 6px; padding: 0 8px; font-size: 12px;
}}
QLabel[classe="ressource"] {{ color: {TEXTE_3}; font-size: 13px; }}
QLabel[classe="ressource"][arabe="true"] {{ font-size: 14px; }}
QLabel[classe="pied"] {{ color: {TEXTE_3}; font-size: 12px; }}
QLabel[classe="piedFort"] {{ color: {TEXTE_2}; font-size: 12px; font-weight: 600; }}
QLabel[classe="piedAlerte"] {{ color: {AMBRE}; font-size: 12px; font-weight: 600; }}
#rondVide {{ background: {GRIS_100}; border: none; border-radius: 20px; }}
QLabel[classe="videTitre"] {{ color: {TEXTE_2}; font-size: 13px; font-weight: 600; }}
QLabel[classe="videTexte"] {{ color: {TEXTE_3}; font-size: 13px; }}

/* ---------- Écran « Terme » sans fiche : accueil, terme introuvable ---------- */
#rondAccueil {{ background: {BLEU_50}; border: 1px solid {BLEU_100}; border-radius: 32px; }}
#rondAccueil[alerte="true"] {{ background: {AMBRE_50}; border-color: {AMBRE_200}; }}
QLabel[classe="accueilTitre"] {{ color: {MARINE}; font-size: 24px; font-weight: 600; }}
QLabel[classe="accueilTexte"] {{ color: {TEXTE_3}; font-size: 14px; }}
QLabel[classe="touche"] {{
    background: {GRIS_50}; color: {TEXTE_2}; border: 1px solid {FILET}; border-radius: 5px;
    padding: 0 6px; font-size: 12px; font-weight: 600;
}}
QLabel[classe="raccourci"] {{ color: {TEXTE_3}; font-size: 13px; }}

/* ---------- Écran « Texte » : zones de texte ---------- */
#zoneTexte {{
    background: transparent; border: none; color: {TEXTE}; font-size: 15px;
    selection-background-color: {BLEU}; selection-color: {SURFACE};
}}
#zoneTexte[arabe="true"] {{ font-size: 18px; }}
QLabel[classe="nomLangue"] {{ color: {TEXTE}; font-size: 14px; font-weight: 600; }}
QLabel[classe="nomLangue"][arabe="true"] {{ font-size: 16px; }}
QLabel[classe="roleZone"] {{ color: {TEXTE_3}; font-size: 13px; }}
QLabel[classe="decompte"] {{ color: {TEXTE_3}; font-size: 12px; }}
#fichierImporte {{ background: {GRIS_50}; border: 1px solid {FILET}; border-radius: 6px; }}
QLabel[classe="nomFichier"] {{ color: {TEXTE_2}; font-size: 12px; }}
#fermerFichier {{ background: transparent; border: none; border-radius: 4px; }}
#fermerFichier:hover, #fermerFichier:focus {{ background: {FILET}; }}

/* ---------- Barres de défilement ---------- */
QScrollBar:vertical {{ background: transparent; width: {LARGEUR_BARRE}px; margin: 4px 3px 4px 3px; }}
QScrollBar::handle:vertical {{ background: {GRIS_300}; border-radius: 2px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXTE_4}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 5px 4px 3px 4px; }}
QScrollBar::handle:horizontal {{ background: {GRIS_300}; border-radius: 2px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: {TEXTE_4}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ---------- Barre d'état ---------- */
#barreEtat {{ background: {SURFACE}; border: none; border-top: 1px solid {FILET}; }}
QLabel[classe="etat"] {{ color: {TEXTE_3}; font-size: 12px; }}

/* ---------- Infobulles ---------- */
QToolTip {{
    background: {MARINE}; color: {SURFACE}; border: 1px solid {MARINE}; padding: 4px 6px; font-size: 12px;
}}
"""

#: Liste des suggestions qui s'ouvre sous la barre de recherche pendant la saisie.
STYLE_DES_SUGGESTIONS = f"""
QAbstractItemView {{
    background: {SURFACE}; color: {TEXTE}; border: 1px solid {FILET};
    font-size: 15px; padding: 4px; outline: 0;
}}
QAbstractItemView::item {{ padding: 6px 10px; border: none; border-radius: 6px; }}
QAbstractItemView::item:selected, QAbstractItemView::item:hover {{ background: {BLEU_50}; color: {BLEU_FONCE}; }}
"""

#: Boîtes de message et fenêtres d'aide.
STYLE_DES_BOITES = f"""
#boite {{ background: {SURFACE}; }}
#rondBoite {{ background: {BLEU_50}; border: 1px solid {BLEU_100}; border-radius: 20px; }}
#rondBoite[alerte="true"] {{ background: {AMBRE_50}; border-color: {AMBRE_200}; }}
QLabel[classe="boiteTitre"] {{ color: {TEXTE}; font-size: 16px; font-weight: 600; }}
QLabel[classe="boiteTexte"] {{ color: {TEXTE_2}; font-size: 14px; }}
#piedBoite {{ background: {GRIS_50}; border: none; border-top: 1px solid {FILET_DOUX}; }}
"""
