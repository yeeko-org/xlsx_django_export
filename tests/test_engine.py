"""Tests para yeeko_xlsx_export.engine."""
from datetime import date, datetime

from yeeko_xlsx_export.engine import export_xlsx


class TestExportXlsx:
    def test_in_memory_returns_bytes(self):
        """Genera un Excel en memoria y verifica que es BytesIO."""
        data = [{
            "name": "Test",
            "table_data": [
                ["ID", "Nombre"],
                [1, "Primero"],
                [2, "Segundo"],
            ],
            "columns_width": [5, 20],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None
        content = result.read()
        # Verificar magic bytes de ZIP (xlsx es un ZIP)
        assert content[:2] == b"PK"

    def test_empty_data(self):
        result = export_xlsx(data=[], in_memory=True)
        assert result is not None

    def test_multiple_sheets(self):
        data = [
            {
                "name": "Hoja 1",
                "table_data": [["Col A"], ["val"]],
            },
            {
                "name": "Hoja 2",
                "table_data": [["Col B"], ["val"]],
            },
        ]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_none_values(self):
        data = [{
            "name": "Test",
            "table_data": [
                ["A", "B"],
                [None, "ok"],
                ["ok", None],
            ],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_dates(self):
        data = [{
            "name": "Fechas",
            "table_data": [
                ["Fecha", "DateTime"],
                [date(2024, 1, 15), datetime(2024, 6, 1, 12, 0)],
            ],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_booleans(self):
        data = [{
            "name": "Bools",
            "table_data": [
                ["Activo"],
                [True],
                [False],
            ],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_lists(self):
        data = [{
            "name": "Listas",
            "table_data": [
                ["Tags"],
                [["python", "django", "excel"]],
            ],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_floats(self):
        data = [{
            "name": "Floats",
            "table_data": [
                ["Valor"],
                [3.14159],
            ],
            "max_decimal": 2,
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None

    def test_handles_dict_cells(self):
        """Legacy compat: celdas como dict con text y format."""
        data = [{
            "name": "Dicts",
            "table_data": [
                [{"text": "Header", "format": {"bold": True}}],
                [{"text": "Normal"}],
            ],
        }]
        result = export_xlsx(data=data, in_memory=True)
        assert result is not None
