
"""ZIP圧縮・解凍サービスの動作を検証するテスト。"""
import zipfile
import unittest
from pathlib import Path

from function.file.zip_service import compress_directory, extract_zip

class ZipServiceTests(unittest.TestCase):
    def test_compress_directory_and_extract_zip(self):
        with self.subTest("round trip"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                source = root / "source"
                (source / "nested").mkdir(parents=True)
                (source / "root.txt").write_text("root", encoding="utf-8")
                (source / "nested" / "child.txt").write_text(
                    "child",
                    encoding="utf-8",
                )
                archive = root / "files.zip"
                destination = root / "destination"

                compress_directory(source, archive)
                extract_zip(archive, destination)

                self.assertEqual(
                    (destination / "root.txt").read_text(encoding="utf-8"),
                    "root",
                )
                self.assertEqual(
                    (destination / "nested" / "child.txt").read_text(
                        encoding="utf-8"
                    ),
                    "child",
                )

    def test_extract_zip_rejects_path_traversal(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as archive_file:
                archive_file.writestr("../outside.txt", "unsafe")

            with self.assertRaisesRegex(ValueError, "ZIP"):
                extract_zip(archive, root / "destination")


if __name__ == "__main__":
    unittest.main()