from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import discord

from function.file.path_service import application_root

_TEMP_ROOT = application_root() / "temp"


def create_template_output_path(
    category: str,
    prefix: str,
    suffix: str = ".csv",
) -> Path:
    """出力カテゴリ内に一意な成果物パスを作成する。"""
    if category not in {"set/response", "get/result"}:
        raise ValueError(f"未対応の出力カテゴリです: {category}")
    if suffix not in {".csv", ".zip"}:
        raise ValueError("出力ファイルの拡張子は .csv または .zip を指定してください。")

    safe_prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", prefix).strip("_")
    if not safe_prefix:
        raise ValueError("出力ファイル名を指定してください。")

    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return _TEMP_ROOT / f"{safe_prefix}_{timestamp}_{uuid4().hex[:8]}{suffix}"


def save_template_output(
    category: str,
    prefix: str,
    content: bytes,
    suffix: str = ".csv",
) -> Path:
    """成果物を分類先へ保存してパスを返す。"""
    output_path = create_template_output_path(category, prefix, suffix)
    output_path.write_bytes(content)
    return output_path


def delete_template_output(output_path: Path) -> None:
    """一時保存した成果物を削除する。"""
    output_path.unlink(missing_ok=True)


async def send_template_output(channel, content: str, output_path: Path) -> None:
    """成果物を送信し、送信後に一時ファイルを削除する。"""
    try:
        await channel.send(
            content,
            file=discord.File(output_path, filename=output_path.name),
        )
    finally:
        delete_template_output(output_path)