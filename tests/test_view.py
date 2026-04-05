"""Tests para yeeko_xlsx_export.view.ExportView."""
import pytest
from django.test import RequestFactory
from rest_framework.filters import OrderingFilter

from yeeko_xlsx_export import ExportView, ModelExport, XlsColumn, FkColumn


# ── Definiciones de export para tests ──────────────────────────

class ArticleExportForView(ModelExport):
    from tests.models import Article
    model = Article
    export_name = "Artículos"
    columns = [
        XlsColumn("id"),
        XlsColumn("title", width=40),
        XlsColumn("word_count"),
        FkColumn("publisher", "name", title="Editorial"),
    ]


class _FakeFilterBackend:
    """Backend de filtro simulado para tests.

    Filtra artículos cuyo title contiene el query param ``title``.
    """

    def filter_queryset(self, request, queryset, view):
        title = request.query_params.get("title")
        if title:
            queryset = queryset.filter(title__icontains=title)
        return queryset


class _FakeViewSet:
    """ViewSet simulado con filtros para copiar."""

    filter_backends = [_FakeFilterBackend, OrderingFilter]
    ordering_fields = ["title", "word_count"]
    ordering = ["title"]
    search_fields = ["title"]


# ── Tests ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExportView:
    def _create_test_data(self):
        from tests.models import Article, Publisher

        pub = Publisher.objects.create(
            name="Jornada", country="México",
        )
        art1 = Article.objects.create(
            title="Conflicto minero en Guerrero",
            word_count=500,
            publisher=pub,
        )
        art2 = Article.objects.create(
            title="Deforestación en Chiapas",
            word_count=300,
            publisher=pub,
        )
        return art1, art2, pub

    def test_basic_export_returns_xlsx(self):
        """GET sin filtros retorna un .xlsx válido."""
        self._create_test_data()
        view = ExportView.as_export_view(ArticleExportForView)
        factory = RequestFactory()
        request = factory.get("/export_xls/")
        response = view(request)

        assert response.status_code == 200
        assert response["Content-Disposition"] == (
            'attachment; filename="articulos.xlsx"'
        )
        # Leer el contenido y verificar magic bytes de ZIP
        content = b"".join(response.streaming_content)
        assert content[:2] == b"PK"

    def test_export_contains_all_rows(self):
        """Sin filtros, el Excel contiene todas las filas."""
        self._create_test_data()
        # Verificar a nivel de generate() que se incluyen ambos
        export = ArticleExportForView()
        data = export.generate()
        table = data[0]["table_data"]
        # Header + 2 artículos
        assert len(table) == 3

    def test_export_with_viewset_filters(self):
        """Los filtros copiados del ViewSet se aplican."""
        art1, art2, pub = self._create_test_data()
        view = ExportView.as_export_view(
            ArticleExportForView,
            viewset_class=_FakeViewSet,
        )
        factory = RequestFactory()
        # Filtrar solo artículos con "minero" en el título
        request = factory.get("/export_xls/", {"title": "minero"})
        response = view(request)

        assert response.status_code == 200
        content = b"".join(response.streaming_content)
        assert content[:2] == b"PK"

    def test_export_with_ordering(self):
        """El ordering del ViewSet se respeta."""
        self._create_test_data()
        view = ExportView.as_export_view(
            ArticleExportForView,
            viewset_class=_FakeViewSet,
        )
        factory = RequestFactory()
        request = factory.get(
            "/export_xls/", {"ordering": "-word_count"},
        )
        response = view(request)
        assert response.status_code == 200

    def test_export_without_viewset(self):
        """as_export_view sin viewset_class funciona."""
        self._create_test_data()
        view = ExportView.as_export_view(ArticleExportForView)
        factory = RequestFactory()
        request = factory.get("/export_xls/")
        response = view(request)
        assert response.status_code == 200

    def test_filter_attrs_copied(self):
        """Verifica que los atributos de filtro se copian."""
        view_fn = ExportView.as_export_view(
            ArticleExportForView,
            viewset_class=_FakeViewSet,
        )
        # as_view() retorna una función; la clase está en .view_class
        view_cls = view_fn.view_class
        assert view_cls.export_class is ArticleExportForView
        assert _FakeFilterBackend in view_cls.filter_backends
        assert OrderingFilter in view_cls.filter_backends
        assert view_cls.ordering_fields == ["title", "word_count"]
        assert view_cls.ordering == ["title"]

    def test_dynamic_class_name(self):
        """La subclase dinámica tiene nombre descriptivo."""
        view_fn = ExportView.as_export_view(ArticleExportForView)
        assert view_fn.view_class.__name__ == (
            "ArticleExportForViewView"
        )