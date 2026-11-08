"""Fixtures comunes: rutas del proyecto y definiciones reales.

Las pruebas usan los **mismos** archivos de ``definitions/`` que la aplicación, así un
error en una definición rompe las pruebas antes de llegar a un vehículo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diag.core.definitions.loader import Definitions, load_definitions

ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS = ROOT / "definitions"
SIM_VEHICLE = DEFINITIONS / "vehicles" / "sim" / "gasolina_4cil_toma_aire.yaml"


@pytest.fixture(scope="session")
def definitions() -> Definitions:
    """Unidades y PIDs reales del proyecto."""
    return load_definitions(DEFINITIONS / "units.yaml", DEFINITIONS / "obd2" / "pids.yaml")


class FakeClock:
    """Reloj manual para pruebas deterministas: el tiempo solo avanza con ``advance``."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
