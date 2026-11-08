"""Generadores de valores para las señales del vehículo simulado.

Cada señal simulada se describe en el YAML del vehículo con un generador, p. ej.::

    engine_rpm: { generator: sine, offset: 800, amplitude: 40, period_s: 5 }

Los generadores son funciones del tiempo: ``value(t)`` devuelve el valor físico en el
instante ``t`` (segundos desde el inicio de la simulación). Los aleatorios usan un
``random.Random`` propio con semilla configurable, para que las pruebas sean reproducibles.

Para añadir un generador: crear su modelo de configuración (con ``generator: Literal[...]``),
implementar ``build()`` y agregarlo a la unión :data:`GeneratorSpec`.
"""

from __future__ import annotations

import math
import random
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Generator(Protocol):
    """Fuente de valores de una señal simulada."""

    def value(self, t: float) -> float:
        """Valor físico en el instante ``t`` (segundos desde el inicio)."""
        ...


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    noise: float = Field(default=0.0, ge=0)
    """Desviación estándar de ruido gaussiano sumado al valor (0 = sin ruido)."""


class _Noisy:
    """Envoltorio que suma ruido gaussiano a otro generador."""

    def __init__(self, inner: Generator, std: float, rng: random.Random) -> None:
        self._inner, self._std, self._rng = inner, std, rng

    def value(self, t: float) -> float:
        return self._inner.value(t) + self._rng.gauss(0.0, self._std)


def _with_noise(generator: Generator, std: float, rng: random.Random) -> Generator:
    return _Noisy(generator, std, rng) if std > 0 else generator


class ConstantSpec(_Spec):
    """Valor fijo."""

    generator: Literal["constant"]
    value: float

    def build(self, rng: random.Random) -> Generator:
        """Crea el generador."""
        constant = self.value

        class _Constant:
            def value(self, t: float) -> float:
                return constant

        return _with_noise(_Constant(), self.noise, rng)


class SineSpec(_Spec):
    """Senoide: ``offset + amplitude * sin(2π (t + phase_s) / period_s)``.

    Útil para señales que oscilan, como una sonda O2 (0,1-0,9 V) o un ralentí inestable.
    """

    generator: Literal["sine"]
    offset: float
    amplitude: float
    period_s: float = Field(gt=0)
    phase_s: float = 0.0

    def build(self, rng: random.Random) -> Generator:
        """Crea el generador."""
        spec = self

        class _Sine:
            def value(self, t: float) -> float:
                angle = 2 * math.pi * (t + spec.phase_s) / spec.period_s
                return spec.offset + spec.amplitude * math.sin(angle)

        return _with_noise(_Sine(), self.noise, rng)


class RampSpec(_Spec):
    """Rampa de ``start`` a ``end`` en ``duration_s`` y luego constante.

    Útil para un calentamiento de motor (refrigerante de 20 °C a 90 °C).
    """

    generator: Literal["ramp"]
    start: float
    end: float
    duration_s: float = Field(gt=0)

    def build(self, rng: random.Random) -> Generator:
        """Crea el generador."""
        spec = self

        class _Ramp:
            def value(self, t: float) -> float:
                progress = min(1.0, max(0.0, t / spec.duration_s))
                return spec.start + (spec.end - spec.start) * progress

        return _with_noise(_Ramp(), self.noise, rng)


class RandomWalkSpec(_Spec):
    """Paseo aleatorio acotado: cada ``interval_s`` el valor cambia hasta ``±step``."""

    generator: Literal["random_walk"]
    start: float
    step: float = Field(gt=0)
    min: float
    max: float
    interval_s: float = Field(default=0.1, gt=0)

    @model_validator(mode="after")
    def _bounds(self) -> RandomWalkSpec:
        if not self.min <= self.start <= self.max:
            raise ValueError("start debe estar entre min y max")
        return self

    def build(self, rng: random.Random) -> Generator:
        """Crea el generador."""
        spec = self

        class _RandomWalk:
            def __init__(self) -> None:
                self._value = spec.start
                self._last_step = 0

            def value(self, t: float) -> float:
                # Avanza tantos pasos como intervalos hayan transcurrido desde la última lectura.
                target_step = int(t / spec.interval_s)
                for _ in range(max(0, target_step - self._last_step)):
                    self._value += rng.uniform(-spec.step, spec.step)
                    self._value = min(spec.max, max(spec.min, self._value))
                self._last_step = max(self._last_step, target_step)
                return self._value

        return _with_noise(_RandomWalk(), self.noise, rng)


#: Unión discriminada por el campo ``generator``.
GeneratorSpec = Annotated[
    ConstantSpec | SineSpec | RampSpec | RandomWalkSpec, Field(discriminator="generator")
]
