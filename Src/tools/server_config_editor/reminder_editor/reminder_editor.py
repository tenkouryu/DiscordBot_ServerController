from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any
import uuid

from .reminder_logic import load_reminders, save_reminders


class ReminderEditor(ttk.Frame):
    def __init__(self, path: Path, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.path = path
        self.reminders: list[dict[str, Any]] = []
        self.dirty = False

        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="追加", command=self.add_reminder).pack(side="left")
        ttk.Button(toolbar, text="編集", command=self.edit_reminder).pack(side="left", padx=4)
        ttk.Button(toolbar, text="削除", command=self.delete_reminder).pack(side="left")
        ttk.Button(toolbar, text="再読込", command=self.reload).pack(side="left", padx=4)
        ttk.Button(toolbar, text="保存", command=self.save).pack(side="right")

        self.tree = ttk.Treeview(
            self,
            columns=("id", "datetime", "channel_id", "content"),
            show="headings",
            selectmode="browse",
        )
        for column, label, width in (
            ("id", "ID", 180),
            ("datetime", "日時", 190),
            ("channel_id", "チャンネルID", 140),
            ("content", "内容", 500),
        ):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 4), foreground="gray")
        self.status.pack(fill="x")
        self.reload()

    def reload(self) -> None:
        try:
            self.reminders = load_reminders(self.path)
        except (OSError, ValueError) as error:
            messagebox.showerror("読み込みエラー", str(error), parent=self)
            return
        self.dirty = False
        self.refresh()
        self.status.config(text=str(self.path))

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(self.reminders):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item["id"],
                    item["datetime"],
                    item["channel_id"],
                    item["content"],
                ),
            )

    def mark_dirty(self) -> None:
        self.dirty = True
        self.status.config(text=f"{self.path} *")

    def confirm_discard(self) -> bool:
        return not self.dirty or messagebox.askyesno(
            "未保存の変更",
            "変更を保存せずに続行しますか？",
            parent=self,
        )

    def selected_index(self) -> int | None:
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def edit_reminder(self, index: int | None = None) -> bool:
        index = self.selected_index() if index is None else index
        if index is None:
            messagebox.showinfo("リマインダー", "編集する予定を選択してください。", parent=self)
            return False
        current = self.reminders[index]
        scheduled = simpledialog.askstring(
            "日時",
            "日時（ISO 8601、+09:00）",
            initialvalue=current["datetime"],
            parent=self,
        )
        if scheduled is None:
            return False
        channel = simpledialog.askstring(
            "チャンネルID",
            "チャンネルID",
            initialvalue=str(current["channel_id"]),
            parent=self,
        )
        if channel is None:
            return False
        content = simpledialog.askstring(
            "内容",
            "リマインダー内容",
            initialvalue=current["content"],
            parent=self,
        )
        if content is None:
            return False
        users = simpledialog.askstring(
            "ユーザーメンション",
            "ユーザーID（カンマ区切り、空欄可）",
            initialvalue=", ".join(map(str, current["mention_users"])),
            parent=self,
        )
        if users is None:
            return False
        roles = simpledialog.askstring(
            "ロールメンション",
            "ロールID（カンマ区切り、空欄可）",
            initialvalue=", ".join(map(str, current["mention_roles"])),
            parent=self,
        )
        if roles is None:
            return False
        self.reminders[index] = {
            "id": current["id"],
            "datetime": scheduled.strip(),
            "channel_id": channel.strip(),
            "content": content,
            "mention_users": self.parse_ids(users),
            "mention_roles": self.parse_ids(roles),
        }
        self.mark_dirty()
        self.refresh()
        return True

    def add_reminder(self) -> None:
        reminder = {
            "id": str(uuid.uuid4()),
            "datetime": "",
            "channel_id": "",
            "content": "",
            "mention_users": [],
            "mention_roles": [],
        }
        self.reminders.append(reminder)
        self.refresh()
        self.tree.selection_set(str(len(self.reminders) - 1))
        if not self.edit_reminder(len(self.reminders) - 1):
            self.reminders.pop()
            self.refresh()

    def delete_reminder(self) -> None:
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("リマインダー", "削除する予定を選択してください。", parent=self)
            return
        if not messagebox.askyesno("確認", "選択した予定を削除しますか？", parent=self):
            return
        self.reminders.pop(index)
        self.mark_dirty()
        self.refresh()

    @staticmethod
    def parse_ids(value: str) -> list[str]:
        return [part.strip() for part in value.split(",") if part.strip()]

    def save(self) -> None:
        try:
            self.reminders = save_reminders(self.path, self.reminders)
        except (OSError, ValueError) as error:
            messagebox.showerror("保存エラー", str(error), parent=self)
            return
        self.dirty = False
        self.refresh()
        self.status.config(text=f"保存しました: {self.path}")
