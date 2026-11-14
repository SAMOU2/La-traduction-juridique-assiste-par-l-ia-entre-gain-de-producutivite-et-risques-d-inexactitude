"""Couche d'intelligence artificielle, facultative, ajoutée par-dessus le moteur de traduction.

Le moteur et le glossaire ne dépendent pas de ce dossier : sans lui, l'application traduit avec
le glossaire, et avec lui seul.

Pour l'instant, ce dossier ne contient que le connecteur (``service``), qui sait parler à un
service d'IA « compatible OpenAI », par exemple NVIDIA Build. L'application ne l'appelle pas
encore.
"""
