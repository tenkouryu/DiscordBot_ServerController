from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """縦スクロールできる領域。内側の `body` にウィジェットを配置する。"""

    def __init__(self, master: tk.Misc, **body_options: object) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, **body_options)
        window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_wheel(self, event: tk.Event) -> None:
        first, last = self.canvas.yview()
        if first > 0.0 or last < 1.0:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0)
