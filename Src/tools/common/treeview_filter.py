from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def matches_filters(values: tuple[str, ...], filters: dict[int, set[str]]) -> bool:
    return all(index < len(values) and values[index] in choices for index, choices in filters.items())


class TreeviewColumnFilter:
    """Add Excel-style value filters to a Treeview without discarding hidden items."""

    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self.filters: dict[int, set[str]] = {}
        self.items: list[str] = []
        self.values: dict[str, tuple[str, ...]] = {}
        self.on_filtered: Callable[[], None] | None = None
        self.on_sort: Callable[[int, bool], None] | None = None
        self.header_suffix: Callable[[int], str] | None = None
        self.sort_column: int | None = None
        self.sort_reverse = False
        self.headers: list[str] = []
        self._read_headers()

    def _read_headers(self) -> None:
        self.headers = []
        for column in self.tree["columns"]:
            text = str(self.tree.heading(column, "text"))
            for marker in (" ▼●", " ▼", " ↑", " ↓"):
                while text.endswith(marker):
                    text = text[: -len(marker)]
            self.headers.append(text)
        self._update_headers()

    def _update_headers(self) -> None:
        for index, column in enumerate(self.tree["columns"]):
            header = self.headers[index] if index < len(self.headers) else str(column)
            marker = " ▼●" if index in self.filters else " ▼"
            if self.header_suffix is not None:
                suffix = self.header_suffix(index)
            elif index == self.sort_column:
                suffix = " ↓" if self.sort_reverse else " ↑"
            else:
                suffix = ""
            self.tree.heading(
                column,
                text=header + suffix + marker,
                command=lambda selected=index: self.open_filter(selected),
            )

    def refresh_headers(self) -> None:
        self._update_headers()

    def prepare_refresh(self) -> None:
        for item in self.items:
            if self.tree.exists(item):
                self.tree.move(item, "", "end")
        self.items.clear()
        self.values.clear()

    def finish_refresh(self) -> None:
        self._read_headers()
        if self.sort_column is not None and self.sort_column >= len(self.tree["columns"]):
            self.sort_column = None
            self.sort_reverse = False
        self.items = list(self.tree.get_children(""))
        self.values = {
            item: tuple(str(value) for value in self.tree.item(item, "values"))
            for item in self.items
        }
        self._apply()

    def update_item(self, item: str) -> None:
        if item in self.items and self.tree.exists(item):
            self.values[item] = tuple(str(value) for value in self.tree.item(item, "values"))
            self._apply()

    def is_visible(self, item: str) -> bool:
        return item in self.items and item in self.tree.get_children("")

    def clear_filters(self) -> None:
        if self.filters:
            self.filters.clear()
            self._apply()

    def _apply(self) -> None:
        for item in self.items:
            if not self.tree.exists(item):
                continue
            if matches_filters(self.values[item], self.filters):
                self.tree.move(item, "", "end")
            else:
                self.tree.detach(item)
        if self.on_sort is None:
            self._apply_sort()
        self._update_headers()
        selection = self.tree.selection()
        if any(not self.is_visible(item) for item in selection):
            self.tree.selection_remove(*selection)
        if self.on_filtered is not None:
            self.on_filtered()

    def open_filter(self, column_index: int) -> None:
        if column_index >= len(self.headers):
            return
        header = self.headers[column_index]
        choices = sorted(
            {row[column_index] for row in self.values.values() if column_index < len(row)},
            key=lambda value: (value.casefold(), value),
        )
        selected = self.filters.get(column_index, set(choices)).copy()

        popup = tk.Toplevel(self.tree)
        popup.title(f"フィルター: {header}")
        popup.transient(self.tree.winfo_toplevel())
        popup.resizable(True, True)
        popup.geometry(f"320x430+{popup.winfo_pointerx()}+{popup.winfo_pointery()}")

        body = ttk.Frame(popup, padding=8)
        body.pack(fill="both", expand=True)
        sort_buttons = ttk.Frame(body)
        sort_buttons.pack(fill="x", pady=(0, 6))
        ttk.Button(
            sort_buttons,
            text="昇順で並べ替え",
            command=lambda: apply_sort(False),
        ).pack(side="left")
        ttk.Button(
            sort_buttons,
            text="降順で並べ替え",
            command=lambda: apply_sort(True),
        ).pack(side="left", padx=(4, 0))
        ttk.Separator(body).pack(fill="x", pady=(0, 6))
        ttk.Label(body, text=f"「{header}」の表示値を選択").pack(anchor="w")
        ttk.Label(body, text="値を検索", foreground="gray").pack(anchor="w", pady=(6, 0))
        search = tk.StringVar()
        ttk.Entry(body, textvariable=search).pack(fill="x", pady=(4, 4))

        all_var = tk.BooleanVar(value=len(selected) == len(choices))
        ttk.Checkbutton(body, text="すべて選択", variable=all_var, command=lambda: toggle_all()).pack(anchor="w")
        options_outer = ttk.Frame(body)
        options_outer.pack(fill="both", expand=True, pady=4)
        canvas = tk.Canvas(options_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(options_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        options = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=options, anchor="nw")
        options.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        variables = {value: tk.BooleanVar(value=value in selected) for value in choices}

        def toggle_all() -> None:
            for variable in variables.values():
                variable.set(all_var.get())

        def sync_all() -> None:
            all_var.set(all(variable.get() for variable in variables.values()))

        def rebuild_options(*_args: object) -> None:
            for child in options.winfo_children():
                child.destroy()
            query = search.get().casefold()
            for value in choices:
                label = value if value else "(空白)"
                if query and query not in label.casefold():
                    continue
                ttk.Checkbutton(
                    options,
                    text=label,
                    variable=variables[value],
                    command=sync_all,
                ).pack(anchor="w", fill="x")
            sync_all()

        search.trace_add("write", rebuild_options)
        rebuild_options()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(6, 0))

        def apply_sort(reverse: bool) -> None:
            if self.on_sort is not None:
                self.on_sort(column_index, reverse)
            else:
                self.sort_column = column_index
                self.sort_reverse = reverse
                self._apply_sort()
                self._update_headers()
            popup.destroy()

        def apply_filter() -> None:
            chosen = {value for value, variable in variables.items() if variable.get()}
            if chosen == set(choices):
                self.filters.pop(column_index, None)
            else:
                self.filters[column_index] = chosen
            popup.destroy()
            self._apply()

        def clear_filter() -> None:
            self.filters.pop(column_index, None)
            popup.destroy()
            self._apply()

        ttk.Button(buttons, text="この列を解除", command=clear_filter).pack(side="left")
        ttk.Button(buttons, text="キャンセル", command=popup.destroy).pack(side="right")
        ttk.Button(buttons, text="適用", command=apply_filter).pack(side="right", padx=4)
        popup.bind("<Return>", lambda _event: apply_filter())
        popup.bind("<Escape>", lambda _event: popup.destroy())
        popup.grab_set()

    def _apply_sort(self) -> None:
        if self.sort_column is None:
            return
        column = str(self.tree["columns"][self.sort_column])
        visible = list(self.tree.get_children(""))
        visible.sort(
            key=lambda item: _sort_value(str(self.tree.set(item, column))),
            reverse=self.sort_reverse,
        )
        for index, item in enumerate(visible):
            self.tree.move(item, "", index)


def _sort_value(value: str) -> tuple[int, object]:
    if not value:
        return 0, ""
    try:
        return 1, float(value)
    except ValueError:
        return 2, value.casefold()
