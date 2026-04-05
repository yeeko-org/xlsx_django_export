"""
Descriptores de columnas para exportación Excel.

XlsColumn — columna vinculada a un campo del modelo.
FkColumn  — columna que cruza una FK (hace explícito el salto).
Include   — integra un ModelExport reutilizable dentro de otro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from django.db import models
    from django.http import HttpRequest


# ── Defaults de width por tipo de campo Django ──────────────────

WIDTH_DEFAULTS: dict[str, int] = {
    "AutoField": 5,
    "BigAutoField": 5,
    "SmallAutoField": 5,
    "BooleanField": 6,
    "NullBooleanField": 6,
    "SmallIntegerField": 8,
    "IntegerField": 8,
    "BigIntegerField": 8,
    "PositiveIntegerField": 8,
    "PositiveSmallIntegerField": 8,
    "DateField": 12,
    "DateTimeField": 15,
    "TextField": 35,
    "ForeignKey": 25,
    "OneToOneField": 25,
}

FALLBACK_WIDTH = 15


def _resolve_width_for_field(
    django_field: Any,
) -> int:
    """Determina el width según el tipo de campo Django."""
    class_name = type(django_field).__name__

    # PK siempre 5
    if getattr(django_field, "primary_key", False):
        return 5

    # CharField depende de max_length
    if class_name == "CharField":
        max_len = getattr(django_field, "max_length", 50) or 50
        return 20 if max_len <= 50 else 30

    return WIDTH_DEFAULTS.get(class_name, FALLBACK_WIDTH)


def _resolve_title_for_field(
    django_field: Any,
    field_name: str,
    model: type[models.Model] | None = None,
) -> str:
    """Determina el título según el campo Django."""
    # verbose_name explícito (Django lo pone en minúsculas)
    verbose = getattr(django_field, "verbose_name", None)

    if field_name == "name" and model is not None:
        model_verbose = getattr(
            model._meta, "verbose_name", model.__name__
        )
        return f"Nombre de {model_verbose}"

    if field_name == "id":
        if model is not None:
            model_verbose = getattr(
                model._meta, "verbose_name", model.__name__
            )
            return f"ID de {model_verbose}"
        return "ID"

    if verbose and verbose != field_name:
        return str(verbose).capitalize()

    # Fallback: humanizar el nombre del campo
    return field_name.replace("_", " ").capitalize()


# ── XlsColumn ──────────────────────────────────────────────────

@dataclass
class XlsColumn:
    """Columna del Excel vinculada a un campo del modelo Django.

    Args:
        field: Nombre del campo en el modelo (soporta paths con __).
        title: Encabezado. None → se resuelve desde verbose_name.
        width: Ancho en caracteres. None → se resuelve por tipo.
        condition: Callable(request) → bool. Columna visible solo
            si retorna True.
        operation: Post-procesamiento: count, sum, min, max, join,
            first, last, distinct_count.
        source: Ruta ORM alternativa para obtener el valor cuando
            difiere del field (ej. paths por relaciones reversas).
        join_separator: Separador para operation="join".
    """
    field: str
    title: str | None = None
    width: int | None = None
    condition: Callable[[HttpRequest], bool] | None = None
    operation: str | None = None
    source: str | None = None
    join_separator: str = ", "

    @property
    def orm_path(self) -> str:
        """Path completo para el ORM (field o source)."""
        return self.source or self.field

    @property
    def needs_collect(self) -> bool:
        """True si la extracción debe recolectar valores (M2M)."""
        return self.source is not None and self.operation is not None

    def resolve_title(
        self, model: type[models.Model] | None = None,
    ) -> str:
        """Resuelve el título de la columna."""
        if self.title is not None:
            return self.title
        if model is None:
            return self.field.replace("_", " ").capitalize()

        # Intentar resolver contra el modelo
        parts = self.field.split("__")
        try:
            django_field = model._meta.get_field(parts[0])
            # Para paths con __, seguir hasta el campo final
            for part in parts[1:]:
                related_model = django_field.related_model
                if related_model is None:
                    break
                django_field = related_model._meta.get_field(part)
            target_model = (
                getattr(django_field, "related_model", None)
                or model
            )
            return _resolve_title_for_field(
                django_field, parts[-1], target_model,
            )
        except Exception:
            return self.field.replace("_", " ").capitalize()

    def resolve_width(
        self, model: type[models.Model] | None = None,
    ) -> int:
        """Resuelve el ancho de la columna."""
        if self.width is not None:
            return self.width
        if model is None:
            return FALLBACK_WIDTH

        parts = self.field.split("__")
        try:
            django_field = model._meta.get_field(parts[0])
            for part in parts[1:]:
                related_model = django_field.related_model
                if related_model is None:
                    break
                django_field = related_model._meta.get_field(part)
            return _resolve_width_for_field(django_field)
        except Exception:
            return FALLBACK_WIDTH


# ── FkColumn ───────────────────────────────────────────────────

@dataclass
class FkColumn(XlsColumn):
    """Columna que cruza una ForeignKey explícitamente.

    En vez de XlsColumn("impact_type__impact_group__name"), se escribe:
        FkColumn("impact_type", "impact_group__name")

    Esto hace explícito el salto de FK y permite inferir
    select_related automáticamente.
    """
    relation: str = ""

    def __init__(
        self,
        relation: str,
        field: str,
        **kwargs: Any,
    ) -> None:
        self.relation = relation
        super().__init__(field=field, **kwargs)

    @property
    def full_path(self) -> str:
        """Path completo: relation__field."""
        return f"{self.relation}__{self.field}"

    @property
    def orm_path(self) -> str:
        return self.source or self.full_path

    def resolve_title(
        self, model: type[models.Model] | None = None,
    ) -> str:
        if self.title is not None:
            return self.title
        if model is None:
            return self.field.replace("_", " ").capitalize()

        # Resolver desde el modelo de la FK
        try:
            fk_field = model._meta.get_field(self.relation)
            related_model = fk_field.related_model
            parts = self.field.split("__")
            django_field = related_model._meta.get_field(parts[0])
            for part in parts[1:]:
                rm = django_field.related_model
                if rm is None:
                    break
                django_field = rm._meta.get_field(part)
            target_model = (
                getattr(django_field, "related_model", None)
                or related_model
            )
            return _resolve_title_for_field(
                django_field, parts[-1], target_model,
            )
        except Exception:
            return self.field.replace("_", " ").capitalize()

    def resolve_width(
        self, model: type[models.Model] | None = None,
    ) -> int:
        if self.width is not None:
            return self.width
        if model is None:
            return FALLBACK_WIDTH

        try:
            fk_field = model._meta.get_field(self.relation)
            related_model = fk_field.related_model
            parts = self.field.split("__")
            django_field = related_model._meta.get_field(parts[0])
            for part in parts[1:]:
                rm = django_field.related_model
                if rm is None:
                    break
                django_field = rm._meta.get_field(part)
            return _resolve_width_for_field(django_field)
        except Exception:
            return FALLBACK_WIDTH


# ── Include ────────────────────────────────────────────────────

@dataclass
class Include:
    """Integra un ModelExport reutilizable dentro de otro.

    Args:
        block: Clase ModelExport a incluir.
        through: Ruta de relación en el modelo padre para llegar
            al objeto del bloque. None → campos leídos directo
            del objeto raíz (caso anotaciones).
    """
    block: type  # type[ModelExport] — string para evitar circular
    through: str | None = None
