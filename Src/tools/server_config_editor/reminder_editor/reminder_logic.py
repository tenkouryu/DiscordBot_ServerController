from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = str(Path(__file__).resolve().parents[3])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from function.reminder.reminder_service import (
    load_reminders_for_editor,
    save_reminders_from_editor,
    validate_reminders_for_editor,
)


def default_path() -> Path:
    """Return the reminders configuration next to the bot's runtime config."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent / "config" / "reminders.json"
    return Path(__file__).resolve().parents[3] / "config" / "reminders.json"


def load_reminders(path: Path) -> list[dict[str, object]]:
    return load_reminders_for_editor(path)


def save_reminders(
    path: Path,
    reminders: list[dict[str, object]],
) -> list[dict[str, object]]:
    return save_reminders_from_editor(path, reminders)


def validate_reminders(
    reminders: list[dict[str, object]],
) -> list[dict[str, object]]:
    return validate_reminders_for_editor(reminders)
