"""
Vistas para exportación Excel.

ExportView — vista standalone (GenericAPIView) para usar con
    path() en urlpatterns.

ExportActionMixin — mixin para ViewSets que agrega la action
    ``export_xls`` automáticamente a partir de un ModelExport.
    Se inyecta dinámicamente por el registry cuando el schema
    define ``xls_export_class``.

Uso standalone::

    urlpatterns = [
        path(
            "impacts/export_xls/",
            ExportView.as_export_view(
                ImpactExport, viewset_class=ImpactViewSet,
            ),
        ),
    ]

Uso como mixin (inyectado por el registry)::

    # El registry hace esto internamente:
    NewViewSet = type(
        "ActorViewSetExport",
        (ExportActionMixin, ActorViewSet),
        {"xls_export_class": ActorExport},
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import FileResponse
from django.template.defaultfilters import slugify
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny

if TYPE_CHECKING:
    from rest_framework.request import Request

    from .export import ModelExport


class ExportView(GenericAPIView):
    """Vista GET que genera un Excel a partir de un ModelExport.

    Hereda de GenericAPIView para reutilizar la maquinaria de
    filtros de DRF (filter_queryset, filterset_class, etc.).

    No se instancia directamente — usar ``as_export_view()``.
    """

    export_class: type[ModelExport] | None = None
    permission_classes = [AllowAny]

    def get_queryset(self):
        """Queryset base desde el ModelExport."""
        return self.export_class().get_base_queryset()

    def get(self, request: Request) -> FileResponse:
        """Genera y retorna el archivo Excel."""
        export = self.export_class()
        qs = self.filter_queryset(self.get_queryset())
        output = export.to_xlsx(
            queryset=qs, request=request,
        )
        output.seek(0)
        filename = f"{slugify(export.export_name)}.xlsx"
        return FileResponse(
            output,
            as_attachment=True,
            filename=filename,
        )

    @classmethod
    def as_export_view(
        cls,
        export_class: type[ModelExport],
        viewset_class: type | None = None,
    ):
        """Crea una vista configurada lista para urlpatterns.

        Genera dinámicamente una subclase de ExportView con los
        atributos de filtrado copiados del ViewSet. Esto permite
        que la misma URL responda a los mismos query params que
        el endpoint de listado (search, ordering, filtros).

        Args:
            export_class: Subclase de ModelExport que define
                las columnas y la lógica de exportación.
            viewset_class: ViewSet del cual copiar filterset_class,
                filter_backends, search_fields, ordering_fields,
                y ordering. Si None, la vista no aplica filtros.

        Returns:
            Vista callable para usar en path() / url().
        """
        attrs: dict = {"export_class": export_class}

        if viewset_class is not None:
            _copy_filter_attrs(viewset_class, attrs)

        view_cls = type(
            f"{export_class.__name__}View",
            (cls,),
            attrs,
        )
        return view_cls.as_view()


# ── Helpers internos ───────────────────────────────────

_FILTER_ATTRS = (
    "filterset_class",
    "filterset_fields",
    "filter_backends",
    "search_fields",
    "ordering_fields",
    "ordering",
)


def _copy_filter_attrs(
    viewset_class: type,
    target: dict,
) -> None:
    """Copia atributos de filtrado del ViewSet al dict destino.

    Las listas/tuplas se copian como list para evitar mutar
    el original del ViewSet.
    """
    for attr in _FILTER_ATTRS:
        value = getattr(viewset_class, attr, None)
        if value is not None:
            target[attr] = (
                list(value) if isinstance(value, (list, tuple))
                else value
            )


# ── ExportActionMixin ─────────────────────────────────────

class ExportActionMixin:
    """Mixin que agrega ``@action export_xls`` a un ViewSet.

    Requiere que ``xls_export_class`` esté definido (se inyecta
    dinámicamente al crear la subclase en el registry).

    Usa el ModelExport para generar el queryset optimizado,
    reutilizando ``filter_queryset()`` del ViewSet para aplicar
    los mismos filtros que el endpoint de listado.
    """

    xls_export_class: type[ModelExport] | None = None

    @action(detail=False, methods=["get"])
    def export_xls(self, request: Request) -> FileResponse:
        """GET /{prefix}/export_xls/ — genera y retorna el .xlsx."""
        export = self.xls_export_class()
        qs = self.filter_queryset(export.get_base_queryset())
        output = export.to_xlsx(queryset=qs, request=request)
        output.seek(0)
        filename = f"{slugify(export.export_name)}.xlsx"
        return FileResponse(
            output, as_attachment=True, filename=filename,
        )
