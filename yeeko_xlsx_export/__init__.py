"""
yeeko_xlsx_export v2.0 — Framework declarativo de exportación Excel.

API pública::

    from yeeko_xlsx_export import (
        XlsColumn, FkColumn, Include,  # descriptores de columnas
        ModelExport,                    # clase base para exports
        export_xlsx,                    # motor xlsxwriter
    )
"""
from .columns import FkColumn, Include, XlsColumn
from .engine import export_xlsx
from .export import ModelExport

__all__ = [
    "XlsColumn",
    "FkColumn",
    "Include",
    "ModelExport",
    "export_xlsx",
]
