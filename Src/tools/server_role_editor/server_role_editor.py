from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
import tkinter as tk

import discord

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from role_logic import load_roles, permission_columns, save_roles
    from permission_labels import permission_display, permission_label
else:
    from .permission_labels import permission_display, permission_label
    from .role_logic import load_roles, permission_columns, save_roles


TRUE_VALUES = {"true", "1", "on", "yes"}
FALSE_VALUES = {"false", "0", "off", "no"}
COLOR_SAMPLES = [
    "#1ABC9C", "#2ECC71", "#3498DB", "#9B59B6", "#E91E63", "#F1C40F",
    "#E67E22", "#E74C3C", "#95A5A6", "#607D8B", "#FFFFFF", "#000000",
]


def default_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        bundled_template = base / "templates" / "set" / "input" / "server_role_template.csv"
        return bundled_template if bundled_template.exists() else base / "server_role_template.csv"
    return Path(__file__).resolve().parents[2] / "templates" / "set" / "input" / "server_role_template.csv"


import sys as _sys

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in _sys.path:
    _sys.path.insert(0, _TOOLS_DIR)
from common.window_base import EditorFrame  # noqa: E402


class ServerRoleEditor(EditorFrame):
    def __init__(self, path: Path, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("サーバーロールCSVエディタ")
        self.geometry("980x660")
        self.minsize(760, 500)
        self.path = path
        self.columns: list[str] = []
        self.roles: list[dict[str, str]] = []
        self.has_bom = True
        self.current_index: int | None = None
        self.dirty = False
        self.permission_vars: dict[str, tk.BooleanVar] = {}

        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="開く...", command=self.open_file).pack(side="left")
        ttk.Button(toolbar, text="保存", command=self.save).pack(side="left", padx=4)
        ttk.Button(toolbar, text="名前を付けて保存...", command=self.save_as).pack(side="left")
        ttk.Button(toolbar, text="権限列を追加...", command=self.add_permissions).pack(side="left", padx=(16, 4))
        ttk.Button(toolbar, text="権限列を削除...", command=self.remove_permissions).pack(side="left")

        content = ttk.Panedwindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        list_frame = ttk.Frame(content, padding=4)
        content.add(list_frame, weight=1)
        ttk.Label(list_frame, text="ロール一覧").pack(anchor="w", pady=(0, 4))
        self.role_list = ttk.Treeview(
            list_frame, columns=("name", "color"), show="tree headings", selectmode="browse"
        )
        self.color_images: dict[str, tk.PhotoImage] = {}
        self.role_list.heading("#0", text="見た目")
        self.role_list.column("#0", width=60, minwidth=50, stretch=False, anchor="center")
        self.role_list.heading("name", text="ロール名")
        self.role_list.heading("color", text="色")
        self.role_list.column("name", width=170, minwidth=90)
        self.role_list.column("color", width=90, minwidth=70, anchor="center")
        self.role_list.pack(fill="both", expand=True)
        self.role_list.bind("<<TreeviewSelect>>", self.on_select_role)
        role_buttons = ttk.Frame(list_frame)
        role_buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(role_buttons, text="ロール追加", command=self.add_role).pack(side="left")
        ttk.Button(role_buttons, text="ロール削除", command=self.delete_role).pack(side="left", padx=4)

        details = ttk.Frame(content, padding=8)
        content.add(details, weight=3)
        ttk.Label(details, text="ロール名").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(details, textvariable=self.name_var)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.name_entry.bind("<KeyRelease>", self.on_detail_change)

        ttk.Label(details, text="色 (#RRGGBB)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        color_frame = ttk.Frame(details)
        color_frame.grid(row=1, column=1, sticky="ew", pady=4)
        self.color_var = tk.StringVar()
        self.color_swatch = tk.Label(
            color_frame, width=4, relief="solid", borderwidth=1, cursor="hand2"
        )
        self.color_swatch.pack(side="left", padx=(0, 6), fill="y")
        self.color_swatch.bind("<Button-1>", lambda _event: self.choose_color())
        self.color_entry = ttk.Entry(color_frame, textvariable=self.color_var, width=12)
        self.color_entry.pack(side="left")
        self.color_entry.bind("<KeyRelease>", self.on_detail_change)
        ttk.Button(color_frame, text="色を選択...", command=self.choose_color).pack(side="left", padx=(4, 8))
        for sample in COLOR_SAMPLES:
            swatch = tk.Label(
                color_frame, bg=sample, width=2, relief="solid", borderwidth=1, cursor="hand2"
            )
            swatch.pack(side="left", padx=1, fill="y")
            swatch.bind("<Button-1>", lambda _event, value=sample: self.pick_sample(value))

        ttk.Label(details, text="権限").grid(row=2, column=0, sticky="nw", padx=(0, 8), pady=4)
        permission_frame = ttk.Frame(details)
        permission_frame.grid(row=2, column=1, sticky="nsew", pady=4)
        self.permission_canvas = tk.Canvas(permission_frame, highlightthickness=0)
        permission_scroll = ttk.Scrollbar(
            permission_frame, orient="vertical", command=self.permission_canvas.yview
        )
        self.permission_canvas.configure(yscrollcommand=permission_scroll.set)
        self.permission_canvas.pack(side="left", fill="both", expand=True)
        permission_scroll.pack(side="right", fill="y")
        self.permission_panel = ttk.Frame(self.permission_canvas)
        self.permission_window = self.permission_canvas.create_window(
            (0, 0), window=self.permission_panel, anchor="nw"
        )
        self.permission_panel.bind("<Configure>", self.on_permission_panel_resize)
        self.permission_canvas.bind("<Configure>", self.on_permission_canvas_resize)
        details.columnconfigure(1, weight=1)
        details.rowconfigure(2, weight=1)
        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 4), foreground="gray")
        self.status.pack(fill="x")

        self.load_file(path)

    def on_permission_panel_resize(self, _event: tk.Event) -> None:
        self.permission_canvas.configure(scrollregion=self.permission_canvas.bbox("all"))

    def on_permission_canvas_resize(self, event: tk.Event) -> None:
        self.permission_canvas.itemconfigure(self.permission_window, width=event.width)

    def open_file(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=self.path.parent,
            filetypes=[("CSV", "*.csv"), ("すべてのファイル", "*.*")],
        )
        if selected and self.confirm_discard():
            self.load_file(Path(selected))

    def load_file(self, path: Path) -> None:
        try:
            columns, roles, has_bom = load_roles(path)
        except (OSError, UnicodeDecodeError, csv.Error, ValueError) as error:
            messagebox.showerror("読み込みエラー", str(error), parent=self)
            return
        self.path = path
        self.columns = columns
        self.roles = roles
        self.has_bom = has_bom
        self.current_index = None
        self.dirty = False
        self.refresh_roles()
        self.title(f"サーバーロールCSVエディタ - {path.name}")
        self.status.config(text=str(path))

    def color_image(self, color: str) -> tk.PhotoImage:
        """一覧用の色見本画像を返す。不正な値は灰色の斜線入り枠にする。"""
        normalized = color.strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", normalized):
            key = "#" + normalized.lstrip("#").upper()
        else:
            key = ""
        if key not in self.color_images:
            image = tk.PhotoImage(width=36, height=14)
            border = "#808080"
            image.put(border, to=(0, 0, 36, 14))
            if key:
                image.put(key, to=(1, 1, 35, 13))
            else:
                image.put("#FFFFFF", to=(1, 1, 35, 13))
                for offset in range(12):
                    image.put(border, to=(8 + offset * 2, 12 - offset, 10 + offset * 2, 13 - offset))
            self.color_images[key] = image
        return self.color_images[key]

    def refresh_roles(self, select_index: int | None = None) -> None:
        self.role_list.delete(*self.role_list.get_children())
        for index, role in enumerate(self.roles):
            self.role_list.insert(
                "", "end", iid=str(index),
                image=self.color_image(role.get("color", "")),
                values=(role.get("name", ""), role.get("color", "")),
            )
        if select_index is not None and 0 <= select_index < len(self.roles):
            item = str(select_index)
            self.role_list.selection_set(item)
            self.role_list.focus(item)
            self.role_list.see(item)
            self.show_role(select_index)
        else:
            self.current_index = None
            self.show_role(None)

    def on_select_role(self, _event: object) -> None:
        selected = self.role_list.selection()
        if not selected:
            return
        index = int(selected[0])
        self.commit_details()
        self.show_role(index)

    def show_role(self, index: int | None) -> None:
        self.current_index = index
        role = self.roles[index] if index is not None else {}
        self.name_var.set(role.get("name", ""))
        self.color_var.set(role.get("color", ""))
        self.update_swatch()
        for child in self.permission_panel.winfo_children():
            child.destroy()
        self.permission_vars.clear()

        flags = permission_columns(self.columns)
        if not flags:
            ttk.Label(
                self.permission_panel,
                text="権限列はありません。「権限列を追加...」から設定する権限を選んでください。",
                foreground="gray",
            ).grid(row=0, column=0, sticky="w", padx=4, pady=4)
            return
        for row, flag in enumerate(flags):
            value = role.get(flag, "false").strip().lower()
            variable = tk.BooleanVar(value=value in TRUE_VALUES)
            self.permission_vars[flag] = variable
            label = permission_label(flag)
            ttk.Checkbutton(
                self.permission_panel,
                text=label,
                variable=variable,
                command=lambda permission=flag: self.set_permission(permission),
            ).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            if value not in TRUE_VALUES | FALSE_VALUES:
                ttk.Label(
                    self.permission_panel,
                    text=f"CSV値が不正です: {role.get(flag, '')}",
                    foreground="red",
                ).grid(row=row, column=1, sticky="w", padx=8, pady=2)

    def on_detail_change(self, _event: tk.Event) -> None:
        self.commit_details()

    def commit_details(self) -> None:
        if self.current_index is None:
            return
        role = self.roles[self.current_index]
        role["name"] = self.name_var.get()
        role["color"] = self.color_var.get()
        self.update_swatch()
        self.role_list.item(
            str(self.current_index),
            image=self.color_image(role["color"]),
            values=(role["name"], role["color"]),
        )
        self.mark_dirty()

    def set_permission(self, permission: str) -> None:
        if self.current_index is None:
            return
        role = self.roles[self.current_index]
        role[permission] = "true" if self.permission_vars[permission].get() else "false"
        self.mark_dirty()

    def update_swatch(self) -> None:
        color = self.color_var.get().strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
            self.color_swatch.configure(bg=color if color.startswith("#") else f"#{color}", text="")
        else:
            self.color_swatch.configure(bg=self.winfo_toplevel().cget("bg"), text="?" if color else "")

    def pick_sample(self, color: str) -> None:
        if self.current_index is None:
            return
        self.color_var.set(color)
        self.commit_details()

    def choose_color(self) -> None:
        if self.current_index is None:
            return
        current = self.color_var.get().strip()
        initial = current if re.fullmatch(r"#[0-9a-fA-F]{6}", current) else None
        selected = colorchooser.askcolor(color=initial, parent=self, title="ロールの色を選択")
        if selected[1]:
            self.color_var.set(selected[1].upper())
            self.commit_details()

    def add_role(self) -> None:
        self.commit_details()
        if "color" not in self.columns:
            self.columns.append("color")
        role = {column: "" for column in self.columns}
        role["name"] = "新しいロール"
        role.update({flag: "false" for flag in permission_columns(self.columns)})
        self.roles.append(role)
        self.dirty = True
        self.refresh_roles(len(self.roles) - 1)
        self.name_entry.focus_set()
        self.name_entry.selection_range(0, "end")

    def delete_role(self) -> None:
        selected = self.role_list.selection()
        if not selected:
            return
        self.commit_details()
        index = int(selected[0])
        name = self.roles[index].get("name", "")
        if not messagebox.askyesno("確認", f"「{name}」を削除しますか?", parent=self):
            return
        del self.roles[index]
        self.dirty = True
        self.refresh_roles(min(index, len(self.roles) - 1) if self.roles else None)

    def add_permissions(self) -> None:
        self.commit_details()
        available = [
            flag for flag in sorted(discord.Permissions.VALID_FLAGS)
            if flag not in self.columns
        ]
        selected = self.choose_permissions("権限列を追加", available)
        if not selected:
            return
        for flag in selected:
            self.columns.append(flag)
            for role in self.roles:
                role[flag] = "false"
        self.dirty = True
        self.refresh_roles(self.current_index)

    def remove_permissions(self) -> None:
        self.commit_details()
        selected = self.choose_permissions(
            "権限列を削除", permission_columns(self.columns)
        )
        if not selected:
            return
        for flag in selected:
            self.columns.remove(flag)
            for role in self.roles:
                role.pop(flag, None)
        self.dirty = True
        self.refresh_roles(self.current_index)

    def choose_permissions(self, title: str, options: list[str]) -> list[str]:
        if not options:
            messagebox.showinfo(title, "選択できる権限列がありません。", parent=self)
            return []
        window = tk.Toplevel(self)
        window.title(title)
        window.transient(self)
        window.geometry("420x480")
        ttk.Label(window, text="権限を選択してください（複数選択可）").pack(
            anchor="w", padx=8, pady=8
        )
        body = ttk.Frame(window)
        body.pack(fill="both", expand=True, padx=8)
        values = tk.Listbox(body, selectmode="extended", exportselection=False)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=values.yview)
        values.configure(yscrollcommand=scrollbar.set)
        values.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for option in options:
            values.insert("end", permission_display(option))

        result: list[str] = []

        def accept() -> None:
            result.extend(options[index] for index in values.curselection())
            window.destroy()

        buttons = ttk.Frame(window, padding=8)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(side="right")
        ttk.Button(buttons, text="追加", command=accept).pack(side="right", padx=4)
        window.grab_set()
        self.wait_window(window)
        return result

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
        self.commit_details()
        for index, role in enumerate(self.roles, start=2):
            if not role.get("name", "").strip():
                messagebox.showerror("入力エラー", f"{index}行目のロール名を入力してください。", parent=self)
                return
            color = role.get("color", "").strip()
            if color and not re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
                messagebox.showerror(
                    "入力エラー", f"{index}行目の色を #RRGGBB 形式で入力してください。", parent=self
                )
                return
            for flag in permission_columns(self.columns):
                value = role.get(flag, "").strip().lower()
                if value not in TRUE_VALUES | FALSE_VALUES:
                    messagebox.showerror(
                        "入力エラー",
                        f"{index}行目の権限「{permission_label(flag)}」の値が true/false ではありません。",
                        parent=self,
                    )
                    return
        try:
            save_roles(path, self.columns, self.roles, self.has_bom)
        except (OSError, csv.Error) as error:
            messagebox.showerror("保存エラー", str(error), parent=self)
            return
        self.path = path
        self.dirty = False
        self.title(f"サーバーロールCSVエディタ - {path.name}")
        self.status.config(text=f"保存しました: {path}")

    def mark_dirty(self) -> None:
        self.dirty = True
        self.title(f"サーバーロールCSVエディタ - {self.path.name} *")

    def confirm_discard(self) -> bool:
        return not self.dirty or messagebox.askyesno(
            "確認", "未保存の変更を破棄しますか?", parent=self
        )


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path()
    ServerRoleEditor(path).mainloop()


if __name__ == "__main__":
    main()
