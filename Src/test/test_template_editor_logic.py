import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.template_editor.template_logic import list_template_files, load_table, normalize, save_table


class TemplateLogicTest(unittest.TestCase):
    def test_roundtrip_preserves_bom_and_quoting(self):
        with tempfile.TemporaryDirectory() as d:
            for bom in (True, False):
                p = Path(d) / "t.csv"
                rows = [["a", "b"], ["x,y", "改行\n含む"], ["", "\"q\""]]
                save_table(p, rows, bom)
                loaded, has_bom = load_table(p)
                self.assertEqual(loaded, rows)
                self.assertEqual(has_bom, bom)

    def test_zip_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("server_member_list.csv", "\ufeffa,b\r\n1,2\r\n".encode("utf-8"))
            rows, bom = load_table(p)
            self.assertEqual((rows, bom), ([["a", "b"], ["1", "2"]], True))
            rows[1][0] = "9"
            save_table(p, rows, bom)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(z.namelist(), ["server_member_list.csv"])
            self.assertEqual(load_table(p)[0][1][0], "9")

    def test_normalize_pads(self):
        self.assertEqual(normalize([["a", "b"], ["c"]]), [["a", "b"], ["c", ""]])

    def test_list_files_excludes_unrelated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for sub in ("ok", ".git", "build", "node_modules"):
                (root / sub).mkdir()
                (root / sub / "a.csv").write_text("a", encoding="utf-8")
            with zipfile.ZipFile(root / "good.zip", "w") as z:
                z.writestr("x.csv", "a")
            with zipfile.ZipFile(root / "bad.zip", "w") as z:
                z.writestr("x.txt", "a")
            (root / "broken.zip").write_bytes(b"nope")
            names = [p.relative_to(root).as_posix() for p in list_template_files(root)]
            self.assertEqual(names, ["good.zip", "ok/a.csv"])

    def test_list_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sub").mkdir()
            (Path(d) / "sub" / "a.csv").write_text("a", encoding="utf-8")
            (Path(d) / "b.txt").write_text("b", encoding="utf-8")
            self.assertEqual([p.name for p in list_template_files(Path(d))], ["a.csv"])


if __name__ == "__main__":
    unittest.main()

