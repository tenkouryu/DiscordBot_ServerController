import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from common.treeview_filter import matches_filters


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


if __name__ == "__main__":
    unittest.main()
