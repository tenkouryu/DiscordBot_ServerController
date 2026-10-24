from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_export_json(text: str) -> dict[str, Any]:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{error.lineno}行 {error.colno}列: {error.msg}"
        ) from error
    if not isinstance(document, dict):
        raise ValueError("JSONの最上位はオブジェクトである必要があります。")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ValueError("schema_version が1のサーバーエクスポートJSONではありません。")
    for key in ("guild", "roles", "members", "channels"):
        expected = dict if key == "guild" else list
        if not isinstance(document.get(key), expected):
            raise ValueError(f"{key} の形式が正しくありません。")
    return document


def format_export_json(text: str) -> str:
    document = parse_export_json(text)
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def load_export_json(path: Path) -> str:
    return format_export_json(path.read_text(encoding="utf-8-sig"))


def save_export_json(path: Path, text: str) -> None:
    formatted = format_export_json(text)
    path.write_text(formatted, encoding="utf-8", newline="\n")
