"""Couche d'intelligence artificielle, facultative, ajoutée par-dessus le moteur de traduction.

Le moteur et le glossaire ne dépendent pas de ce dossier : sans lui, l'application traduit avec
le glossaire, et avec lui seul.

Ce dossier contient :

* ``service`` : le connecteur, qui sait parler à un service d'IA « compatible OpenAI », par exemple
  NVIDIA Build ;
* ``essai`` : l'essai de la connexion, en deux temps (le service répond-il ? le modèle répond-il ?) ;
* ``lecture`` : la lecture de ce qu'un modèle a écrit, sans la « réflexion » qui précède sa réponse.

Aucun de ces modules ne connaît l'interface graphique. L'IA est éteinte au départ. L'application
ne les appelle que depuis l'écran « Paramètres », partie « Intelligence artificielle », quand
l'utilisateur a allumé l'IA et clique sur « Tester la connexion ». L'IA ne traduit encore rien.

Une seule exception, hors de l'usage courant : le contrôle de l'installation (``controle.py``),
lancé avec l'option ``--controle-connexion``, demande au service proposé par défaut la liste de ses
modèles, sans clé et sans aucun texte.
"""
