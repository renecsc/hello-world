"""Conversión de unidades de visualización (RU-15, RS-15) con el units.yaml real."""

from __future__ import annotations

import pytest

from diag.core.decoding.units import UnitError
from diag.core.definitions.loader import Definitions


@pytest.mark.parametrize(
    ("value", "source", "target", "expected"),
    [
        (0.45, "V", "mV", 450.0),
        (100.0, "°C", "°F", 212.0),
        (-40.0, "°C", "°F", -40.0),
        (0.0, "°C", "K", 273.15),
        (100.0, "kPa", "bar", 1.0),
        (100.0, "kPa", "psi", 14.50377),
        (100.0, "km/h", "mph", 62.13712),
        (10.0, "g/s", "kg/h", 36.0),
        (14.5, "psi", "bar", 0.99974),  # entre dos unidades no base
    ],
)
def test_convert(
    definitions: Definitions, value: float, source: str, target: str, expected: float
) -> None:
    assert definitions.units.convert(value, source, target) == pytest.approx(expected, rel=1e-5)


def test_roundtrip(definitions: Definitions) -> None:
    units = definitions.units
    assert units.convert(units.convert(87.3, "°C", "°F"), "°F", "°C") == pytest.approx(87.3)


def test_incompatible_units(definitions: Definitions) -> None:
    with pytest.raises(UnitError, match="No se puede convertir"):
        definitions.units.convert(1.0, "V", "°C")


def test_unknown_unit(definitions: Definitions) -> None:
    with pytest.raises(UnitError, match="desconocida"):
        definitions.units.get("furlong")


def test_compatible_units(definitions: Definitions) -> None:
    assert set(definitions.units.compatible_units("V")) == {"V", "mV"}
