import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.config_editor.config_logic import (
    default_config_path,
    is_secret_key,
    load_config,
    save_config,
    text_to_value,
    value_to_text,
)


class ConfigLogicTest(unittest.TestCase):
    def test_roundtrip_with_bom_and_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"BOT_TOKEN": "x", "n": 1}), encoding="utf-8-sig")
            data = load_config(p)
            data["日本語"] = "値"
            save_config(p, data)
            self.assertEqual(load_config(p), data)
            self.assertFalse(p.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_value_conversion(self):
        self.assertEqual(text_to_value("abc", "old"), "abc")
        self.assertEqual(text_to_value("5", 1), 5)
        self.assertEqual(value_to_text([1]), "[1]")
        with self.assertRaises(ValueError):
            text_to_value("{", 1)

    def test_secret(self):
        self.assertTrue(is_secret_key("BOT_TOKEN"))
        self.assertTrue(is_secret_key("encryption_key"))
        self.assertFalse(is_secret_key("name"))

    def test_default_path_for_frozen_release_executable(self):
        executable = Path("C:/release/tools/config_editor.exe")
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(executable)
        ):
            self.assertEqual(default_config_path(), Path("C:/release/config/config.json"))


if __name__ == "__main__":
    unittest.main()
