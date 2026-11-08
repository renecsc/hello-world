"""Esquemas de los archivos de definición (RS-10, RS-12, RS-15).

Cada archivo YAML de ``definitions/`` se valida contra uno de estos modelos ``pydantic``.
Las reglas de validación de *un solo archivo* están aquí; las que cruzan archivos
(p. ej. "la unidad de una señal existe en ``units.yaml``") están en ``loader.py``.

Todos los modelos prohíben campos desconocidos (``extra="forbid"``) para detectar errores
de tipeo en las definiciones, que de otro modo se ignorarían en silencio.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StringConstraints, model_validator

from diag.core.decoding.formula import Formula, FormulaError, byte_variable_names

SUPPORTED_SCHEMA_VERSION = 1
"""Versión de esquema que entiende esta versión del software."""

#: Texto por idioma, p. ej. ``{"es": "RPM del motor", "en": "Engine speed"}``.
LocalizedText = Annotated[dict[str, str], Field(min_length=1)]

#: Clave estable de una señal: minúsculas, dígitos y guion bajo, empezando por letra.
SignalKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]

#: PID en hexadecimal de 2 dígitos, p. ej. ``"0C"``.
HexPid = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{2}$")]


class _StrictModel(BaseModel):
    """Base común: inmutable y sin campos extra."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _VersionedFile(_StrictModel):
    """Base de los archivos de definición: todos declaran su versión de esquema."""

    schema_version: Literal[1]


# --- units.yaml --------------------------------------------------------------------------


class UnitSpec(_StrictModel):
    """Relación de una unidad con la base: ``valor = base * factor + offset``."""

    factor: float
    offset: float = 0.0

    @model_validator(mode="after")
    def _factor_not_zero(self) -> UnitSpec:
        if self.factor == 0:
            raise ValueError("factor no puede ser 0")
        return self


class QuantitySpec(_StrictModel):
    """Una magnitud física (tensión, temperatura...) y sus unidades."""

    name: LocalizedText
    base: str
    units: dict[str, UnitSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _base_is_identity(self) -> QuantitySpec:
        base = self.units.get(self.base)
        if base is None:
            raise ValueError(f"la unidad base '{self.base}' no está en 'units'")
        if (base.factor, base.offset) != (1.0, 0.0):
            raise ValueError(f"la unidad base '{self.base}' debe tener factor 1 y offset 0")
        return self


class UnitsFile(_VersionedFile):
    """Contenido de ``definitions/units.yaml``."""

    quantities: dict[str, QuantitySpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _symbols_unique(self) -> UnitsFile:
        seen: dict[str, str] = {}
        for quantity, spec in self.quantities.items():
            for symbol in spec.units:
                if symbol in seen:
                    raise ValueError(
                        f"la unidad '{symbol}' aparece en '{seen[symbol]}' y en '{quantity}'"
                    )
                seen[symbol] = quantity
        return self


# --- obd2/pids.yaml ----------------------------------------------------------------------


class ValueRange(_StrictModel):
    """Rango físico [min, max] que puede tomar una señal."""

    min: float
    max: float

    @model_validator(mode="after")
    def _ordered(self) -> ValueRange:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) mayor que max ({self.max})")
        return self


class SignalSpec(_StrictModel):
    """Una señal extraída de los bytes de un PID.

    La fórmula se valida y compila al cargar; la versión compilada queda en
    :attr:`compiled_formula`. Las variables permitidas dependen de los bytes del PID, por
    eso la compilación la hace :class:`PidSpec`.
    """

    key: SignalKey
    name: LocalizedText
    formula: str = Field(min_length=1)
    unit: str
    range: ValueRange
    category: SignalKey

    _compiled: Formula | None = PrivateAttr(default=None)

    @property
    def compiled_formula(self) -> Formula:
        """Fórmula compilada. Siempre disponible en un ``SignalSpec`` cargado vía ``PidSpec``."""
        if self._compiled is None:  # pragma: no cover - solo por uso incorrecto
            raise RuntimeError(f"Fórmula de '{self.key}' sin compilar.")
        return self._compiled


class PidSpec(_StrictModel):
    """Un PID del servicio 01 y las señales que contiene."""

    id: HexPid
    bytes: int = Field(ge=1, le=8)
    signals: list[SignalSpec] = Field(min_length=1)

    @property
    def pid(self) -> int:
        """Valor numérico del PID."""
        return int(self.id, 16)

    @model_validator(mode="after")
    def _compile_formulas(self) -> PidSpec:
        # Las variables permitidas (A, B, ...) dependen de cuántos bytes tiene el PID.
        allowed = byte_variable_names(self.bytes)
        for signal in self.signals:
            try:
                signal._compiled = Formula.parse(signal.formula, allowed)
            except FormulaError as exc:
                # El error se informa en la ruta del PID (aquí se conocen sus bytes); se
                # antepone la clave de la señal para ubicar la fórmula exacta.
                raise ValueError(f"señal '{signal.key}': {exc}") from exc
        return self


class PidsFile(_VersionedFile):
    """Contenido de ``definitions/obd2/pids.yaml``."""

    pids: list[PidSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> PidsFile:
        pid_ids = [p.pid for p in self.pids]
        duplicated_pids = {f"{p:02X}" for p in pid_ids if pid_ids.count(p) > 1}
        if duplicated_pids:
            raise ValueError(f"PIDs duplicados: {', '.join(sorted(duplicated_pids))}")
        keys = [s.key for p in self.pids for s in p.signals]
        duplicated_keys = {k for k in keys if keys.count(k) > 1}
        if duplicated_keys:
            raise ValueError(f"claves de señal duplicadas: {', '.join(sorted(duplicated_keys))}")
        return self
