from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

BOM = b"\xef\xbb\xbf"
CHANNEL_TYPES = ("text", "voice")
TEMPLATE_NAME_TEXT = "設定するチャンネル名を入力"
BASE_COLUMNS = ("name", "type", "category")


@dataclass
class ChannelTable:
    columns: list[str]
    rows: list[dict[str, str]]
    has_bom: bool


def numbered_columns(columns: list[str], prefix: str) -> list[str]:
    pattern = re.compile(rf"{prefix}_(\d+)\Z")
    numbered = [(int(m.group(1)), c) for c in columns if (m := pattern.fullmatch(c))]
    return [column for _, column in sorted(numbered)]


def load_table(path: Path) -> ChannelTable:
    raw = path.read_bytes()
    has_bom = raw.startswith(BOM)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    if not rows or not rows[0]:
        raise ValueError("CSVにヘッダー行がありません。")
    source_columns = rows[0]
    if len(source_columns) != len(set(source_columns)):
        raise ValueError("CSVに同じ名前の列が複数あります。")
    if "name" not in source_columns or "type" not in source_columns:
        raise ValueError("チャンネルCSVとして認識できません。name列とtype列が必要です。")

    columns = list(source_columns)
    if "category" not in columns:
        columns.insert(columns.index("type") + 1, "category")
    table_rows: list[dict[str, str]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) > len(source_columns):
            raise ValueError(f"{line_number}行目の列数がヘッダーより多くなっています。")
        values = row + [""] * (len(source_columns) - len(row))
        if not any(value.strip() for value in values):
            continue
        item = dict(zip(source_columns, values))
        if item.get("name", "").strip() == TEMPLATE_NAME_TEXT:
            continue
        for column in columns:
            item.setdefault(column, "")
        table_rows.append(item)
    return ChannelTable(columns, table_rows, has_bom)


def save_table(path: Path, table: ChannelTable) -> None:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(table.columns)
    for row in table.rows:
        writer.writerow([row.get(column, "") for column in table.columns])
    path.write_bytes((BOM if table.has_bom else b"") + output.getvalue().encode("utf-8"))


def new_row(table: ChannelTable) -> dict[str, str]:
    row = {column: "" for column in table.columns}
    row["type"] = CHANNEL_TYPES[0]
    return row


def add_numbered_column(table: ChannelTable, prefix: str) -> str:
    existing = numbered_columns(table.columns, prefix)
    last = int(existing[-1].rsplit("_", 1)[1]) if existing else 0
    name = f"{prefix}_{last + 1}"
    if existing:
        insert_at = table.columns.index(existing[-1]) + 1
    else:
        # role_ は category の後ろ、user_ は最後のrole_(無ければ category)の後ろ
        anchors = numbered_columns(table.columns, "role") if prefix == "user" else []
        anchor = anchors[-1] if anchors else "category"
        insert_at = table.columns.index(anchor) + 1
    table.columns.insert(insert_at, name)
    for row in table.rows:
        row[name] = ""
    return name


def remove_last_numbered_column(table: ChannelTable, prefix: str) -> str:
    existing = numbered_columns(table.columns, prefix)
    if not existing:
        raise ValueError(f"{prefix}_ 列がありません。")
    name = existing[-1]
    table.columns.remove(name)
    for row in table.rows:
        row.pop(name, None)
    return name


def validate_row(row: dict[str, str]) -> str | None:
    """行の入力ミスを日本語メッセージで返す。問題なければ None。"""
    if not row.get("name", "").strip():
        return "チャンネル名(name)を入力してください。"
    if row.get("type", "").strip().lower() not in CHANNEL_TYPES:
        return "type は text または voice を指定してください。"
    return None
