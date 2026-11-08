"""Decodificación de los bytes de un PID en valores físicos, y su inversa.

- :func:`decode_pid` se usa al leer un vehículo: bytes → valores de cada señal.
- :func:`encode_pid` se usa en el **simulador**: valores físicos → bytes.

La inversa no se escribe a mano en las definiciones (sería duplicar información y una
fuente de errores). Se obtiene a partir de la propia fórmula, con esta hipótesis, que
cumplen todas las fórmulas de SAE J1979 de este proyecto:

    La fórmula es **lineal** en el entero formado por sus bytes, en orden big-endian.
    Ej.: ``(A*256 + B)/4`` es lineal en ``raw = A<<8 | B``.

:func:`linear_inverse` comprueba esa hipótesis en varios puntos; si no se cumple, la señal
no es simulable y se informa al cargar el vehículo simulado, no en mitad de la ejecución.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from diag.core.decoding.formula import BYTE_VARIABLE_NAMES, Formula, byte_variables
from diag.core.definitions.schema import PidSpec, SignalSpec

_BITS_PER_BYTE = 8
#: Tolerancia relativa al comprobar la linealidad (errores de coma flotante).
_LINEARITY_TOLERANCE = 1e-9
#: Fracciones del rango crudo donde se verifica la linealidad.
_LINEARITY_PROBES = (0.0, 0.25, 0.5, 0.75, 1.0)


class EncodingError(ValueError):
    """La fórmula no es invertible con la hipótesis lineal."""


def decode_pid(spec: PidSpec, data: bytes) -> dict[str, float]:
    """Calcula el valor físico de cada señal de un PID.

    Args:
        spec: Definición del PID.
        data: Bytes de datos (sin el número de PID).

    Returns:
        ``{clave_señal: valor}`` en la unidad base de cada señal.

    Raises:
        ValueError: Si la cantidad de bytes no coincide con la definición.
        FormulaEvaluationError: Si una fórmula falla al evaluarse.
    """
    if len(data) != spec.bytes:
        raise ValueError(f"PID {spec.id}: se esperaban {spec.bytes} bytes, llegaron {len(data)}.")
    variables = byte_variables(data)
    return {s.key: s.compiled_formula.evaluate(variables) for s in spec.signals}


@dataclass(frozen=True, slots=True)
class LinearInverse:
    """Inversa de una fórmula lineal: ``raw = round((valor - offset) / slope)``.

    Attributes:
        byte_names: Variables que forman el entero crudo, de más a menos significativa.
        slope: Pendiente de la fórmula respecto al entero crudo.
        offset: Valor de la fórmula cuando el entero crudo es 0.
        raw_max: Máximo entero crudo representable.
    """

    byte_names: tuple[str, ...]
    slope: float
    offset: float
    raw_max: int

    def encode(self, value: float) -> dict[str, int]:
        """Valor físico → bytes, saturando al rango representable."""
        raw = round((value - self.offset) / self.slope)
        raw = max(0, min(self.raw_max, raw))
        count = len(self.byte_names)
        return {
            name: (raw >> (_BITS_PER_BYTE * (count - 1 - i))) & 0xFF
            for i, name in enumerate(self.byte_names)
        }


def linear_inverse(formula: Formula) -> LinearInverse:
    """Obtiene la inversa lineal de una fórmula.

    Raises:
        EncodingError: Si la fórmula no usa variables de bytes contiguas desde la primera
            que usa, o no es lineal en el entero crudo.
    """
    names = tuple(n for n in BYTE_VARIABLE_NAMES if n in formula.variables)
    if not names:
        raise EncodingError(f"'{formula.expression}' no depende de ningún byte.")
    first = BYTE_VARIABLE_NAMES.index(names[0])
    if names != BYTE_VARIABLE_NAMES[first : first + len(names)]:
        raise EncodingError(f"'{formula.expression}' usa bytes no contiguos.")

    raw_max = (1 << (_BITS_PER_BYTE * len(names))) - 1

    def evaluate(raw: int) -> float:
        count = len(names)
        values = {
            n: float((raw >> (_BITS_PER_BYTE * (count - 1 - i))) & 0xFF)
            for i, n in enumerate(names)
        }
        return formula.evaluate(values)

    offset = evaluate(0)
    slope = (evaluate(raw_max) - offset) / raw_max
    if slope == 0:
        raise EncodingError(f"'{formula.expression}' es constante.")
    for fraction in _LINEARITY_PROBES:
        raw = round(raw_max * fraction)
        expected = offset + slope * raw
        if abs(evaluate(raw) - expected) > _LINEARITY_TOLERANCE * max(1.0, abs(expected)):
            raise EncodingError(f"'{formula.expression}' no es lineal; no se puede simular.")
    return LinearInverse(byte_names=names, slope=slope, offset=offset, raw_max=raw_max)


class PidEncoder:
    """Codificador de un PID completo a partir de los valores de sus señales.

    Se construye una vez por PID (al cargar el vehículo simulado), validando que todas sus
    señales sean invertibles.

    Raises:
        EncodingError: Si alguna señal no es invertible.
    """

    def __init__(self, spec: PidSpec) -> None:
        self.spec = spec
        self._inverses: dict[str, tuple[SignalSpec, LinearInverse]] = {
            s.key: (s, linear_inverse(s.compiled_formula)) for s in spec.signals
        }

    def encode(self, values: Mapping[str, float]) -> bytes:
        """Construye los bytes del PID.

        Args:
            values: Valor físico de cada señal. Las que falten quedan con sus bytes en 0.
        """
        data = dict.fromkeys(BYTE_VARIABLE_NAMES[: self.spec.bytes], 0)
        for key, value in values.items():
            if key in self._inverses:
                data.update(self._inverses[key][1].encode(value))
        return bytes(data[name] for name in BYTE_VARIABLE_NAMES[: self.spec.bytes])
