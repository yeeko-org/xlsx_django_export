"""Tests para yeeko_xlsx_export.operations."""
from yeeko_xlsx_export.operations import apply_operation


class TestApplyOperation:
    def test_count(self):
        assert apply_operation("count", [1, 2, 3]) == 3

    def test_count_empty(self):
        assert apply_operation("count", []) == 0

    def test_count_none(self):
        assert apply_operation("count", None) == 0

    def test_sum(self):
        assert apply_operation("sum", [10, 20, 30]) == 60

    def test_sum_empty(self):
        assert apply_operation("sum", []) == 0

    def test_min(self):
        assert apply_operation("min", [3, 1, 2]) == 1

    def test_min_empty(self):
        assert apply_operation("min", []) == ""

    def test_max(self):
        assert apply_operation("max", [3, 1, 2]) == 3

    def test_first(self):
        assert apply_operation("first", ["a", "b", "c"]) == "a"

    def test_first_empty(self):
        assert apply_operation("first", []) == ""

    def test_last(self):
        assert apply_operation("last", ["a", "b", "c"]) == "c"

    def test_join(self):
        assert apply_operation("join", ["a", "b", "c"]) == "a, b, c"

    def test_join_custom_separator(self):
        result = apply_operation(
            "join", ["x", "y"], join_separator=" | ",
        )
        assert result == "x | y"

    def test_join_filters_none(self):
        assert apply_operation("join", ["a", None, "b"]) == "a, b"

    def test_join_empty(self):
        assert apply_operation("join", []) == ""

    def test_distinct_count(self):
        assert apply_operation(
            "distinct_count", [1, 2, 2, 3, 3, 3],
        ) == 3

    def test_unknown_operation(self):
        """Operación desconocida retorna el valor sin cambios."""
        assert apply_operation("unknown", [1, 2]) == [1, 2]
