from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

BOM = b"\xef\xbb\xbf"
ACTIONS = ("追加", "削除")
TEMPLATE_ACTION_TEXT = "追加または削除を入力"


@dataclass(frozen=True)
class Format:
    """メンバーロールCSVの形式ごとの列定義。"""

    key: str
    label: str
    user_id: str
    username: str
    display_name: str
    role_prefix: str
    action: str | None
    allow_unnumbered_role: bool


SET_FORMAT = Format(
    "set", "member role set 用", "ユーザーID", "ユーザー名", "表示名", "ロール", "追加/削除", True
)
UPDATE_FORMAT = Format(
    "update", "member role update 用", "User ID", "Name", "Display Name", "Role", None, False
)


@dataclass
class MemberTable:
    format: Format
    columns: list[str]
    rows: list[dict[str, str]]
    has_bom: bool


def _role_pattern(fmt: Format) -> re.Pattern[str]:
    digits = r"\d*" if fmt.allow_unnumbered_role else r"\d+"
    return re.compile(rf"{re.escape(fmt.role_prefix)}({digits})\Z")


def detect_format(columns: list[str]) -> Format | None:
    """列名からCSV形式を判別する。"""
    if SET_FORMAT.action in columns:
        return SET_FORMAT
    if UPDATE_FORMAT.user_id in columns or UPDATE_FORMAT.username in columns:
        return UPDATE_FORMAT
    return None


def role_columns(columns: list[str], fmt: Format) -> list[str]:
    pattern = _role_pattern(fmt)
    numbered = [
        (int(match.group(1) or 0), column)
        for column in columns
        if (match := pattern.fullmatch(column))
    ]
    return [column for _, column in sorted(numbered)]


def load_table(path: Path) -> MemberTable:
    raw = path.read_bytes()
    has_bom = raw.startswith(BOM)
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    if not rows or not rows[0]:
        raise ValueError("CSVにヘッダー行がありません。")

    source_columns = rows[0]
    if len(source_columns) != len(set(source_columns)):
        raise ValueError("CSVに同じ名前の列が複数あります。")
    fmt = detect_format(source_columns)
    if fmt is None:
        raise ValueError(
            "メンバーロールCSVとして認識できません。"
            "「追加/削除」列(set用)、または「User ID」「Name」列(update用)が必要です。"
        )
    columns = list(source_columns)
    if not role_columns(columns, fmt):
        columns.append(f"{fmt.role_prefix}1")

    table_rows: list[dict[str, str]] = []
    for line_number, row in enumerate(rows[1:], start=2):
        if len(row) > len(source_columns):
            raise ValueError(f"{line_number}行目の列数がヘッダーより多くなっています。")
        values = row + [""] * (len(source_columns) - len(row))
        if not any(value.strip() for value in values):
            continue
        item = dict(zip(source_columns, values))
        if fmt.action and item.get(fmt.action, "").strip() == TEMPLATE_ACTION_TEXT:
            continue
        for column in columns:
            item.setdefault(column, "")
        table_rows.append(item)
    return MemberTable(fmt, columns, table_rows, has_bom)


def save_table(path: Path, table: MemberTable) -> None:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(table.columns)
    for row in table.rows:
        writer.writerow([row.get(column, "") for column in table.columns])
    data = output.getvalue().encode("utf-8")
    path.write_bytes((BOM if table.has_bom else b"") + data)


def new_row(table: MemberTable) -> dict[str, str]:
    row = {column: "" for column in table.columns}
    if table.format.action:
        row[table.format.action] = ACTIONS[0]
    return row


def add_role_column(table: MemberTable) -> str:
    existing = role_columns(table.columns, table.format)
    pattern = _role_pattern(table.format)
    last_number = int(pattern.fullmatch(existing[-1]).group(1) or 0) if existing else 0
    name = f"{table.format.role_prefix}{last_number + 1}"
    insert_at = table.columns.index(existing[-1]) + 1 if existing else len(table.columns)
    table.columns.insert(insert_at, name)
    for row in table.rows:
        row[name] = ""
    return name


def remove_last_role_column(table: MemberTable) -> str:
    existing = role_columns(table.columns, table.format)
    if len(existing) <= 1:
        raise ValueError("ロール列は最低1列必要です。")
    name = existing[-1]
    table.columns.remove(name)
    for row in table.rows:
        row.pop(name, None)
    return name


def validate_row(table: MemberTable, row: dict[str, str]) -> str | None:
    """行の入力ミスを日本語メッセージで返す。問題なければ None。"""
    fmt = table.format
    if fmt.action and row.get(fmt.action, "").strip() not in ACTIONS:
        return f"「{fmt.action}」は「追加」または「削除」を指定してください。"

    user_id = row.get(fmt.user_id, "").strip()
    username = row.get(fmt.username, "").strip()
    display_name = row.get(fmt.display_name, "").strip()
    if not (user_id or username or display_name):
        return f"「{fmt.user_id}」「{fmt.username}」「{fmt.display_name}」のいずれかを入力してください。"
    if user_id and not user_id.isdecimal():
        return f"「{fmt.user_id}」は数字で入力してください。"

    if fmt.action:
        roles = [row.get(column, "").strip() for column in role_columns(table.columns, fmt)]
        if not any(roles):
            return "ロール名を1つ以上入力してください。"
    return None
