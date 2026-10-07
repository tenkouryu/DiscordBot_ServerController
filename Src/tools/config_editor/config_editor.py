from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config_logic import (default_config_path, is_secret_key, load_config, save_config,
                              text_to_value, value_to_text)
else:
    from .config_logic import (default_config_path, is_secret_key, load_config, save_config,
                               text_to_value, value_to_text)


import sys as _sys

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in _sys.path:
    _sys.path.insert(0, _TOOLS_DIR)
from common.window_base import EditorFrame  # noqa: E402


class ConfigEditor(EditorFrame):
    def __init__(self, path: Path, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("設定エディタ")
        self.geometry("640x420")
        self.path = path
        self.original: dict[str, Any] = {}
        self.rows: dict[str, tuple[tk.StringVar, ttk.Entry, tk.BooleanVar]] = {}

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.path_label = ttk.Label(top, text=str(path))
        self.path_label.pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="開く...", command=self.choose_file).pack(side="right")

        self.form = ttk.Frame(self, padding=8)
        self.form.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="項目追加", command=self.add_item).pack(side="left")
        ttk.Button(bottom, text="再読込", command=self.reload).pack(side="left", padx=4)
        ttk.Button(bottom, text="保存", command=self.save).pack(side="right")
        ttk.Label(self, text="保存後はBotの再起動が必要です", foreground="gray").pack(pady=(0, 6))
        self.reload()

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=self.path.parent, filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if selected:
            self.path = Path(selected)
            self.path_label.config(text=selected)
            self.reload()

    def reload(self) -> None:
        try:
            self.original = load_config(self.path)
        except (OSError, ValueError) as error:
            messagebox.showerror("読み込みエラー", str(error))
            self.original = {}
        self.render()

    def render(self) -> None:
        for child in self.form.winfo_children():
            child.destroy()
        self.rows.clear()
        self.form.columnconfigure(1, weight=1)
        for index, (key, value) in enumerate(self.original.items()):
            self.add_row(index, key, value)

    def add_row(self, index: int, key: str, value: Any) -> None:
        ttk.Label(self.form, text=key).grid(row=index, column=0, sticky="w", padx=4, pady=2)
        var = tk.StringVar(value=value_to_text(value))
        secret = is_secret_key(key)
        entry = ttk.Entry(self.form, textvariable=var, show="*" if secret else "")
        entry.grid(row=index, column=1, sticky="ew", padx=4)
        shown = tk.BooleanVar(value=not secret)
        if secret:
            def toggle(e: ttk.Entry = entry, s: tk.BooleanVar = shown) -> None:
                e.config(show="" if s.get() else "*")
            ttk.Checkbutton(self.form, text="表示", variable=shown, command=toggle).grid(row=index, column=2)
        ttk.Button(self.form, text="削除", command=lambda k=key: self.remove_item(k)).grid(row=index, column=3, padx=4)
        self.rows[key] = (var, entry, shown)

    def collect(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, (var, _entry, _shown) in self.rows.items():
            try:
                result[key] = text_to_value(var.get(), self.original.get(key, ""))
            except ValueError as error:
                raise ValueError(f"{key}: {error}") from error
        return result

    def add_item(self) -> None:
        window = tk.Toplevel(self)
        window.title("項目追加")
        name = tk.StringVar()
        ttk.Label(window, text="キー名").pack(padx=8, pady=4)
        ttk.Entry(window, textvariable=name).pack(padx=8)

        def ok() -> None:
            key = name.get().strip()
            if not key or key in self.rows:
                messagebox.showwarning("追加できません", "キー名が空、または既に存在します", parent=window)
                return
            try:
                self.original = {**self.collect(), key: ""}
            except ValueError as error:
                messagebox.showerror("入力エラー", str(error), parent=window)
                return
            window.destroy()
            self.render()

        ttk.Button(window, text="追加", command=ok).pack(pady=8)

    def remove_item(self, key: str) -> None:
        if not messagebox.askyesno("確認", f"{key} を削除しますか?"):
            return
        try:
            data = self.collect()
        except ValueError as error:
            messagebox.showerror("入力エラー", str(error))
            return
        data.pop(key, None)
        self.original = data
        self.render()

    def save(self) -> None:
        try:
            data = self.collect()
            save_config(self.path, data)
        except (OSError, ValueError) as error:
            messagebox.showerror("保存エラー", str(error))
            return
        self.original = data
        messagebox.showinfo("保存", "保存しました。Botを再起動すると反映されます。")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_config_path()
    ConfigEditor(path).mainloop()


if __name__ == "__main__":
    main()
