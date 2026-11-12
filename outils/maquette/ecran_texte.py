"""Écran 2 de la proposition : traduction d'un texte."""
from __future__ import annotations

from kit import (
    AMBRE,
    AMBRE_50,
    AMBRE_200,
    BAS,
    BLEU,
    BLEU_FONCE,
    CY,
    FILET,
    FILET_DOUX,
    GRIS_50,
    GRIS_100,
    SURFACE,
    T2,
    T3,
    T4,
    X0,
    X1,
    Dessin,
    abreger,
    abreger_debut,
    barre_d_etat,
    barre_d_outils,
    bouton,
    capitales,
    couper,
    couper_riche,
    entete,
    fenetre,
    fin_fenetre,
    numero,
    pastille,
)
from mesure import largeur

from traducteur.glossaire import Glossaire
from traducteur.interface.texte import EXEMPLES
from traducteur.langues import FR
from traducteur.traduction import SOURCE, TERME, Traducteur

NOTES = """
  PROPOSITION DE NOUVELLE INTERFACE — Traducteur juridique français ⇄ arabe
  Écran 2 / 2 : TRADUCTION D'UN TEXTE

  Zone du texte source et zone de la traduction, puis les cinq étapes du traitement :
    Segmentation en phrases → Découpage en mots → Recherche dans le CSV → Règles linguistiques → Reconstruction
  En bas, les termes du glossaire relevés dans le texte reprennent l'enchaînement de l'écran 1, en colonnes :
    1 Terme → 2 Définition → 3 Équivalent → 4 Contextualisation → 5 Ressources

  Le texte, sa traduction et le tableau sont ceux que l'application produit avec le glossaire fourni
  (texte d'exemple : articles 106 et 107 du Code civil, suivis d'une phrase d'essai).

  Notes techniques
  - SVG 1.1 autonome : aucune police, image ou feuille de style externe.
  - Les textes restent des textes. Les retours à la ligne des paragraphes sont fixes (une balise <text> par ligne).
  - Police : Segoe UI (Windows). Les largeurs ont été calculées avec Selawik, de mêmes dimensions.
  - Texte arabe : chaque ligne est ancrée par son bord droit (text-anchor="end") et placée entre les marques
    U+202B et U+202C pour que la ponctuation et les mots latins se rangent de droite à gauche.
  - Dans les deux zones de texte : en bleu, les termes du glossaire ; en gris italique, les mots absents du glossaire.
  - Couleurs : texte #101828 / #344054 / #667085 / #98A2B3 · bleu #2251CC / #1A3FA6 · teintes #F1F5FF /
    #DFE8FF · filets #E1E6EE / #EDF0F5 · fond #F4F6F9 · ambre #B54708 / #FFFAEB / #FEDF89.
"""

STYLE_TERME = {"couleur": BLEU}
STYLE_ABSENT = {"couleur": T4, "style": "italic"}
EN_EVIDENCE = {"poids": 600, "couleur": BLEU_FONCE}
#: Colonnes du tableau : 224 · 340 · 208 · 320 · 300
COLONNES = [X0, 288, 628, 836, 1156, X1]
ETAPES = ["Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
MILIEU = (X0 + X1) / 2
HAUT, SOUS_ENTETE, PIED, FOND_ZONES = 176, 216, 428, 472
HAUT_ETAPES = 488
HAUT_TABLEAU = 548
FOND_TABLEAU = BAS - 26 - 16

#: Passages montrés dans la colonne « Contextualisation » : (début, terme, fin) en français, puis en arabe.
#: En arabe, les points de suspension sont écrits avec trois points : ce signe est dans toutes les polices arabes.
PASSAGES = {
    "contrat": (("Le ", "contrat", " fait la loi des parties."), ("", "العقد", " شريعة المتعاقدين.")),
    "loi": (("… pour les causes prévues par la ", "loi", "."), ("... للأسباب التي يقررها ", "القانون", ".")),
    "partie": (("Le contrat fait la loi des ", "parties", "."), ("العقد شريعة المتعاقدين.", "", "")),
    "consentement": (("… ni modifié que de leur ", "consentement", " mutuel…"),
                     ("... ولا تعديله إلا باتفاق الطرفين...", "", "")),
    "cause": (("… ou pour les ", "causes", " prévues par la loi."), ("... أو ", "للأسباب", " التي يقررها القانون.")),
}


def segments_source(traduction) -> list[list[tuple[str, dict]]]:
    """Le texte source, paragraphe par paragraphe, les termes du glossaire en bleu."""
    texte, segments, position = traduction.texte_source, [], 0
    for occurrence in sorted(traduction.occurrences, key=lambda o: o.debut):
        if occurrence.debut > position:
            segments.append((texte[position:occurrence.debut], {}))
        segments.append((texte[occurrence.debut:occurrence.fin], STYLE_TERME))
        position = occurrence.fin
    segments.append((texte[position:], {}))
    return _paragraphes(segments)


def segments_cible(traduction) -> list[list[tuple[str, dict]]]:
    styles = {TERME: STYLE_TERME, SOURCE: STYLE_ABSENT}
    return _paragraphes([(morceau.texte, styles.get(morceau.nature, {})) for morceau in traduction.morceaux])


def _paragraphes(segments):
    paragraphes, courant = [], []
    for texte, style in segments:
        morceaux = texte.split("\n")
        for rang, morceau in enumerate(morceaux):
            if rang:
                paragraphes.append(courant)
                courant = []
            if morceau:
                courant.append((morceau, style))
    paragraphes.append(courant)
    return paragraphes


def dessiner(glossaire: Glossaire) -> str:
    traduction = Traducteur(glossaire).traduire(EXEMPLES[FR], FR)
    phrases, mots, caracteres = len(traduction.phrases), traduction.mots, len(EXEMPLES[FR])
    phrases_cible, mots_cible, caracteres_cible = traduction.decompte_cible()
    d = Dessin()
    fenetre(d)
    barre_d_outils(d, "texte")

    d.titre("Barre d'outils, à droite : importer, exporter, traduire")
    y = CY + 51
    bouton(d, X1 - 132, y, 132, 38, "Traduire", "primaire", "echange", taille=13.5)
    bouton(d, X1 - 132 - 12 - 116, y, 116, 38, "Exporter", "contour", "exporter")
    bouton(d, X1 - 132 - 24 - 232, y, 116, 38, "Importer", "contour", "importer")
    d.texte(X1 - 132 - 24 - 232 - 16, y + 23.2, "Import : .txt, .docx, .doc · Export : .docx, .txt", taille=12,
            couleur=T3, ancre="end")

    # ------------------------------------------------------------------ les deux zones de texte
    d.titre("Texte source (à gauche) et traduction (à droite)")
    d.rect(X0, HAUT, X1 - X0, FOND_ZONES - HAUT, 12, fill=SURFACE, trait=FILET)
    with d.g(trait=FILET_DOUX):
        d.ligne(X0, SOUS_ENTETE, X1, SOUS_ENTETE, trait=None)
        d.ligne(X0, PIED, X1, PIED, trait=None)
        d.ligne(MILIEU, HAUT, MILIEU, FOND_ZONES, trait=FILET)

    d.c("En-tête de la zone source : langue, fichier importé")
    role = {"dx": 6, "couleur": T3, "taille": 12.5}  # « dx » ajoute 6 px à l'espace qui suit le nom de la langue
    d.texte(X0 + 24, HAUT + 25.2, [("Français", {"poids": 600}), (" texte source", role)], taille=13.5)
    fichier = "articles_106-107.docx"
    large = 10 + 14 + 7 + largeur(fichier, 12) + 10 + 12 + 9
    fx = MILIEU - 24 - large
    d.rect(fx, HAUT + 8, large, 24, 6, fill=GRIS_50, trait=FILET)
    d.icone("document", fx + 9, HAUT + 13, 14, T3, 1.5)
    d.texte(fx + 30, HAUT + 24.2, fichier, taille=12, couleur=T2)
    d.icone("croix", fx + large - 21, HAUT + 14, 12, T4, 1.7)
    d.texte(fx - 10, HAUT + 24.2, "Importé de", taille=12, couleur=T3, ancre="end")

    d.c("En-tête de la zone cible : langue, état de la traduction")
    d.texte(MILIEU + 24, HAUT + 25.6, [("العربية", {"poids": 600, "taille": 15}), (" traduction", role)], arabe=False,
            taille=13.5)
    etat = f"Traduction partielle · {traduction.mots_reconnus} mots sur {mots} trouvés"
    large = 10 + 14 + 7 + largeur(etat, 12, 600) + 16
    ex = X1 - 24 - large
    d.rect(ex, HAUT + 8, large, 24, 12, fill=AMBRE_50, trait=AMBRE_200)
    d.icone("alerte", ex + 9, HAUT + 13, 14, AMBRE, 1.6)
    d.texte(ex + 30, HAUT + 24.2, etat, taille=12, poids=600, couleur=AMBRE)

    d.c("Texte source : les termes du glossaire sont en bleu")
    base = SOUS_ENTETE + 31
    with d.g(taille=15):
        for paragraphe in segments_source(traduction):
            for ligne in couper_riche(paragraphe, MILIEU - X0 - 48 - 14, 15):
                d.texte(X0 + 24, base, ligne)
                base += 26
            base += 8

    d.c("Traduction : termes en bleu ; en gris italique, le mot absent du glossaire, laissé en français")
    base = SOUS_ENTETE + 34
    with d.g(taille=17.5, ancre="end"):
        for paragraphe in segments_cible(traduction):
            for ligne in couper_riche(paragraphe, X1 - MILIEU - 48 - 40, 17.5):
                d.texte(X1 - 24, base, ligne)
                base += 32
            base += 8

    d.c("Pied des deux zones : décomptes, légende, actions")
    with d.g(taille=12, couleur=T3):
        d.texte(X0 + 24, PIED + 26.5, f"{phrases} phrases · {mots} mots · {caracteres} caractères")
        d.texte(MILIEU + 24, PIED + 26.5,
                f"{phrases_cible} phrases · {mots_cible} mots · {caracteres_cible} caractères")
    bouton(d, MILIEU - 24 - 84, PIED + 7, 84, 30, "Effacer", "contour", taille=12.5)
    bouton(d, X1 - 24 - 96, PIED + 7, 96, 30, "Copier", "contour", "copier", taille=12.5)
    legende = [(BLEU, "terme du glossaire"), (T4, "mot absent, à traduire")]
    x = X1 - 24 - 96 - 24 - sum(8 + 7 + largeur(texte, 12) + 18 for _, texte in legende) + 18
    for couleur, texte in legende:
        d.cercle(x + 4, PIED + 22.5, 4, fill=couleur)
        d.texte(x + 15, PIED + 26.5, texte, taille=12, couleur=T3)
        x += 8 + 7 + largeur(texte, 12) + 18

    # ------------------------------------------------------------------ étapes du traitement
    d.titre("Les cinq étapes du traitement, avec leur résultat")
    d.rect(X0, HAUT_ETAPES, X1 - X0, 44, 10, fill=SURFACE, trait=FILET)
    regles = sum(traduction.regles.values())
    etapes = [("Segmentation", f"{phrases} phrases"), ("Découpage", f"{mots} mots"),
              ("Recherche dans le CSV", f"{traduction.mots_reconnus} mots sur {mots}"),
              ("Règles linguistiques", f"{regles} appliquées"), ("Reconstruction", f"{phrases_cible} phrases")]
    # Les étapes occupent leur largeur propre ; l'espace restant est réparti également entre elles.
    larges = [20 + 10 + largeur(nom, 12.5, 600) + 4 + largeur(" " + resultat, 12.5) for nom, resultat in etapes]
    intervalle = (X1 - X0 - 2 * 24 - sum(larges)) / 4
    gauche = X0 + 24
    for rang, (nom, resultat) in enumerate(etapes):
        if rang:
            d.icone("chevron-d", gauche - intervalle / 2 - 7, HAUT_ETAPES + 15, 14, T4, 1.5)
        d.rect(gauche, HAUT_ETAPES + 12, 20, 20, 6, fill=GRIS_100)
        d.texte(gauche + 10, HAUT_ETAPES + 26.2, str(rang + 1), taille=11.5, poids=600, couleur=T2, ancre="middle")
        d.texte(gauche + 30, HAUT_ETAPES + 26.5, [(nom, {"poids": 600}), (" " + resultat, {"dx": 4, "couleur": T3})],
                taille=12.5)
        gauche += larges[rang] + intervalle

    # ------------------------------------------------------------------ tableau des termes
    d.titre("Termes juridiques détectés : l'enchaînement 1 à 5, en colonnes")
    d.brut(f'<clipPath id="c-tableau"><rect x="{X0}" y="{HAUT_TABLEAU}" width="{X1 - X0}" '
           f'height="{FOND_TABLEAU - HAUT_TABLEAU}" rx="12"/></clipPath>')
    d.rect(X0, HAUT_TABLEAU, X1 - X0, FOND_TABLEAU - HAUT_TABLEAU, 12, fill=SURFACE)
    d.brut('<g clip-path="url(#c-tableau)">')
    d.niveau += 1
    titre = "Termes juridiques détectés"
    d.texte(X0 + 24, HAUT_TABLEAU + 26.5, titre, taille=13.5, poids=600)
    fin = X0 + 24 + largeur(titre, 13.5, 600) + 12
    fin += pastille(d, fin, HAUT_TABLEAU + 13, str(len(traduction.termes)))
    d.texte(fin + 12, HAUT_TABLEAU + 26.5, "Cliquez sur un terme pour ouvrir sa fiche", taille=12, couleur=T3)
    d.c("Légende : état de la définition")
    x = X1 - 24
    for icone, couleur, texte in (("document", T3, "Source citée"), ("alerte", AMBRE, "Définition à vérifier")):
        x -= largeur(texte, 12)
        d.texte(x, HAUT_TABLEAU + 26.5, texte, taille=12, couleur=T3)
        x -= 20
        d.icone(icone, x, HAUT_TABLEAU + 15, 14, couleur, 1.6)
        x -= 18

    entete_y = HAUT_TABLEAU + 42
    lignes_y = entete_y + 30
    d.rect(X0, entete_y, X1 - X0, 30, fill=GRIS_50)
    d.rect(COLONNES[2], lignes_y, COLONNES[3] - COLONNES[2], FOND_TABLEAU - lignes_y, fill="#F7F9FF")
    for rang, etape in enumerate(ETAPES):
        gauche = COLONNES[rang] + 24
        numero(d, gauche + 8, entete_y + 15, rang + 1, plein=rang == 2, r=8, taille=10)
        capitales(d, gauche + 23, entete_y + 18.8, etape, couleur=BLEU_FONCE if rang == 2 else T3)
    pas = 62
    with d.g(trait=FILET_DOUX):
        d.ligne(X0, entete_y, X1, entete_y, trait=None)
        d.ligne(X0, lignes_y, X1, lignes_y, trait=None)
        for x in COLONNES[1:5]:
            d.ligne(x, entete_y, x, FOND_TABLEAU, trait=None)
        for rangee in range(1, 5):
            d.ligne(X0, lignes_y + rangee * pas, X1, lignes_y + rangee * pas, trait=None)

    for rangee, detecte in enumerate(traduction.termes[:5]):
        entree, haut = detecte.entree, lignes_y + rangee * pas
        d.c(f"Rangée {rangee + 1} : {entree.terme_fr}")
        # 1 Terme
        x = COLONNES[0] + 24
        d.texte(x, haut + 26, entree.terme_fr, taille=13.5, poids=600, couleur=BLEU_FONCE)
        nombre = len(detecte.occurrences)
        d.texte(x, haut + 45, [(entree.categorie_fr, {"style": "italic"}),
                               f" · {nombre} occurrence{'s' if nombre > 1 else ''}"], taille=11.5, couleur=T3)
        # 2 Définition
        x, droite = COLONNES[1] + 24, COLONNES[2] - 24
        a_verifier = entree.source_definition.startswith("à vérifier")
        d.icone("alerte" if a_verifier else "document", x, haut + 14.5, 14, AMBRE if a_verifier else T3, 1.6)
        lignes = couper(entree.definition_fr, droite - x - 22 - 14, 12.5)
        if len(lignes) > 2:
            lignes = [lignes[0], abreger(" ".join(lignes[1:]), droite - x - 22 - 14, 12.5)]
        with d.g(taille=12.5, couleur=T2):
            for rang, ligne in enumerate(lignes):
                d.texte(x + 22, haut + 26 + rang * 19, ligne)
        # 3 Équivalent
        droite = COLONNES[3] - 24
        d.texte(droite, haut + 29, entree.terme_ar, taille=17, poids=600, couleur=BLEU_FONCE, ancre="end")
        grammaire = entree.categorie_ar + (f"، ج. {entree.pluriel_ar}" if entree.pluriel_ar else "")
        d.texte(droite, haut + 49, grammaire, taille=12.5, couleur=T3, ancre="end")
        # 4 Contextualisation
        x, droite = COLONNES[3] + 24, COLONNES[4] - 24
        (avant, terme, apres), (avant_ar, terme_ar, apres_ar) = PASSAGES[entree.terme_fr]
        d.texte(x, haut + 26, [avant, (terme, EN_EVIDENCE), apres], taille=12.5, couleur=T2)
        passage = [avant_ar] + ([(terme_ar, EN_EVIDENCE)] if terme_ar else []) + [apres_ar]
        d.texte(droite, haut + 48, [partie for partie in passage if partie], taille=14, couleur=T2, ancre="end")
        # 5 Ressources
        x, droite = COLONNES[4] + 24, COLONNES[5] - 24
        titre_ressource, _, detail = entree.ressources[0].partition(", ")
        d.texte(x, haut + 26, titre_ressource, taille=12.5, poids=600)
        autres = len(entree.ressources) - 1
        if autres:
            pastille(d, droite - round(largeur(f"+{autres}", 11, 600) + 12), haut + 13, f"+{autres}")
        d.texte(x, haut + 45, abreger_debut(detail, droite - x - 8, 12), taille=12, couleur=T3)

    d.c("Barre de défilement du tableau")
    d.rect(X1 - 9, lignes_y + 6, 4, 86, 2, fill="#CDD3DD")
    d.niveau -= 1
    d.brut("</g>")
    d.rect(X0, HAUT_TABLEAU, X1 - X0, FOND_TABLEAU - HAUT_TABLEAU, 12, fill="none", trait=FILET)

    barre_d_etat(d, f"Traduction : {traduction.mots_reconnus} mots sur {mots} trouvés dans le glossaire.")
    fin_fenetre(d)
    lignes = entete(
        "Proposition — Écran 2 : traduction d'un texte juridique (français vers arabe)",
        "Fenêtre d'application de bureau, écran Texte. À gauche, le texte source en français ; à droite, sa "
        "traduction en arabe, avec l'état de la traduction. En dessous, une bande résume les cinq étapes du "
        "traitement. En bas, un tableau liste les termes du glossaire relevés dans le texte, avec en colonnes : "
        "terme, définition, équivalent, contextualisation et ressources.", NOTES, d.icones)
    return "\n".join(lignes + d.lignes + ["</svg>", ""])


