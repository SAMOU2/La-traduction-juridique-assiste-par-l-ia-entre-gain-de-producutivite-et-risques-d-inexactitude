"""Écran « Terme » de la proposition : fiche d'un terme, et états sans fiche (accueil, terme introuvable)."""
from __future__ import annotations

from kit import (
    AMBRE,
    AMBRE_50,
    AMBRE_200,
    BAS,
    BLEU,
    BLEU_50,
    BLEU_100,
    BLEU_200,
    BLEU_FONCE,
    CY,
    FILET,
    FILET_DOUX,
    GRIS_50,
    GRIS_100,
    MARINE,
    SURFACE,
    T1,
    T2,
    T3,
    T4,
    X0,
    X1,
    Dessin,
    abreger_lettres,
    barre_d_etat,
    barre_d_outils,
    bouton,
    capitales,
    couper_net,
    couper_riche_net,
    entete,
    fenetre,
    fin_fenetre,
    numero,
    pastille,
    puce,
)
from mesure import est_arabe, largeur

from traducteur.glossaire import Glossaire
from traducteur.langues import FR, cle_stricte

NOTES = """
  PROPOSITION DE NOUVELLE INTERFACE — Traducteur juridique français ⇄ arabe
  Écran « Terme » : {sujet}

  Enchaînement affiché (cinq champs côte à côte, dans une seule fiche) :
    1 Terme → 2 Définition → 3 Équivalent → 4 Contextualisation → 5 Ressources
{contenu}

  Notes techniques
  - SVG 1.1 autonome : aucune police, image ou feuille de style externe.
  - Les textes restent des textes (modifiables dans un éditeur de code ou un éditeur vectoriel).
  - Police : Segoe UI (Windows). Les largeurs ont été calculées avec Selawik, de mêmes dimensions.
  - Texte arabe : chaque ligne est ancrée par son bord droit (text-anchor="end") ou centrée, et placée
    entre les marques U+202B et U+202C pour que la ponctuation et les mots latins se rangent
    de droite à gauche.
  - Couleurs : texte #101828 / #344054 / #667085 / #98A2B3 · bleu #2251CC / #1A3FA6 · teintes #F1F5FF /
    #DFE8FF · filets #E1E6EE / #EDF0F5 · fond #F4F6F9 · marine #0F1F3D · ambre #B54708 / #FFFAEB / #FEDF89.
"""

EN_EVIDENCE = {"poids": 600, "couleur": BLEU_FONCE}
COLONNES = [X0, 336, 628, 892, 1184, X1]  # largeurs : 272 · 292 · 264 · 292 · 272
ETAPES = ["Terme", "Définition", "Équivalent", "Contextualisation", "Ressources"]
HAUT = 176  # haut de la fiche
ENTETE, CORPS, PIED = 50, 336, 44  # hauteurs de l'en-tête, du corps et du pied de la fiche
FOND_PAGE = BAS - 26 - 16  # bas de la zone des panneaux


def recherche(d: Dessin, debut: float, texte: str, resume: str, focus: bool = True) -> None:
    """La barre de recherche, à droite du sens de traduction."""
    d.titre("Barre de recherche")
    y, large = CY + 48, X1 - debut
    if focus:
        d.rect(debut - 3, y - 3, large + 6, 50, 13, fill=BLEU_100)
    d.rect(debut, y, large, 44, 10, fill=SURFACE, trait=BLEU if focus else FILET, epaisseur=1.5 if focus else None)
    d.icone("loupe", debut + 14, y + 13, 18, T3, 1.5)
    bx = X1 - 6 - 112
    bouton(d, bx, y + 5, 112, 34, "Rechercher", "primaire", taille=13.5)
    if not texte:
        d.texte(debut + 44, y + 27.6, "Saisir un terme juridique, en français ou en arabe…", taille=16, couleur=T4)
        curseur = debut + 41.5
    else:
        d.texte(debut + 44, y + 27.6, texte, taille=16)
        curseur = debut + 44 + largeur(texte, 16) + 2.5
        d.cercle(bx - 24, y + 22, 9, fill=GRIS_100)
        d.icone("croix", bx - 29.5, y + 16.5, 11, T3, 1.8)
        d.texte(bx - 48, y + 26.4, resume, taille=12.5, couleur=T3, ancre="end")
    if focus:
        d.ligne(curseur, y + 12, curseur, y + 32, trait=T1, epaisseur=1.2)


def en_tete_des_etapes(d: Dessin, haut: float, legendes: list[str] | None = None) -> None:
    """Les cinq étapes de l'enchaînement, reliées par des flèches."""
    milieu = haut + ENTETE / 2
    for rang, etape in enumerate(ETAPES):
        gauche = COLONNES[rang] + 24
        numero(d, gauche + 11, milieu, rang + 1, plein=rang == 2)
        d.texte(gauche + 31, milieu + 4.8, etape, taille=13.5, poids=600, couleur=BLEU_FONCE if rang == 2 else T1)
        if legendes:
            d.texte(gauche + 31, milieu + 25, legendes[rang], taille=12, couleur=T3)
        if rang < 4:
            debut = gauche + 31 + largeur(etape, 13.5, 600) + 14
            fin = COLONNES[rang + 1] + 24 - 14
            d.chemin(f"M{debut:.1f} {milieu}H{fin}M{fin - 4.5} {milieu - 4}l4.5 4-4.5 4", fill="none", trait="#CBD3DF",
                     epaisseur=1.25, stroke_linecap="round", stroke_linejoin="round")


def dessiner(glossaire: Glossaire, requete: str, sens: int = 0) -> str:
    """Fiche du terme cherché. ``sens`` : rang de l'entrée affichée quand le terme a plusieurs sens."""
    resultats = glossaire.chercher(requete, FR)
    exacts = [entree for entree in resultats if cle_stricte(entree.terme_fr) == cle_stricte(requete)]
    entree = exacts[sens]
    autres = [resultat for resultat in resultats if resultat not in exacts]
    expressions = glossaire.expressions(entree, FR)
    que_des_expressions = all(autre in expressions for autre in autres)
    plusieurs_sens = len(exacts) > 1
    if plusieurs_sens:
        resume = f"{len(exacts)} sens · {len(autres)} résultats proches"
    else:
        resume = f"1 terme · {len(autres)} expressions"

    d = Dessin()
    fenetre(d)
    recherche(d, barre_d_outils(d, "terme"), requete, resume)

    onglets = 38 if plusieurs_sens else 0
    sous_entete = HAUT + onglets + ENTETE
    pied = sous_entete + CORPS
    fond = pied + PIED
    base_pied = pied + 26.5
    haut_corps = sous_entete + 26  # première ligne de base des champs

    # ------------------------------------------------------------------ fiche
    d.titre("Fiche du terme : les cinq champs de l'enchaînement")
    d.brut(f'<clipPath id="c-fiche"><rect x="{X0}" y="{HAUT}" width="{X1 - X0}" height="{fond - HAUT}" rx="12"/>'
           "</clipPath>")
    d.rect(X0, HAUT, X1 - X0, fond - HAUT, 12, fill=SURFACE)
    d.brut('<g clip-path="url(#c-fiche)">')
    d.niveau += 1
    if plusieurs_sens:
        d.c("Le terme a plusieurs sens : un onglet par entrée du glossaire")
        d.rect(X0, HAUT, X1 - X0, onglets, fill=GRIS_50)
        x = X0 + 16
        for rang, exact in enumerate(exacts):
            choisi = rang == sens
            # Trois parties : numéro du sens, équivalent, domaine. « dx » ajoute 5 px à l'espace qui les sépare.
            parties = [(f"Sens {rang + 1} ", {"poids": 600, "couleur": T1 if choisi else T3}),
                       (exact.terme_ar, {"dx": 5, "poids": 600, "taille": 14.5,
                                         "couleur": BLEU_FONCE if choisi else T2}),
                       (f" {exact.domaines[0]}", {"dx": 5, "couleur": T3})]
            large = (12 + largeur(f"Sens {rang + 1} ", 12.5, 600) + 5 + largeur(exact.terme_ar, 14.5, 600) + 5
                     + largeur(f" {exact.domaines[0]}", 12.5) + 12)
            if choisi:
                d.rect(x, HAUT + 6, large, 26, 7, fill=SURFACE, trait=BLEU_200)
            d.texte(x + 12, HAUT + 23.6, parties, arabe=False, taille=12.5)
            x += large + 6
        note = f"« {requete} » a {len(exacts)} sens dans le glossaire : choisissez celui qui convient au texte."
        d.texte(X1 - 24, HAUT + 23.4, note, taille=12, couleur=AMBRE, ancre="end")
        d.icone("alerte", X1 - 24 - largeur(note, 12) - 21, HAUT + 12, 14, AMBRE, 1.6)
        d.ligne(X0, HAUT + onglets, X1, HAUT + onglets)

    d.c("Le champ 3 (équivalent) est mis en avant : fond teinté, filet bleu en haut")
    d.rect(COLONNES[2], HAUT + onglets, COLONNES[3] - COLONNES[2], fond - HAUT - onglets, fill=BLEU_50)
    d.rect(COLONNES[2], HAUT + onglets, COLONNES[3] - COLONNES[2], 3, fill=BLEU)
    with d.g(trait=FILET_DOUX):
        d.ligne(X0, sous_entete, X1, sous_entete, trait=None)
        d.ligne(X0, pied, X1, pied, trait=None)
        for x in COLONNES[1:5]:
            d.ligne(x, sous_entete, x, fond, trait=BLEU_100 if x in COLONNES[2:4] else None)
    d.c("En-tête : les cinq étapes, reliées par des flèches")
    en_tete_des_etapes(d, HAUT + onglets)

    # --- 1 Terme
    d.titre("1 · Terme")
    x, droite = COLONNES[0] + 24, COLONNES[1] - 24
    capitales(d, x, haut_corps, "Français · source")
    d.texte(x, haut_corps + 42, entree.terme_fr, taille=34, poids=600, couleur=MARINE, espacement=-0.4)
    d.texte(x, haut_corps + 67, [(entree.categorie_fr, {"style": "italic"}), f" · pl. {entree.pluriel_fr}"],
            taille=12.5, couleur=T3)
    base = haut_corps + 102
    capitales(d, x, base, "Domaine")
    d.texte(x, base + 21, " › ".join(entree.domaines), taille=13, couleur=T2)
    base += 52
    for titre, termes in (("Synonyme" + ("s" if len(entree.synonymes_fr) > 1 else ""), entree.synonymes_fr),
                          ("Termes associés", entree.termes_associes)):
        if not termes:
            continue
        capitales(d, x, base, titre)
        px, py = x, base + 10
        for terme in termes:
            connu = glossaire.par_terme(terme, FR) is not None
            if px > x and px + round(largeur(terme, 12.5) + 20) > droite:
                px, py = x, py + 30
            px += puce(d, px, py, terme, "lien" if connu else "neutre") + 6
        base = py + 24 + 28
    d.c("Pied : numéro de l'entrée et passage à l'entrée voisine")
    d.icone("fiche", x, base_pied - 12.5, 16, T3)
    d.texte(x + 23, base_pied, f"Entrée {entree.numero} sur 1 000", taille=12, couleur=T3)
    for decalage, icone, actif in ((56, "chevron-g", entree.numero > 1), (26, "chevron-d", True)):
        d.rect(droite - decalage, pied + 9, 26, 26, 6, fill=SURFACE, trait=FILET)
        d.icone(icone, droite - decalage + 7, pied + 16, 12, T2 if actif else T4, 1.7)

    # --- 2 Définition
    d.titre("2 · Définition (français, puis arabe)")
    x, droite = COLONNES[1] + 24, COLONNES[2] - 24
    capitales(d, x, haut_corps, "Français")
    base = haut_corps + 24
    with d.g(taille=14):
        for ligne in couper_net(entree.definition_fr, droite - x - 6, 14):
            d.texte(x, base, ligne)
            base += 22
    d.ligne(x, base, droite, base)
    d.texte(droite, base + 23, "العربية", taille=12.5, couleur=T3, ancre="end")
    base += 53
    with d.g(taille=16.5, ancre="end"):
        for ligne in couper_net(entree.definition_ar, droite - x - 16, 16.5):
            d.texte(droite, base, ligne)
            base += 30
    d.c("Pied : source de la définition, toujours affichée en entier")
    if entree.source_definition.startswith("à vérifier"):
        detail = entree.source_definition.partition("(")[2].rstrip(")")
        d.icone("alerte", x, base_pied - 12.5, 16, AMBRE, 1.6)
        d.texte(x + 23, base_pied,
                [("À vérifier", {"poids": 600, "couleur": AMBRE}), (f" · {detail}", {"couleur": T3})], taille=12)
    else:
        d.icone("document", x, base_pied - 12.5, 16, T3)
        d.texte(x + 23, base_pied, [("Source : ", {"couleur": T3}), (entree.source_definition, {"poids": 600})],
                taille=12, couleur=T2)

    # --- 3 Équivalent
    d.titre("3 · Équivalent (champ centré)")
    centre = (COLONNES[2] + COLONNES[3]) / 2
    capitales(d, centre, haut_corps, "Arabe · cible", ancre="middle", couleur=BLEU)
    milieu = sous_entete + CORPS / 2 + (-26 if entree.synonymes_ar else 10)
    d.texte(centre, milieu, entree.terme_ar, taille=58, poids=600, couleur=BLEU_FONCE, ancre="middle")
    # Séparateur : la virgule arabe, présente dans toutes les polices arabes (comme dans l'application).
    grammaire = entree.categorie_ar + (f"، ج. {entree.pluriel_ar}" if entree.pluriel_ar else "")
    d.texte(centre, milieu + 40, grammaire, taille=14.5, couleur=T2, ancre="middle")
    if entree.synonymes_ar:
        d.ligne(centre - 28, milieu + 72, centre + 28, milieu + 72, trait=BLEU_200)
        titre = "Autre équivalent" if len(entree.synonymes_ar) == 1 else "Autres équivalents"
        capitales(d, centre, milieu + 106, titre, ancre="middle")
        larges = [round(largeur(synonyme, 14) + 20) for synonyme in entree.synonymes_ar]
        px = centre - (sum(larges) + 6 * (len(larges) - 1)) / 2
        for synonyme in entree.synonymes_ar:
            px += puce(d, px, milieu + 118, synonyme, h=26) + 6
    libelle = "Copier l’équivalent"
    depart = centre - (16 + 7 + largeur(libelle, 12.5, 600)) / 2
    d.icone("copier", depart, base_pied - 12.5, 16, BLEU, 1.5)
    d.texte(depart + 23, base_pied, libelle, taille=12.5, poids=600, couleur=BLEU)

    # --- 4 Contextualisation
    x, droite = COLONNES[3] + 24, COLONNES[4] - 24
    if entree.contextes:
        d.titre("4 · Contextualisation (exemples du glossaire, le terme en évidence)")
        base = sous_entete + 18
        for rang, contexte in enumerate(entree.contextes):
            if rang:
                d.ligne(x, base, droite, base)
                base += 16
            puce(d, x, base, contexte.source, "source", h=20, taille=11.5)
            base += 42
            avant, _, apres = contexte.fr.partition(entree.terme_fr)
            with d.g(taille=14):
                for ligne in couper_riche_net([(avant, {}), (entree.terme_fr, EN_EVIDENCE), (apres, {})],
                                              droite - x - 6, 14):
                    d.texte(x, base, ligne)
                    base += 22
            base += 8
            forme = "ال" + entree.terme_ar
            avant, _, apres = contexte.ar.partition(forme)
            with d.g(taille=16.5, ancre="end"):
                for ligne in couper_riche_net([(avant, {}), (forme, EN_EVIDENCE), (apres, {})], droite - x - 16, 16.5):
                    d.texte(droite, base, ligne)
                    base += 30
            base -= 10
        d.icone("texte", x, base_pied - 12.5, 16, T3)
        d.texte(x + 23, base_pied, f"{len(entree.contextes)} exemples dans le glossaire", taille=12, couleur=T3)
    else:
        d.titre("4 · Contextualisation : le glossaire ne donne pas d'exemple pour ce terme")
        centre_4 = (x + droite) / 2
        milieu = sous_entete + CORPS / 2 - 40
        d.cercle(centre_4, milieu, 20, fill=GRIS_100)
        d.icone("texte", centre_4 - 9, milieu - 9, 18, T4, 1.5)
        d.texte(centre_4, milieu + 48, "Aucun exemple pour ce terme", taille=13, poids=600, couleur=T2, ancre="middle")
        with d.g(taille=12.5, couleur=T3, ancre="middle"):
            for rang, ligne in enumerate(("Ajoutez-en dans les colonnes", "contexte_fr et contexte_ar du fichier",
                                          "CSV, puis rechargez le glossaire (F5).")):
                d.texte(centre_4, milieu + 72 + rang * 19, ligne)

    # --- 5 Ressources
    d.titre("5 · Ressources")
    x, droite = COLONNES[4] + 24, COLONNES[5] - 24
    base = sous_entete + 30
    for rang, ressource in enumerate(entree.ressources):
        if rang:
            d.ligne(x, base - 6, droite, base - 6)
            base += 16
        if est_arabe(ressource):
            titre, _, detail = ressource.partition("، ")
            with d.g(taille=15, poids=600, ancre="end"):
                for ligne in couper_net(titre, droite - x - 12, 15, 600):
                    d.texte(droite, base + 2, ligne)
                    base += 26
            with d.g(taille=13.5, couleur=T3, ancre="end"):
                for ligne in couper_net(detail, droite - x - 12, 13.5):
                    d.texte(droite, base, ligne)
                    base += 23
            base -= 5
            continue
        titre, _, detail = ressource.partition(", ")
        with d.g(taille=13, poids=600):
            for ligne in couper_net(titre, droite - x - 4, 13, 600):
                d.texte(x, base, ligne)
                base += 19
        if detail.startswith("www."):
            d.texte(x, base, detail, taille=12.5, couleur=BLEU)
            d.icone("lien", x + largeur(detail, 12.5) + 6, base - 10.5, 12, BLEU, 1.5)
            base += 18
        elif detail:
            with d.g(taille=12.5, couleur=T3):
                for ligne in couper_net(detail, droite - x - 4, 12.5):
                    d.texte(x, base, ligne)
                    base += 18
    d.icone("copier", x, base_pied - 12.5, 16, BLEU, 1.5)
    d.texte(x + 23, base_pied, "Copier les références", taille=12.5, poids=600, couleur=BLEU)
    d.niveau -= 1
    d.brut("</g>")
    d.rect(X0, HAUT, X1 - X0, fond - HAUT, 12, fill="none", trait=FILET)

    # ------------------------------------------------------------------ expressions et termes proches
    if autres:
        d.titre("Autres entrées du glossaire liées à la recherche (un clic ouvre la fiche)")
        haut_liste = fond + 16
        rangees = -(-len(autres) // 4)
        pas, large = 36, (X1 - X0) / 4
        hauteur = min(40 + rangees * pas + 4, FOND_PAGE - haut_liste)
        d.rect(X0, haut_liste, X1 - X0, hauteur, 12, fill=SURFACE, trait=FILET)
        titre = f"Expressions avec « {requete} »" if que_des_expressions else "Expressions et termes proches"
        d.texte(X0 + 24, haut_liste + 25.5, titre, taille=13.5, poids=600)
        pastille(d, X0 + 24 + largeur(titre, 13.5, 600) + 12, haut_liste + 12, str(len(autres)))
        d.texte(X1 - 24, haut_liste + 25.5, "Cliquez sur une ligne pour ouvrir sa fiche", taille=12, couleur=T3,
                ancre="end")
        haut = haut_liste + 40
        with d.g(trait=FILET_DOUX):
            d.ligne(X0, haut, X1, haut, trait=None)
            for colonne in range(1, 4):
                d.ligne(X0 + colonne * large, haut, X0 + colonne * large, haut_liste + hauteur, trait=None)
            for rangee in range(1, rangees):
                d.ligne(X0, haut + rangee * pas, X1, haut + rangee * pas, trait=None)
        survol = 1  # la deuxième ligne est montrée telle qu'elle apparaît sous le pointeur
        for rang, autre in enumerate(autres):
            rangee, colonne = divmod(rang, 4)
            cx, cy = X0 + colonne * large, haut + rangee * pas
            if rang == survol:
                d.rect(cx + 6, cy + 4, large - 12, pas - 7, 6, fill=BLEU_50)
            gauche = cx + (24 if colonne == 0 else 16)
            droite = cx + large - (24 if colonne == 3 else 16)
            # Un terme trop long pour la case est abrégé ; il reste entier dans l'infobulle et dans la fiche.
            place = droite - gauche - largeur(autre.terme_ar, 14.5) - 22
            d.texte(gauche, cy + 22.8, abreger_lettres(autre.terme_fr, place, 13), taille=13,
                    couleur=BLEU_FONCE if rang == survol else T1)
            d.texte(droite, cy + 23.2, autre.terme_ar, taille=14.5, couleur=BLEU_FONCE if rang == survol else T2,
                    ancre="end")

    barre_d_etat(d, f"« {requete} » : {len(resultats)} entrées trouvées dans le glossaire.")
    fin_fenetre(d)
    if plusieurs_sens:
        sans_exemple = sum(1 for autre in glossaire.entrees if not autre.contextes)
        sujet = "CAS COURANT — terme à deux sens, définition à vérifier, pas d'exemple"
        contenu = (f"  Le contenu vient du glossaire fourni (donnees/glossaire_juridique.csv), entrée « {requete} ».\n"
                   "  Ce que montre cet écran : les onglets des deux sens ; la mention « À vérifier » ; le champ 4\n"
                   f"  quand le glossaire ne donne pas d'exemple (c'est le cas de {sans_exemple} entrées sur 1 000).")
        description = ("Fenêtre d'application de bureau. La barre de recherche contient le terme « action », qui a "
                       "deux sens dans le glossaire : deux onglets permettent de choisir. La fiche présente les cinq "
                       "champs ; la définition porte la mention « À vérifier » et le champ des exemples indique qu'il "
                       "n'y en a pas. Sous la fiche, les expressions et les termes proches.")
        titre = "Proposition — Écran « Terme » : terme à deux sens, sans exemple"
    else:
        sujet = "RECHERCHE D'UN TERME"
        contenu = (f"  Sous la fiche : les expressions du glossaire qui contiennent le terme.\n"
                   f"  Le contenu vient du glossaire fourni (donnees/glossaire_juridique.csv), entrée « {requete} ».")
        description = ("Fenêtre d'application de bureau. En haut, le sélecteur d'écran, le sens de traduction et la "
                       "barre de recherche, qui contient le terme « contrat ». En dessous, une fiche présente cinq "
                       "champs côte à côte : terme, définition, équivalent en arabe, contextualisation et ressources. "
                       "Sous la fiche, la liste des expressions du glossaire qui contiennent le terme.")
        titre = "Proposition — Écran « Terme » : recherche d'un terme juridique (français vers arabe)"
    lignes = entete(titre, description, NOTES.format(sujet=sujet, contenu=contenu), d.icones)
    return "\n".join(lignes + d.lignes + ["</svg>", ""])


LEGENDES = ["catégorie, domaine, synonymes", "en français et en arabe, avec sa source", "dans la langue cible",
            "exemples d’emploi dans les deux langues", "textes de loi, ouvrages, sites officiels"]
RACCOURCIS = [("Ctrl+F", "aller à la barre de recherche"), ("Ctrl+I", "inverser le sens de traduction"),
              ("Ctrl+2", "traduire un texte"), ("F5", "recharger le glossaire")]


def dessiner_sans_fiche(glossaire: Glossaire, requete: str = "", exemples: tuple[str, ...] = ()) -> str:
    """Écran sans fiche : à l'ouverture de l'application (``requete`` vide) ou quand le terme est introuvable."""
    d = Dessin()
    fenetre(d)
    propositions = [entree.terme_fr for entree in glossaire.propositions(requete, FR)] if requete else list(exemples)
    recherche(d, barre_d_outils(d, "terme"), requete, "Aucun résultat")

    d.titre("Panneau d'accueil : l'enchaînement est rappelé en haut, le message est au centre")
    fond = FOND_PAGE
    d.rect(X0, HAUT, X1 - X0, fond - HAUT, 12, fill=SURFACE, trait=FILET)
    en_tete_des_etapes(d, HAUT + 4, LEGENDES)
    sous_entete = HAUT + 80
    d.ligne(X0, sous_entete, X1, sous_entete)
    d.ligne(X0, fond - 48, X1, fond - 48)

    centre = (X0 + X1) / 2
    milieu = (sous_entete + fond - 48) / 2
    if requete:
        fond_icone, trait_icone, couleur_icone = AMBRE_50, AMBRE_200, AMBRE
        titre = f"Aucune entrée pour « {requete} »"
        textes = ["Ce terme n’est pas dans le glossaire. Vérifiez son orthographe, ou ouvrez un terme proche."]
        etiquette = "Termes proches"
    else:
        fond_icone, trait_icone, couleur_icone = BLEU_50, BLEU_100, BLEU
        titre = "Recherchez un terme juridique"
        textes = ["Saisissez un terme en français ou en arabe, puis appuyez sur Entrée.",
                  "Le sens de traduction s’adapte à la langue du terme."]
        etiquette = "Par exemple"
    haut_bloc = milieu - (64 + 28 + 30 + len(textes) * 22 + 34 + 12 + 30) / 2 - 18  # un peu au-dessus du centre
    d.cercle(centre, haut_bloc + 32, 32, fill=fond_icone, trait=trait_icone)
    d.icone("loupe", centre - 14, haut_bloc + 18, 28, couleur_icone, 1.4)
    base = haut_bloc + 64 + 28 + 22
    d.texte(centre, base, titre, taille=24, poids=600, couleur=MARINE, ancre="middle", espacement=-0.2)
    base += 30
    with d.g(taille=14, couleur=T3, ancre="middle"):
        for texte in textes:
            d.texte(centre, base, texte)
            base += 22
    base += 22
    capitales(d, centre, base, etiquette, ancre="middle")
    larges = [round(largeur(proposition, 13.5) + 28) for proposition in propositions]
    x = centre - (sum(larges) + 8 * (len(larges) - 1)) / 2
    for proposition, large in zip(propositions, larges, strict=True):
        d.rect(x, base + 12, large, 30, 8, fill=BLEU_50, trait=BLEU_100)
        d.texte(x + large / 2, base + 12 + 19.8, proposition, taille=13.5, couleur=BLEU_FONCE, ancre="middle")
        x += large + 8

    d.c("Pied du panneau")
    if requete:
        d.texte(centre, fond - 19.5, "Pour obtenir sa fiche, ajoutez ce terme au fichier CSV, puis rechargez le "
                "glossaire (F5).", taille=12.5, couleur=T3, ancre="middle")
    else:
        larges = [largeur(touche, 11.5, 600) + 14 + 8 + largeur(action, 12.5) for touche, action in RACCOURCIS]
        x = centre - (sum(larges) + 36 * (len(larges) - 1)) / 2
        for (touche, action), large in zip(RACCOURCIS, larges, strict=True):
            l_touche = largeur(touche, 11.5, 600) + 14
            d.rect(x, fond - 35, l_touche, 22, 5, fill=GRIS_50, trait=FILET)
            d.texte(x + l_touche / 2, fond - 19.8, touche, taille=11.5, poids=600, couleur=T2, ancre="middle")
            d.texte(x + l_touche + 8, fond - 19.5, action, taille=12.5, couleur=T3)
            x += large + 36

    if requete:
        barre_d_etat(d, f"Aucune entrée du glossaire ne correspond à « {requete} ».")
        sujet = "TERME INTROUVABLE"
        contenu = "  Aucune fiche : le message propose les termes du glossaire dont l'écriture est proche."
        titre = "Proposition — Écran « Terme » : terme introuvable"
        description = ("Fenêtre d'application de bureau. La barre de recherche contient « contart », qui n'est pas "
                       "dans le glossaire. Un panneau rappelle les cinq champs de l'enchaînement, annonce qu'aucune "
                       "entrée ne correspond et propose deux termes proches : contrat et constat.")
    else:
        barre_d_etat(d, "Glossaire chargé : 1 000 entrées.")
        sujet = "À L'OUVERTURE DE L'APPLICATION"
        contenu = "  Aucune fiche : le panneau rappelle l'enchaînement et invite à chercher un terme."
        titre = "Proposition — Écran « Terme » : à l'ouverture de l'application"
        description = ("Fenêtre d'application de bureau, avant toute recherche. Un panneau rappelle les cinq champs de "
                       "l'enchaînement, invite à saisir un terme en français ou en arabe et propose cinq termes "
                       "d'exemple. En bas, quatre raccourcis clavier.")
    fin_fenetre(d)
    lignes = entete(titre, description, NOTES.format(sujet=sujet, contenu=contenu), d.icones)
    return "\n".join(lignes + d.lignes + ["</svg>", ""])
