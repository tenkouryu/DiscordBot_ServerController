from __future__ import annotations

import csv
import io
import os
import sys
import zipfile
from pathlib import Path

BOM = b"\xef\xbb\xbf"


def default_templates_dir() -> Path:
    """Src/templates を返す。exe実行時は exe 隣の templates、無ければ exe のあるフォルダ。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        return base / "templates" if (base / "templates").is_dir() else base
    return Path(__file__).resolve().parents[2] / "templates"


EXCLUDED_DIRS = {
    "build", "dist", "node_modules", "site-packages", "venv", "env",
    "__pycache__", "temp", "tmp", "cache",
}


def _is_excluded_dir(name: str) -> bool:
    return name.startswith((".", "$")) or name.lower() in EXCLUDED_DIRS


def _is_csv_zip(path: Path) -> bool:
    """zipのうちCSVを含むものだけを対象にする。"""
    try:
        with zipfile.ZipFile(path) as archive:
            return any(n.lower().endswith(".csv") for n in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def list_template_files(root: Path) -> list[Path]:
    """関連しそうなCSV/zipだけを列挙する。隠し・ビルド・環境系フォルダは辿らない。"""
    found: list[Path] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not _is_excluded_dir(d)]
        for name in files:
            path = Path(current) / name
            suffix = path.suffix.lower()
            if suffix == ".csv" or (suffix == ".zip" and _is_csv_zip(path)):
                found.append(path)
    return sorted(found)


def _zip_csv_name(path: Path) -> str:
    """zip内のCSVエントリ名を返す。既存zipに無ければ拡張子を .csv にした名前。"""
    if path.exists():
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if names:
            return names[0]
    return path.stem + ".csv"


def load_table(path: Path) -> tuple[list[list[str]], bool]:
    """CSV(またはCSVを含むzip)を行リストで読み込む。戻り値は (行, BOM有無)。"""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(_zip_csv_name(path))
    else:
        raw = path.read_bytes()
    has_bom = raw.startswith(BOM)
    text = raw.decode("utf-8-sig")
    rows = [list(row) for row in csv.reader(io.StringIO(text, newline=""))]
    return normalize(rows), has_bom


def normalize(rows: list[list[str]]) -> list[list[str]]:
    """全行の列数を最大列数にそろえる。"""
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def save_table(path: Path, rows: list[list[str]], bom: bool) -> None:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\r\n").writerows(rows)
    data = buffer.getvalue().encode("utf-8")
    data = (BOM if bom else b"") + data
    if path.suffix.lower() == ".zip":
        name = _zip_csv_name(path)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(name, data)
    else:
        path.write_bytes(data)

