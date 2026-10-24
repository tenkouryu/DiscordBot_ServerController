from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.server_config_editor.reminder_editor.reminder_logic import (
    default_path,
    load_reminders,
    save_reminders,
    validate_reminders,
)


class ReminderEditorLogicTests(unittest.TestCase):
    def test_default_path_for_source_and_frozen_editor(self) -> None:
        source_path = default_path()
        self.assertTrue(source_path.as_posix().endswith("/Src/config/reminders.json"))

        executable = Path("C:/release/tools/server_config_editor.exe")
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(executable)
        ):
            self.assertEqual(
                default_path(),
                Path("C:/release/config/reminders.json"),
            )

    def test_load_save_and_validate_reminders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reminders.json"
            path.write_text(
                json.dumps(
                    {
                        "reminders": [
                            {
                                "id": "editor-test",
                                "datetime": "2026-10-25T10:00:00+09:00",
                                "channel_id": "123456",
                                "content": "edited reminder",
                                "mention_users": ["234567"],
                                "mention_roles": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            reminders = load_reminders(path)
            self.assertEqual(reminders[0]["id"], "editor-test")
            reminders[0]["content"] = "updated"
            validated = validate_reminders(reminders)
            self.assertEqual(validated[0]["content"], "updated")
            self.assertEqual(load_reminders(path)[0]["content"], "edited reminder")

            save_reminders(path, validated)

            self.assertEqual(load_reminders(path)[0]["content"], "updated")

    def test_invalid_reminder_is_not_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reminders.json"
            original = '{"reminders": []}\n'
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ValueError):
                save_reminders(
                    path,
                    [
                        {
                            "id": "invalid",
                            "datetime": "2026-10-25T10:00:00+00:00",
                            "channel_id": "123456",
                            "content": "invalid timezone",
                        }
                    ],
                )

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
