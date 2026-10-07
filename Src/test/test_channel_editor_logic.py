import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "channel_editor"))
import channel_logic as logic  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "set" / "input" / "channel_template.csv"


class ChannelLogicTests(unittest.TestCase):
    def write(self, text: str, bom: bool = False) -> Path:
        directory = tempfile.mkdtemp()
        path = Path(directory) / "c.csv"
        path.write_bytes((logic.BOM if bom else b"") + text.encode("utf-8"))
        return path

    def test_template_instruction_row_is_skipped(self):
        table = logic.load_table(TEMPLATE)
        self.assertEqual(table.rows, [])
        self.assertEqual(table.columns, ["name", "type", "category", "role_1", "role_2", "user_1", "user_2"])

    def test_round_trip_keeps_bom_and_result_columns(self):
        path = self.write("name,type,category,result,reason\r\nabc,text,cat,成功,\r\n", bom=True)
        table = logic.load_table(path)
        self.assertTrue(table.has_bom)
        logic.save_table(path, table)
        self.assertEqual(path.read_bytes(), logic.BOM + "name,type,category,result,reason\r\nabc,text,cat,成功,\r\n".encode())

    def test_missing_category_is_added(self):
        table = logic.load_table(self.write("name,type\r\na,voice\r\n"))
        self.assertEqual(table.columns, ["name", "type", "category"])

    def test_unrecognised_csv_is_rejected(self):
        with self.assertRaises(ValueError):
            logic.load_table(self.write("a,b\r\n1,2\r\n"))

    def test_add_and_remove_numbered_columns(self):
        table = logic.load_table(self.write("name,type,category\r\na,text,\r\n"))
        self.assertEqual(logic.add_numbered_column(table, "role"), "role_1")
        self.assertEqual(logic.add_numbered_column(table, "user"), "user_1")
        self.assertEqual(logic.add_numbered_column(table, "role"), "role_2")
        self.assertEqual(table.columns, ["name", "type", "category", "role_1", "role_2", "user_1"])
        self.assertEqual(logic.remove_last_numbered_column(table, "role"), "role_2")
        self.assertNotIn("role_2", table.rows[0])
        with self.assertRaises(ValueError):
            logic.remove_last_numbered_column(table, "nothing")

    def test_validate_row(self):
        self.assertIsNone(logic.validate_row({"name": "a", "type": "Text"}))
        self.assertIsNotNone(logic.validate_row({"name": "", "type": "text"}))
        self.assertIsNotNone(logic.validate_row({"name": "a", "type": "stage"}))


if __name__ == "__main__":
    unittest.main()
