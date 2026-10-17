"""Aria C: coordonatele accidentelor („Harta pietonului – Iași”, persoana 3).

Intrare: `accidents.json` de la persoana 2 (`loc_text` brut, coordonate null).
Ieșire: `coordonate/out/<data_mode>/accidents.json`, cu `lat`, `lon`,
`precizie_loc`, `in_iasi` completate, plus `raport_coordonate.json` cu metoda,
obiectele OSM folosite și ce rămâne de verificat manual.

Nicio coordonată nu e inventată: totul vine dintr-un index OSM local construit
cu osmnx (`python -m coordonate descarca`) și e trasabil la un obiect OSM.
Rezolvarea nu face cereri în rețea.
"""

from __future__ import annotations

__version__ = "0.2.0"
