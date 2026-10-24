from __future__ import annotations

import csv
import io
from pathlib import Path

BOM = b"\xef\xbb\xbf"
FIXED_COLUMNS = {"id", "name", "color", "result", "reason"}
TEMPLATE_ROW_NAME = "設定するロール名を入力"


def load_roles(path: Path) -> tuple[list[str], list[dict[str, str]], bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(BOM)
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = list(reader)
    if not rows or not rows[0]:
        raise ValueError("CSVにヘッダー行がありません。")

    source_columns = rows[0]
    if len(source_columns) != len(set(source_columns)):
        raise ValueError("CSVに同じ名前の列が複数あります。")
    if "name" not in source_columns:
        raise ValueError("CSVに name 列がありません。")
    columns = list(source_columns)
    if "color" not in source_columns:
        columns.append("color")

    roles: list[dict[str, str]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) > len(source_columns):
            raise ValueError(f"{line_number}行目の列数がヘッダーより多くなっています。")
        values = row + [""] * (len(source_columns) - len(row))
        if not any(value.strip() for value in values):
            continue
        role = dict(zip(source_columns, values))
        role.setdefault("color", "")
        if role.get("name", "").strip() == TEMPLATE_ROW_NAME:
            continue
        roles.append(role)
    return columns, roles, has_bom


def save_roles(path: Path, columns: list[str], roles: list[dict[str, str]], has_bom: bool) -> None:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(columns)
    for role in roles:
        writer.writerow([role.get(column, "") for column in columns])
    data = output.getvalue().encode("utf-8")
    path.write_bytes((BOM if has_bom else b"") + data)


def permission_columns(columns: list[str]) -> list[str]:
    return [column for column in columns if column not in FIXED_COLUMNS]
