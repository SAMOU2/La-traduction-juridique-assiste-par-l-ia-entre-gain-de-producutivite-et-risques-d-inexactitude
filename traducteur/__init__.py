"""Traducteur juridique français ⇄ arabe — prototype.

Le paquet est organisé en trois parties :

* le « moteur », sans interface graphique : ``langues`` (normalisation du
  texte), ``glossaire`` (lecture du fichier CSV et recherche des termes),
  ``segmentation`` et ``traduction`` (traduction d'un texte) et ``documents``
  (import et export des fichiers .txt et .docx) ;
* l'interface de bureau (PySide6 / Qt), dans le sous-paquet ``interface`` ;
* la couche d'intelligence artificielle, facultative, dans le sous-paquet
  ``ia``. Le moteur et l'interface ne l'appellent pas encore.
"""

__version__ = "0.5.3"
NOM_APPLICATION = "Traducteur juridique"
