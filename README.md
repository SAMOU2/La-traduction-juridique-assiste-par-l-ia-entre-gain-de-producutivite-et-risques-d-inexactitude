# La-traduction-juridique-assiste-par-l-ia-entre-gain-de-producutivite-et-risques-d-inexactitude

Prototype d'une application de bureau de traduction juridique **français ⇄ arabe**, « à la
Reverso ». Pour chaque terme, elle suit l'enchaînement :

**① Terme → ② Définition → ③ Équivalent → ④ Contextualisation → ⑤ Ressources**

Le dépôt contient l'application (Python et PySide6) et sa [maquette](#maquette-de-lapplication-de-bureau).

## L'application (version 0.1)

![Écran de recherche de l'application](docs/apercu-recherche.png)

*Capture produite sous Linux, sans écran. L'aspect des caractères peut changer d'un système à l'autre.*

### Ce qui est fait, ce qui reste à faire

| Fonctionnalité | État |
| --- | --- |
| Lecture du glossaire CSV | Fait |
| Écran « Recherche d'un terme » : barre de recherche et cinq champs côte à côte | Fait, dans les deux sens (français → arabe et arabe → français) |
| Écran « Traduction d'un texte » : segmentation en phrases, découpage en mots, recherche de chaque mot dans le CSV, règles lexicales, grammaticales et sémantiques, reconstruction du paragraphe | À faire |
| Import et export de fichiers `.txt`, `.docx`, `.doc` | À faire |
| Fichier `.exe` pour Windows | À faire |

### Installation

Il faut **Python 3.10 ou plus récent** ([python.org](https://www.python.org/downloads/)). Sous
Windows, cocher « Add python.exe to PATH » pendant l'installation.

Dans VS Code, ouvrir le dossier du projet, puis un terminal (menu *Terminal → Nouveau terminal*) :

```
python -m pip install -r requirements.txt
```

Si la commande `python` n'est pas reconnue sous Windows, écrire `py` à la place.

### Lancement

```
python main.py
```

Ou, dans VS Code : ouvrir `main.py`, puis cliquer sur ▶ (« Exécuter le fichier Python »).

L'application s'ouvre avec le glossaire d'exemple. Pour l'ouvrir avec un autre glossaire :
`python main.py chemin/vers/mon_glossaire.csv`.

### Utilisation

- Saisir un terme, en français ou en arabe, puis appuyer sur Entrée. Si le terme est écrit dans
  l'autre langue, le sens de traduction s'inverse tout seul. Le bouton ⇄ l'inverse à la main.
- Sous la barre de recherche, les entrées trouvées s'affichent sous forme de puces (huit au
  plus). Cliquer sur une puce affiche cette entrée.
- Si rien n'est trouvé, l'application propose les termes dont l'écriture est proche.
- Dans les champs, un clic sur une puce écrite en bleu ou sur une expression ouvre l'entrée
  correspondante.
- *Fichier → Ouvrir un glossaire…* charge un autre fichier CSV. L'application le rouvrira au
  prochain lancement. *Fichier → Recharger le glossaire* relit le fichier après une
  modification.

La recherche ne tient pas compte des majuscules, des accents, d'un article placé devant le terme
(« le contrat », « العقد »), des signes diacritiques arabes ni des variantes d'écriture de la
hamza, du ta marbuta et de l'alif maqsura. Le pluriel est reconnu s'il figure dans le glossaire.

| Raccourci | Action |
| --- | --- |
| Ctrl+F | Aller à la barre de recherche |
| Ctrl+I | Inverser le sens de traduction |
| Ctrl+O | Ouvrir un glossaire |
| F5 | Recharger le glossaire |
| Ctrl+Q | Quitter |

### Le glossaire CSV

Une ligne par terme ; la première ligne donne le nom des colonnes. Seules les deux premières
colonnes du tableau sont obligatoires.

| Colonne | Champ alimenté |
| --- | --- |
| `terme_fr`, `terme_ar` | ① Terme et ③ Équivalent, selon le sens de traduction |
| `categorie_fr`, `categorie_ar` | Catégorie grammaticale, sous le terme |
| `pluriel_fr`, `pluriel_ar` | Pluriel, sous le terme ; il sert aussi à la recherche |
| `domaine` | ① Terme, rubrique « Domaine » |
| `synonymes_fr`, `synonymes_ar` | ① Terme, rubrique « Synonymes » ; ils servent aussi à la recherche |
| `termes_associes` | ① Terme, rubrique « Termes associés » |
| `definition_fr`, `definition_ar`, `source_definition` | ② Définition |
| `contexte_fr`, `contexte_ar`, `source_contexte` | ④ Contextualisation |
| `ressources` | ⑤ Ressources |

- Dans une cellule, plusieurs valeurs se séparent par une barre verticale : `convention | accord`.
  Pour les exemples, le premier exemple français va avec le premier exemple arabe et la première
  source, et ainsi de suite.
- Depuis Excel : *Enregistrer sous → CSV UTF-8 (délimité par des virgules)*. Un classeur
  `.xlsx` n'est pas lu directement.
- Le séparateur (point-virgule, virgule ou tabulation) et l'encodage (UTF-8, UTF-16,
  Windows-1256, Windows-1252) sont reconnus automatiquement.
- D'autres noms de colonnes sont acceptés (« Français », « Arabe », « Définition »…). Un fichier
  sans ligne d'en-tête fonctionne aussi : la colonne arabe et la colonne française sont
  repérées d'après leur écriture.
- Les lignes sans terme français ou sans terme arabe sont ignorées. Leur nombre est indiqué à
  l'ouverture du fichier.
- Les expressions du champ ③ ne viennent pas d'une colonne : ce sont les autres entrées du
  glossaire qui contiennent le terme (« contrat de vente » pour « contrat »).

Le rappel du format se trouve aussi dans l'application : *Aide → Format du glossaire CSV*.

### Le glossaire d'exemple

`donnees/glossaire_juridique.csv` contient 40 entrées de droit civil. Il sert à essayer
l'application et doit être remplacé par le glossaire du projet.

- **Extraits authentiques.** Les définitions et les exemples qui portent une référence viennent
  du Code civil algérien (ordonnance n° 75-58 du 26 septembre 1975), articles 1er, 54, 55, 59,
  106, 107, 124, 351 et 467, en français et en arabe. Ils ont été relevés sur des sites web
  juridiques et n'ont pas été comparés au Journal officiel : ils sont à vérifier avant d'être
  cités. Les articles longs sont découpés en phrases, et le début des définitions de
  « contrat », « vente » et « bail » est retiré (« Le contrat est une… »). Le texte arabe a
  reçu trois retouches : une hamza ajoutée à l'article 59 (« الإخلال »), le choix d'une des
  deux versions trouvées pour le début de l'article 124, et une virgule ajoutée dans
  l'intitulé de l'ordonnance.
- **Contenu d'illustration.** Les couples de termes (français et arabe), les catégories
  grammaticales, les pluriels, les domaines, les synonymes, les termes associés et la référence
  au *Vocabulaire juridique* de G. Cornu ont été rédigés pour la démonstration. Ils doivent
  être vérifiés par un juriste ou un traducteur.

### Organisation du code

```
main.py                      lance l'application
requirements.txt             bibliothèques nécessaires
donnees/
  glossaire_juridique.csv    glossaire d'exemple
traducteur/
  langues.py                 comparaison des mots : accents, variantes d'écriture de l'arabe
  glossaire.py               lecture du CSV et recherche des termes
  surlignage.py              repérage du terme dans les exemples
  application.py             démarrage de l'application
  interface/
    fenetre.py               fenêtre : menus, barre d'outils, barre d'état
    recherche.py             écran de recherche
    cartes.py                les cinq champs
    composants.py            puces, étiquettes, disposition des puces
    theme.py                 couleurs et feuille de style
    icones.py                icônes
tests/                       tests automatiques
maquette/                    maquette SVG des deux écrans
```

`langues.py`, `glossaire.py` et `surlignage.py` n'utilisent pas l'interface graphique. L'écran
« Traduction d'un texte » pourra s'en servir.

### Tests

```
python -m pip install -r requirements-dev.txt
python -m pytest
```

Les 130 tests s'exécutent sans ouvrir de fenêtre.

### Limites connues

- L'application a été développée et testée sous Linux, sans écran, avec Python 3.11 et
  PySide6 6.7 et 6.12. Elle n'a pas encore été essayée sous Windows ni sous macOS.
- La recherche compare des formes écrites. Un mot conjugué ou décliné n'est trouvé que si
  cette forme figure dans le glossaire (colonnes des termes, des pluriels ou des synonymes).
- Les suggestions affichées pendant la saisie tiennent compte des accents ; la recherche
  lancée avec Entrée, non.
- Les équivalents affichés sont ceux du glossaire chargé. L'application ne les vérifie pas.

## Maquette de l'application de bureau

Maquette SVG des deux écrans du prototype. L'écran 1 est programmé (voir ci-dessus) ; l'écran 2
reste à faire.

### Écran 1 — Recherche d'un terme

![Écran 1 : recherche d'un terme](maquette/01-recherche-terme.svg)

Le terme saisi dans la barre de recherche est cherché dans le glossaire CSV. Le résultat
s'affiche dans cinq champs placés côte à côte, un par élément de l'enchaînement.

### Écran 2 — Traduction d'un texte

![Écran 2 : traduction d'un texte](maquette/02-traduction-texte.svg)

Le paragraphe source est saisi, collé ou importé dans la zone de texte de gauche ; sa
traduction apparaît dans la zone de droite (écriture de droite à gauche pour l'arabe).
La bande centrale reprend les étapes de l'algorithme : segmentation en phrases, découpage
en mots, recherche de chaque mot dans le CSV, application des règles lexicales,
grammaticales et sémantiques, puis reconstruction du paragraphe. Le tableau du bas
applique l'enchaînement de l'écran 1 aux termes juridiques repérés dans le texte.

### Fonctionnalités demandées et emplacement dans la maquette

| Fonctionnalité | Emplacement |
| --- | --- |
| Champs horizontaux pour chaque élément de l'enchaînement | Écran 1 : les cinq cartes numérotées. Écran 2 : les cinq colonnes du tableau. |
| Import et export de fichiers `.txt`, `.docx`, `.doc` | Boutons **Importer** et **Exporter** de la barre d'outils (les deux écrans). Le fichier importé est rappelé dans l'en-tête de la zone source (écran 2). |
| Barre de recherche des mots | Écran 1, en haut, avec les entrées correspondantes du glossaire. |
| Zones de texte pour un paragraphe | Écran 2 : zone source et zone cible. |

Éléments communs aux deux écrans : le sélecteur **Terme / Texte**, le choix du sens de
traduction (le bouton ⇄ inverse français et arabe) et la barre d'état qui indique le
fichier CSV chargé.

### Points à valider

- **Structure du CSV.** L'application lit les colonnes décrites dans la section
  [Le glossaire CSV](#le-glossaire-csv). Il reste à confirmer que le glossaire du projet
  contient une définition, des exemples et des ressources pour chaque terme, et pas seulement
  le mot et sa traduction. Un fichier limité aux deux colonnes de termes est accepté : les
  champs ②, ④ et ⑤ restent alors vides.
- **Nom de l'application.** « Traducteur juridique » est un nom provisoire.
- **Cas non dessinés.** Le sens arabe → français et le cas d'un mot absent du CSV ne figurent
  pas dans la maquette. Ils sont programmés dans l'application : mêmes écrans avec les langues
  inversées, et proposition des termes proches quand rien n'est trouvé.

### Contenu d'exemple de la maquette

Les textes juridiques sont des extraits du Code civil algérien (ordonnance n° 75-58 du
26 septembre 1975), articles 54, 106 et 107, dans leurs versions française et arabe. Dans
le paragraphe arabe de l'écran 2, une virgule de l'article 106 est remplacée par un point
pour obtenir quatre phrases, comme en français.

Le reste est donné à titre d'illustration : nom et taille du glossaire, numéro d'entrée,
nom du document importé, définitions de « loi » et de « bonne foi », expressions,
synonymes et termes associés.

### Modifier la maquette

Les deux fichiers du dossier `maquette/` sont des SVG autonomes : ni image ni police
externe, et les textes restent des textes. Ils s'affichent dans un navigateur et se
modifient dans un éditeur de code ou un éditeur vectoriel (rendu non vérifié dans Inkscape
et Figma). Ils utilisent les polices du système (Segoe UI sous Windows), le rendu peut
donc varier légèrement d'un appareil à l'autre.
