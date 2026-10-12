import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from common.treeview_filter import _sort_value, matches_filters


class FakeTreeview:
    def __init__(self):
        self.columns = ("name", "type")
        self.headings = {
            "name": {"text": "名前"},
            "type": {"text": "種類"},
        }

    def __getitem__(self, key):
        if key == "columns":
            return self.columns
        raise KeyError(key)

    def heading(self, column, option=None, **kwargs):
        if kwargs:
            self.headings[column].update(kwargs)
        if option is not None:
            return self.headings[column].get(option)
        return self.headings[column]


class TreeviewFilterTests(unittest.TestCase):
    def test_multiple_column_filters_use_and_and_match_exact_values(self):
        filters = {0: {"alpha", "beta"}, 1: {"text"}}
        self.assertTrue(matches_filters(("alpha", "text"), filters))
        self.assertFalse(matches_filters(("alpha", "voice"), filters))
        self.assertFalse(matches_filters(("gamma", "text"), filters))

    def test_blank_values_and_empty_filter(self):
        self.assertTrue(matches_filters(("name", ""), {1: {""}}))
        self.assertFalse(matches_filters(("name", "text"), {1: {""}}))
        self.assertTrue(matches_filters(("name", "text"), {}))

    def test_missing_column_does_not_match(self):
        self.assertFalse(matches_filters(("name",), {1: {""}}))

    def test_excel_dropdown_sort_values_are_numeric_and_case_insensitive(self):
        self.assertLess(_sort_value("2"), _sort_value("10"))
        self.assertEqual(_sort_value("Voice"), _sort_value("voice"))
        self.assertLess(_sort_value(""), _sort_value("1"))

    def test_column_heading_opens_filter_dropdown_and_keeps_sort_indicator(self):
        from common.treeview_filter import TreeviewColumnFilter

        tree = FakeTreeview()
        column_filter = TreeviewColumnFilter(tree)
        opened_columns = []
        column_filter.open_filter = opened_columns.append
        column_filter.header_suffix = lambda index: " ↑" if index == 0 else ""

        column_filter.refresh_headers()
        tree.heading("name")["command"]()

        self.assertEqual(opened_columns, [0])
        self.assertEqual(tree.heading("name", "text"), "名前 ↑ ▼")


if __name__ == "__main__":
    unittest.main()
