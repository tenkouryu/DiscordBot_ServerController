from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.server_export_editor.json_editor_logic import (
    format_export_json,
    load_export_json,
    parse_export_json,
    save_export_json,
)
from tools.server_export_editor.server_export_editor import _new_item, _sort_value


SAMPLE = {
    "schema_version": 1,
    "guild": {"id": "10", "name": "移行元"},
    "roles": [],
    "members": [],
    "channels": [],
}


class ServerExportEditorTests(unittest.TestCase):
    def test_format_preserves_unicode_and_json_values(self):
        source = json.dumps({**SAMPLE, "guild": {"name": "移行先"}}, ensure_ascii=True)

        result = format_export_json(source)

        self.assertIn("移行先", result)
        self.assertEqual(json.loads(result)["guild"]["name"], "移行先")

    def test_rejects_non_export_or_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            parse_export_json('{"roles": [], "members": [], "channels": [], "guild": {}}')
        with self.assertRaisesRegex(ValueError, "行"):
            parse_export_json("{")

    def test_loads_utf8_bom_and_save_writes_formatted_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server_export.json"
            path.write_bytes(b"\xef\xbb\xbf" + json.dumps(SAMPLE).encode("utf-8"))

            loaded = load_export_json(path)
            save_export_json(path, loaded)

            saved = path.read_text(encoding="utf-8")
        self.assertEqual(json.loads(saved), SAMPLE)
        self.assertTrue(saved.endswith("\n"))
        self.assertIn('"schema_version": 1', saved)

    def test_new_items_get_unique_ids_and_export_compatible_fields(self):
        document = {
            "roles": [
                {
                    "id": "4",
                    "name": "Editor",
                    "position": 1,
                    "permissions": {"view_channel": True},
                },
                {
                    "id": "9",
                    "name": "Moderator",
                    "position": 4,
                    "permissions": {"manage_messages": True},
                }
            ],
            "members": [{"id": "8"}],
            "channels": [{"id": "12"}],
        }

        role = _new_item("roles", document)
        member = _new_item("members", document)
        channel = _new_item("channels", document)

        self.assertEqual(role["id"], "10")
        self.assertEqual(role["position"], 1)
        self.assertEqual(document["roles"][0]["position"], 2)
        self.assertEqual(document["roles"][1]["position"], 5)
        self.assertEqual(role["permissions"], {"view_channel": False})
        self.assertEqual(member["id"], "9")
        self.assertEqual(member["role_ids"], [])
        self.assertEqual(channel["id"], "13")
        self.assertEqual(channel["type"], "text")
        self.assertEqual(channel["permission_overwrites"], [])

    def test_new_role_defaults_to_lowest_position_above_everyone(self):
        document = {
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "position": 0,
                    "permissions": {},
                }
            ],
            "members": [],
            "channels": [],
        }

        role = _new_item("roles", document)

        self.assertEqual(role["position"], 1)

    def test_new_role_skips_everyone_position_and_shifts_existing_roles(self):
        document = {
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "position": 1,
                    "permissions": {},
                },
                {
                    "id": "2",
                    "name": "Editor",
                    "is_default": False,
                    "position": 2,
                    "permissions": {},
                },
            ],
            "members": [],
            "channels": [],
        }

        role = _new_item("roles", document)

        self.assertEqual(role["position"], 2)
        self.assertEqual(document["roles"][1]["position"], 3)
        self.assertNotIn(role["position"], [item["position"] for item in document["roles"]])

    def test_new_role_can_copy_everyone_permissions(self):
        document = {
            "roles": [
                {
                    "id": "1",
                    "name": "@everyone",
                    "is_default": True,
                    "position": 0,
                    "permissions": {"view_channel": True, "send_messages": False},
                },
                {
                    "id": "2",
                    "name": "Moderator",
                    "is_default": False,
                    "position": 1,
                    "permissions": {"view_channel": False, "send_messages": True},
                },
            ],
            "members": [],
            "channels": [],
        }

        role = _new_item("roles", document, match_everyone_permissions=True)

        self.assertEqual(
            role["permissions"],
            {"view_channel": True, "send_messages": False},
        )

    def test_sort_values_sort_numbers_numerically_and_text_case_insensitively(self):
        self.assertLess(_sort_value("2"), _sort_value("10"))
        self.assertEqual(_sort_value("Editor"), _sort_value("editor"))
        self.assertLess(_sort_value(""), _sort_value("1"))


if __name__ == "__main__":
    unittest.main()
