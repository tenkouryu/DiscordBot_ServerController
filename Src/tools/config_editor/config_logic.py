from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECRET_HINTS = ("token", "key", "secret", "password")


def default_config_path() -> Path:
    """リポジトリの Src/config/config.json を返す。"""
    return Path(__file__).resolve().parents[2] / "config" / "config.json"


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in SECRET_HINTS)


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("設定ファイルのトップレベルはオブジェクトである必要があります")
    return data


def save_config(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def value_to_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def text_to_value(text: str, original: Any) -> Any:
    """元が文字列ならそのまま、それ以外はJSONとして解釈する。"""
    if isinstance(original, str) or original is None and not text.strip():
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"JSONとして解釈できません: {error}") from error
