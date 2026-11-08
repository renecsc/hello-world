"""Carga y validación de archivos de definición (RS-10, RS-12, RNF-10).

Responsabilidades:

1. Leer YAML de forma **segura** (``yaml.SafeLoader``: no construye objetos Python).
2. Validar contra los esquemas de :mod:`diag.core.definitions.schema`.
3. Hacer las validaciones **entre archivos** (p. ej. que cada unidad usada por una señal
   exista en ``units.yaml``).
4. Informar cada error con **archivo, línea y ruta** dentro del documento, para que
   corregir una definición no requiera leer código (RS-12).
5. Construir catálogos de solo lectura listos para usar por el resto del sistema.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from diag.core.decoding.units import UnitCatalog, UnitDef
from diag.core.definitions.schema import PidsFile, PidSpec, SignalSpec, UnitsFile

_Location = tuple[str | int, ...]
_Model = TypeVar("_Model", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class DefinitionIssue:
    """Un problema concreto en un archivo de definición."""

    path: Path
    line: int | None
    location: str
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else str(self.path)
        return f"{where}: {self.location or '(raíz)'}: {self.message}"


class DefinitionError(ValueError):
    """Uno o más archivos de definición son inválidos.

    Attributes:
        issues: Lista de problemas encontrados, cada uno con archivo y línea.
    """

    def __init__(self, issues: list[DefinitionIssue]) -> None:
        self.issues = issues
        detail = "\n".join(f"  - {issue}" for issue in issues)
        super().__init__(f"Definiciones inválidas ({len(issues)} problema/s):\n{detail}")


# --- Lectura de YAML con números de línea --------------------------------------------------


def _line_map(node: yaml.Node, location: _Location = ()) -> Iterator[tuple[_Location, int]]:
    """Recorre el árbol YAML y produce ``(ruta, línea)`` para cada nodo.

    La ruta usa claves (``str``) para mapas e índices (``int``) para listas: el mismo
    formato que ``pydantic`` usa en ``ValidationError.errors()[i]["loc"]``.
    """
    yield location, node.start_mark.line + 1  # PyYAML numera desde 0
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            yield from _line_map(value_node, (*location, str(key_node.value)))
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            yield from _line_map(item, (*location, index))


def _read_yaml(path: Path) -> tuple[Any, dict[_Location, int]]:
    """Lee un YAML y devuelve ``(datos, mapa ruta→línea)``.

    Raises:
        DefinitionError: Si el archivo no existe o no es YAML válido.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DefinitionError([DefinitionIssue(path, None, "", f"no se pudo leer: {exc}")]) from exc
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        data = yaml.load(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else None
        raise DefinitionError([DefinitionIssue(path, line, "", f"YAML inválido: {exc}")]) from exc
    lines = dict(_line_map(node)) if node is not None else {}
    return data, lines


def _line_for(location: _Location, lines: Mapping[_Location, int]) -> int | None:
    """Línea del nodo más profundo conocido que contiene ``location``."""
    for end in range(len(location), -1, -1):
        line = lines.get(location[:end])
        if line is not None:
            return line
    return None


def validate_file(model: type[_Model], path: Path) -> tuple[_Model, dict[_Location, int]]:
    """Lee un YAML y lo valida contra ``model``.

    Es la vía común para cargar **cualquier** archivo de definición (también los de otras
    capas, como los vehículos del simulador), para que todos informen errores igual.

    Returns:
        ``(modelo_validado, mapa ruta→línea)``; el mapa sirve para validaciones posteriores.

    Raises:
        DefinitionError: Con archivo, línea y ruta de cada problema.
    """
    data, lines = _read_yaml(path)
    try:
        return model.model_validate(data), lines
    except ValidationError as exc:
        issues = [
            DefinitionIssue(
                path=path,
                line=_line_for(tuple(err["loc"]), lines),
                location=".".join(str(part) for part in err["loc"]),
                message=err["msg"],
            )
            for err in exc.errors()
        ]
        raise DefinitionError(issues) from exc


# --- Catálogos ---------------------------------------------------------------------------


def load_units(path: Path) -> UnitCatalog:
    """Carga ``units.yaml`` y construye el catálogo de unidades.

    Raises:
        DefinitionError: Si el archivo es inválido.
    """
    spec, _ = validate_file(UnitsFile, path)
    units = {
        symbol: UnitDef(symbol=symbol, quantity=quantity, factor=u.factor, offset=u.offset)
        for quantity, q in spec.quantities.items()
        for symbol, u in q.units.items()
    }
    return UnitCatalog(units, {quantity: q.base for quantity, q in spec.quantities.items()})


class PidCatalog:
    """Catálogo de solo lectura de los PIDs del servicio 01 y sus señales.

    Args:
        pids: PIDs validados.
    """

    def __init__(self, pids: list[PidSpec]) -> None:
        self._by_pid = {p.pid: p for p in pids}
        self._signals = {s.key: (p, s) for p in pids for s in p.signals}

    def pid(self, pid: int) -> PidSpec | None:
        """Definición de un PID, o ``None`` si no está definido."""
        return self._by_pid.get(pid)

    def signal(self, key: str) -> tuple[PidSpec, SignalSpec]:
        """PID y definición de una señal por su clave.

        Raises:
            KeyError: Si la señal no existe.
        """
        return self._signals[key]

    @property
    def pids(self) -> list[PidSpec]:
        """Todos los PIDs, en el orden del archivo."""
        return list(self._by_pid.values())

    @property
    def signal_keys(self) -> list[str]:
        """Claves de todas las señales, en el orden del archivo."""
        return list(self._signals)

    def data_lengths(self) -> dict[int, int]:
        """Bytes de datos de cada PID. Lo usa el analizador de respuestas multi-PID."""
        return {pid: spec.bytes for pid, spec in self._by_pid.items()}


def load_pids(path: Path, units: UnitCatalog) -> PidCatalog:
    """Carga ``obd2/pids.yaml`` y comprueba que todas las unidades existan.

    Args:
        path: Ruta del archivo.
        units: Catálogo de unidades ya cargado, para la validación cruzada.

    Raises:
        DefinitionError: Si el archivo es inválido o usa unidades desconocidas.
    """
    spec, lines = validate_file(PidsFile, path)
    issues = [
        DefinitionIssue(
            path=path,
            line=_line_for(("pids", i, "signals", j, "unit"), lines),
            location=f"pids.{i}.signals.{j}.unit",
            message=f"unidad '{signal.unit}' no definida en units.yaml",
        )
        for i, pid in enumerate(spec.pids)
        for j, signal in enumerate(pid.signals)
        if signal.unit not in units
    ]
    if issues:
        raise DefinitionError(issues)
    return PidCatalog(spec.pids)


@dataclass(frozen=True, slots=True)
class Definitions:
    """Conjunto de definiciones cargadas que necesita la aplicación."""

    units: UnitCatalog
    pids: PidCatalog


def load_definitions(units_path: Path, pids_path: Path) -> Definitions:
    """Carga todas las definiciones en el orden correcto (las unidades primero).

    Las rutas vienen de la configuración (``config/default.yaml``), nunca del código.

    Raises:
        DefinitionError: Si alguna definición es inválida.
    """
    units = load_units(units_path)
    return Definitions(units=units, pids=load_pids(pids_path, units))
