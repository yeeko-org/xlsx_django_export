"""
ModelExport — clase base para definir exportaciones Excel.

Reemplaza tanto a ExportBlock como a ExportXlsMixin. Define las
columnas de forma declarativa y genera automáticamente:
- Headers con títulos y anchos
- Extracción de datos (extract_row)
- Optimizaciones ORM (select_related / prefetch_related)
- Estructura lista para export_xlsx()
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .columns import FkColumn, Include, XlsColumn
from .engine import export_xlsx
from .resolve import (
    ResolvedColumn,
    extract_row_auto,
    flatten_columns,
    infer_optimizations,
)

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest


class ModelExport:
    """Clase base para exportaciones Excel.

    Subclases definen `model`, `columns`, y opcionalmente
    `export_name`, `extra_prefetch`, y overrides de métodos.

    Ejemplo mínimo::

        class ImpactExport(ModelExport):
            model = Impact
            export_name = "Afectaciones"
            columns = [
                XlsColumn("id"),
                XlsColumn("description"),
                FkColumn("impact_type", "name"),
                Include(MentionBlock, through="mention"),
            ]
    """

    model: type[Model]
    columns: list[XlsColumn | FkColumn | Include] = []
    export_name: str = "Exportación"
    extra_prefetch: list[str] = []

    def get_base_queryset(self) -> QuerySet:
        """QuerySet base. Default: model.objects.all()."""
        return self.model.objects.all()

    def get_queryset(
        self, request: HttpRequest | None = None,
    ) -> QuerySet:
        """Aplica optimizaciones ORM al queryset base.

        Infiere select_related y prefetch_related a partir de las
        columnas declaradas. Aplica annotations de get_annotations().

        Este método puede recibir un queryset ya filtrado
        externamente (desde la vista) — ver generate().
        """
        qs = self.get_base_queryset()
        return self._apply_optimizations(qs)

    def _apply_optimizations(self, qs: QuerySet) -> QuerySet:
        """Aplica select/prefetch/annotations a un queryset."""
        selects, prefetches = infer_optimizations(
            self.model, self.columns,
        )
        if selects:
            qs = qs.select_related(*sorted(selects))
        all_prefetches = set(self.extra_prefetch) | prefetches
        if all_prefetches:
            qs = qs.prefetch_related(*sorted(all_prefetches))

        annotations = self.get_annotations()
        if annotations:
            qs = qs.annotate(**annotations)

        return qs

    def get_annotations(self) -> dict[str, Any]:
        """Anotaciones ORM adicionales.

        Override en subclases para agregar Subquery, Count, etc.
        Default: vacío.
        """
        return {}

    def get_resolved_columns(
        self, request: HttpRequest | None = None,
    ) -> list[ResolvedColumn]:
        """Aplana columnas, filtra por condition, resuelve metadata.

        Returns:
            Lista plana de ResolvedColumn listas para generar
            headers y extraer datos.
        """
        return flatten_columns(
            self.columns,
            model=self.model,
            request=request,
        )

    def extract_row(
        self, obj: Any, request: HttpRequest | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Extrae una fila de un objeto ORM.

        Default: auto-generado a partir de columns.
        Override solo para casos complejos (ej. expand 1→N).

        Puede retornar:
        - dict: una fila normal.
        - list[dict]: múltiples filas (expand_rows pattern).
        """
        return extract_row_auto(obj, self.columns, request)

    def post_process_rows(
        self, rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Hook para transformaciones post-extracción.

        Default: identidad. Override para agregar, filtrar, o
        transformar filas después de la extracción.
        """
        return rows

    def generate(
        self,
        queryset: QuerySet | None = None,
        request: HttpRequest | None = None,
    ) -> list[dict[str, Any]]:
        """Genera la estructura de datos para export_xlsx().

        Orquesta todo el pipeline:
        1. Resuelve columnas → headers + widths
        2. Obtiene queryset (o usa el proporcionado)
        3. Extrae filas (aplana si extract_row retorna lista)
        4. Post-procesa
        5. Retorna la estructura [{name, table_data, columns_width}]

        Args:
            queryset: QuerySet ya filtrado (desde la vista).
                Si None, usa get_queryset().
            request: Request actual (para conditions y filtros).

        Returns:
            Lista de dicts para export_xlsx(data=...).
        """
        # 1. Resolver columnas
        resolved = self.get_resolved_columns(request)

        # 2. Headers y widths
        headers = [rc.title for rc in resolved]
        widths = [rc.width for rc in resolved]

        # 3. Queryset
        if queryset is None:
            qs = self.get_queryset(request)
        else:
            qs = self._apply_optimizations(queryset)

        # 4. Extraer filas
        raw_rows: list[dict[str, Any]] = []
        for obj in qs:
            result = self.extract_row(obj, request)
            if isinstance(result, list):
                raw_rows.extend(result)
            else:
                raw_rows.append(result)

        # 5. Post-procesar
        raw_rows = self.post_process_rows(raw_rows)

        # 6. Convertir dicts a listas ordenadas por resolved cols
        col_keys = _build_col_keys(resolved)
        table_data = [headers]
        for row_dict in raw_rows:
            row_list = [
                row_dict.get(key, "") for key in col_keys
            ]
            table_data.append(row_list)

        return [{
            "name": self.export_name,
            "table_data": table_data,
            "columns_width": widths,
        }]

    def to_xlsx(
        self,
        queryset: QuerySet | None = None,
        request: HttpRequest | None = None,
        in_memory: bool = True,
    ):
        """Atajo: genera el Excel completo.

        Args:
            queryset: QuerySet ya filtrado.
            request: Request actual.
            in_memory: Si True, retorna BytesIO.

        Returns:
            BytesIO con el archivo Excel (si in_memory=True).
        """
        data = self.generate(queryset, request)
        from django.template.defaultfilters import slugify
        file_name = slugify(self.export_name) + ".xlsx"
        return export_xlsx(
            name=file_name, data=data, in_memory=in_memory,
        )


def _build_col_keys(
    resolved: list[ResolvedColumn],
) -> list[str]:
    """Construye las keys del dict de fila para cada columna.

    Combina through_chain + key para generar la misma clave que
    extract_row_auto produce en el dict de fila.
    """
    keys: list[str] = []
    for rc in resolved:
        if rc.through_chain:
            prefix = "__".join(rc.through_chain)
            keys.append(f"{prefix}__{rc.key}")
        else:
            keys.append(rc.key)
    return keys
