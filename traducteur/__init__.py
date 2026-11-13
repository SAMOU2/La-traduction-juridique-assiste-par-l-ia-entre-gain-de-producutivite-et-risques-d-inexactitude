"""Traducteur juridique français ⇄ arabe — prototype.

Le paquet est organisé en deux parties :

* le « moteur », sans interface graphique : ``langues`` (normalisation du
  texte), ``glossaire`` (lecture du fichier CSV et recherche des termes),
  ``segmentation`` et ``traduction`` (traduction d'un texte) et ``documents``
  (import et export des fichiers .txt et .docx) ;
* l'interface de bureau (PySide6 / Qt), dans le sous-paquet ``interface``.
"""

__version__ = "0.5.2"
NOM_APPLICATION = "Traducteur juridique"
