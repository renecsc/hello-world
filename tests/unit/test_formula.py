"""Evaluador de fórmulas: cálculo correcto y rechazo de todo lo que no está en la lista blanca."""

from __future__ import annotations

import pytest

from diag.core.decoding.formula import (
    Formula,
    FormulaError,
    FormulaEvaluationError,
    byte_variable_names,
    byte_variables,
)

AB = frozenset({"A", "B"})


@pytest.mark.parametrize(
    ("expression", "data", "expected"),
    [
        ("(A * 256 + B) / 4", b"\x1a\xf8", 1726.0),  # RPM, ejemplo SAE J1979
        ("A - 40", b"\x7b\x00", 83.0),
        ("(A - 128) * 100 / 128", b"\x80\x00", 0.0),
        ("-A + 1", b"\x05\x00", -4.0),
        ("bit(A, 7)", b"\x80\x00", 1.0),
        ("signed(A, 8)", b"\xff\x00", -1.0),
        ("min(A, B) + max(A, B)", b"\x02\x09", 11.0),
        ("(A << 8 | B) & 0x0FFF", b"\xab\xcd", 0x0BCD),
    ],
)
def test_evaluates(expression: str, data: bytes, expected: float) -> None:
    formula = Formula.parse(expression, AB)
    assert formula.evaluate(byte_variables(data)) == pytest.approx(expected)


def test_reports_used_variables() -> None:
    assert Formula.parse("B / 2", AB).variables == {"B"}


@pytest.mark.parametrize(
    "expression",
    [
        "C + 1",  # variable no permitida para un dato de 2 bytes
        "__import__('os').system('ls')",  # llamada no permitida
        "A.real",  # acceso a atributos
        "A ** 2",  # potencia (posible abuso de CPU)
        "'texto'",  # constante no numérica
        "True + A",  # booleanos
        "A if B else 0",  # condicionales
        "[A, B]",  # listas
        "lambda: A",  # funciones anónimas
        "min(A, key=B)",  # argumentos con nombre
        "abs(A, B)",  # aridad incorrecta
        "A +",  # sintaxis
    ],
)
def test_rejects_unsafe_or_invalid(expression: str) -> None:
    with pytest.raises(FormulaError):
        Formula.parse(expression, AB)


def test_rejects_too_long() -> None:
    with pytest.raises(FormulaError, match="supera"):
        Formula.parse("A" + " + A" * 100, AB, max_length=50)


def test_division_by_zero_is_evaluation_error() -> None:
    formula = Formula.parse("A / B", AB)
    with pytest.raises(FormulaEvaluationError):
        formula.evaluate({"A": 1, "B": 0})


def test_byte_variable_names() -> None:
    assert byte_variable_names(3) == {"A", "B", "C"}
    with pytest.raises(ValueError):
        byte_variable_names(0)
