"""Conversión de unidades de visualización (RU-15, RS-15).

Las unidades se definen en ``definitions/units.yaml``, agrupadas por **magnitud**
(tensión, temperatura, presión...). Cada magnitud tiene una unidad **base** y cada unidad
se relaciona con la base mediante una transformación lineal::

    valor_en_unidad = valor_en_base * factor + offset

Así se cubren escalas (V → mV: ``factor = 1000``) y desplazamientos (°C → °F:
``factor = 1.8, offset = 32``). Convertir entre dos unidades cualesquiera de la misma
magnitud pasa por la base.

Regla de diseño (RS-15): los datos se adquieren y almacenan siempre en la unidad de la
definición de la señal; la conversión se aplica solo al presentar o exportar.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class UnitError(ValueError):
    """Unidad desconocida o conversión entre magnitudes distintas."""


@dataclass(frozen=True, slots=True)
class UnitDef:
    """Una unidad y su relación con la unidad base de su magnitud.

    Attributes:
        symbol: Símbolo, p. ej. ``mV``.
        quantity: Magnitud a la que pertenece, p. ej. ``voltage``.
        factor: Multiplicador desde la base. Nunca cero.
        offset: Desplazamiento desde la base.
    """

    symbol: str
    quantity: str
    factor: float
    offset: float = 0.0

    def from_base(self, value: float) -> float:
        """Convierte un valor expresado en la unidad base a esta unidad."""
        return value * self.factor + self.offset

    def to_base(self, value: float) -> float:
        """Convierte un valor expresado en esta unidad a la unidad base."""
        return (value - self.offset) / self.factor


class UnitCatalog:
    """Catálogo de unidades conocidas, construido a partir de ``units.yaml``.

    Args:
        units: Todas las unidades, indexadas por símbolo.
        base_units: Unidad base de cada magnitud, indexada por magnitud.

    Raises:
        UnitError: Si los datos son incoherentes (factor cero, base inexistente...).
    """

    def __init__(self, units: Mapping[str, UnitDef], base_units: Mapping[str, str]) -> None:
        for unit in units.values():
            if unit.factor == 0:
                raise UnitError(f"La unidad '{unit.symbol}' tiene factor 0.")
        for quantity, base in base_units.items():
            base_def = units.get(base)
            if base_def is None or base_def.quantity != quantity:
                raise UnitError(f"La base '{base}' de '{quantity}' no está en esa magnitud.")
        self._units = dict(units)
        self._base_units = dict(base_units)

    def get(self, symbol: str) -> UnitDef:
        """Devuelve la definición de una unidad.

        Raises:
            UnitError: Si la unidad no existe.
        """
        try:
            return self._units[symbol]
        except KeyError:
            raise UnitError(f"Unidad desconocida: '{symbol}'.") from None

    def __contains__(self, symbol: object) -> bool:
        return symbol in self._units

    def compatible_units(self, symbol: str) -> list[str]:
        """Unidades a las que se puede convertir ``symbol`` (incluida ella misma).

        Sirve para poblar el selector de unidad de la UI.
        """
        quantity = self.get(symbol).quantity
        return [s for s, u in self._units.items() if u.quantity == quantity]

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convierte ``value`` de ``from_unit`` a ``to_unit``.

        Raises:
            UnitError: Si alguna unidad no existe o pertenecen a magnitudes distintas.
        """
        if from_unit == to_unit:
            return value
        source, target = self.get(from_unit), self.get(to_unit)
        if source.quantity != target.quantity:
            raise UnitError(
                f"No se puede convertir '{from_unit}' ({source.quantity}) a "
                f"'{to_unit}' ({target.quantity})."
            )
        return target.from_base(source.to_base(value))
