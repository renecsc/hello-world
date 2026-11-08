"""``diag-sim``: prueba de extremo a extremo del núcleo contra el vehículo simulado.

Uso::

    diag-sim                                  # identificación, DTCs, freeze frame y 5 s de datos
    diag-sim --duration 10 --signals engine_rpm,ltft_b1,o2_b1s1_voltage
    diag-sim --unit o2_b1s1_voltage=mV --unit coolant_temp=°F

Es una herramienta de desarrollo para validar la Fase 1 sin vehículo; la interfaz de
usuario real es la web (Svelte). Muestra en consola la tabla completa de señales
soportadas (RU-10), con mín./máx./media (RU-12) y la unidad elegida (RU-15).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from diag.config import load_settings
from diag.core.decoding.units import UnitCatalog, UnitError
from diag.core.definitions.loader import DefinitionError, Definitions, load_definitions
from diag.infra.simulator.adapter import load_sim_vehicle
from diag.services.obd2_client import Obd2Client

#: Variable de entorno que puede indicar la carpeta de configuración.
CONFIG_DIR_ENV = "DIAG_CONFIG_DIR"
#: Idioma de los nombres de señales (los textos de la UI web irán en i18n/).
LANGUAGE = "es"


@dataclass
class _Stats:
    """Estadísticas acumuladas de una señal (RU-12)."""

    count: int = 0
    total: float = 0.0
    minimum: float = field(default=float("inf"))
    maximum: float = field(default=float("-inf"))
    last: float = 0.0

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)
        self.last = value

    @property
    def mean(self) -> float:
        return self.total / self.count if self.count else float("nan")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="diag-sim", description=__doc__.split("\n")[0])
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(os.environ.get(CONFIG_DIR_ENV, "config")),
        help=f"carpeta de configuración (por defecto ./config o ${CONFIG_DIR_ENV})",
    )
    parser.add_argument("--duration", type=float, default=5.0, help="segundos de datos en vivo")
    parser.add_argument("--signals", help="señales separadas por coma (por defecto: todas)")
    parser.add_argument(
        "--unit",
        action="append",
        default=[],
        metavar="SEÑAL=UNIDAD",
        help="unidad de visualización para una señal; se puede repetir",
    )
    return parser.parse_args(argv)


def _display_units(requested: list[str], definitions: Definitions) -> dict[str, str]:
    """Valida ``--unit señal=unidad`` contra los catálogos."""
    result: dict[str, str] = {}
    for item in requested:
        key, sep, unit = item.partition("=")
        if not sep:
            raise ValueError(f"Formato inválido '{item}', use SEÑAL=UNIDAD.")
        base = definitions.pids.signal(key)[1].unit
        if unit not in definitions.units.compatible_units(base):
            options = ", ".join(definitions.units.compatible_units(base))
            raise ValueError(f"'{key}' está en {base}; unidades posibles: {options}.")
        result[key] = unit
    return result


def _fmt(value: float, base: str, shown: str, units: UnitCatalog) -> str:
    return f"{units.convert(value, base, shown):10.3f}"


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    logging.basicConfig(level=settings.logging.level, format="%(levelname)s %(name)s: %(message)s")
    definitions = load_definitions(settings.definitions.units, settings.definitions.pids)
    display = _display_units(args.unit, definitions)

    adapter = load_sim_vehicle(
        settings.simulator.vehicle,
        definitions.pids,
        response_delay_s=settings.simulator.response_delay_s,
        seed=settings.simulator.seed,
    )
    client = Obd2Client(
        adapter, definitions.pids, max_pids_per_request=settings.obd2.max_pids_per_request
    )

    info = await client.connect()
    print(f"Vehículo : {adapter.vehicle.name}")
    print(f"VIN      : {info.vin}")
    print(f"Protocolo: {info.protocol}")
    print(f"ECUs     : {', '.join(f'{e:03X}' for e in info.ecus)}\n")

    print("Códigos de avería:")
    for dtc in await client.read_all_dtcs() or []:
        print(f"  {dtc.code}  {dtc.kind.value:<9}  ECU {dtc.source_id:03X}")
    for frame in await client.read_freeze_frames():
        print(f"\nFreeze frame (ECU {frame.source_id:03X}, DTC {frame.dtc}):")
        for s in frame.values:
            name = definitions.pids.signal(s.signal)[1].name.get(LANGUAGE, s.signal)
            shown = display.get(s.signal, s.unit)
            print(f"  {name:<45}{_fmt(s.value, s.unit, shown, definitions.units)} {shown}")

    available = client.supported_signals()
    keys = args.signals.split(",") if args.signals else list(available)
    stats = {k: _Stats() for k in keys}
    end = time.monotonic() + args.duration
    reads = 0
    while time.monotonic() < end:
        for sample in await client.read_signals(keys):
            stats[sample.signal].add(sample.value)
        reads += 1

    print(f"\nDatos en vivo: {len(keys)} señales, {reads} ciclos en {args.duration:.1f} s")
    print(f"  {'Señal':<45}{'Actual':>10}{'Mín':>11}{'Máx':>11}{'Media':>11}  Unidad")
    for key in keys:
        spec = definitions.pids.signal(key)[1]
        st, shown = stats[key], display.get(key, spec.unit)
        cells = " ".join(
            _fmt(v, spec.unit, shown, definitions.units)
            for v in (st.last, st.minimum, st.maximum, st.mean)
        )
        print(f"  {spec.name.get(LANGUAGE, key):<45}{cells}  {shown}")
    await client.disconnect()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de ``diag-sim``. Devuelve el código de salida."""
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (DefinitionError, UnitError, ValueError, KeyError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
