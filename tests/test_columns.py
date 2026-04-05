"""Tests para yeeko_xlsx_export.columns."""
import pytest
from yeeko_xlsx_export.columns import (
    CollectColumn, FkColumn, Include, XlsColumn,
    _resolve_width_for_field,
)


class TestXlsColumn:
    def test_basic_creation(self):
        col = XlsColumn("name")
        assert col.field == "name"
        assert col.title is None
        assert col.width is None
        assert col.operation is None

    def test_orm_path_without_source(self):
        col = XlsColumn("title")
        assert col.orm_path == "title"

    def test_orm_path_with_source(self):
        col = XlsColumn(
            "note_count",
            source="participants__mention__note__date",
        )
        assert col.orm_path == "participants__mention__note__date"

    def test_needs_collect_always_false(self):
        col = XlsColumn(
            "note_count",
            source="participants__mention__note__date",
            operation="count",
        )
        assert col.needs_collect is False

    def test_no_collect_without_source(self):
        col = XlsColumn("name", operation="count")
        assert col.needs_collect is False

    def test_resolve_title_explicit(self):
        col = XlsColumn("x", title="Mi título")
        assert col.resolve_title() == "Mi título"

    def test_resolve_title_fallback(self):
        col = XlsColumn("some_field")
        assert col.resolve_title() == "Some field"

    @pytest.mark.django_db
    def test_resolve_title_from_model(self):
        from tests.models import Article
        col = XlsColumn("title")
        resolved = col.resolve_title(Article)
        assert resolved == "Título"

    @pytest.mark.django_db
    def test_resolve_title_name_field(self):
        from tests.models import Publisher
        col = XlsColumn("name")
        resolved = col.resolve_title(Publisher)
        assert resolved == "Nombre de editorial"

    @pytest.mark.django_db
    def test_resolve_title_id_field(self):
        from tests.models import Article
        col = XlsColumn("id")
        resolved = col.resolve_title(Article)
        assert resolved == "ID de artículo"

    @pytest.mark.django_db
    def test_resolve_width_date(self):
        from tests.models import Article
        col = XlsColumn("published_date")
        assert col.resolve_width(Article) == 12

    @pytest.mark.django_db
    def test_resolve_width_explicit(self):
        col = XlsColumn("title", width=40)
        assert col.resolve_width() == 40

    @pytest.mark.django_db
    def test_resolve_width_textfield(self):
        from tests.models import Article
        col = XlsColumn("body")
        assert col.resolve_width(Article) == 35


class TestFkColumn:
    def test_full_path(self):
        col = FkColumn("publisher", "name")
        assert col.full_path == "publisher__name"

    def test_orm_path(self):
        col = FkColumn("publisher", "name")
        assert col.orm_path == "publisher__name"

    def test_orm_path_with_source(self):
        col = FkColumn(
            "publisher", "name",
            source="publisher__country",
        )
        assert col.orm_path == "publisher__country"

    @pytest.mark.django_db
    def test_resolve_title_from_fk_model(self):
        from tests.models import Article
        col = FkColumn("publisher", "name")
        resolved = col.resolve_title(Article)
        assert resolved == "Nombre de editorial"

    @pytest.mark.django_db
    def test_resolve_title_explicit(self):
        from tests.models import Article
        col = FkColumn(
            "publisher", "country", title="País editorial",
        )
        assert col.resolve_title(Article) == "País editorial"


class TestCollectColumn:
    def test_full_path(self):
        col = CollectColumn("tags", "name")
        assert col.full_path == "tags__name"

    def test_orm_path(self):
        col = CollectColumn("tags", "name")
        assert col.orm_path == "tags__name"

    def test_default_operation_is_join(self):
        col = CollectColumn("tags", "name")
        assert col.operation == "join"

    def test_explicit_operation(self):
        col = CollectColumn("tags", "name", operation="count")
        assert col.operation == "count"

    def test_needs_collect_always_true(self):
        col = CollectColumn("tags", "name")
        assert col.needs_collect is True

    def test_deep_chain_full_path(self):
        col = CollectColumn(
            "participants__mention__note", "date",
        )
        assert col.full_path == (
            "participants__mention__note__date"
        )

    def test_resolve_title_explicit(self):
        col = CollectColumn(
            "tags", "name", title="Etiquetas",
        )
        assert col.resolve_title() == "Etiquetas"

    def test_resolve_title_fallback(self):
        col = CollectColumn("tags", "some_field")
        assert col.resolve_title() == "Some field"

    @pytest.mark.django_db
    def test_resolve_title_from_model(self):
        from tests.models import Article
        col = CollectColumn("tags", "name")
        resolved = col.resolve_title(Article)
        assert resolved == "Nombre de etiqueta"

    @pytest.mark.django_db
    def test_resolve_width_explicit(self):
        col = CollectColumn("tags", "name", width=30)
        assert col.resolve_width() == 30

    @pytest.mark.django_db
    def test_resolve_width_from_model(self):
        from tests.models import Article
        col = CollectColumn("tags", "name")
        # CharField max_length=50 → 20
        assert col.resolve_width(Article) == 20


class TestInclude:
    def test_basic(self):
        inc = Include(block=object, through="mention")
        assert inc.through == "mention"

    def test_no_through(self):
        inc = Include(block=object)
        assert inc.through is None
