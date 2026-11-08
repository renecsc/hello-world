"""Decodificación de PIDs y su inversa (usada por el simulador)."""

from __future__ import annotations

import pytest

from diag.core.decoding.formula import Formula
from diag.core.decoding.signals import EncodingError, PidEncoder, decode_pid, linear_inverse
from diag.core.definitions.loader import Definitions


def test_decode_rpm(definitions: Definitions) -> None:
    spec = definitions.pids.pid(0x0C)
    assert spec is not None
    assert decode_pid(spec, b"\x1a\xf8") == {"engine_rpm": 1726.0}


def test_decode_wrong_length(definitions: Definitions) -> None:
    spec = definitions.pids.pid(0x0C)
    assert spec is not None
    with pytest.raises(ValueError):
        decode_pid(spec, b"\x1a")


def test_every_defined_pid_roundtrips(definitions: Definitions) -> None:
    """Toda señal de pids.yaml debe ser simulable y volver al valor original (± resolución)."""
    for spec in definitions.pids.pids:
        encoder = PidEncoder(spec)
        values = {s.key: (s.range.min + s.range.max) / 2 for s in spec.signals}
        decoded = decode_pid(spec, encoder.encode(values))
        for signal in spec.signals:
            resolution = linear_inverse(signal.compiled_formula).slope
            assert decoded[signal.key] == pytest.approx(values[signal.key], abs=abs(resolution))


def test_encode_saturates(definitions: Definitions) -> None:
    spec = definitions.pids.pid(0x05)  # refrigerante: -40 .. 215 °C
    assert spec is not None
    encoder = PidEncoder(spec)
    assert decode_pid(spec, encoder.encode({"coolant_temp": 999})) == {"coolant_temp": 215.0}
    assert decode_pid(spec, encoder.encode({"coolant_temp": -999})) == {"coolant_temp": -40.0}


@pytest.mark.parametrize("expression", ["A * A", "bit(A, 3)", "A + C", "1 + 0 * A"])
def test_non_invertible(expression: str) -> None:
    formula = Formula.parse(expression, {"A", "B", "C"})
    with pytest.raises(EncodingError):
        linear_inverse(formula)
