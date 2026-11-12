"""Lance le traducteur juridique.

Dans VS Code : ouvrir ce fichier, puis cliquer sur « Exécuter le fichier Python » (▶).
Dans un terminal : python main.py
"""

import sys

from traducteur.application import main

if __name__ == "__main__":
    sys.exit(main())
