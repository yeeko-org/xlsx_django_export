"""
Motor de escritura Excel basado en xlsxwriter.

Función principal: export_xlsx() — genera un archivo .xlsx a partir
de una estructura de datos con worksheets, headers, y filas.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import xlsxwriter


def _get_timezone() -> ZoneInfo:
    """Obtiene la timezone desde settings de Django."""
    try:
        from django.conf import settings
        tz_name = getattr(settings, "TIME_ZONE", "UTC")
    except Exception:
        tz_name = "UTC"
    return ZoneInfo(tz_name)


def _resolve_max_decimal(
    max_decimals: list[int | None] | None,
    col_idx: int,
    ws_default: int,
) -> int:
    """Jerarquía: columna > worksheet > 2."""
    if max_decimals and col_idx < len(max_decimals):
        col_val = max_decimals[col_idx]
        if col_val is not None:
            return col_val
    return ws_default


def export_xlsx(
    name: str = "export.xlsx",
    data: list[dict[str, Any]] | None = None,
    in_memory: bool = False,
) -> io.BytesIO | None:
    """Genera un archivo Excel con una o más hojas.

    Args:
        name: Nombre del archivo (solo si in_memory=False).
        data: Lista de dicts, cada uno con:
            - name: nombre de la pestaña
            - table_data: lista de filas (la primera es headers)
            - columns_width: lista de anchos en caracteres
            - columns_width_pixel: lista de anchos en píxeles
            - max_decimal: máximo de decimales para floats
        in_memory: Si True, genera en BytesIO y lo retorna.

    Returns:
        BytesIO si in_memory=True, None si escribe a disco.
    """
    output = None
    if in_memory:
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    else:
        workbook = xlsxwriter.Workbook(name)

    # ── Formatos reutilizables ──────────────────────────────
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#D9E1F2",
        "border": 1,
        "border_color": "#B4C6E7",
        "text_wrap": True,
        "valign": "vcenter",
    })
    bold_fmt = workbook.add_format({"bold": True})
    date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})
    datetime_fmt = workbook.add_format({
        "num_format": "dd/mm/yyyy hh:mm",
    })
    bool_bold_fmt = workbook.add_format({"bold": True})

    tz = _get_timezone()

    if data is None:
        data = []

    for idx, ws_data in enumerate(data, start=1):
        ws_name = ws_data.get("name", f"page {idx}")
        table_data = ws_data.get("table_data", [])
        columns_width = ws_data.get("columns_width")
        columns_width_pixel = ws_data.get("columns_width_pixel")
        max_decimal = ws_data.get("max_decimal", 2)
        max_decimals = ws_data.get("max_decimals")

        worksheet = workbook.add_worksheet(ws_name)

        # ── Anchos de columna ───────────────────────────────
        if columns_width:
            for c, w in enumerate(columns_width):
                worksheet.set_column(c, c, w)
        elif columns_width_pixel:
            for c, w in enumerate(columns_width_pixel):
                try:
                    worksheet.set_column(c, c, int(w / 7.5))
                except (TypeError, ValueError):
                    continue

        # ── Escribir filas ──────────────────────────────────
        for row_idx, row_data in enumerate(table_data):
            is_header = row_idx == 0
            for col_idx, cell in enumerate(row_data):
                is_first_col = col_idx == 0 and not is_header
                cell_fmt = (
                    header_fmt if is_header
                    else bold_fmt if is_first_col
                    else None
                )

                col_decimal = _resolve_max_decimal(
                    max_decimals, col_idx, max_decimal,
                )
                _write_cell(
                    worksheet, workbook,
                    row_idx, col_idx, cell,
                    cell_fmt, date_fmt, datetime_fmt,
                    bold_fmt, bool_bold_fmt,
                    tz, col_decimal, is_first_col,
                )

    workbook.close()

    if in_memory:
        output.seek(0)
        return output
    return None


def _write_cell(
    worksheet: Any,
    workbook: Any,
    row: int,
    col: int,
    cell: Any,
    cell_fmt: Any,
    date_fmt: Any,
    datetime_fmt: Any,
    bold_fmt: Any,
    bool_bold_fmt: Any,
    tz: ZoneInfo,
    max_decimal: int,
    is_first_col: bool,
) -> None:
    """Escribe una celda aplicando formato según su tipo."""

    # ── dict con formato explícito (legacy compat) ──────────
    if isinstance(cell, dict):
        text = cell.get("text", "")
        fmt_config = cell.get("format")
        if isinstance(fmt_config, dict):
            fmt = workbook.add_format(fmt_config)
            worksheet.write(row, col, text, fmt)
        else:
            worksheet.write(row, col, text, cell_fmt)
        return

    # ── listas → join con ", " ──────────────────────────────
    if isinstance(cell, list):
        text = ", ".join(str(c) for c in cell if c is not None)
        worksheet.write(row, col, text, cell_fmt)
        return

    # ── booleanos (antes de int, porque bool es subclase) ───
    if isinstance(cell, bool):
        text = "Sí" if cell else "No"
        fmt = bold_fmt if is_first_col else None
        worksheet.write(row, col, text, fmt)
        return

    # ── datetime (antes de date, porque datetime hereda) ────
    if isinstance(cell, datetime):
        if cell.tzinfo is not None:
            cell = cell.astimezone(tz)
        dt_fmt = (
            workbook.add_format({
                "num_format": "dd/mm/yyyy hh:mm",
                "bold": True,
            })
            if is_first_col else datetime_fmt
        )
        worksheet.write_datetime(row, col, cell, dt_fmt)
        return

    # ── date ────────────────────────────────────────────────
    if isinstance(cell, date):
        d_fmt = (
            workbook.add_format({
                "num_format": "dd/mm/yyyy",
                "bold": True,
            })
            if is_first_col else date_fmt
        )
        worksheet.write_datetime(row, col, cell, d_fmt)
        return

    if isinstance(cell, (float, Decimal)):
        rounded = float(f"{float(cell):.{max_decimal}f}")
        worksheet.write(row, col, rounded, cell_fmt)
        return

    if isinstance(cell, int):
        worksheet.write(row, col, cell, cell_fmt)
        return

    # ── None → vacío ────────────────────────────────────────
    if cell is None:
        worksheet.write(row, col, "", cell_fmt)
        return

    # ── str y fallback ──────────────────────────────────────
    worksheet.write(row, col, str(cell), cell_fmt)
