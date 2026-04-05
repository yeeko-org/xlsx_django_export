"""
yeeko_xlsx_export v2.0 — Framework declarativo de exportación Excel.

API pública::

    from yeeko_xlsx_export import (
        XlsColumn, FkColumn, Include,  # descriptores de columnas
        ModelExport,                    # clase base para exports
        ExportView,                     # vista standalone
        ExportActionMixin,              # mixin para ViewSets
        export_xlsx,                    # motor xlsxwriter
    )
"""
from .columns import CollectColumn, FkColumn, Include, XlsColumn
from .engine import export_xlsx
from .export import ModelExport
from .view import ExportActionMixin, ExportView

__all__ = [
    "XlsColumn",
    "FkColumn",
    "CollectColumn",
    "Include",
    "ModelExport",
    "ExportView",
    "ExportActionMixin",
    "export_xlsx",
]
