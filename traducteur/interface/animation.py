"""Allumage progressif des étapes : chaque étape s'allume à son tour, avec un halo passager.

L'enchaînement ① Terme → … → ⑤ Ressources, et les étapes du traitement d'un texte, sont
dessinés par plusieurs composants. Tous confient le rythme de l'allumage à ``Allumage`` :
le composant donne les étapes à allumer, puis se redessine à chaque signal ``change`` en
lisant le niveau (de 0 : éteinte, à 1 : allumée) et le halo de chaque étape.

Les animations se désactivent d'un coup avec ``definir_actives(False)`` (réglage de
l'application, tests) : chaque étape prend alors tout de suite son état final.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal

_actives = True


def definir_actives(actives: bool) -> None:
    """Active ou désactive les animations de toute l'application."""
    global _actives  # réglage unique, lu par tous les composants
    _actives = bool(actives)


def actives() -> bool:
    return _actives


class Allumage(QObject):
    """Rythme de l'allumage d'une suite d'étapes."""

    #: Les niveaux ont changé : le composant doit se redessiner.
    change = Signal()
    #: Toutes les étapes ont pris leur état final.
    termine = Signal()

    #: Délai entre l'allumage de deux étapes voisines, en millisecondes.
    INTERVALLE = 150
    #: Durée de la montée d'une étape, de éteinte à allumée.
    MONTEE = 220
    #: Durée du halo qui entoure une étape au moment où elle s'allume.
    HALO = 620
    #: Délai entre deux images.
    IMAGE = 16

    def __init__(self, nombre: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cibles = [False] * nombre
        self._en_cours = False
        self._horloge = QElapsedTimer()
        self._images = QTimer(self)
        self._images.setInterval(self.IMAGE)
        self._images.timeout.connect(self._avancer)

    # ------------------------------------------------------------------ commandes
    def definir(self, etapes: Sequence[bool], *, animer: bool = True) -> None:
        """Fixe les étapes à allumer (vrai) et celles qui restent éteintes (faux).

        Avec ``animer``, les étapes s'allument l'une après l'autre, dans l'ordre ; sinon, ou si
        les animations sont désactivées, elles prennent tout de suite leur état final.
        """
        self._cibles = [bool(etape) for etape in etapes]
        if animer and _actives and any(self._cibles):
            self._en_cours = True
            self._horloge.start()
            self._images.start()
        else:
            self._arreter()
        self.change.emit()

    def terminer(self) -> None:
        """Passe tout de suite à l'état final."""
        if self._en_cours:
            self._arreter()
            self.change.emit()

    # ------------------------------------------------------------------ lecture
    def allumees(self) -> list[bool]:
        """Pour chaque étape : vrai si elle est (ou sera, à la fin de l'animation) allumée."""
        return list(self._cibles)

    def en_cours(self) -> bool:
        return self._en_cours

    def niveau(self, rang: int) -> float:
        """Niveau d'allumage d'une étape : 0 (éteinte) à 1 (allumée)."""
        if not self._cibles[rang]:
            return 0.0
        if not self._en_cours:
            return 1.0
        avance = (self._horloge.elapsed() - rang * self.INTERVALLE) / self.MONTEE
        avance = min(max(avance, 0.0), 1.0)
        return 1.0 - (1.0 - avance) ** 2  # départ vif, arrivée douce

    def halo(self, rang: int) -> float:
        """Intensité du halo d'une étape : 0 (aucun) à 1 ; il apparaît vite et s'efface lentement."""
        if not self._cibles[rang] or not self._en_cours:
            return 0.0
        avance = (self._horloge.elapsed() - rang * self.INTERVALLE) / self.HALO
        if avance <= 0.0 or avance >= 1.0:
            return 0.0
        return avance / 0.2 if avance < 0.2 else (1.0 - avance) / 0.8

    def duree(self) -> int:
        """Durée totale de l'animation, en millisecondes."""
        return (len(self._cibles) - 1) * self.INTERVALLE + max(self.MONTEE, self.HALO)

    # ------------------------------------------------------------------ interne
    def _avancer(self) -> None:
        if self._horloge.elapsed() >= self.duree():
            self._arreter()
        self.change.emit()

    def _arreter(self) -> None:
        etait_en_cours = self._en_cours
        self._en_cours = False
        self._images.stop()
        if etait_en_cours:
            self.termine.emit()


__all__ = ["Allumage", "actives", "definir_actives"]
