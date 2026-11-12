"""Traducteur juridique français ⇄ arabe — prototype.

Le paquet est organisé en deux parties :

* le « moteur », sans interface graphique : ``langues`` (normalisation du
  texte) et ``glossaire`` (lecture du fichier CSV et recherche des termes) ;
* l'interface de bureau (PySide6 / Qt), dans le sous-paquet ``interface``.
"""

__version__ = "0.1.0"
NOM_APPLICATION = "Traducteur juridique"
