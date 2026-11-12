"""Couleurs et feuille de style de l'interface, reprises de la maquette."""

MARINE = "#0B1B3A"
BLEU = "#2459D6"
BLEU_FONCE = "#1C47B3"
BLEU_PALE = "#EEF4FF"
AMBRE = "#B45309"
VERT = "#15803D"
TEXTE = "#0F172A"
TEXTE_2 = "#475569"
TEXTE_3 = "#64748B"
TEXTE_4 = "#94A3B8"
FILET = "#E2E8F0"
FOND = "#F3F5F9"

#: Hauteur des puces, en pixels. Le rayon des angles ne doit pas dépasser la
#: moitié de la hauteur, sinon Qt dessine des angles droits.
HAUTEUR_PUCE = 28
#: Taille des caractères et marge intérieure horizontale des puces, en pixels.
TAILLE_PUCE = 13
MARGE_PUCE = 12

FEUILLE_DE_STYLE = f"""
#centre {{ background: {FOND}; }}
#centre QLabel {{ color: {TEXTE}; font-size: 14px; background: transparent; }}

/* ---------- Barre d'outils : sens de traduction, glossaire ---------- */
#barreOutils {{ background: #FFFFFF; border: none; border-bottom: 1px solid {FILET}; }}
#pastilleLangue {{ background: #FFFFFF; border: 1px solid #D5DCE8; border-radius: 10px; }}
#centre QLabel[classe="codeLangue"] {{
    background: {BLEU_PALE}; color: {BLEU_FONCE}; border-radius: 6px;
    font-size: 11px; font-weight: 700; padding: 2px 6px;
}}
#centre QLabel[classe="legende"] {{ color: {TEXTE_4}; font-size: 10px; font-weight: 600; }}
#centre QLabel[classe="nomLangue"] {{ font-size: 15px; font-weight: 600; }}
#boutonInverser {{ background: {BLEU_PALE}; border: 1px solid #C7D7FB; border-radius: 18px; }}
#boutonInverser:hover {{ background: #DCE8FF; }}
#boutonInverser:pressed {{ background: #C7D7FB; }}
#boutonGlossaire {{
    background: #FFFFFF; color: {TEXTE}; border: 1px solid #D5DCE8; border-radius: 10px;
    padding: 0 14px; font-size: 13px; font-weight: 600;
}}
#boutonGlossaire:hover {{ background: #F8FAFC; border-color: #B8C4D6; }}
#boutonGlossaire:pressed {{ background: #EEF2F7; }}

/* ---------- Barre de recherche ---------- */
#barreRecherche {{ background: #FFFFFF; border: 2px solid {BLEU}; border-radius: 14px; }}
#champRecherche {{
    background: transparent; border: none; color: {TEXTE}; font-size: 20px;
    selection-background-color: {BLEU}; selection-color: #FFFFFF;
}}
#boutonRechercher {{
    background: {BLEU}; color: #FFFFFF; border: none; border-radius: 10px;
    padding: 0 22px; font-size: 15px; font-weight: 600;
}}
#boutonRechercher:hover {{ background: {BLEU_FONCE}; }}
#boutonRechercher:pressed {{ background: #163A94; }}
#centre QLabel[classe="resultats"] {{ color: {TEXTE_3}; font-size: 13px; }}

/* ---------- Puces ---------- */
QPushButton[classe="puce"] {{
    background: #FFFFFF; color: #334155; border: 1px solid #D5DCE8; border-radius: 13px;
    padding: 0 {MARGE_PUCE}px; font-size: {TAILLE_PUCE}px;
}}
QPushButton[classe="puce"]:hover {{ background: {BLEU_PALE}; border-color: #A9C1F5; color: {BLEU_FONCE}; }}
QPushButton[classe="puce"]:checked {{
    background: {BLEU}; border-color: {BLEU}; color: #FFFFFF; font-weight: 600;
}}
QPushButton[classe="puceGrise"] {{
    background: #F1F5F9; color: {BLEU_FONCE}; border: 1px solid {FILET}; border-radius: 13px;
    padding: 0 {MARGE_PUCE}px; font-size: {TAILLE_PUCE}px;
}}
QPushButton[classe="puceGrise"]:hover {{ background: {BLEU_PALE}; border-color: #A9C1F5; color: {BLEU_FONCE}; }}
#centre QLabel[classe="puceFixe"] {{
    background: #F1F5F9; color: #334155; border: 1px solid {FILET}; border-radius: 13px;
    padding: 0 {MARGE_PUCE}px; font-size: {TAILLE_PUCE}px;
}}

/* ---------- Enchaînement : Terme > Définition > Équivalent > Contextualisation > Ressources ---------- */
#centre QLabel[classe="numero"] {{
    background: {BLEU}; color: #FFFFFF; border-radius: 13px; font-size: 13px; font-weight: 700;
}}
#centre QLabel[classe="titreCarte"] {{ color: {MARINE}; font-size: 16px; font-weight: 700; }}

/* ---------- Cartes ---------- */
#carte {{ background: #FFFFFF; border: 1px solid {FILET}; border-radius: 14px; }}
#carte[accent="true"] {{ border: 2px solid {BLEU}; }}
#piedCarte {{ background: transparent; border: none; border-top: 1px solid {FILET}; }}
#panneau {{ background: #F4F6FA; border: none; border-radius: 10px; }}
#panneau[accent="true"] {{ background: {BLEU_PALE}; }}
#exemple {{ background: #FBFCFE; border: 1px solid {FILET}; border-radius: 10px; }}
#ligneExpression {{ background: transparent; border: none; border-bottom: 1px solid #EEF2F7; }}
#ligneExpression:hover {{ background: #F5F8FF; }}
#separateur {{ background: {FILET}; border: none; }}
#vignette {{ background: {BLEU_PALE}; border: none; border-radius: 8px; }}

#centre QLabel[classe="legendeLangue"] {{ color: {TEXTE_3}; font-size: 13px; }}
#centre QLabel[classe="terme"] {{ color: {MARINE}; font-weight: 700; }}
#centre QLabel[classe="equivalent"] {{ color: {BLEU_FONCE}; font-weight: 700; }}
#centre QLabel[classe="categorie"] {{ color: {TEXTE_2}; font-size: 14px; }}
#centre QLabel[classe="rubrique"] {{ color: {TEXTE_4}; font-size: 11px; font-weight: 700; }}
#centre QLabel[classe="texte"] {{ color: {TEXTE}; font-size: 15px; }}
#centre QLabel[classe="texteArabe"] {{ color: {TEXTE}; font-size: 17px; }}
#centre QLabel[classe="expression"] {{ color: {TEXTE}; font-size: 14px; }}
#centre QLabel[classe="expressionArabe"] {{ color: {TEXTE}; font-size: 16px; }}
#centre QLabel[classe="sourceExemple"] {{
    background: #EEF2F7; color: {TEXTE_2}; border-radius: 9px;
    font-size: 11px; font-weight: 600; padding: 3px 9px;
}}
#centre QLabel[classe="ressource"] {{ color: {TEXTE_2}; font-size: 13px; }}
#centre QLabel[classe="ressourceArabe"] {{ color: {TEXTE_2}; font-size: 15px; }}
#centre QLabel[classe="discret"] {{ color: {TEXTE_3}; font-size: 13px; }}
#centre QLabel[classe="pied"] {{ color: {TEXTE_3}; font-size: 12px; }}
QPushButton[classe="lien"] {{
    background: transparent; border: none; color: {BLEU_FONCE};
    font-size: 13px; font-weight: 600; text-align: left; padding: 2px 0;
}}
QPushButton[classe="lien"]:hover {{ color: {BLEU}; text-decoration: underline; }}
QPushButton[classe="lien"]:disabled {{ color: {TEXTE_4}; }}

/* ---------- Zones défilantes ---------- */
QScrollArea#corpsCarte, QScrollArea#defilementCartes {{ background: transparent; border: none; }}
QWidget#contenuCarte, QWidget#rangeeCartes {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar[inactive="true"]::handle:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 4px 0 0 0; }}
QScrollBar::handle:horizontal {{ background: #CBD5E1; border-radius: 4px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: #94A3B8; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* ---------- Barre d'état ---------- */
QStatusBar {{ background: #FFFFFF; color: {TEXTE_2}; border-top: 1px solid {FILET}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {TEXTE_3}; font-size: 12px; padding: 0 6px; }}
"""

#: Liste des suggestions qui s'ouvre sous la barre de recherche pendant la saisie.
STYLE_DES_SUGGESTIONS = f"""
QAbstractItemView {{
    background: #FFFFFF; color: {TEXTE}; border: 1px solid #D5DCE8;
    font-size: 15px; padding: 4px; outline: 0;
}}
QAbstractItemView::item {{ padding: 6px 10px; border: none; }}
QAbstractItemView::item:selected, QAbstractItemView::item:hover {{ background: {BLEU_PALE}; color: {BLEU_FONCE}; }}
"""
