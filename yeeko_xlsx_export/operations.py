"""
Operaciones post-extracción para columnas de exportación.

Cada operación recibe el valor extraído de una columna y lo transforma
antes de escribirlo en la celda Excel. Se usan con XlsColumn(operation=...).
"""
from __future__ import annotations

from typing import Any, Callable


def _count(value: Any) -> int:
    return len(value) if value else 0


def _sum(value: Any) -> int | float:
    return sum(value) if value else 0


def _min(value: Any) -> Any:
    return min(value) if value else ""


def _max(value: Any) -> Any:
    return max(value) if value else ""


def _first(value: Any) -> Any:
    return value[0] if value else ""


def _last(value: Any) -> Any:
    return value[-1] if value else ""


def _join(value: Any, separator: str = ", ") -> str:
    if not value:
        return ""
    return separator.join(str(v) for v in value if v is not None)


def _distinct_count(value: Any) -> int:
    return len(set(value)) if value else 0


OPERATIONS: dict[str, Callable] = {
    "count": _count,
    "sum": _sum,
    "min": _min,
    "max": _max,
    "first": _first,
    "last": _last,
    "join": _join,
    "distinct_count": _distinct_count,
}


def apply_operation(
    operation: str,
    value: Any,
    join_separator: str = ", ",
) -> Any:
    """Aplica una operación al valor extraído.

    Args:
        operation: Nombre de la operación (key de OPERATIONS).
        value: Valor sobre el que operar (normalmente una lista).
        join_separator: Separador para la operación 'join'.

    Returns:
        El valor transformado, listo para escribir en celda.
    """
    func = OPERATIONS.get(operation)
    if func is None:
        return value
    if operation == "join":
        return func(value, join_separator)
    return func(value)
