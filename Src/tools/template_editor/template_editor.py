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
                                normalize, save_table)
else:
    from .template_logic import (default_templates_dir, list_template_files, load_table,
                                 normalize, save_table)


class TemplateEditor(tk.Tk):
    def __init__(self, root_dir: Path) -> None:
        super().__init__()
        self.title("テンプレートエディタ")
        self.geometry("960x520")
        self.root_dir = root_dir
        self.path: Path | None = None
        self.bom = False
        self.rows: list[list[str]] = []
        self.dirty = False
        self.entry: ttk.Entry | None = None

        left = ttk.Frame(self, padding=4)
        left.pack(side="left", fill="y")
        self.files = tk.Listbox(left, width=34, exportselection=False)
        self.files.pack(fill="y", expand=True)
        self.files.bind("<<ListboxSelect>>", self.on_select)
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
        self.files.delete(0, "end")
        for path in self.paths:
            self.files.insert("end", str(path.relative_to(self.root_dir)))
        if not self.paths:
            self.files.insert("end", "表示するファイルがありません")
            self.files.itemconfig(0, foreground="gray")

    def on_select(self, _event: object) -> None:
        selection = self.files.curselection()
        if not self.paths:
            self.files.selection_clear(0, "end")
            return
        if selection and self.confirm_discard():
            self.load(self.paths[selection[0]])

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
            self.table.heading(column, text=header[i] or f"({i + 1})")
            self.table.column(column, width=140, stretch=False)
        for index, row in enumerate(self.rows[1:]):
            self.table.insert("", "end", iid=str(index), values=row)
        self.title(f"テンプレートエディタ - {self.path.name if self.path else ''}{' *' if self.dirty else ''}")

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
            values = list(self.table.item(row_id, "values"))
            values[col_index] = value
            self.table.item(row_id, values=values)
            self.mark_dirty()

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


