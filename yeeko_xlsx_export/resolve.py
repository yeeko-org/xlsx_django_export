"""
Resolución de field paths, inferencia de optimizaciones ORM,
y extracción automática de filas.

Este módulo contiene la lógica core que conecta las definiciones
declarativas (XlsColumn, FkColumn, Include) con el ORM de Django
y la generación de datos para el Excel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .columns import FkColumn, Include, XlsColumn
from .operations import apply_operation

if TYPE_CHECKING:
    from django.db import models
    from django.http import HttpRequest


# ── Resolución de field paths ──────────────────────────────────

def resolve_field_path(
    obj: Any,
    path: str,
    collect: bool = False,
) -> Any:
    """Resuelve un path ORM (a__b__c) sobre un objeto.

    Reemplaza la función legacy `safe_attr`. Recorre getattr
    encadenado, retornando None si cualquier eslabón es None.

    Args:
        obj: Objeto Django (instancia de modelo).
        path: Path separado por "__" (ej. "note__source__name").
        collect: Si True, al encontrar un Manager (reverse FK /
            M2M), itera .all() y recolecta valores en lista plana.
            Usado cuando la columna tiene source + operation.

    Returns:
        El valor final, o None, o lista de valores si collect=True.
    """
    parts = path.split("__")
    current = obj

    for i, part in enumerate(parts):
        if current is None:
            return [] if collect else None

        attr = getattr(current, part, None)
        if attr is None:
            return [] if collect else None

        # Detectar si es un Manager (RelatedManager, ManyRelated)
        is_manager = hasattr(attr, "all") and callable(attr.all)

        if is_manager:
            if collect:
                # Recolectar: iterar .all() y seguir por el resto
                remaining = "__".join(parts[i + 1:])
                if not remaining:
                    return list(attr.all())
                results = []
                for related_obj in attr.all():
                    val = resolve_field_path(
                        related_obj, remaining, collect=True,
                    )
                    if isinstance(val, list):
                        results.extend(val)
                    elif val is not None:
                        results.append(val)
                return results
            else:
                # Sin collect, un Manager no tiene sentido escalar
                return None

        current = attr

    return current


# ── Inferencia de select_related / prefetch_related ────────────

def _classify_relation(
    model: type[models.Model],
    field_name: str,
) -> str | None:
    """Clasifica un campo del modelo como relación.

    Returns:
        'select' para FK/OneToOne, 'prefetch' para M2M/reverse,
        None si no es relación.
    """
    try:
        field_obj = model._meta.get_field(field_name)
    except Exception:
        return None

    if field_obj.many_to_many or field_obj.one_to_many:
        return "prefetch"
    if field_obj.is_relation:
        return "select"
    return None


def _walk_path_for_optimization(
    model: type[models.Model],
    path: str,
    prefix: str = "",
) -> tuple[set[str], set[str]]:
    """Analiza un path y determina qué optimizaciones necesita.

    Una vez que se cruza una frontera de prefetch (reverse FK o
    M2M), todos los segmentos subsiguientes extienden el
    prefetch_related — ``select_related`` no puede cruzar esa
    frontera.

    Returns:
        (select_related paths, prefetch_related paths)
    """
    selects: set[str] = set()
    prefetches: set[str] = set()

    parts = path.split("__")
    current_model = model
    accumulated = prefix
    in_prefetch = False

    for part in parts:
        if current_model is None:
            break

        rel_type = _classify_relation(current_model, part)
        if rel_type is None:
            break

        accumulated = (
            f"{accumulated}__{part}" if accumulated else part
        )

        try:
            field_obj = current_model._meta.get_field(part)
        except Exception:
            break

        if rel_type == "prefetch":
            in_prefetch = True

        if in_prefetch:
            prefetches.add(accumulated)
        else:
            selects.add(accumulated)

        current_model = getattr(
            field_obj, "related_model", None
        )

    # Solo conservar el prefetch más profundo de cada cadena:
    # "a__b" y "a__b__c" → solo "a__b__c"
    to_discard = set()
    for p in prefetches:
        for q in prefetches:
            if q != p and q.startswith(f"{p}__"):
                to_discard.add(p)
    prefetches -= to_discard

    return selects, prefetches


def infer_optimizations(
    model: type[models.Model],
    columns: list[XlsColumn | FkColumn | Include],
    through_prefix: str = "",
) -> tuple[set[str], set[str]]:
    """Infiere select_related y prefetch_related de las columnas.

    Recorre recursivamente la lista de columnas (entrando en
    Includes) e inspecciona model._meta para cada field path.

    Args:
        model: Modelo Django raíz.
        columns: Lista de columnas/includes.
        through_prefix: Prefijo acumulado por Includes anidados.

    Returns:
        (set de select_related, set de prefetch_related)
    """
    selects: set[str] = set()
    prefetches: set[str] = set()

    for col in columns:
        if isinstance(col, Include):
            block_instance = col.block()
            block_model = getattr(col.block, "model", None)
            new_prefix = through_prefix

            if col.through:
                # Inferir optimización para el through mismo
                s, p = _walk_path_for_optimization(
                    model, col.through, through_prefix,
                )
                selects.update(s)
                prefetches.update(p)
                new_prefix = (
                    f"{through_prefix}__{col.through}"
                    if through_prefix else col.through
                )

            # Recursión sobre las columnas del bloque
            resolve_model = block_model or model
            s, p = infer_optimizations(
                resolve_model,
                block_instance.columns,
                new_prefix,
            )
            selects.update(s)
            prefetches.update(p)

        elif isinstance(col, (XlsColumn, FkColumn)):
            path = col.orm_path
            full_path = (
                f"{through_prefix}__{path}"
                if through_prefix else path
            )
            s, p = _walk_path_for_optimization(
                model, full_path,
            )
            selects.update(s)
            prefetches.update(p)

    return selects, prefetches


# ── Aplanar columnas resueltas ─────────────────────────────────

@dataclass
class ResolvedColumn:
    """Columna ya resuelta con título, width, y path de extracción."""
    title: str
    width: int
    orm_path: str
    operation: str | None
    join_separator: str
    needs_collect: bool
    through_chain: list[str]
    # Referencia al XlsColumn original para acceder a condition
    source_column: XlsColumn


def flatten_columns(
    columns: list[XlsColumn | FkColumn | Include],
    model: type[models.Model] | None = None,
    request: HttpRequest | None = None,
    through_chain: list[str] | None = None,
) -> list[ResolvedColumn]:
    """Aplana columnas (expandiendo Includes) y resuelve metadata.

    Filtra columnas por condition (si request disponible).
    Resuelve títulos y widths contra el modelo.

    Args:
        columns: Lista de columnas/includes.
        model: Modelo Django raíz (para resolver title/width).
        request: Request actual (para evaluar conditions).
        through_chain: Cadena de through acumulada (uso interno).

    Returns:
        Lista plana de ResolvedColumn.
    """
    if through_chain is None:
        through_chain = []

    result: list[ResolvedColumn] = []

    for col in columns:
        if isinstance(col, Include):
            block_instance = col.block()
            block_model = getattr(col.block, "model", None)
            child_chain = (
                through_chain + [col.through]
                if col.through else through_chain
            )
            child_columns = flatten_columns(
                block_instance.columns,
                model=block_model,
                request=request,
                through_chain=child_chain,
            )
            result.extend(child_columns)

        elif isinstance(col, (XlsColumn, FkColumn)):
            # Evaluar condition
            if col.condition is not None:
                if request is None or not col.condition(request):
                    continue

            result.append(ResolvedColumn(
                title=col.resolve_title(model),
                width=col.resolve_width(model),
                orm_path=col.orm_path,
                operation=col.operation,
                join_separator=col.join_separator,
                needs_collect=col.needs_collect,
                through_chain=list(through_chain),
                source_column=col,
            ))

    return result


# ── Extracción automática de filas ─────────────────────────────

def extract_row_auto(
    obj: Any,
    columns: list[XlsColumn | FkColumn | Include],
    request: HttpRequest | None = None,
) -> dict[str, Any]:
    """Genera un dict de datos para una fila del Excel.

    Recorre las columnas declaradas y extrae valores del objeto ORM.

    Args:
        obj: Instancia del modelo Django.
        columns: Lista de columnas/includes (sin aplanar).
        request: Request (para evaluar conditions).

    Returns:
        Dict {field_key: valor} para la fila.
    """
    row: dict[str, Any] = {}

    for col in columns:
        if isinstance(col, Include):
            block_instance = col.block()

            if col.through:
                # Obtener el sub-objeto via through
                sub_obj = resolve_field_path(obj, col.through)
                if sub_obj is not None:
                    sub_row = extract_row_auto(
                        sub_obj,
                        block_instance.columns,
                        request,
                    )
                else:
                    # Sub-objeto None: llenar con vacíos
                    sub_row = {
                        _col_key(c): ""
                        for c in _leaf_columns(
                            block_instance.columns,
                        )
                    }
                # Prefijar keys con through
                for key, value in sub_row.items():
                    row[f"{col.through}__{key}"] = value
            else:
                # Sin through: leer directo del obj raíz
                sub_row = extract_row_auto(
                    obj, block_instance.columns, request,
                )
                row.update(sub_row)

        elif isinstance(col, (XlsColumn, FkColumn)):
            # Evaluar condition
            if col.condition is not None:
                if request is None or not col.condition(request):
                    continue

            key = _col_key(col)

            if col.needs_collect:
                # Recolectar valores por relación reversa
                value = resolve_field_path(
                    obj, col.orm_path, collect=True,
                )
                value = apply_operation(
                    col.operation, value, col.join_separator,
                )
            elif col.operation:
                value = resolve_field_path(obj, col.orm_path)
                if isinstance(value, (list, tuple)):
                    value = apply_operation(
                        col.operation, value, col.join_separator,
                    )
            else:
                path = (
                    col.full_path
                    if isinstance(col, FkColumn)
                    else col.field
                )
                value = resolve_field_path(obj, path)

            row[key] = value

    return row


def _col_key(col: XlsColumn | FkColumn) -> str:
    """Key del dict de fila para una columna."""
    if isinstance(col, FkColumn):
        return col.full_path
    return col.field


def _leaf_columns(
    columns: list[XlsColumn | FkColumn | Include],
) -> list[XlsColumn | FkColumn]:
    """Obtiene las columnas hoja (sin Includes) recursivamente."""
    result: list[XlsColumn | FkColumn] = []
    for col in columns:
        if isinstance(col, Include):
            block_instance = col.block()
            leaves = _leaf_columns(block_instance.columns)
            if col.through:
                # No necesitamos prefijar aquí, solo recolectar
                result.extend(leaves)
            else:
                result.extend(leaves)
        elif isinstance(col, (XlsColumn, FkColumn)):
            result.append(col)
    return result
