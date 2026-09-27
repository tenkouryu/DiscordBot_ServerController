from __future__ import annotations

import sys
from pathlib import Path


def application_root() -> Path:
    """設定やテンプレートを配置するアプリケーションルートを返す。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]