"""Tests end-to-end para yeeko_xlsx_export.export.ModelExport."""
import pytest
from yeeko_xlsx_export import (
    CollectColumn, FkColumn, Include, ModelExport, XlsColumn,
)


# ── Definiciones de export para tests ──────────────────────────

class PublisherBlock(ModelExport):
    from tests.models import Publisher
    model = Publisher
    columns = [
        XlsColumn("name"),
        XlsColumn("country"),
    ]


class ArticleExport(ModelExport):
    from tests.models import Article
    model = Article
    export_name = "Artículos de prueba"
    columns = [
        XlsColumn("id"),
        XlsColumn("title", width=40),
        XlsColumn("word_count"),
        XlsColumn("is_featured"),
        XlsColumn("published_date"),
        FkColumn("publisher", "name", title="Editorial"),
        Include(PublisherBlock, through="publisher"),
    ]


class ArticleWithOpsExport(ModelExport):
    from tests.models import Article
    model = Article
    export_name = "Artículos con operaciones"
    columns = [
        XlsColumn("id"),
        XlsColumn("title"),
        CollectColumn(
            "comments", "text", operation="count",
        ),
        CollectColumn("tags", "name"),
    ]


# ── Tests ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestModelExportGenerate:
    def _create_test_data(self):
        from tests.models import Article, Comment, Publisher, Tag

        pub = Publisher.objects.create(
            name="Jornada", country="México",
        )
        art1 = Article.objects.create(
            title="Artículo uno",
            word_count=500,
            is_featured=True,
            publisher=pub,
        )
        art2 = Article.objects.create(
            title="Artículo dos",
            word_count=300,
            publisher=pub,
        )
        Comment.objects.create(
            article=art1, author_name="Ana", text="Buen artículo",
        )
        Comment.objects.create(
            article=art1, author_name="Pedro", text="Interesante",
        )
        tag1 = Tag.objects.create(name="política")
        tag2 = Tag.objects.create(name="medio ambiente")
        art1.tags.add(tag1, tag2)
        return art1, art2, pub

    def test_generate_basic(self):
        art1, art2, pub = self._create_test_data()
        export = ArticleExport()
        data = export.generate()

        assert len(data) == 1
        sheet = data[0]
        assert sheet["name"] == "Artículos de prueba"

        table = sheet["table_data"]
        # Header + 2 filas
        assert len(table) == 3

        # Verificar header
        headers = table[0]
        assert "ID de artículo" in headers
        assert "Editorial" in headers

        # Verificar que los datos están
        row1_values = table[1]
        row2_values = table[2]
        all_values = row1_values + row2_values
        # Los títulos deben aparecer en alguna fila
        titles = [v for v in all_values if isinstance(v, str)]
        assert any("Artículo" in t for t in titles)

    def test_generate_with_operations(self):
        art1, art2, pub = self._create_test_data()
        export = ArticleWithOpsExport()
        data = export.generate()

        table = data[0]["table_data"]
        assert len(table) == 3  # header + 2 articles

        # Encontrar la fila del art1 (tiene 2 comments, 2 tags)
        for row in table[1:]:
            if row[0] == art1.id:
                comment_count = row[2]
                tag_list = row[3]
                assert comment_count == 2
                assert "política" in tag_list
                assert "medio ambiente" in tag_list
                break
        else:
            pytest.fail("art1 no encontrado en los datos")

    def test_to_xlsx(self):
        self._create_test_data()
        export = ArticleExport()
        result = export.to_xlsx(in_memory=True)
        assert result is not None
        content = result.read()
        assert content[:2] == b"PK"  # ZIP magic bytes

    def test_inferred_optimizations(self):
        """Verifica que las optimizaciones se infieren."""
        from yeeko_xlsx_export.resolve import infer_optimizations
        from tests.models import Article

        selects, prefetches = infer_optimizations(
            Article, ArticleExport.columns,
        )
        assert "publisher" in selects

    def test_inferred_optimizations_with_ops(self):
        from yeeko_xlsx_export.resolve import infer_optimizations
        from tests.models import Article

        selects, prefetches = infer_optimizations(
            Article, ArticleWithOpsExport.columns,
        )
        assert "comments" in prefetches
        assert "tags" in prefetches
