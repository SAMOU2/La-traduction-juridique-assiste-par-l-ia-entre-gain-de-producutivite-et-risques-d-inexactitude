# La-traduction-juridique-assiste-par-l-ia-entre-gain-de-producutivite-et-risques-d-inexactitude

Prototype d'une application de bureau de traduction juridique **français ⇄ arabe**, « à la
Reverso ». Pour chaque terme, elle suit l'enchaînement :

**① Terme → ② Définition → ③ Équivalent → ④ Contextualisation → ⑤ Ressources**

Le dépôt contient l'application (Python et PySide6) et sa [maquette](#maquette-de-lapplication-de-bureau).

## L'application (version 0.2)

L'application a deux écrans. On passe de l'un à l'autre avec le sélecteur **Terme | Texte**, en
haut à gauche de la fenêtre (ou avec Ctrl+1 et Ctrl+2).

**Écran « Terme »** — recherche d'un terme dans le glossaire :

![Écran de recherche d'un terme](docs/apercu-recherche.png)

**Écran « Texte »** — traduction d'un texte à l'aide du glossaire :

![Écran de traduction d'un texte](docs/apercu-texte.png)

*Captures produites sous Linux, sans écran. L'aspect des caractères peut changer d'un système à l'autre.*

### Ce qui est fait, ce qui reste à faire

| Fonctionnalité | État |
| --- | --- |
| Lecture du glossaire CSV | Fait |
| Écran « Terme » : barre de recherche et cinq champs côte à côte | Fait, dans les deux sens (français → arabe et arabe → français) |
| Écran « Texte » : zones de texte, segmentation en phrases, découpage en mots, recherche de chaque mot dans le CSV, règles lexicales, grammaticales et sémantiques, reconstruction du paragraphe | Fait, dans les deux sens. La traduction se limite au contenu du glossaire : voir [Comment le texte est traduit](#comment-le-texte-est-traduit). |
| Import de fichiers `.txt`, `.docx`, `.doc` | Fait |
| Export de la traduction en `.docx` ou `.txt` | Fait. L'export au format `.doc` n'est pas proposé ; Word ouvre les fichiers `.docx`. |
| Fichier `.exe` pour Windows | À faire |

### Installation

Il faut **Python 3.10 ou plus récent**.

Sous Windows, si la commande `python` répond « Python was not found », Python n'est pas encore
installé sur l'ordinateur :

1. Installer le **Python Install Manager** depuis le
   [Microsoft Store](https://apps.microsoft.com/detail/9NQ7512CXL7T) (bouton « Installer »). Il
   est aussi proposé sur [python.org](https://www.python.org/downloads/).
2. Ouvrir un nouveau terminal. À la première utilisation de la commande `python`, la dernière
   version de Python est téléchargée et installée automatiquement.

Dans VS Code, ouvrir le dossier du projet, puis un terminal (menu *Terminal → Nouveau terminal*) :

```
python -m pip install -r requirements.txt
```

Cette commande télécharge PySide6, soit environ 85 Mo sous Windows. Si la commande `python`
n'est toujours pas reconnue, écrire `py` à la place.

### Lancement

```
python main.py
```

Ou, dans VS Code : ouvrir `main.py`, puis cliquer sur ▶ (« Exécuter le fichier Python »).

L'application s'ouvre avec le glossaire d'exemple. Pour l'ouvrir avec un autre glossaire :
`python main.py chemin/vers/mon_glossaire.csv`.

### Mise à jour

Pour récupérer la dernière version du dépôt, dans le terminal de VS Code :

```
git pull origin main
python -m pip install -r requirements.txt
python main.py
```

### Utiliser l'écran « Terme »

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

**Les cinq champs sont remplis avec le contenu du fichier CSV, et rien d'autre.** Un terme qui
n'est pas dans le CSV n'a pas de fiche. Un terme dont la ligne n'a pas de définition, d'exemple
ou de ressource a le champ correspondant vide. Pour compléter, modifier le fichier CSV, puis
*Fichier → Recharger le glossaire* (F5).

La recherche ne tient pas compte des majuscules, des accents, d'un article placé devant le terme
(« le contrat », « العقد »), des signes diacritiques arabes ni des variantes d'écriture de la
hamza, du ta marbuta et de l'alif maqsura. Le pluriel est reconnu s'il figure dans le glossaire.

### Utiliser l'écran « Texte »

1. Cliquer sur **Texte**, en haut à gauche (ou Ctrl+2).
2. Écrire ou coller le texte dans la zone de gauche. Le bouton **Importer** ouvre un fichier
   `.txt`, `.docx` ou `.doc`. Le lien *Insérer un exemple* place un texte d'essai.
3. Cliquer sur **Traduire** (ou Ctrl+Entrée). Un fichier importé est traduit tout de suite. Si
   le texte est écrit dans l'autre langue, le sens de traduction s'inverse tout seul.
4. La traduction s'affiche dans la zone de droite :
   - en orange, les termes du glossaire (dans les deux zones) ;
   - en gris, les mots absents du glossaire : ils restent dans la langue source et sont à
     traduire à la main.
5. L'étiquette placée au-dessus de la traduction indique le résultat : « Traduction terminée »
   (tous les mots ont été trouvés), « Traduction partielle », « Aucun mot trouvé », ou « Texte
   modifié » quand le texte source a changé depuis la dernière traduction.
6. La bande du milieu donne le résultat des cinq étapes. Laisser le pointeur sur une étape
   affiche le détail (règles appliquées, mots non trouvés).
7. Le tableau « Termes juridiques détectés » applique l'enchaînement ① à ⑤ à chaque terme du
   glossaire relevé dans le texte. Un clic sur un terme ouvre sa fiche dans l'écran « Terme ».
8. **Copier** place la traduction dans le presse-papiers. **Exporter** l'enregistre dans un
   fichier `.docx` ou `.txt`.

Chaque écran garde son propre sens de traduction.

### Comment le texte est traduit

La traduction utilise **le glossaire CSV et lui seul** : ni dictionnaire général, ni service en
ligne, ni modèle d'intelligence artificielle. Elle suit cinq étapes :

1. **Segmentation** : le texte est découpé en phrases.
2. **Découpage** : chaque phrase est découpée en mots.
3. **Recherche dans le CSV** : la phrase entière est cherchée parmi les exemples du glossaire,
   puis les expressions les plus longues (« contrat de vente »), puis les mots un par un.
4. **Règles linguistiques** :
   - lexique : expression de plusieurs mots, synonyme ramené au terme du glossaire ;
   - grammaire : pluriel, article défini ou indéfini, complément du nom (« la nullité du
     contrat » ↔ « بطلان العقد »), possessif et particules collées au mot arabe (و، ب، ل…) ;
   - sémantique : quand une forme correspond à plusieurs entrées (« droit » : « حق » ou
     « قانون »), le choix se fait d'après les autres termes de la phrase et du texte.
5. **Reconstruction** : chaque phrase est récrite dans la langue cible, avec sa ponctuation.

Ce que cela donne :

- Une phrase identique à un exemple du glossaire (colonnes `contexte_fr` et `contexte_ar`) reçoit
  la traduction de cet exemple.
- Les autres phrases sont traduites mot à mot. Les termes du glossaire sont traduits ; les
  autres mots (verbes, mots grammaticaux, mots absents du CSV) restent dans la langue source, en
  gris. Exemple avec le glossaire fourni : « La nullité du contrat de vente protège
  l'acheteur. » donne « بطلان عقد البيع protège المشتري. ».
- L'ordre des mots n'est pas modifié. Les verbes ne sont pas conjugués et les adjectifs ne sont
  pas accordés.
- Une phrase où aucun terme n'est trouvé est recopiée telle quelle.
- Pour traduire davantage, il faut enrichir le CSV : termes, pluriels, synonymes, exemples.

Le résultat est une aide à la traduction. Il doit être complété et vérifié par le traducteur.

### Import et export

| Format | Import | Export |
| --- | --- | --- |
| `.txt` | Oui. L'encodage est reconnu (UTF-8, UTF-16, Windows-1256, Windows-1252). | Oui, en UTF-8. |
| `.docx` (Word) | Oui | Oui. Les paragraphes arabes sont écrits de droite à gauche. |
| `.doc` (Word 97 à 2003) | Oui | Non |

- Seul le texte du corps du document est lu : un paragraphe par ligne, les cellules d'un
  tableau séparées par des tabulations. La mise en forme, les images, les en-têtes, les pieds de
  page et les notes ne sont pas repris. Dans un fichier `.doc`, le texte des zones de texte
  (cadres flottants) est placé à la fin.
- Le format est reconnu d'après le contenu du fichier, pas d'après son nom. Certains sites et
  logiciels produisent des fichiers nommés `.doc` qui sont en réalité une page web (HTML) ou un
  fichier XML de Word 2003 : leur texte est lu, sans les balises. Un fichier `.txt` est
  toujours lu tel quel.
- Un fichier Word protégé par un mot de passe, créé avant Word 97 ou endommagé est refusé, avec
  un message qui en donne la raison.
- Les fichiers PDF et RTF ne sont pas lus : le message d'erreur indique comment les convertir.
- Le nom proposé pour l'export est celui du fichier importé suivi de `_traduction`. Le fichier
  exporté contient le texte de la zone de droite, y compris les mots non traduits.

### Raccourcis

| Raccourci | Action |
| --- | --- |
| Ctrl+1, Ctrl+2 | Afficher l'écran « Terme », l'écran « Texte » |
| Ctrl+I | Inverser le sens de traduction |
| Ctrl+F | Aller à la barre de recherche |
| Ctrl+Entrée | Traduire le texte |
| Ctrl+Maj+C | Copier la traduction |
| Ctrl+Maj+O | Importer un texte |
| Ctrl+E | Exporter la traduction |
| Ctrl+O | Ouvrir un glossaire |
| F5 | Recharger le glossaire |
| Ctrl+Q | Quitter |

### Le glossaire CSV

Une ligne par terme ; la première ligne donne le nom des colonnes. Seules les deux premières
colonnes du tableau sont obligatoires.

| Colonne | Écran « Terme » | Écran « Texte » |
| --- | --- | --- |
| `terme_fr`, `terme_ar` | ① Terme et ③ Équivalent, selon le sens de traduction | Mots et expressions cherchés dans le texte, et leur traduction |
| `categorie_fr`, `categorie_ar` | Catégorie grammaticale, sous le terme | Si `categorie_fr` contient « masculin » ou « féminin », l'article français est écrit (« le », « la », « un », « une ») |
| `pluriel_fr`, `pluriel_ar` | Pluriel, sous le terme ; il sert aussi à la recherche | Reconnaissance et écriture du pluriel |
| `domaine` | ① Terme, rubrique « Domaine » | — |
| `synonymes_fr`, `synonymes_ar` | ① Terme, rubrique « Synonymes » ; ils servent aussi à la recherche | Un synonyme trouvé dans le texte est traduit comme le terme |
| `termes_associes` | ① Terme, rubrique « Termes associés » | Choix entre deux entrées de même forme |
| `definition_fr`, `definition_ar`, `source_definition` | ② Définition | Colonne « Définition » du tableau |
| `contexte_fr`, `contexte_ar`, `source_contexte` | ④ Contextualisation | Une phrase du texte identique à un exemple reçoit la traduction de cet exemple |
| `ressources` | ⑤ Ressources | Colonne « Ressources » du tableau |

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
l'application et doit être remplacé par le glossaire du projet. Chaque entrée a une définition
dans les deux langues, la source de cette définition et des ressources. Neuf entrées n'ont pas
d'exemple : leur champ ④ reste vide.

- **Extraits du Code civil algérien** (ordonnance n° 75-58 du 26 septembre 1975), en français
  et en arabe :
  - les définitions de « contrat » (art. 54), « vente » et « contrat de vente » (art. 351),
    « bail » et « contrat de bail » (art. 467) et « propriété » (art. 674) ;
  - tous les exemples : articles 1er, 40, 55, 59, 102, 106, 107, 124, 188, 351 et 467, et
    l'intitulé de l'ordonnance.

  Ces textes ont été relevés sur des sites web juridiques et n'ont pas été comparés au Journal
  officiel : ils sont à vérifier avant d'être cités. Les articles longs sont découpés en
  phrases, et le début des définitions est retiré (« Le contrat est une… »). Le texte arabe a
  reçu trois retouches : une hamza ajoutée à l'article 59 (« الإخلال »), le choix d'une des
  deux versions trouvées pour le début de l'article 124, et une virgule ajoutée dans
  l'intitulé de l'ordonnance.
- **Définitions d'exemple.** Les 34 autres définitions, en français et en arabe, ont été
  rédigées pour la démonstration. Elles ne viennent d'aucun dictionnaire juridique et doivent
  être remplacées ou vérifiées. La source affichée pour 33 d'entre elles est « à vérifier
  (définition d'exemple) » ; celle de « conclusion du contrat » est « D'après le Code civil,
  art. 59 ».
- **Autre contenu d'illustration.** Les couples de termes (français et arabe), les catégories
  grammaticales, les pluriels, les domaines, les synonymes, les termes associés et les
  ressources ont été rédigés pour la démonstration. Le *Vocabulaire juridique* de G. Cornu est
  cité comme ouvrage à consulter : les définitions n'en sont pas tirées. La référence de la loi
  n° 90-11 du 21 avril 1990 (entrée « contrat de travail ») n'a pas été vérifiée. L'ensemble
  doit être contrôlé par un juriste ou un traducteur.

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
  segmentation.py            découpage d'un texte en phrases, puis en mots
  traduction.py              traduction d'un texte : recherche, règles, reconstruction
  documents.py               import et export des fichiers .txt, .docx et .doc
  application.py             démarrage de l'application
  interface/
    fenetre.py               fenêtre : menus, barre d'outils, barre d'état
    recherche.py             écran « Terme »
    cartes.py                les cinq champs de l'écran « Terme »
    texte.py                 écran « Texte »
    composants.py            puces, étiquettes, disposition des puces
    theme.py                 couleurs et feuille de style
    icones.py                icônes
tests/                       tests automatiques
docs/                        captures d'écran
maquette/                    maquette SVG des deux écrans
```

Les modules placés directement dans `traducteur/` n'utilisent pas l'interface graphique, sauf
`application.py`. La lecture et l'écriture des fichiers Word n'utilisent aucune bibliothèque
supplémentaire.

### Tests

```
python -m pip install -r requirements-dev.txt
python -m pytest
```

Les 278 tests s'exécutent sans ouvrir de fenêtre.

### Limites connues

- **Systèmes essayés.** Les tests ont été exécutés sous Linux, sans écran, avec Python 3.11
  (PySide6 6.7 et 6.11) et Python 3.15 (PySide6 6.12). Aucun test n'a été exécuté sous Windows ni
  sous macOS.
- **PySide6 6.12 avec Python 3.11.** Avec ces deux versions, l'application se ferme brutalement
  après quelques milliers d'opérations (« Fatal Python error: none_dealloc »). `requirements.txt`
  installe donc une version antérieure de PySide6 avec Python 3.10 et 3.11 (Python 3.10 n'a pas
  été essayé : c'est une précaution). Si l'application détecte ce défaut au lancement, elle
  affiche un avertissement. Le défaut ne s'est pas produit avec Python 3.15.
- **Traduction d'un texte.** Elle se limite au glossaire : voir
  [Comment le texte est traduit](#comment-le-texte-est-traduit). En particulier :
  - un mot conjugué ou décliné n'est reconnu que si cette forme figure dans le glossaire, ou si
    elle s'en déduit par une règle simple (pluriel français en « s », « x » ou « aux » ;
    article, particule et terminaisons courantes en arabe) ;
  - quand le pluriel arabe d'un terme n'est pas connu, le terme reste au singulier ;
  - sans genre dans la colonne `categorie_fr`, l'article français n'est pas écrit devant une
    consonne ;
  - quand le contexte ne permet pas de choisir entre deux entrées de même forme, la première
    entrée du glossaire est retenue et le tableau signale le terme comme ambigu. Un choix fait
    d'après le contexte peut aussi être faux : le tableau indique alors l'autre sens.
- **Fichiers `.doc`.** Le lecteur a été essayé sur 471 fichiers d'exemple des projets Apache POI
  et LibreOffice : 362 sont lus (dont 47 sans texte dans le corps du document) et 109 sont
  refusés avec un message (fichiers d'avant Word 97, protégés, endommagés ou d'un autre type).
  Il a aussi été essayé sur 12 000 copies abîmées de fichiers `.doc` et `.docx`. Aucun de ces
  essais n'a arrêté la lecture brutalement. Pour les 11 documents fournis aussi au format
  `.docx`, le texte lu est le même dans les deux formats. Des documents en russe, en chinois et
  en hébreu sont lus correctement.
- **Fichiers `.doc` en arabe.** Cinq fichiers réels ont été essayés. Ce sont des pages web ou des
  fichiers XML de Word 2003 enregistrés sous le nom `.doc` : le texte de leur corps est lu en
  entier. Aucun fichier arabe au format binaire de Word 97 à 2003 n'a pu être essayé : ce cas
  n'est vérifié que par un fichier construit pour les tests.
- **Recherche d'un terme.** Les suggestions affichées pendant la saisie tiennent compte des
  accents ; la recherche lancée avec Entrée, non.
- **Contenu.** Les équivalents, les définitions et les exemples affichés sont ceux du glossaire
  chargé. L'application ne les vérifie pas.
- **Petite fenêtre.** À la taille minimale (900 × 560), les zones de texte n'affichent que deux
  ou trois lignes et le tableau des termes une seule ligne ; il faut faire défiler.

## Maquette de l'application de bureau

Maquette SVG des deux écrans du prototype. Les deux écrans sont programmés (voir ci-dessus).
Une différence avec la maquette : dans l'application, les boutons **Importer** et **Exporter**
ne figurent que sur l'écran « Texte » ; sur l'écran « Terme », ils sont remplacés par le bouton
**Ouvrir un glossaire…**.

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
