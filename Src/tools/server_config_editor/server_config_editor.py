from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from server_config_editor.channel_editor.channel_editor import ChannelEditor  # noqa: E402
from server_config_editor.channel_editor.channel_editor import default_path as default_channel_path  # noqa: E402
from server_config_editor.config_editor.config_editor import ConfigEditor  # noqa: E402
from server_config_editor.config_editor.config_logic import default_config_path  # noqa: E402
from server_config_editor.member_role_editor.member_role_editor import MemberRoleEditor  # noqa: E402
from server_config_editor.member_role_editor.member_role_editor import default_path as default_member_path  # noqa: E402
from server_config_editor.reminder_editor.reminder_editor import ReminderEditor  # noqa: E402
from server_config_editor.reminder_editor.reminder_logic import default_path as default_reminder_path  # noqa: E402
from server_config_editor.scenario_editor.scenario_editor import ScenarioEditor  # noqa: E402
from server_config_editor.server_role_editor.server_role_editor import ServerRoleEditor  # noqa: E402
from server_config_editor.server_role_editor.server_role_editor import default_path as default_role_path  # noqa: E402
from server_config_editor.template_editor.template_editor import TemplateEditor  # noqa: E402
from server_config_editor.template_editor.template_logic import default_templates_dir  # noqa: E402
from server_config_editor.server_export_editor.server_export_editor import ServerExportJsonEditor  # noqa: E402

APP_TITLE = "サーバー設定統合エディター"


def default_scenario_path() -> Path | None:
    candidate = default_templates_dir() / "set" / "input" / "scenario_template.csv"
    return candidate if candidate.exists() else None


class ServerConfigEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(820, 540)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.editors: list[tuple[str, tk.Misc]] = []

        self.add_tab("設定", ConfigEditor(default_config_path(), self.notebook))
        self.add_tab("テンプレート", TemplateEditor(default_templates_dir(), self.notebook))
        self.add_tab("サーバーロール", ServerRoleEditor(default_role_path(), self.notebook))
        self.add_tab("メンバーロール", MemberRoleEditor(default_member_path(), self.notebook))
        self.add_tab("チャンネル", ChannelEditor(default_channel_path(), self.notebook))
        self.add_tab("シナリオ", ScenarioEditor(default_scenario_path(), None, self.notebook))
        self.add_tab(
            "リマインダー",
            ReminderEditor(default_reminder_path(), self.notebook),
        )
        self.add_tab(
            "サーバーエクスポート",
            ServerExportJsonEditor(master=self.notebook),
        )
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_tab(self, label: str, editor: tk.Misc) -> None:
        self.notebook.add(editor, text=label)
        self.editors.append((label, editor))

        def on_title(text: str, editor: tk.Misc = editor, label: str = label) -> None:
            self.notebook.tab(editor, text=label + (" *" if text.endswith(" *") else ""))

        editor.on_title = on_title

    def can_close(self, editor: tk.Misc) -> bool:
        if hasattr(editor, "_confirm_pending_changes"):
            return editor._confirm_pending_changes()
        if hasattr(editor, "confirm_discard"):
            return editor.confirm_discard()
        return True

    def on_close(self) -> None:
        for _label, editor in self.editors:
            if getattr(editor, "dirty", False):
                self.notebook.select(editor)
                if not self.can_close(editor):
                    return
        self.destroy()


def main() -> None:
    ServerConfigEditorApp().mainloop()


if __name__ == "__main__":
    main()
