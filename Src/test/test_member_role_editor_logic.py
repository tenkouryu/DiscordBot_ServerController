import tempfile
import unittest
from pathlib import Path

from tools.member_role_editor.member_logic import (
    SET_FORMAT,
    UPDATE_FORMAT,
    add_role_column,
    detect_format,
    load_table,
    new_row,
    remove_last_role_column,
    role_columns,
    save_table,
    validate_row,
)

REPO = Path(__file__).resolve().parents[2]


def write(directory, text, name="m.csv"):
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


class MemberRoleEditorLogicTest(unittest.TestCase):
    def test_detects_both_formats(self):
        self.assertIs(detect_format(["追加/削除", "ユーザーID", "ロール1"]), SET_FORMAT)
        self.assertIs(detect_format(["User ID", "Name", "Role1"]), UPDATE_FORMAT)
        self.assertIsNone(detect_format(["name", "color"]))

    def test_set_template_skips_instruction_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(
                directory,
                "\ufeff追加/削除,ユーザーID,ユーザー名,表示名,ロール1,ロール2\r\n"
                "追加または削除を入力,ID,名前,表示,ロール,ロール\r\n"
                "追加,123,,,Mod,\r\n\r\n",
            )
            table = load_table(path)
        self.assertIs(table.format, SET_FORMAT)
        self.assertTrue(table.has_bom)
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.rows[0]["ロール1"], "Mod")

    def test_update_format_round_trip_keeps_result_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(
                directory,
                "User ID,Name,Display Name,Role1,result,reason\r\n"
                "1,alice,Alice,A,成功,\r\n",
            )
            table = load_table(path)
            out = Path(directory) / "out.csv"
            save_table(out, table)
            self.assertEqual(
                out.read_bytes().decode("utf-8"),
                "User ID,Name,Display Name,Role1,result,reason\r\n1,alice,Alice,A,成功,\r\n",
            )

    def test_add_and_remove_role_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            table = load_table(write(directory, "User ID,Name,Role1,Role2,result\n1,a,A,B,x\n"))
        self.assertEqual(add_role_column(table), "Role3")
        self.assertEqual(table.columns, ["User ID", "Name", "Role1", "Role2", "Role3", "result"])
        self.assertEqual(remove_last_role_column(table), "Role3")
        remove_last_role_column(table)
        with self.assertRaises(ValueError):
            remove_last_role_column(table)
        self.assertEqual(role_columns(table.columns, UPDATE_FORMAT), ["Role1"])

    def test_missing_role_column_is_added(self):
        with tempfile.TemporaryDirectory() as directory:
            table = load_table(write(directory, "User ID,Name\n1,a\n"))
        self.assertEqual(table.columns, ["User ID", "Name", "Role1"])

    def test_unnumbered_role_column_is_supported_for_set(self):
        with tempfile.TemporaryDirectory() as directory:
            table = load_table(write(directory, "追加/削除,ユーザー名,ロール\n追加,a,X\n"))
        self.assertEqual(role_columns(table.columns, SET_FORMAT), ["ロール"])
        self.assertEqual(add_role_column(table), "ロール1")

    def test_rejects_unknown_format_and_duplicate_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                load_table(write(directory, "name,color\nA,#fff\n"))
            with self.assertRaises(ValueError):
                load_table(write(directory, "User ID,User ID\n1,2\n", "d.csv"))

    def test_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            set_table = load_table(write(directory, "追加/削除,ユーザーID,ユーザー名,表示名,ロール1\n追加,1,,,A\n"))
            update_table = load_table(write(directory, "User ID,Name,Display Name,Role1\n1,,,\n", "u.csv"))

        row = set_table.rows[0]
        self.assertIsNone(validate_row(set_table, row))
        self.assertIn("追加", validate_row(set_table, {**row, "追加/削除": "変更"}))
        self.assertIn("数字", validate_row(set_table, {**row, "ユーザーID": "abc"}))
        self.assertIn("いずれか", validate_row(set_table, {**row, "ユーザーID": ""}))
        self.assertIn("ロール名", validate_row(set_table, {**row, "ロール1": ""}))
        self.assertIsNone(validate_row(update_table, update_table.rows[0]))
        self.assertEqual(new_row(set_table)["追加/削除"], "追加")

    def test_shipped_templates_load(self):
        template = REPO / "release" / "tools" / "templates" / "set" / "input" / "member_role_template.csv"
        table = load_table(template)
        self.assertIs(table.format, SET_FORMAT)
        self.assertEqual(table.rows, [])


if __name__ == "__main__":
    unittest.main()
