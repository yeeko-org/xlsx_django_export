"""Tests para yeeko_xlsx_export.resolve."""
import pytest
from yeeko_xlsx_export.columns import (
    CollectColumn, FkColumn, Include, XlsColumn,
)
from yeeko_xlsx_export.resolve import (
    extract_row_auto,
    flatten_columns,
    infer_optimizations,
    resolve_field_path,
)


# ── Tests de resolve_field_path ────────────────────────────────

class SimpleObj:
    """Objeto mock para tests de resolución de paths."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestResolveFieldPath:
    def test_simple_field(self):
        obj = SimpleObj(name="test")
        assert resolve_field_path(obj, "name") == "test"

    def test_nested_field(self):
        inner = SimpleObj(name="inner")
        obj = SimpleObj(child=inner)
        assert resolve_field_path(obj, "child__name") == "inner"

    def test_none_in_chain(self):
        obj = SimpleObj(child=None)
        assert resolve_field_path(obj, "child__name") is None

    def test_missing_attr(self):
        obj = SimpleObj(name="test")
        assert resolve_field_path(obj, "nonexistent") is None

    def test_none_in_chain_collect(self):
        obj = SimpleObj(child=None)
        result = resolve_field_path(
            obj, "child__name", collect=True,
        )
        assert result == []

    def test_collect_with_manager_like(self):
        """Simula un Manager con método .all()."""
        class FakeManager:
            def all(self):
                return [
                    SimpleObj(date="2024-01"),
                    SimpleObj(date="2024-02"),
                ]

        obj = SimpleObj(comments=FakeManager())
        result = resolve_field_path(
            obj, "comments__date", collect=True,
        )
        assert result == ["2024-01", "2024-02"]

    def test_collect_nested_managers(self):
        """Simula managers anidados (M2M → FK → campo)."""
        class InnerManager:
            def all(self):
                return [
                    SimpleObj(val=10),
                    SimpleObj(val=20),
                ]

        class OuterItem:
            def __init__(self):
                self.children = InnerManager()

        class OuterManager:
            def all(self):
                return [OuterItem(), OuterItem()]

        obj = SimpleObj(parents=OuterManager())
        result = resolve_field_path(
            obj, "parents__children__val", collect=True,
        )
        assert result == [10, 20, 10, 20]


# ── Tests de infer_optimizations ───────────────────────────────

@pytest.mark.django_db
class TestInferOptimizations:
    def test_fk_column_infers_select(self):
        from tests.models import Article
        columns = [FkColumn("publisher", "name")]
        selects, prefetches = infer_optimizations(
            Article, columns,
        )
        assert "publisher" in selects

    def test_m2m_infers_prefetch(self):
        from tests.models import Article
        columns = [
            CollectColumn("tags", "name"),
        ]
        selects, prefetches = infer_optimizations(
            Article, columns,
        )
        assert "tags" in prefetches

    def test_reverse_fk_infers_prefetch(self):
        from tests.models import Article
        columns = [
            CollectColumn(
                "comments", "text", operation="count",
            ),
        ]
        selects, prefetches = infer_optimizations(
            Article, columns,
        )
        assert "comments" in prefetches

    def test_include_with_through(self):
        """Include con through infiere select para la FK."""
        from tests.models import Article
        from yeeko_xlsx_export import ModelExport

        class PublisherBlock(ModelExport):
            model = Article  # no importa para este test
            columns = [XlsColumn("name")]

        columns = [Include(PublisherBlock, through="publisher")]
        selects, _ = infer_optimizations(Article, columns)
        assert "publisher" in selects

    def test_plain_field_no_optimization(self):
        from tests.models import Article
        columns = [XlsColumn("title")]
        selects, prefetches = infer_optimizations(
            Article, columns,
        )
        assert len(selects) == 0
        assert len(prefetches) == 0


# ── Tests de flatten_columns ───────────────────────────────────

@pytest.mark.django_db
class TestFlattenColumns:
    def test_simple_columns(self):
        from tests.models import Article
        columns = [
            XlsColumn("id"),
            XlsColumn("title"),
        ]
        resolved = flatten_columns(columns, model=Article)
        assert len(resolved) == 2
        assert resolved[0].title == "ID de artículo"
        assert resolved[1].title == "Título"

    def test_condition_filters(self):
        columns = [
            XlsColumn("id"),
            XlsColumn(
                "secret", condition=lambda r: False,
            ),
        ]
        resolved = flatten_columns(columns, request=object())
        assert len(resolved) == 1

    def test_include_flattens(self):
        from tests.models import Article, Publisher
        from yeeko_xlsx_export import ModelExport

        class PubBlock(ModelExport):
            model = Publisher
            columns = [XlsColumn("name")]

        columns = [
            XlsColumn("title"),
            Include(PubBlock, through="publisher"),
        ]
        resolved = flatten_columns(columns, model=Article)
        assert len(resolved) == 2
        assert resolved[1].through_chain == ["publisher"]


# ── Tests de extract_row_auto ──────────────────────────────────

class TestExtractRowAuto:
    def test_simple_extraction(self):
        obj = SimpleObj(id=1, name="test")
        columns = [
            XlsColumn("id"),
            XlsColumn("name"),
        ]
        row = extract_row_auto(obj, columns)
        assert row == {"id": 1, "name": "test"}

    def test_fk_column_extraction(self):
        publisher = SimpleObj(name="Acme")
        obj = SimpleObj(publisher=publisher)
        columns = [FkColumn("publisher", "name")]
        row = extract_row_auto(obj, columns)
        assert row == {"publisher__name": "Acme"}

    def test_include_with_through(self):
        from yeeko_xlsx_export import ModelExport

        class InnerBlock(ModelExport):
            columns = [XlsColumn("val")]

        inner_obj = SimpleObj(val=42)
        obj = SimpleObj(child=inner_obj)
        columns = [Include(InnerBlock, through="child")]
        row = extract_row_auto(obj, columns)
        assert row == {"child__val": 42}

    def test_include_without_through(self):
        from yeeko_xlsx_export import ModelExport

        class AnnotBlock(ModelExport):
            columns = [XlsColumn("computed")]

        obj = SimpleObj(computed=99)
        columns = [Include(AnnotBlock)]
        row = extract_row_auto(obj, columns)
        assert row == {"computed": 99}

    def test_none_sub_object(self):
        from yeeko_xlsx_export import ModelExport

        class InnerBlock(ModelExport):
            columns = [XlsColumn("val")]

        obj = SimpleObj(child=None)
        columns = [Include(InnerBlock, through="child")]
        row = extract_row_auto(obj, columns)
        assert row == {"child__val": ""}

    def test_operation_on_collected_values(self):
        class FakeManager:
            def all(self):
                return [
                    SimpleObj(score=10),
                    SimpleObj(score=20),
                    SimpleObj(score=30),
                ]

        obj = SimpleObj(items=FakeManager())
        columns = [
            CollectColumn(
                "items", "score", operation="sum",
            ),
        ]
        row = extract_row_auto(obj, columns)
        assert row["items__score"] == 60

    def test_condition_excludes_column(self):
        obj = SimpleObj(public=1, secret=2)
        columns = [
            XlsColumn("public"),
            XlsColumn("secret", condition=lambda r: False),
        ]
        row = extract_row_auto(obj, columns, request=object())
        assert "public" in row
        assert "secret" not in row
