from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class EditorFrame(ttk.Frame):
    """単体起動(自前のウィンドウ)とタブへの埋め込みの両方で動くエディタの土台。"""

    def __init__(self, master: tk.Misc | None = None) -> None:
        self._own_root: tk.Tk | None = None
        self._root_closing = False
        if master is None:
            self._own_root = master = tk.Tk()
            original_destroy = master.destroy

            def destroy_root() -> None:
                self._root_closing = True
                original_destroy()

            master.destroy = destroy_root
        super().__init__(master)
        if self._own_root is not None:
            self.pack(fill="both", expand=True)
        self.on_title: Callable[[str], None] | None = None
        self.close_handler: Callable[[], None] | None = None
        self._title_text = ""

    @property
    def embedded(self) -> bool:
        return self._own_root is None

    def title(self, text: str | None = None) -> str:
        if text is None:
            return self._title_text
        self._title_text = text
        if self._own_root is not None:
            self._own_root.title(text)
        elif self.on_title is not None:
            self.on_title(text)
        return text

    def geometry(self, size: str) -> None:
        if self._own_root is not None:
            self._own_root.geometry(size)

    def minsize(self, width: int, height: int) -> None:
        if self._own_root is not None:
            self._own_root.minsize(width, height)

    def protocol(self, name: str, func: Callable[[], None]) -> None:
        if self._own_root is not None:
            self._own_root.protocol(name, func)
        elif name == "WM_DELETE_WINDOW":
            self.close_handler = func

    def destroy(self) -> None:
        root = self._own_root
        if root is not None and not self._root_closing:
            root.destroy()
        else:
            super().destroy()
