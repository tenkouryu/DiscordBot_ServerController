from __future__ import annotations

import csv
import sys
import zipfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from template_logic import (default_templates_dir, list_template_files, load_table,
                                normalize, row_matches_filters, save_table)
else:
    from .template_logic import (default_templates_dir, list_template_files, load_table,
                                 normalize, row_matches_filters, save_table)


import sys as _sys

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in _sys.path:
    _sys.path.insert(0, _TOOLS_DIR)
from common.window_base import EditorFrame  # noqa: E402


class TemplateEditor(EditorFrame):
    def __init__(self, root_dir: Path, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("テンプレートエディタ")
        self.geometry("960x520")
        self.root_dir = root_dir
        self.path: Path | None = None
        self.bom = False
        self.rows: list[list[str]] = []
        self.dirty = False
        self.entry: ttk.Entry | None = None
        self.filters: dict[int, set[str]] = {}

        left = ttk.Frame(self, padding=4)
        left.pack(side="left", fill="y")
        file_list = ttk.Frame(left)
        file_list.pack(fill="both", expand=True)
        self.files = ttk.Treeview(file_list, columns=("file", "type"), show="headings",
                                  selectmode="browse", height=20)
        self.files.heading("file", text="ファイル")
        self.files.heading("type", text="種別")
        self.files.column("file", width=260, minwidth=140, stretch=True)
        self.files.column("type", width=70, minwidth=60, stretch=False, anchor="center")
        self.files.pack(side="left", fill="y", expand=True)
        self.files.bind("<<TreeviewSelect>>", self.on_select)
        files_scroll = ttk.Scrollbar(file_list, orient="vertical", command=self.files.yview)
        files_scroll.pack(side="right", fill="y")
        self.files.configure(yscrollcommand=files_scroll.set)
        ttk.Button(left, text="フォルダを開く...", command=self.open_folder).pack(fill="x", pady=2)
        ttk.Button(left, text="ファイルを開く...", command=self.open_other).pack(fill="x")
        ttk.Button(left, text="一覧を更新", command=self.refresh_list).pack(fill="x")

        right = ttk.Frame(self, padding=4)
        right.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        for text, command in (("行追加", self.add_row), ("行削除", self.delete_row),
                              ("列追加", self.add_column), ("列削除", self.delete_column),
                              ("列名変更", self.rename_column)):
            ttk.Button(bar, text=text, command=command).pack(side="left", padx=2)
        ttk.Button(bar, text="フィルター解除", command=self.clear_filters).pack(side="left", padx=(10, 2))
        ttk.Button(bar, text="保存", command=self.save).pack(side="right")
        ttk.Button(bar, text="名前を付けて保存", command=self.save_as).pack(side="right", padx=2)

        self.table = ttk.Treeview(right, show="headings", selectmode="browse")
        self.table.pack(fill="both", expand=True, pady=4)
        scroll_x = ttk.Scrollbar(right, orient="horizontal", command=self.table.xview)
        scroll_x.pack(fill="x")
        self.table.configure(xscrollcommand=scroll_x.set)
        self.table.bind("<Double-1>", self.begin_edit)
        self.status = ttk.Label(right, text="セルをダブルクリックで編集。1行目はヘッダ行です。", foreground="gray")
        self.status.pack(anchor="w")
        self.refresh_list()

    def refresh_list(self) -> None:
        self.paths = list_template_files(self.root_dir)
        self.files.delete(*self.files.get_children())
        for index, path in enumerate(self.paths):
            self.files.insert(
                "", "end", iid=str(index),
                values=(str(path.relative_to(self.root_dir)), path.suffix[1:].upper()),
            )
        if not self.paths:
            self.files.insert("", "end", iid="empty", values=("表示するファイルがありません", ""))

    def on_select(self, _event: object) -> None:
        selection = self.files.selection()
        if not self.paths:
            if selection:
                self.files.selection_remove(*selection)
            return
        if selection and self.confirm_discard():
            self.load(self.paths[int(selection[0])])

    def open_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.root_dir, mustexist=True)
        if selected:
            self.root_dir = Path(selected)
            self.refresh_list()
            if not self.paths:
                self.status.config(text="このフォルダにCSV/zipファイルがありません。")

    def open_other(self) -> None:
        selected = filedialog.askopenfilename(initialdir=self.root_dir, filetypes=[("CSV / ZIP", "*.csv *.zip")])
        if selected and self.confirm_discard():
            self.load(Path(selected))

    def confirm_discard(self) -> bool:
        return not self.dirty or messagebox.askyesno("確認", "未保存の変更を破棄しますか?")

    def load(self, path: Path) -> None:
        try:
            self.rows, self.bom = load_table(path)
        except (OSError, UnicodeDecodeError, csv.Error, zipfile.BadZipFile, KeyError) as error:
            messagebox.showerror("読み込みエラー", str(error))
            return
        self.path = path
        self.dirty = False
        self.filters.clear()
        self.render()

    def render(self) -> None:
        self.cancel_edit()
        self.rows = normalize(self.rows)
        width = len(self.rows[0]) if self.rows else 0
        ids = [str(i) for i in range(width)]
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=ids)
        header = self.rows[0] if self.rows else []
        for i, column in enumerate(ids):
            label = header[i] or f"({i + 1})"
            indicator = " ▼●" if i in self.filters else " ▼"
            self.table.heading(
                column,
                text=label + indicator,
                command=lambda index=i: self.open_column_filter(index),
            )
            self.table.column(column, width=140, stretch=False)
        for index, row in enumerate(self.rows[1:]):
            if row_matches_filters(row, self.filters):
                self.table.insert("", "end", iid=str(index), values=row)
        if self.filters:
            count = len(self.table.get_children())
            self.status.config(text=f"フィルター適用中: {count} / {max(0, len(self.rows) - 1)} 行")
        elif self.status.cget("text").startswith("フィルター適用中:"):
            self.status.config(text="セルをダブルクリックで編集。1行目はヘッダ行です。")
        self.title(f"テンプレートエディタ - {self.path.name if self.path else ''}{' *' if self.dirty else ''}")

    def open_column_filter(self, column_index: int) -> None:
        if not self.rows or column_index >= len(self.rows[0]):
            return
        header = self.rows[0][column_index] or f"({column_index + 1})"
        values = sorted({row[column_index] for row in self.rows[1:]}, key=lambda value: (value.casefold(), value))
        selected = self.filters.get(column_index, set(values)).copy()
        popup = tk.Toplevel(self)
        popup.title(f"フィルター: {header}")
        popup.transient(self.winfo_toplevel())
        popup.resizable(True, True)
        popup.geometry(f"320x430+{popup.winfo_pointerx()}+{popup.winfo_pointery()}")

        body = ttk.Frame(popup, padding=8)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"「{header}」の表示値を選択").pack(anchor="w")
        search = tk.StringVar()
        ttk.Label(body, text="値を検索", foreground="gray").pack(anchor="w", pady=(6, 0))
        ttk.Entry(body, textvariable=search).pack(fill="x", pady=(6, 4))

        all_var = tk.BooleanVar(value=len(selected) == len(values))
        options_canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=options_canvas.yview)
        options_canvas.configure(yscrollcommand=scrollbar.set)
        options_frame = ttk.Frame(options_canvas)
        options_window = options_canvas.create_window((0, 0), window=options_frame, anchor="nw")
        options_frame.bind(
            "<Configure>", lambda _e: options_canvas.configure(scrollregion=options_canvas.bbox("all"))
        )
        options_canvas.bind(
            "<Configure>", lambda event: options_canvas.itemconfigure(options_window, width=event.width)
        )
        scrollbar.pack(side="right", fill="y")
        options_canvas.pack(fill="both", expand=True, pady=4)

        check_vars: dict[str, tk.BooleanVar] = {
            value: tk.BooleanVar(value=value in selected) for value in values
        }

        def sync_all() -> None:
            all_var.set(all(variable.get() for variable in check_vars.values()))

        def toggle_all() -> None:
            for variable in check_vars.values():
                variable.set(all_var.get())

        ttk.Checkbutton(body, text="すべて選択", variable=all_var, command=toggle_all).pack(anchor="w")

        def rebuild_options(*_args: object) -> None:
            for child in options_frame.winfo_children():
                child.destroy()
            query = search.get().casefold()
            for value in values:
                label = value if value else "(空白)"
                if query and query not in label.casefold():
                    continue
                ttk.Checkbutton(
                    options_frame,
                    text=label,
                    variable=check_vars[value],
                    command=sync_all,
                ).pack(anchor="w", fill="x")

        search.trace_add("write", rebuild_options)
        rebuild_options()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(6, 0))

        def apply_filter() -> None:
            chosen = {value for value, variable in check_vars.items() if variable.get()}
            if chosen == set(values):
                self.filters.pop(column_index, None)
            else:
                self.filters[column_index] = chosen
            popup.destroy()
            self.render()

        def clear_filter() -> None:
            self.filters.pop(column_index, None)
            popup.destroy()
            self.render()

        ttk.Button(buttons, text="この列を解除", command=clear_filter).pack(side="left")
        ttk.Button(buttons, text="キャンセル", command=popup.destroy).pack(side="right")
        ttk.Button(buttons, text="適用", command=apply_filter).pack(side="right", padx=4)
        popup.bind("<Return>", lambda _event: apply_filter())
        popup.bind("<Escape>", lambda _event: popup.destroy())
        popup.grab_set()

    def clear_filters(self) -> None:
        if self.filters:
            self.filters.clear()
            self.render()

    def mark_dirty(self) -> None:
        self.dirty = True
        self.title(self.title().rstrip(" *") + " *")

    def begin_edit(self, event: tk.Event) -> None:
        self.cancel_edit()
        row_id = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not row_id or not column:
            return
        col_index = int(column[1:]) - 1
        x, y, w, h = self.table.bbox(row_id, column)
        entry = ttk.Entry(self.table)
        entry.insert(0, self.rows[int(row_id) + 1][col_index])
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.bind("<Return>", lambda _e: self.commit_edit(row_id, col_index))
        entry.bind("<FocusOut>", lambda _e: self.commit_edit(row_id, col_index))
        entry.bind("<Escape>", lambda _e: self.cancel_edit())
        self.entry = entry

    def commit_edit(self, row_id: str, col_index: int) -> None:
        if self.entry is None:
            return
        value = self.entry.get()
        self.cancel_edit()
        if self.rows[int(row_id) + 1][col_index] != value:
            self.rows[int(row_id) + 1][col_index] = value
            self.mark_dirty()
            self.render()

    def cancel_edit(self) -> None:
        if self.entry is not None:
            entry, self.entry = self.entry, None
            entry.destroy()

    def selected_row(self) -> int | None:
        selection = self.table.selection()
        return int(selection[0]) if selection else None

    def add_row(self) -> None:
        if self.path is None:
            return
        self.rows.append([""] * len(self.rows[0]))
        self.mark_dirty()
        self.render()

    def delete_row(self) -> None:
        index = self.selected_row()
        if index is None:
            return
        del self.rows[index + 1]
        self.mark_dirty()
        self.render()

    def ask_column(self, prompt: str) -> int | None:
        if not self.rows or not self.rows[0]:
            return None
        names = [f"{i + 1}:{name}" for i, name in enumerate(self.rows[0])]
        number = simpledialog.askinteger("列選択", f"{prompt}\n" + "  ".join(names),
                                         minvalue=1, maxvalue=len(names), parent=self)
        return None if number is None else number - 1

    def add_column(self) -> None:
        if self.path is None:
            return
        name = simpledialog.askstring("列追加", "新しい列名", parent=self)
        if name is None:
            return
        self.rows[0].append(name)
        for row in self.rows[1:]:
            row.append("")
        self.mark_dirty()
        self.render()

    def delete_column(self) -> None:
        index = self.ask_column("削除する列の番号")
        if index is None:
            return
        for row in self.rows:
            del row[index]
        self.filters = {
            old_index - 1 if old_index > index else old_index: values
            for old_index, values in self.filters.items()
            if old_index != index
        }
        self.mark_dirty()
        self.render()

    def rename_column(self) -> None:
        index = self.ask_column("名前を変更する列の番号")
        if index is None:
            return
        name = simpledialog.askstring("列名変更", "新しい列名", initialvalue=self.rows[0][index], parent=self)
        if name is not None:
            self.rows[0][index] = name
            self.mark_dirty()
            self.render()

    def save_as(self) -> None:
        if self.path is None:
            return
        selected = filedialog.asksaveasfilename(
            initialdir=self.path.parent, initialfile=self.path.name, defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("ZIP", "*.zip")])
        if selected:
            self.path = Path(selected)
            self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.cancel_edit()
        try:
            save_table(self.path, self.rows, self.bom)
        except OSError as error:
            messagebox.showerror("保存エラー", str(error))
            return
        self.dirty = False
        self.render()
        self.status.config(text=f"保存しました: {self.path}")


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default_templates_dir()
    TemplateEditor(root).mainloop()


if __name__ == "__main__":
    main()
