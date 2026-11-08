"""Evaluador de fórmulas de conversión, seguro y sin ``eval`` (RS-13, RNF-05).

Las definiciones (``definitions/*.yaml``) describen cómo convertir bytes crudos en valores
físicos con expresiones como ``(A*256 + B) / 4``. Este módulo:

1. **Analiza** la expresión una sola vez, al cargar la definición, con ``ast.parse``.
2. **Valida** que solo use construcciones de una lista blanca: números, variables
   permitidas, aritmética, operaciones de bits y unas pocas funciones.
3. La **compila** a funciones Python anidadas (closures), que luego se evalúan rápido
   para cada muestra sin volver a analizar el texto.

Nunca se ejecuta código arbitrario: un nodo AST que no esté en la lista blanca produce
``FormulaError`` al cargar, con un mensaje que indica qué no se admite.

Convención de variables de bytes: ``A`` es el primer byte de datos del PID/DID, ``B`` el
segundo, etc. (la misma convención que usan las tablas públicas de SAE J1979).
"""

from __future__ import annotations

import ast
import operator
import string
from collections.abc import Callable, Mapping
from dataclasses import dataclass

#: Nombres de las variables de bytes, en orden: ``A`` = byte 0, ``B`` = byte 1, ...
BYTE_VARIABLE_NAMES: tuple[str, ...] = tuple(string.ascii_uppercase)

#: Longitud máxima de una expresión. Protege contra definiciones malformadas o abusivas;
#: las fórmulas reales de SAE J1979 tienen menos de 40 caracteres.
DEFAULT_MAX_EXPRESSION_LENGTH = 256

_Evaluator = Callable[[Mapping[str, float]], float]


class FormulaError(ValueError):
    """La expresión no es válida o usa algo fuera de la lista blanca."""


class FormulaEvaluationError(ArithmeticError):
    """La expresión es válida pero falló al evaluarse (p. ej. división por cero)."""


def _bit(value: float, index: float) -> float:
    """Devuelve el bit ``index`` (0 = menos significativo) de ``value`` como 0 o 1."""
    return float((int(value) >> int(index)) & 1)


def _signed(value: float, bits: float) -> float:
    """Interpreta ``value`` como entero con signo en complemento a dos de ``bits`` bits.

    Ejemplo: ``signed(A, 8)`` con ``A = 0xFF`` devuelve ``-1``.
    """
    width = int(bits)
    raw = int(value) & ((1 << width) - 1)
    return float(raw - (1 << width) if raw & (1 << (width - 1)) else raw)


@dataclass(frozen=True, slots=True)
class _FunctionSpec:
    """Función disponible dentro de una fórmula y cuántos argumentos acepta."""

    impl: Callable[..., float]
    min_args: int
    max_args: int


#: Funciones permitidas dentro de las fórmulas.
FUNCTIONS: Mapping[str, _FunctionSpec] = {
    "min": _FunctionSpec(lambda *a: float(min(a)), 2, 8),
    "max": _FunctionSpec(lambda *a: float(max(a)), 2, 8),
    "abs": _FunctionSpec(lambda a: float(abs(a)), 1, 1),
    "bit": _FunctionSpec(_bit, 2, 2),
    "signed": _FunctionSpec(_signed, 2, 2),
}

_BINARY_OPERATORS: Mapping[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    # Operaciones de bits: se aplican sobre la parte entera de los operandos.
    ast.BitAnd: lambda a, b: float(int(a) & int(b)),
    ast.BitOr: lambda a, b: float(int(a) | int(b)),
    ast.RShift: lambda a, b: float(int(a) >> int(b)),
    ast.LShift: lambda a, b: float(int(a) << int(b)),
}

_UNARY_OPERATORS: Mapping[type[ast.unaryop], Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


@dataclass(frozen=True, slots=True)
class Formula:
    """Fórmula ya validada y compilada.

    Se crea con :meth:`Formula.parse`; no instanciar directamente.

    Attributes:
        expression: Texto original de la fórmula.
        variables: Variables que la fórmula usa realmente (subconjunto de las permitidas).
    """

    expression: str
    variables: frozenset[str]
    _evaluator: _Evaluator

    @classmethod
    def parse(
        cls,
        expression: str,
        allowed_variables: frozenset[str] | set[str],
        *,
        max_length: int = DEFAULT_MAX_EXPRESSION_LENGTH,
    ) -> Formula:
        """Analiza, valida y compila una expresión.

        Args:
            expression: Texto de la fórmula, p. ej. ``"(A*256 + B) / 4"``.
            allowed_variables: Variables que la fórmula puede usar (p. ej. ``{"A", "B"}``
                para un PID de 2 bytes).
            max_length: Longitud máxima admitida para la expresión.

        Returns:
            La fórmula compilada.

        Raises:
            FormulaError: Si la sintaxis es inválida, supera ``max_length`` o usa algo
                fuera de la lista blanca (variable no permitida, función desconocida...).
        """
        if len(expression) > max_length:
            raise FormulaError(f"La fórmula supera {max_length} caracteres ({len(expression)}).")
        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError as exc:
            raise FormulaError(f"Sintaxis inválida en '{expression}': {exc.msg}") from exc

        used: set[str] = set()
        evaluator = _compile(tree.body, frozenset(allowed_variables), used, expression)
        return cls(expression=expression, variables=frozenset(used), _evaluator=evaluator)

    def evaluate(self, variables: Mapping[str, float]) -> float:
        """Evalúa la fórmula.

        Args:
            variables: Valor de cada variable usada (``self.variables``).

        Returns:
            Resultado numérico.

        Raises:
            FormulaEvaluationError: Si falta una variable o hay un error aritmético.
        """
        try:
            return self._evaluator(variables)
        except KeyError as exc:
            raise FormulaEvaluationError(
                f"Falta la variable {exc} para evaluar '{self.expression}'."
            ) from exc
        except (ArithmeticError, ValueError) as exc:
            raise FormulaEvaluationError(f"Error al evaluar '{self.expression}': {exc}") from exc


def byte_variables(data: bytes) -> dict[str, float]:
    """Asigna cada byte de ``data`` a su variable (``A`` = ``data[0]``, ...).

    Raises:
        ValueError: Si ``data`` tiene más bytes que variables disponibles.
    """
    if len(data) > len(BYTE_VARIABLE_NAMES):
        raise ValueError(f"Máximo {len(BYTE_VARIABLE_NAMES)} bytes por fórmula.")
    return {name: float(b) for name, b in zip(BYTE_VARIABLE_NAMES, data, strict=False)}


def byte_variable_names(count: int) -> frozenset[str]:
    """Variables de bytes permitidas para un dato de ``count`` bytes (``A`` .. ).

    Raises:
        ValueError: Si ``count`` está fuera de rango.
    """
    if not 0 < count <= len(BYTE_VARIABLE_NAMES):
        raise ValueError(f"Cantidad de bytes fuera de rango: {count}.")
    return frozenset(BYTE_VARIABLE_NAMES[:count])


def _compile(node: ast.expr, allowed: frozenset[str], used: set[str], source: str) -> _Evaluator:
    """Convierte recursivamente un nodo AST en una función evaluadora.

    ``used`` acumula las variables encontradas. ``source`` solo se usa en los mensajes.
    """
    if isinstance(node, ast.Constant):
        # ``bool`` es subclase de ``int``: se excluye explícitamente.
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise FormulaError(f"Constante no numérica {node.value!r} en '{source}'.")
        constant = float(node.value)
        return lambda _v: constant

    if isinstance(node, ast.Name):
        if node.id not in allowed:
            permitted = ", ".join(sorted(allowed)) or "(ninguna)"
            raise FormulaError(
                f"Variable '{node.id}' no permitida en '{source}'. Permitidas: {permitted}."
            )
        used.add(node.id)
        name = node.id
        return lambda v: float(v[name])

    if isinstance(node, ast.BinOp):
        binary = _BINARY_OPERATORS.get(type(node.op))
        if binary is None:
            raise FormulaError(f"Operador '{type(node.op).__name__}' no permitido en '{source}'.")
        left = _compile(node.left, allowed, used, source)
        right = _compile(node.right, allowed, used, source)
        return lambda v: binary(left(v), right(v))

    if isinstance(node, ast.UnaryOp):
        unary = _UNARY_OPERATORS.get(type(node.op))
        if unary is None:
            raise FormulaError(f"Operador '{type(node.op).__name__}' no permitido en '{source}'.")
        operand = _compile(node.operand, allowed, used, source)
        return lambda v: unary(operand(v))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise FormulaError(
                f"Función no permitida en '{source}'. Disponibles: {', '.join(FUNCTIONS)}."
            )
        if node.keywords:
            raise FormulaError(f"Argumentos con nombre no permitidos en '{source}'.")
        spec = FUNCTIONS[node.func.id]
        if not spec.min_args <= len(node.args) <= spec.max_args:
            raise FormulaError(
                f"'{node.func.id}' acepta entre {spec.min_args} y {spec.max_args} "
                f"argumentos en '{source}'."
            )
        args = [_compile(arg, allowed, used, source) for arg in node.args]
        impl = spec.impl
        return lambda v: impl(*(a(v) for a in args))

    raise FormulaError(f"Construcción '{type(node).__name__}' no permitida en '{source}'.")
