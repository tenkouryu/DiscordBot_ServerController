from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from .json_editor_logic import load_export_json, parse_export_json, save_export_json

_TOOLS_DIR = str(Path(__file__).resolve().parents[2])
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from common.treeview_filter import TreeviewColumnFilter  # noqa: E402
from common.window_base import EditorFrame  # noqa: E402

APP_TITLE = "サーバーエクスポートJSONエディター"
SECTION_OPTIONS = (
    ("roles", "サーバーロール", ("name", "color", "position")),
    ("members", "メンバーロール", ("name", "display_name", "roles")),
    ("channels", "チャンネル", ("name", "type", "category_name")),
)
READ_ONLY_FIELDS = {"id", "category_id", "is_default", "managed", "bot"}
BOOL_FIELDS = {"hoist", "mentionable", "nsfw"}
INT_FIELDS = {
    "position",
    "slowmode_seconds",
    "bitrate",
    "user_limit",
    "default_auto_archive_duration",
    "default_thread_slowmode_seconds",
}
ENUM_FIELDS = {
    "type": ("category", "text", "news", "voice", "stage_voice", "forum"),
    "video_quality_mode": ("auto", "full"),
    "default_sort_order": ("", "latest_activity", "creation_date"),
    "default_layout": ("not_set", "list_view", "gallery_view"),
}


def _sort_value(value: str) -> tuple[int, Any]:
    if not value:
        return 0, ""
    try:
        return 1, float(value)
    except ValueError:
        return 2, value.casefold()


def _new_id(items: list[dict[str, Any]]) -> str:
    numeric_ids = [
        int(item["id"])
        for item in items
        if str(item.get("id", "")).isdecimal()
    ]
    candidate = max(numeric_ids, default=0) + 1
    existing = {str(item.get("id")) for item in items}
    while str(candidate) in existing:
        candidate += 1
    return str(candidate)


def _new_item(
    section: str,
    document: dict[str, Any],
    *,
    match_everyone_permissions: bool = False,
) -> dict[str, Any]:
    if section == "roles":
        existing_permissions = next(
            (item["permissions"].copy() for item in document["roles"] if "permissions" in item),
            {},
        )
        everyone_role = next(
            (role for role in document["roles"] if role.get("is_default")),
            None,
        )
        permissions = (
            everyone_role["permissions"].copy()
            if match_everyone_permissions and everyone_role is not None
            else {key: False for key in existing_permissions}
        )
        lowest_position = 1
        while any(
            role.get("is_default") and role.get("position") == lowest_position
            for role in document["roles"]
        ):
            lowest_position += 1
        for role in document["roles"]:
            if (
                not role.get("is_default")
                and type(role.get("position")) is int
                and role["position"] >= lowest_position
            ):
                role["position"] += 1
        return {
            "id": _new_id(document["roles"]),
            "name": "新しいロール",
            "color": "#000000",
            "position": lowest_position,
            "is_default": False,
            "managed": False,
            "hoist": False,
            "mentionable": False,
            "permissions": permissions,
        }
    if section == "members":
        return {
            "id": _new_id(document["members"]),
            "name": "username",
            "display_name": "表示名",
            "bot": False,
            "role_ids": [],
        }
    channel_type = "category" if not document["channels"] else "text"
    item: dict[str, Any] = {
        "id": _new_id(document["channels"]),
        "name": "新しいチャンネル",
        "type": channel_type,
        "position": len(document["channels"]),
        "category_id": None,
        "category_name": None,
        "permission_overwrites": [],
    }
    if channel_type == "text":
        item.update(topic=None, nsfw=False, slowmode_seconds=0)
    return item


class SectionEditor(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        section: str,
        label: str,
        columns: tuple[str, ...],
        get_document: Callable[[], dict[str, Any]],
        mark_dirty: Callable[[], None],
        refresh_related: Callable[[SectionEditor], None],
    ) -> None:
        super().__init__(master)
        self.section = section
        self.label = label
        self.columns = columns
        self.get_document = get_document
        self.mark_dirty = mark_dirty
        self.refresh_related = refresh_related
        self.current_item: dict[str, Any] | None = None
        self._rendering = False
        self.sort_column: int | None = None
        self.sort_reverse = False

        content = ttk.Panedwindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=6, pady=6)
        list_frame = ttk.Frame(content, padding=4)
        content.add(list_frame, weight=2)
        ttk.Label(list_frame, text=f"{label}一覧").pack(anchor="w", pady=(0, 4))
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        for column in columns:
            self.tree.heading(column, text=self._column_label(column))
            self.tree.column(column, width=130, minwidth=70)
        self.tree.pack(fill="both", expand=True)
        self.column_filter = TreeviewColumnFilter(self.tree)
        self.column_filter.on_filtered = self._apply_sort
        self.column_filter.on_sort = self.sort_by
        self.column_filter.header_suffix = self._sort_marker
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        buttons = ttk.Frame(list_frame)
        buttons.pack(fill="x", pady=(5, 0))
        ttk.Button(buttons, text="追加", command=self.add_item).pack(side="left")
        ttk.Button(buttons, text="削除", command=self.delete_item).pack(side="left", padx=4)

        details_outer = ttk.Frame(content)
        content.add(details_outer, weight=3)
        self.details_canvas = tk.Canvas(details_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            details_outer,
            orient="vertical",
            command=self.details_canvas.yview,
        )
        self.details_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.details_canvas.pack(side="left", fill="both", expand=True)
        self.details = ttk.Frame(self.details_canvas, padding=8)
        self.details.columnconfigure(1, weight=1)
        self.details_window = self.details_canvas.create_window(
            (0, 0),
            window=self.details,
            anchor="nw",
        )
        self.details.bind(
            "<Configure>",
            lambda _event: self.details_canvas.configure(
                scrollregion=self.details_canvas.bbox("all")
            ),
        )
        self.details_canvas.bind(
            "<Configure>",
            lambda event: self.details_canvas.itemconfigure(
                self.details_window,
                width=event.width,
            ),
        )
        self.refresh()

    @staticmethod
    def _column_label(column: str) -> str:
        return {
            "name": "名前",
            "display_name": "表示名",
            "color": "色",
            "position": "位置",
            "type": "種類",
            "category_name": "カテゴリー",
            "roles": "割り当てロール",
        }.get(column, column)

    @property
    def items(self) -> list[dict[str, Any]]:
        return self.get_document()[self.section]

    def _summary(self, item: dict[str, Any]) -> tuple[str, ...]:
        values: list[str] = []
        for column in self.columns:
            if column == "roles":
                role_names = self._role_names(item)
                values.append(", ".join(role_names) or "（なし）")
            else:
                value = item.get(column)
                values.append("" if value is None else str(value))
        return tuple(values)

    def _role_names(self, item: dict[str, Any]) -> list[str]:
        roles = {
            str(role["id"]): role["name"]
            for role in self.get_document()["roles"]
        }
        return [
            roles[role_id]
            for role_id in item.get("role_ids", [])
            if role_id in roles
        ]

    def refresh(self, select_index: int | None = None) -> None:
        self._rendering = True
        self.column_filter.prepare_refresh()
        self.tree.delete(*self.tree.get_children(""))
        for column in self.columns:
            self.tree.heading(column, text=self._column_label(column))
        for index, item in enumerate(self.items):
            self.tree.insert("", "end", iid=str(index), values=self._summary(item))
        self.column_filter.finish_refresh()
        self.column_filter.refresh_headers()
        if select_index is not None and 0 <= select_index < len(self.items):
            selected = str(select_index)
            if self.column_filter.is_visible(selected):
                self.tree.selection_set(selected)
                self.tree.focus(selected)
                self.tree.see(selected)
                self.show_item(self.items[select_index])
            else:
                self.current_item = None
                self.show_item(None)
        else:
            self.current_item = None
            self.show_item(None)
        self._rendering = False

    def _sort_marker(self, column_index: int) -> str:
        if column_index != self.sort_column:
            return ""
        return " ↓" if self.sort_reverse else " ↑"

    def sort_by(self, column_index: int, reverse: bool | None = None) -> None:
        if reverse is None:
            if self.sort_column == column_index:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_column = column_index
                self.sort_reverse = False
        else:
            self.sort_column = column_index
            self.sort_reverse = reverse
        self._apply_sort()

    def _apply_sort(self) -> None:
        if not hasattr(self, "tree"):
            return
        if self.sort_column is None:
            self.column_filter.refresh_headers()
            return
        visible = list(self.tree.get_children(""))
        visible.sort(
            key=lambda item: _sort_value(
                str(self.tree.set(item, self.columns[self.sort_column]))
            ),
            reverse=self.sort_reverse,
        )
        for index, item in enumerate(visible):
            self.tree.move(item, "", index)
        self.column_filter.refresh_headers()

    def on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if selected:
            self.show_item(self.items[int(selected[0])])

    def show_item(self, item: dict[str, Any] | None) -> None:
        self.current_item = item
        self.details_canvas.yview_moveto(0)
        for child in self.details.winfo_children():
            child.destroy()
        if item is None:
            ttk.Label(
                self.details,
                text="左の一覧から編集対象を選択してください。",
                foreground="gray",
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            return

        row = 0
        ttk.Label(
            self.details,
            text=f"{self.label}の設定",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1
        for field, value in item.items():
            if field == "permissions" and self.section == "roles":
                row = self._add_permissions(row, item)
            elif field == "role_ids" and self.section == "members":
                row = self._add_member_roles(row, item)
            elif isinstance(value, (dict, list)):
                row = self._add_json_field(row, item, field, value)
            elif field in READ_ONLY_FIELDS:
                row = self._add_readonly(row, field, value)
            else:
                row = self._add_field(row, item, field, value)

    def _add_readonly(self, row: int, field: str, value: Any) -> int:
        ttk.Label(self.details, text=self._column_label(field)).grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        ttk.Label(self.details, text=str(value), foreground="gray").grid(
            row=row, column=1, sticky="w", pady=4
        )
        return row + 1

    def _add_field(
        self,
        row: int,
        item: dict[str, Any],
        field: str,
        value: Any,
    ) -> int:
        ttk.Label(self.details, text=self._column_label(field)).grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        if field in BOOL_FIELDS or isinstance(value, bool):
            variable = tk.BooleanVar(value=bool(value))
            widget: tk.Widget = ttk.Checkbutton(
                self.details,
                variable=variable,
                command=lambda: self._set_value(item, field, variable.get()),
            )
            widget.grid(row=row, column=1, sticky="w", pady=4)
        elif field in ENUM_FIELDS:
            variable = tk.StringVar(value="" if value is None else str(value))
            widget = ttk.Combobox(
                self.details,
                textvariable=variable,
                values=ENUM_FIELDS[field],
                state="readonly",
            )
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            widget.bind(
                "<<ComboboxSelected>>",
                lambda _event: self._set_value(
                    item,
                    field,
                    variable.get() or None,
                ),
            )
        else:
            variable = tk.StringVar(value="" if value is None else str(value))
            widget = ttk.Entry(self.details, textvariable=variable)
            widget.grid(row=row, column=1, sticky="ew", pady=4)

            def update(*_args: object) -> None:
                if self._rendering:
                    return
                text = variable.get()
                if field in INT_FIELDS:
                    if text.isdecimal():
                        self._set_value(item, field, int(text))
                    elif text == "":
                        self._set_value(item, field, 0)
                    return
                if value is None and text == "":
                    parsed: Any = None
                else:
                    parsed = text
                self._set_value(item, field, parsed)

            variable.trace_add("write", update)
        return row + 1

    def _add_permissions(self, row: int, item: dict[str, Any]) -> int:
        ttk.Label(self.details, text="権限").grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        panel = ttk.Frame(self.details)
        panel.grid(row=row, column=1, sticky="ew", pady=4)
        permissions = item["permissions"]
        for index, permission in enumerate(sorted(permissions)):
            variable = tk.BooleanVar(value=bool(permissions[permission]))
            ttk.Checkbutton(
                panel,
                text=permission,
                variable=variable,
                command=lambda name=permission, var=variable: self._set_permission(
                    item,
                    name,
                    var.get(),
                ),
            ).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 8))
        return row + 1

    def _add_member_roles(self, row: int, item: dict[str, Any]) -> int:
        ttk.Label(self.details, text="割り当てロール").grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        panel = ttk.Frame(self.details)
        panel.grid(row=row, column=1, sticky="ew", pady=4)
        selected_ids = set(item["role_ids"])
        for index, role in enumerate(self.get_document()["roles"]):
            role_id = str(role["id"])
            variable = tk.BooleanVar(value=role_id in selected_ids)
            ttk.Checkbutton(
                panel,
                text=role["name"],
                variable=variable,
                command=lambda value=role_id, var=variable: self._set_member_role(
                    item,
                    value,
                    var.get(),
                ),
            ).grid(row=index, column=0, sticky="w")
        return row + 1

    def _add_json_field(
        self,
        row: int,
        item: dict[str, Any],
        field: str,
        value: dict[str, Any] | list[Any],
    ) -> int:
        ttk.Label(self.details, text=self._column_label(field)).grid(
            row=row, column=0, sticky="nw", padx=(0, 8), pady=4
        )
        editor = tk.Text(self.details, height=8, width=48, wrap="none", font=("Consolas", 9))
        editor.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
        editor.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        def apply_value() -> None:
            try:
                parsed = json.loads(editor.get("1.0", "end-1c"))
            except json.JSONDecodeError as error:
                messagebox.showerror(
                    "JSON入力エラー",
                    f"{error.lineno}行 {error.colno}列: {error.msg}",
                    parent=self,
                )
                return
            if not isinstance(parsed, type(value)):
                messagebox.showerror(
                    "JSON入力エラー",
                    "元の項目と同じ種類（配列またはオブジェクト）を入力してください。",
                    parent=self,
                )
                return
            self._set_value(item, field, parsed)

        ttk.Button(
            self.details,
            text=f"{field}を反映",
            command=apply_value,
        ).grid(row=row, column=1, sticky="e", pady=(0, 6))
        return row + 1

    def _set_value(self, item: dict[str, Any], field: str, value: Any) -> None:
        if item.get(field) == value:
            return
        previous = item.get(field)
        item[field] = value
        if field == "name":
            self._update_name_references(item, previous, value)
            self.refresh_related(self)
        self.mark_dirty()
        self.refresh_item_summary(item)

    def _update_name_references(
        self,
        item: dict[str, Any],
        previous: Any,
        current: Any,
    ) -> None:
        if not isinstance(previous, str) or not isinstance(current, str):
            return
        document = self.get_document()
        if self.section == "roles":
            role_id = str(item.get("id"))
            for channel in document["channels"]:
                for overwrite in channel.get("permission_overwrites", []):
                    if (
                        overwrite.get("target_type") == "role"
                        and overwrite.get("target_id") == role_id
                    ):
                        overwrite["target_name"] = current
        elif self.section == "members":
            member_id = str(item.get("id"))
            for channel in document["channels"]:
                for overwrite in channel.get("permission_overwrites", []):
                    if (
                        overwrite.get("target_type") == "member"
                        and overwrite.get("target_id") == member_id
                    ):
                        overwrite["target_name"] = current
        elif item.get("type") == "category":
            category_id = str(item.get("id"))
            for channel in document["channels"]:
                if (
                    channel.get("category_id") == category_id
                    or channel.get("category_name", "").casefold() == previous.casefold()
                ):
                    channel["category_name"] = current

    def _set_permission(
        self,
        item: dict[str, Any],
        permission: str,
        enabled: bool,
    ) -> None:
        if item["permissions"].get(permission) == enabled:
            return
        item["permissions"][permission] = enabled
        self.mark_dirty()

    def _set_member_role(
        self,
        item: dict[str, Any],
        role_id: str,
        enabled: bool,
    ) -> None:
        selected = set(item["role_ids"])
        if enabled:
            selected.add(role_id)
        else:
            selected.discard(role_id)
        role_order = {str(role["id"]): index for index, role in enumerate(self.get_document()["roles"])}
        item["role_ids"] = sorted(selected, key=lambda value: role_order.get(value, len(role_order)))
        self.mark_dirty()
        self.refresh_item_summary(item)

    def refresh_item_summary(self, item: dict[str, Any]) -> None:
        try:
            index = self.items.index(item)
        except ValueError:
            return
        item_id = str(index)
        if self.tree.exists(item_id):
            self.tree.item(item_id, values=self._summary(item))
            self.column_filter.update_item(item_id)

    def add_item(self) -> None:
        match_everyone_permissions = False
        if self.section == "roles":
            match_everyone_permissions = messagebox.askyesno(
                "権限設定",
                "新しいロールの権限を@everyoneと同じにしますか？",
                parent=self,
                default="no",
            )
        item = _new_item(
            self.section,
            self.get_document(),
            match_everyone_permissions=match_everyone_permissions,
        )
        self.items.append(item)
        self.mark_dirty()
        self.column_filter.clear_filters()
        self.refresh_related(self)
        self.refresh(len(self.items) - 1)

    def delete_item(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        index = int(selected[0])
        item = self.items[index]
        if not messagebox.askyesno(
            "確認",
            f"選択した{self.label}をJSONから削除しますか？",
            parent=self,
        ):
            return
        del self.items[index]
        if self.section == "roles":
            role_id = str(item.get("id"))
            for member in self.get_document()["members"]:
                member["role_ids"] = [
                    value for value in member.get("role_ids", []) if value != role_id
                ]
            for channel in self.get_document()["channels"]:
                channel["permission_overwrites"] = [
                    overwrite
                    for overwrite in channel.get("permission_overwrites", [])
                    if not (
                        overwrite.get("target_type") == "role"
                        and overwrite.get("target_id") == role_id
                    )
                ]
        elif self.section == "members":
            member_id = str(item.get("id"))
            for channel in self.get_document()["channels"]:
                channel["permission_overwrites"] = [
                    overwrite
                    for overwrite in channel.get("permission_overwrites", [])
                    if not (
                        overwrite.get("target_type") == "member"
                        and overwrite.get("target_id") == member_id
                    )
                ]
        self.column_filter.clear_filters()
        self.mark_dirty()
        self.refresh_related(self)
        next_index = min(index, len(self.items) - 1) if self.items else None
        self.refresh(next_index)


class ServerExportJsonEditor(EditorFrame):
    def __init__(
        self,
        path: Path | None = None,
        master: tk.Misc | None = None,
    ) -> None:
        super().__init__(master)
        self.path = path
        self.dirty = False
        self.document: dict[str, Any] | None = None
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(850, 560)

        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="開く...", command=self.open_file).pack(side="left")
        ttk.Button(toolbar, text="保存", command=self.save).pack(side="left", padx=4)
        ttk.Button(toolbar, text="名前を付けて保存...", command=self.save_as).pack(side="left")
        self.guild_label = ttk.Label(toolbar, text="JSONファイルを開いてください", foreground="gray")
        self.guild_label.pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.editors: list[SectionEditor] = []
        for section, label, columns in SECTION_OPTIONS:
            editor = SectionEditor(
                self.notebook,
                section,
                label,
                columns,
                self._get_document,
                self.mark_dirty,
                self.refresh_editors,
            )
            self.notebook.add(editor, text=label)
            self.editors.append(editor)

        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 4), foreground="gray")
        self.status.pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if path is not None:
            self.load_file(path)
        else:
            self.document = {
                "schema_version": 1,
                "guild": {},
                "roles": [],
                "members": [],
                "channels": [],
            }
            self.refresh_editors()
            self.status.config(text="サーバーエクスポートJSONを開いて編集してください。")

    def _get_document(self) -> dict[str, Any]:
        if self.document is None:
            return {"roles": [], "members": [], "channels": []}
        return self.document

    def refresh_editors(self, source: SectionEditor | None = None) -> None:
        for editor in self.editors:
            if editor is not source:
                editor.refresh()
        guild = self._get_document().get("guild", {})
        self.guild_label.config(text=guild.get("name", "サーバー情報なし"))

    def mark_dirty(self) -> None:
        self.dirty = True
        self.update_title()

    def update_title(self) -> None:
        name = self.path.name if self.path is not None else "未保存"
        self.title(f"{name}{' *' if self.dirty else ''} - {APP_TITLE}")

    def confirm_discard(self) -> bool:
        return not self.dirty or messagebox.askyesno(
            "未保存の変更",
            "変更を保存せずに続行しますか？",
            parent=self,
        )

    def open_file(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=self.path.parent if self.path else None,
            filetypes=[("JSON", "*.json"), ("すべてのファイル", "*.*")],
        )
        if selected and self.confirm_discard():
            self.load_file(Path(selected))

    def load_file(self, path: Path) -> None:
        try:
            self.document = parse_export_json(load_export_json(path))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            messagebox.showerror("読み込みエラー", str(error), parent=self)
            return
        self.path = path
        self.dirty = False
        self.update_title()
        self.refresh_editors()
        self.status.config(text=str(path))

    def save(self) -> None:
        if self.path is None:
            self.save_as()
            return
        self.save_to(self.path)

    def save_as(self) -> None:
        selected = filedialog.asksaveasfilename(
            initialdir=self.path.parent if self.path else None,
            initialfile=self.path.name if self.path else "server_export.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if selected:
            self.save_to(Path(selected))

    def save_to(self, path: Path) -> None:
        try:
            save_export_json(
                path,
                json.dumps(self._get_document(), ensure_ascii=False, indent=2),
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("保存エラー", str(error), parent=self)
            return
        self.path = path
        self.dirty = False
        self.update_title()
        self.status.config(text=f"保存しました: {path}")

    def on_close(self) -> None:
        if self.confirm_discard():
            self.destroy()

