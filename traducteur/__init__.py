"""Traducteur juridique français ⇄ arabe — prototype.

Le paquet est organisé en trois parties :

* le « moteur », sans interface graphique : ``langues`` (normalisation du
  texte), ``glossaire`` (lecture du fichier CSV et recherche des termes),
  ``segmentation`` et ``traduction`` (traduction d'un texte) et ``documents``
  (import et export des fichiers .txt et .docx) ;
* l'interface de bureau (PySide6 / Qt), dans le sous-paquet ``interface`` ;
* la couche d'intelligence artificielle, facultative, dans le sous-paquet
  ``ia``. Le moteur ne l'appelle pas. L'interface ne l'appelle que depuis
  l'écran « Paramètres », pour régler et essayer la connexion : l'IA ne
  traduit encore rien.
"""

__version__ = "0.6.0"
NOM_APPLICATION = "Traducteur juridique"
