import tempfile
import unittest
from pathlib import Path

from tools.server_role_editor.role_logic import load_roles, permission_columns, save_roles


class ServerRoleEditorLogicTest(unittest.TestCase):
    def test_loads_template_and_skips_instruction_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.csv"
            path.write_text(
                "\ufeffname,color,manage_channels\r\n"
                "設定するロール名を入力,色を #RRGGBB 形式で入力,false\r\n"
                "Moderator,#123ABC,true\r\n",
                encoding="utf-8",
            )

            columns, roles, has_bom = load_roles(path)

            self.assertEqual(columns, ["name", "color", "manage_channels"])
            self.assertEqual(roles, [{
                "name": "Moderator",
                "color": "#123ABC",
                "manage_channels": "true",
            }])
            self.assertTrue(has_bom)

    def test_adds_color_column_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.csv"
            path.write_text("name\r\nModerator\r\n", encoding="utf-8")

            columns, roles, _ = load_roles(path)

            self.assertEqual(columns, ["name", "color"])
            self.assertEqual(roles[0], {"name": "Moderator", "color": ""})

    def test_rejects_missing_name_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.csv"
            path.write_text("role,color\r\nModerator,#123ABC\r\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "name"):
                load_roles(path)

    def test_save_preserves_bom_and_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roles.csv"
            columns = ["name", "color", "manage_channels"]
            roles = [{
                "name": "Moderator, Jr.",
                "color": "#123ABC",
                "manage_channels": "true",
            }]

            save_roles(path, columns, roles, True)

            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(load_roles(path)[:2], (columns, roles))

    def test_permission_columns_excludes_role_metadata(self):
        self.assertEqual(
            permission_columns(["id", "name", "color", "manage_channels", "reason"]),
            ["manage_channels"],
        )


if __name__ == "__main__":
    unittest.main()
