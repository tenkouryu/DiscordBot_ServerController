from __future__ import annotations

import csv
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from member_logic import (
        ACTIONS,
        MemberTable,
        add_role_column,
        load_table,
        new_row,
        remove_last_role_column,
        role_columns,
        save_table,
        validate_row,
    )
else:
    from .member_logic import (
        ACTIONS,
        MemberTable,
        add_role_column,
        load_table,
        new_row,
        remove_last_role_column,
        role_columns,
        save_table,
        validate_row,
    )

APP_TITLE = "メンバーロールCSVエディタ"


def default_path() -> Path:
    name = "member_role_template.csv"
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        bundled = base / "templates" / "set" / "input" / name
        return bundled if bundled.exists() else base / name
    return Path(__file__).resolve().parents[2] / "templates" / "set" / "input" / name


import sys as _sys

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in _sys.path:
    _sys.path.insert(0, _TOOLS_DIR)
from common.window_base import EditorFrame  # noqa: E402


class MemberRoleEditor(EditorFrame):
    def __init__(self, path: Path, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title(APP_TITLE)
        self.geometry("980x600")
        self.minsize(760, 460)
        self.path = path
        self.table: MemberTable | None = None
        self.current_index: int | None = None
        self.dirty = False
        self.field_vars: dict[str, tk.StringVar] = {}

        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="開く...", command=self.open_file).pack(side="left")
        ttk.Button(toolbar, text="保存", command=self.save).pack(side="left", padx=4)
        ttk.Button(toolbar, text="名前を付けて保存...", command=self.save_as).pack(side="left")
        ttk.Button(toolbar, text="ロール列を追加", command=self.add_role_col).pack(side="left", padx=(16, 4))
        ttk.Button(toolbar, text="ロール列を削除", command=self.remove_role_col).pack(side="left")
        self.format_label = ttk.Label(toolbar, text="", foreground="gray")
        self.format_label.pack(side="right")

        content = ttk.Panedwindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        list_frame = ttk.Frame(content, padding=4)
        content.add(list_frame, weight=3)
        ttk.Label(list_frame, text="メンバー一覧").pack(anchor="w", pady=(0, 4))
        self.row_list = ttk.Treeview(
            list_frame, columns=("target", "action", "roles"), show="headings", selectmode="browse"
        )
        self.row_list.heading("target", text="対象メンバー")
        self.row_list.heading("action", text="操作")
        self.row_list.heading("roles", text="ロール")
        self.row_list.column("target", width=150, minwidth=90)
        self.row_list.column("action", width=60, minwidth=50, anchor="center")
        self.row_list.column("roles", width=200, minwidth=90)
        self.row_list.pack(fill="both", expand=True)
        self.row_list.bind("<<TreeviewSelect>>", self.on_select_row)
        row_buttons = ttk.Frame(list_frame)
        row_buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(row_buttons, text="行を追加", command=self.add_row).pack(side="left")
        ttk.Button(row_buttons, text="行を削除", command=self.delete_row).pack(side="left", padx=4)

        details_outer = ttk.Frame(content)
        content.add(details_outer, weight=2)
        self.details_canvas = tk.Canvas(details_outer, highlightthickness=0)
        details_scroll = ttk.Scrollbar(details_outer, orient="vertical", command=self.details_canvas.yview)
        self.details_canvas.configure(yscrollcommand=details_scroll.set)
        details_scroll.pack(side="right", fill="y")
        self.details_canvas.pack(side="left", fill="both", expand=True)
        self.details = ttk.Frame(self.details_canvas, padding=8)
        self.details.columnconfigure(1, weight=1)
        self.details_window = self.details_canvas.create_window((0, 0), window=self.details, anchor="nw")
        self.details.bind(
            "<Configure>",
            lambda _e: self.details_canvas.configure(scrollregion=self.details_canvas.bbox("all")),
        )
        self.details_canvas.bind(
            "<Configure>", lambda e: self.details_canvas.itemconfigure(self.details_window, width=e.width)
        )
        self.details_canvas.bind("<Enter>", lambda _e: self.details_canvas.bind_all("<MouseWheel>", self.on_wheel))
        self.details_canvas.bind("<Leave>", lambda _e: self.details_canvas.unbind_all("<MouseWheel>"))

        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 4), foreground="gray")
        self.status.pack(fill="x")
        self.load_file(path)

    def on_wheel(self, event: tk.Event) -> None:
        first, last = self.details_canvas.yview()
        if first > 0.0 or last < 1.0:
            self.details_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def open_file(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=self.path.parent,
            filetypes=[("CSV", "*.csv"), ("すべてのファイル", "*.*")],
        )
        if selected and self.confirm_discard():
            self.load_file(Path(selected))

    def load_file(self, path: Path) -> None:
        try:
            table = load_table(path)
        except (OSError, UnicodeDecodeError, csv.Error, ValueError) as error:
            messagebox.showerror("読み込みエラー", str(error), parent=self)
            return
        self.path = path
        self.table = table
        self.current_index = None
        self.dirty = False
        self.format_label.config(text=f"形式: {table.format.label}")
        self.update_title()
        self.status.config(text=str(path))
        self.refresh_rows(0 if table.rows else None)

    def summarize(self, row: dict[str, str]) -> tuple[str, str, str]:
        fmt = self.table.format
        target = (
            row.get(fmt.user_id, "").strip()
            or row.get(fmt.username, "").strip()
            or row.get(fmt.display_name, "").strip()
        )
        action = row.get(fmt.action, "") if fmt.action else "置換"
        roles = ", ".join(
            value
            for column in role_columns(self.table.columns, fmt)
            if (value := row.get(column, "").strip())
        )
        return target, action, roles

    def refresh_rows(self, select_index: int | None = None) -> None:
        self.row_list.delete(*self.row_list.get_children())
        for index, row in enumerate(self.table.rows):
            self.row_list.insert("", "end", iid=str(index), values=self.summarize(row))
        if select_index is not None and 0 <= select_index < len(self.table.rows):
            item = str(select_index)
            self.row_list.selection_set(item)
            self.row_list.focus(item)
            self.row_list.see(item)
            self.show_row(select_index)
        else:
            self.show_row(None)

    def on_select_row(self, _event: object) -> None:
        selected = self.row_list.selection()
        if selected:
            self.show_row(int(selected[0]))

    def show_row(self, index: int | None) -> None:
        self.current_index = index
        self.details_canvas.yview_moveto(0)
        for child in self.details.winfo_children():
            child.destroy()
        self.field_vars.clear()
        if index is None:
            ttk.Label(
                self.details, text="左の一覧から行を選ぶか、「行を追加」を押してください。", foreground="gray"
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            return

        fmt = self.table.format
        row = self.table.rows[index]
        for line, column in enumerate(self.table.columns):
            ttk.Label(self.details, text=column).grid(row=line, column=0, sticky="w", padx=(0, 8), pady=4)
            variable = tk.StringVar(value=row.get(column, ""))
            variable.trace_add("write", lambda *_args, name=column: self.on_field_change(name))
            self.field_vars[column] = variable
            if column == fmt.action:
                widget = ttk.Combobox(
                    self.details, textvariable=variable, values=ACTIONS, state="readonly"
                )
            else:
                widget = ttk.Entry(self.details, textvariable=variable)
            widget.grid(row=line, column=1, sticky="ew", pady=4)

    def on_field_change(self, column: str) -> None:
        if self.current_index is None or column not in self.field_vars:
            return
        row = self.table.rows[self.current_index]
        row[column] = self.field_vars[column].get()
        self.row_list.item(str(self.current_index), values=self.summarize(row))
        self.mark_dirty()

    def add_row(self) -> None:
        self.table.rows.append(new_row(self.table))
        self.mark_dirty()
        self.refresh_rows(len(self.table.rows) - 1)

    def delete_row(self) -> None:
        index = self.current_index
        if index is None:
            return
        if not messagebox.askyesno("確認", "選択した行を削除しますか?", parent=self):
            return
        del self.table.rows[index]
        self.mark_dirty()
        self.refresh_rows(min(index, len(self.table.rows) - 1) if self.table.rows else None)

    def add_role_col(self) -> None:
        name = add_role_column(self.table)
        self.mark_dirty()
        self.status.config(text=f"列「{name}」を追加しました。")
        self.refresh_rows(self.current_index)

    def remove_role_col(self) -> None:
        try:
            name = remove_last_role_column(self.table)
        except ValueError as error:
            messagebox.showinfo("ロール列を削除", str(error), parent=self)
            return
        self.mark_dirty()
        self.status.config(text=f"列「{name}」を削除しました。")
        self.refresh_rows(self.current_index)

    def save_as(self) -> None:
        selected = filedialog.asksaveasfilename(
            initialdir=self.path.parent,
            initialfile=self.path.name,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if selected:
            self.save_to(Path(selected))

    def save(self) -> None:
        self.save_to(self.path)

    def save_to(self, path: Path) -> None:
        for line_number, row in enumerate(self.table.rows, start=2):
            error = validate_row(self.table, row)
            if error:
                messagebox.showerror("入力エラー", f"{line_number}行目: {error}", parent=self)
                return
        try:
            save_table(path, self.table)
        except (OSError, csv.Error) as error:
            messagebox.showerror("保存エラー", str(error), parent=self)
            return
        self.path = path
        self.dirty = False
        self.update_title()
        self.status.config(text=f"保存しました: {path}")

    def update_title(self) -> None:
        self.title(f"{APP_TITLE} - {self.path.name}{' *' if self.dirty else ''}")

    def mark_dirty(self) -> None:
        self.dirty = True
        self.update_title()

    def confirm_discard(self) -> bool:
        return not self.dirty or messagebox.askyesno(
            "確認", "未保存の変更を破棄しますか?", parent=self
        )


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path()
    MemberRoleEditor(path).mainloop()


if __name__ == "__main__":
    main()
