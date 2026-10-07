from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import io
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


_REQUIRED_COLUMNS = {
    "scenario_id",
    "step",
    "instruction",
    "completion_type",
    "completion_value",
    "response",
}

_EMOJI_OPTIONS = (
    ("😀", "顔・感情", "笑顔 にこにこ"),
    ("😃", "顔・感情", "笑顔 にこにこ"),
    ("😄", "顔・感情", "笑顔 にこにこ"),
    ("😁", "顔・感情", "笑顔 にこにこ"),
    ("😆", "顔・感情", "笑い うれしい"),
    ("😅", "顔・感情", "苦笑 汗"),
    ("😂", "顔・感情", "笑い 泣く"),
    ("🤣", "顔・感情", "爆笑 笑い"),
    ("😊", "顔・感情", "笑顔 うれしい"),
    ("😇", "顔・感情", "天使"),
    ("🙂", "顔・感情", "笑顔"),
    ("🙃", "顔・感情", "逆さ 顔"),
    ("😉", "顔・感情", "ウインク"),
    ("😍", "顔・感情", "好き ハート"),
    ("🥰", "顔・感情", "好き ハート"),
    ("😘", "顔・感情", "キス"),
    ("😋", "顔・感情", "おいしい"),
    ("😎", "顔・感情", "サングラス"),
    ("🤔", "顔・感情", "考える"),
    ("😐", "顔・感情", "無表情"),
    ("😴", "顔・感情", "眠い"),
    ("😭", "顔・感情", "泣く 悲しい"),
    ("😡", "顔・感情", "怒り"),
    ("🤯", "顔・感情", "驚き"),
    ("🥳", "顔・感情", "お祝い"),
    ("🤗", "顔・感情", "ハグ"),
    ("🫡", "顔・感情", "敬礼"),
    ("👋", "手・人", "手を振る こんにちは"),
    ("✋", "手・人", "手 止まる"),
    ("👌", "手・人", "オーケー OK"),
    ("✌️", "手・人", "ピース"),
    ("🤞", "手・人", "幸運"),
    ("🤟", "手・人", "愛してる"),
    ("🤘", "手・人", "ロック"),
    ("👈", "手・人", "左 指"),
    ("👉", "手・人", "右 指"),
    ("👆", "手・人", "上 指"),
    ("👇", "手・人", "下 指"),
    ("☝️", "手・人", "上 指"),
    ("👍", "手・人", "いいね 賛成"),
    ("👎", "手・人", "よくない 反対"),
    ("✊", "手・人", "拳"),
    ("👊", "手・人", "パンチ"),
    ("👏", "手・人", "拍手"),
    ("🙌", "手・人", "万歳"),
    ("🤝", "手・人", "握手"),
    ("🙏", "手・人", "お願い 感謝"),
    ("💪", "手・人", "力 強い"),
    ("❤️", "ハート・記号", "赤 ハート"),
    ("🧡", "ハート・記号", "オレンジ ハート"),
    ("💛", "ハート・記号", "黄色 ハート"),
    ("💚", "ハート・記号", "緑 ハート"),
    ("💙", "ハート・記号", "青 ハート"),
    ("💜", "ハート・記号", "紫 ハート"),
    ("🖤", "ハート・記号", "黒 ハート"),
    ("🤍", "ハート・記号", "白 ハート"),
    ("🤎", "ハート・記号", "茶色 ハート"),
    ("💔", "ハート・記号", "失恋 割れたハート"),
    ("💕", "ハート・記号", "ハート 好き"),
    ("💖", "ハート・記号", "輝く ハート"),
    ("✅", "ハート・記号", "完了 正解 チェック"),
    ("☑️", "ハート・記号", "チェック"),
    ("✔️", "ハート・記号", "チェック 正解"),
    ("❌", "ハート・記号", "バツ 不正解"),
    ("❎", "ハート・記号", "バツ"),
    ("❓", "ハート・記号", "質問 はてな"),
    ("❗", "ハート・記号", "注意 びっくり"),
    ("💯", "ハート・記号", "満点 百点"),
    ("🔔", "ハート・記号", "ベル 通知"),
    ("⭐", "ハート・記号", "星"),
    ("🌟", "ハート・記号", "星 輝く"),
    ("✨", "ハート・記号", "きらきら"),
    ("⚡", "ハート・記号", "雷"),
    ("🔥", "ハート・記号", "火 炎"),
    ("💥", "ハート・記号", "爆発"),
    ("🎉", "イベント・遊び", "お祝い パーティー"),
    ("🎊", "イベント・遊び", "くす玉 お祝い"),
    ("🎈", "イベント・遊び", "風船"),
    ("🎁", "イベント・遊び", "プレゼント"),
    ("🎮", "イベント・遊び", "ゲーム"),
    ("🎲", "イベント・遊び", "サイコロ"),
    ("🃏", "イベント・遊び", "カード ジョーカー"),
    ("🎯", "イベント・遊び", "的 当たり"),
    ("🏆", "イベント・遊び", "トロフィー 優勝"),
    ("🥇", "イベント・遊び", "金メダル 一位"),
    ("🥈", "イベント・遊び", "銀メダル 二位"),
    ("🥉", "イベント・遊び", "銅メダル 三位"),
    ("⚔️", "イベント・遊び", "剣 先攻"),
    ("🛡️", "イベント・遊び", "盾 後攻"),
    ("🏁", "イベント・遊び", "ゴール レース"),
    ("🚩", "イベント・遊び", "旗"),
    ("🎤", "イベント・遊び", "マイク"),
    ("🎵", "イベント・遊び", "音楽 音符"),
    ("🐶", "動物・自然", "犬 いぬ"),
    ("🐱", "動物・自然", "猫 ねこ"),
    ("🐭", "動物・自然", "ねずみ"),
    ("🐰", "動物・自然", "うさぎ"),
    ("🦊", "動物・自然", "きつね"),
    ("🐻", "動物・自然", "くま"),
    ("🐼", "動物・自然", "パンダ"),
    ("🐸", "動物・自然", "かえる"),
    ("🐵", "動物・自然", "さる"),
    ("🦁", "動物・自然", "ライオン"),
    ("🐧", "動物・自然", "ペンギン"),
    ("🐦", "動物・自然", "鳥"),
    ("🦋", "動物・自然", "蝶"),
    ("🌸", "動物・自然", "桜 花"),
    ("🌻", "動物・自然", "ひまわり 花"),
    ("🌈", "動物・自然", "虹"),
    ("☀️", "動物・自然", "太陽 晴れ"),
    ("🌙", "動物・自然", "月"),
    ("☁️", "動物・自然", "雲"),
    ("❄️", "動物・自然", "雪"),
    ("🍎", "食べ物・飲み物", "りんご 果物"),
    ("🍓", "食べ物・飲み物", "いちご 果物"),
    ("🍒", "食べ物・飲み物", "さくらんぼ 果物"),
    ("🍉", "食べ物・飲み物", "すいか 果物"),
    ("🍕", "食べ物・飲み物", "ピザ"),
    ("🍔", "食べ物・飲み物", "ハンバーガー"),
    ("🍜", "食べ物・飲み物", "ラーメン"),
    ("🍣", "食べ物・飲み物", "寿司"),
    ("🍰", "食べ物・飲み物", "ケーキ"),
    ("☕", "食べ物・飲み物", "コーヒー"),
    ("🍺", "食べ物・飲み物", "ビール"),
    ("🥤", "食べ物・飲み物", "飲み物"),
    ("🚀", "その他", "ロケット"),
    ("💎", "その他", "宝石"),
    ("🔑", "その他", "鍵"),
    ("📌", "その他", "ピン"),
    ("📣", "その他", "メガホン"),
)
_EMOJI_CATEGORIES = ("すべて", *dict.fromkeys(option[1] for option in _EMOJI_OPTIONS))


@dataclass
class ScenarioCsvDocument:
    path: Path
    scenarios: dict[str, list[dict[str, str]]]
    rows: list[dict[str, str]]
    fieldnames: list[str]
    delimiter: str
    encoding: str


def filter_emoji_options(
    query: str, category: str = "すべて"
) -> list[tuple[str, str, str]]:
    """絵文字候補をカテゴリと絵文字・日本語キーワードで絞り込む。"""
    normalized_query = query.strip().casefold()
    return [
        option
        for option in _EMOJI_OPTIONS
        if (category == "すべて" or option[1] == category)
        and (
            not normalized_query
            or normalized_query in "".join(option).casefold()
        )
    ]


def load_scenario_documents(
    paths: list[Path],
) -> tuple[
    dict[Path, ScenarioCsvDocument],
    dict[str, tuple[Path, str, list[dict[str, str]]]],
]:
    """複数CSVを読み込み、一覧表示名から元ファイルとシナリオを引けるようにする。"""
    documents: dict[Path, ScenarioCsvDocument] = {}
    scenarios: dict[str, tuple[Path, str, list[dict[str, str]]]] = {}
    for path in sorted(set(paths), key=lambda item: str(item).casefold()):
        try:
            data, rows, fieldnames, delimiter, encoding = _read_scenario_csv(path)
        except (OSError, UnicodeError, ValueError) as error:
            raise ValueError(f"{path.name}: {error}") from error
        if not data:
            continue
        documents[path] = ScenarioCsvDocument(
            path, data, rows, fieldnames, delimiter, encoding
        )
        for scenario_id, steps in data.items():
            label = f"{scenario_id} — {path.name}"
            unique_label = label
            suffix = 2
            while unique_label in scenarios:
                unique_label = f"{label} ({suffix})"
                suffix += 1
            scenarios[unique_label] = (path, scenario_id, steps)
    return documents, scenarios


def load_scenarios(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    """CSVを読み込み、シナリオIDごとにステップをまとめる。"""
    return _read_scenario_csv(csv_path)[0]


def _read_scenario_csv(
    csv_path: Path,
) -> tuple[
    dict[str, list[dict[str, str]]],
    list[dict[str, str]],
    list[str],
    str,
    str,
]:
    """シナリオと、保存時に必要な行順・列・CSV形式を読み込む。"""
    raw = csv_path.read_bytes()
    last_decode_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp932", "utf-16"):
        try:
            text = raw.decode(encoding)
            output_encoding = (
                "utf-8-sig" if encoding == "utf-8-sig" and raw.startswith(b"\xef\xbb\xbf")
                else "utf-8" if encoding == "utf-8-sig"
                else encoding
            )
            sample = "\n".join(text.splitlines()[:3])
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
            except csv.Error:
                delimiter = max((",", "\t", ";"), key=sample.count)

            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            if reader.fieldnames:
                reader.fieldnames = [field.strip() for field in reader.fieldnames]
            fieldnames = reader.fieldnames or []
            columns = set(reader.fieldnames or [])
            missing_columns = _REQUIRED_COLUMNS - columns
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                detected = ", ".join(sorted(columns)) or "なし"
                raise ValueError(
                    f"CSVに必要な列がありません: {missing}（検出した列: {detected}）"
                )

            scenarios: dict[str, list[dict[str, str]]] = {}
            rows: list[dict[str, str]] = []
            for row_number, row in enumerate(reader, start=2):
                scenario_id = (row.get("scenario_id") or "").strip()
                if not scenario_id:
                    raise ValueError(f"{row_number}行目: scenario_idが空です")

                step_text = (row.get("step") or "").strip()
                try:
                    int(step_text)
                except ValueError as error:
                    raise ValueError(f"{row_number}行目: stepは整数で指定してください") from error

                normalized_row = {
                    key: (value or "").strip()
                    for key, value in row.items()
                    if key is not None
                }
                rows.append(normalized_row)
                scenarios.setdefault(scenario_id, []).append(normalized_row)
            break
        except UnicodeDecodeError as error:
            last_decode_error = error
    else:
        raise ValueError(f"CSVの文字コードを判定できませんでした: {last_decode_error}")

    for steps in scenarios.values():
        steps.sort(key=lambda row: int(row["step"]))
    return scenarios, rows, fieldnames, delimiter, output_encoding


def save_scenario_csv(
    csv_path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
    delimiter: str,
    encoding: str,
) -> None:
    """元CSVの列順・区切り文字・文字コードを保って安全に上書きする。"""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=delimiter,
        lineterminator="\r\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    contents = output.getvalue().encode(encoding)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=csv_path.parent, prefix=f"{csv_path.name}.", suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(contents)
        os.replace(temporary_path, csv_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


import sys as _sys

_TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if _TOOLS_DIR not in _sys.path:
    _sys.path.insert(0, _TOOLS_DIR)
from common.window_base import EditorFrame  # noqa: E402


class ScenarioEditor(EditorFrame):
    def __init__(self, csv_path: Path | None = None, scenario_id: str | None = None, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.title("シナリオエディター")
        self.geometry("1000x680")
        self.minsize(760, 500)
        self.csv_path: Path | None = None
        self.csv_documents: dict[Path, ScenarioCsvDocument] = {}
        self.scenarios: dict[str, list[dict[str, str]]] = {}
        self.scenario_sources: dict[str, tuple[Path, str]] = {}
        self.csv_rows: list[dict[str, str]] = []
        self.fieldnames: list[str] = []
        self.delimiter = ","
        self.encoding = "utf-8"
        self.current_scenario_label: str | None = None
        self.current_step_index: int | None = None
        self.dirty_paths: set[Path] = set()
        self.dirty = False
        self.initial_scenario = scenario_id

        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="CSVを開く...", command=self.choose_file).pack(side="left")
        ttk.Button(
            toolbar, text="フォルダを開く...", command=self.choose_folder
        ).pack(side="left", padx=(6, 0))
        self.path_label = ttk.Label(toolbar, text="CSVファイルを選択してください")
        self.path_label.pack(side="left", padx=8, fill="x", expand=True)

        content = ttk.PanedWindow(self, orient="horizontal")
        content.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        navigation = ttk.Frame(content, padding=(0, 0, 8, 0))
        content.add(navigation, weight=1)
        ttk.Label(navigation, text="シナリオ").pack(anchor="w")
        scenario_frame = ttk.Frame(navigation)
        scenario_frame.pack(fill="x", pady=(4, 10))
        self.scenario_list = tk.Listbox(scenario_frame, height=6, exportselection=False)
        scenario_scrollbar = ttk.Scrollbar(
            scenario_frame, orient="vertical", command=self.scenario_list.yview
        )
        self.scenario_list.configure(yscrollcommand=scenario_scrollbar.set)
        self.scenario_list.pack(side="left", fill="both", expand=True)
        scenario_scrollbar.pack(side="right", fill="y")
        self.scenario_list.bind("<<ListboxSelect>>", self._on_scenario_selected)

        ttk.Label(navigation, text="ステップ").pack(anchor="w")
        step_frame = ttk.Frame(navigation)
        step_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.step_list = ttk.Treeview(step_frame, columns=("step",), show="headings")
        self.step_list.heading("step", text="Step")
        self.step_list.column("step", width=100, anchor="center")
        step_scrollbar = ttk.Scrollbar(
            step_frame, orient="vertical", command=self.step_list.yview
        )
        self.step_list.configure(yscrollcommand=step_scrollbar.set)
        self.step_list.pack(side="left", fill="both", expand=True)
        step_scrollbar.pack(side="right", fill="y")
        self.step_list.bind("<<TreeviewSelect>>", self._on_step_selected)

        details = ttk.Frame(content)
        content.add(details, weight=3)
        self.detail_heading = ttk.Label(details, text="シナリオCSVを開いてください")
        self.detail_heading.pack(anchor="w", pady=(0, 6))
        editor_frame = ttk.Frame(details)
        editor_frame.pack(fill="both", expand=True)
        self.editor_canvas = tk.Canvas(editor_frame, highlightthickness=0)
        editor_scrollbar = ttk.Scrollbar(
            editor_frame, orient="vertical", command=self.editor_canvas.yview
        )
        self.editor_canvas.configure(yscrollcommand=editor_scrollbar.set)
        self.editor_canvas.pack(side="left", fill="both", expand=True)
        editor_scrollbar.pack(side="right", fill="y")
        self.editor_form = ttk.Frame(self.editor_canvas, padding=(2, 2, 8, 8))
        self.editor_window = self.editor_canvas.create_window(
            (0, 0), window=self.editor_form, anchor="nw"
        )
        self.editor_form.bind(
            "<Configure>",
            lambda _event: self.editor_canvas.configure(
                scrollregion=self.editor_canvas.bbox("all")
            ),
        )
        self.editor_canvas.bind(
            "<Configure>",
            lambda event: self.editor_canvas.itemconfigure(
                self.editor_window, width=event.width
            ),
        )
        self.editor_form.columnconfigure(0, weight=1)

        self.field_widgets: dict[str, tk.Text | ttk.Entry] = {}
        self.branch_rows: list[
            tuple[str, ttk.Combobox, ttk.Entry, ttk.Frame]
        ] = []
        self._add_text_field("instruction", "指示", 4)
        self._add_entry_field("completion_type", "完了条件")
        self._add_completion_value_field()
        self._add_text_field("response", "返信", 4)
        ttk.Label(self.editor_form, text="分岐").grid(
            row=8, column=0, sticky="w", pady=(8, 2)
        )
        self.branch_frame = ttk.Frame(self.editor_form)
        self.branch_frame.grid(row=9, column=0, sticky="ew")
        self.branch_frame.columnconfigure(1, weight=1)
        self.add_branch_button = ttk.Button(
            self.editor_form, text="分岐を追加", command=self._add_branch
        )
        self.add_branch_button.grid(row=10, column=0, sticky="w", pady=(4, 0))
        self.status_label = ttk.Label(details, text="変更はまだ保存されていません")
        self.status_label.pack(anchor="w", pady=(4, 0))

        controls = ttk.Frame(details, padding=(0, 8, 0, 0))
        controls.pack(fill="x")
        self.previous_button = ttk.Button(
            controls, text="前のステップ", command=lambda: self._move_step(-1), state="disabled"
        )
        self.previous_button.pack(side="left")
        self.position_label = ttk.Label(controls, text="")
        self.position_label.pack(side="left", expand=True)
        self.next_button = ttk.Button(
            controls, text="次のステップ", command=lambda: self._move_step(1), state="disabled"
        )
        self.next_button.pack(side="right")
        self.save_button = ttk.Button(
            controls, text="CSVに保存", command=self.save, state="disabled"
        )
        self.save_button.pack(side="right", padx=8)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after_idle(lambda: self._load_file(csv_path) if csv_path else self.choose_file())

    def _add_text_field(self, key: str, label: str, height: int) -> None:
        row = len(self.field_widgets) * 2
        ttk.Label(self.editor_form, text=label).grid(
            row=row, column=0, sticky="w", pady=(4, 2)
        )
        text = tk.Text(self.editor_form, height=height, wrap="word", undo=True)
        text.grid(row=row + 1, column=0, sticky="ew")
        text.bind("<KeyRelease>", self._mark_dirty)
        self.field_widgets[key] = text

    def _add_entry_field(self, key: str, label: str) -> None:
        row = len(self.field_widgets) * 2
        ttk.Label(self.editor_form, text=label).grid(
            row=row, column=0, sticky="w", pady=(4, 2)
        )
        entry = ttk.Entry(self.editor_form)
        entry.grid(row=row + 1, column=0, sticky="ew")
        if key == "completion_type":
            self.completion_type_entry = entry
            entry.bind("<KeyRelease>", self._on_completion_type_changed)
        else:
            entry.bind("<KeyRelease>", self._mark_dirty)
        self.field_widgets[key] = entry

    def _add_completion_value_field(self) -> None:
        row = len(self.field_widgets) * 2
        ttk.Label(self.editor_form, text="完了値").grid(
            row=row, column=0, sticky="w", pady=(4, 2)
        )
        controls = ttk.Frame(self.editor_form)
        controls.grid(row=row + 1, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        entry = ttk.Entry(controls)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<KeyRelease>", self._mark_dirty)
        self.completion_value_entry = entry
        self.completion_emoji_button = ttk.Button(
            controls,
            text="絵文字を選択...",
            command=lambda: self._choose_emoji(self.completion_value_entry),
            state="disabled",
        )
        self.completion_emoji_button.grid(row=0, column=1, padx=(6, 0))
        self.field_widgets["completion_value"] = entry

    def _on_completion_type_changed(self, _event: tk.Event | None = None) -> None:
        self._mark_dirty()
        self._update_completion_emoji_button()

    def _update_completion_emoji_button(self) -> None:
        completion_type = self.completion_type_entry.get().strip().lower()
        self.completion_emoji_button.config(
            state="normal" if completion_type == "reaction" else "disabled"
        )

    def _mark_dirty(self, _event: tk.Event | None = None) -> None:
        if not self.dirty:
            self.dirty = True
            self._update_dirty_status()

    def _update_dirty_status(self) -> None:
        if self.dirty:
            self.status_label.config(text="未保存の変更があります")
            self.title("シナリオエディター *")
        else:
            self.status_label.config(text="変更は保存されています")
            self.title("シナリオエディター")

    def _confirm_pending_changes(self) -> bool:
        self._commit_editor()
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "未保存の変更",
            "変更を保存してから続けますか？\n「いいえ」を選ぶと変更を破棄します。",
            parent=self,
        )
        if answer is None:
            return False
        if answer:
            return self.save()
        return True

    def _close(self) -> None:
        if self._confirm_pending_changes():
            self.destroy()

    def choose_file(self) -> None:
        if not self._confirm_pending_changes():
            return
        initialdir = self.csv_path.parent if self.csv_path else Path.cwd()
        selected = filedialog.askopenfilename(
            parent=self,
            initialdir=initialdir,
            filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")],
        )
        if selected:
            self._load_file(Path(selected))

    def choose_folder(self) -> None:
        if not self._confirm_pending_changes():
            return
        initialdir = self.csv_path.parent if self.csv_path else Path.cwd()
        selected = filedialog.askdirectory(
            parent=self, initialdir=initialdir, mustexist=True
        )
        if selected:
            folder = Path(selected)
            paths = sorted(
                (path for path in folder.glob("*.csv") if path.is_file()),
                key=lambda path: path.name.casefold(),
            )
            if not paths:
                messagebox.showwarning(
                    "CSVがありません",
                    "選択したフォルダ直下にCSVファイルがありません。",
                    parent=self,
                )
                return
            self._load_paths(paths, folder)

    def _load_file(self, path: Path) -> None:
        self._load_paths([path], path)

    def _load_paths(self, paths: list[Path], display_path: Path) -> None:
        try:
            documents, scenarios = load_scenario_documents(paths)
            if not scenarios:
                raise ValueError("CSVに表示できるシナリオがありません")
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("CSV読み込みエラー", str(error), parent=self)
            return

        self.csv_path = paths[0]
        self.csv_documents = documents
        self.scenario_sources = {
            label: (path, scenario_id)
            for label, (path, scenario_id, _steps) in scenarios.items()
        }
        self.scenarios = {
            label: steps for label, (_path, _scenario_id, steps) in scenarios.items()
        }
        self.dirty_paths.clear()
        self.dirty = False
        self.current_scenario_label = None
        self.current_step_index = None
        self.save_button.config(state="normal")
        self._update_dirty_status()
        self.path_label.config(text=str(display_path))
        self.scenario_list.delete(0, tk.END)
        for label in scenarios:
            self.scenario_list.insert(tk.END, label)

        scenario_labels = list(scenarios)
        selected_scenario = self.initial_scenario
        self.initial_scenario = None
        if selected_scenario and selected_scenario not in scenarios:
            matching = [
                label
                for label, (_path, scenario_id) in self.scenario_sources.items()
                if scenario_id == selected_scenario
            ]
            if matching:
                selected_scenario = matching[0]
        if selected_scenario and selected_scenario not in scenarios:
            messagebox.showwarning(
                "シナリオが見つかりません",
                f"指定されたシナリオがCSVにありません: {selected_scenario}",
                parent=self,
            )
            selected_scenario = None
        selected_index = (
            scenario_labels.index(selected_scenario) if selected_scenario else 0
        )
        self.scenario_list.selection_set(selected_index)
        self.scenario_list.activate(selected_index)
        self._show_scenario(selected_index)

    def _on_scenario_selected(self, _event: tk.Event | None = None) -> None:
        selection = self.scenario_list.curselection()
        if selection:
            self._show_scenario(selection[0])

    def _show_scenario(self, scenario_index: int) -> None:
        self._commit_editor()
        scenario_label = self.scenario_list.get(scenario_index)
        steps = self.scenarios[scenario_label]
        for item in self.step_list.get_children():
            self.step_list.delete(item)
        for index, step in enumerate(steps):
            self.step_list.insert("", "end", iid=str(index), values=(step["step"],))
        if steps:
            self.step_list.selection_set("0")
            self.step_list.focus("0")
            self._show_step(0)

    def _on_step_selected(self, _event: tk.Event | None = None) -> None:
        selection = self.step_list.selection()
        if selection:
            self._show_step(int(selection[0]))

    def _show_step(self, step_index: int) -> None:
        scenario_index = self.scenario_list.curselection()[0]
        scenario_label = self.scenario_list.get(scenario_index)
        _path, scenario_id = self.scenario_sources[scenario_label]
        steps = self.scenarios[scenario_label]
        step = steps[step_index]
        self._commit_editor()
        csv_path = self.scenario_sources[scenario_label][0]
        document = self.csv_documents[csv_path]
        self.fieldnames = document.fieldnames
        self.csv_rows = document.rows
        self.delimiter = document.delimiter
        self.encoding = document.encoding

        for key, widget in self.field_widgets.items():
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", step.get(key, ""))
            else:
                widget.delete(0, tk.END)
                widget.insert(0, step.get(key, ""))
        self._update_completion_emoji_button()

        for _suffix, _reaction, _target, frame in self.branch_rows:
            frame.destroy()
        self.branch_rows.clear()
        suffixes = {
            key.removeprefix("branch_reaction_")
            for key in step
            if key.startswith("branch_reaction_")
            and (
                step.get(key)
                or step.get(f"branch_step_{key.removeprefix('branch_reaction_')}")
            )
        }
        for suffix in sorted(
            suffixes,
            key=lambda value: (
                not value.isdigit(),
                int(value) if value.isdigit() else value,
            ),
        ):
            self._add_branch(
                suffix,
                step.get(f"branch_reaction_{suffix}", ""),
                step.get(f"branch_step_{suffix}", ""),
            )

        self.detail_heading.config(
            text=f"{scenario_id}  —  Step {step['step']}  ({csv_path.name})"
        )
        self.current_scenario_label = scenario_label
        self.current_step_index = step_index
        self.editor_canvas.yview_moveto(0)
        self.position_label.config(text=f"{step_index + 1} / {len(steps)}")
        self.previous_button.config(state="normal" if step_index > 0 else "disabled")
        self.next_button.config(
            state="normal" if step_index < len(steps) - 1 else "disabled"
        )

    def _add_branch(
        self,
        suffix: str | None = None,
        reaction: str = "",
        target_step: str = "",
    ) -> None:
        if suffix is None:
            used = {
                row_suffix
                for row_suffix, _reaction, _target, _frame in self.branch_rows
            }
            used.update(
                key.removeprefix("branch_reaction_")
                for key in self.fieldnames
                if key.startswith("branch_reaction_")
            )
            number = 1
            while str(number) in used:
                number += 1
            suffix = str(number)

        frame = ttk.Frame(self.branch_frame)
        frame.grid(row=len(self.branch_rows), column=0, sticky="ew", pady=2)
        ttk.Label(frame, text="リアクション").pack(side="left")
        reaction_options = ["", *(option[0] for option in _EMOJI_OPTIONS)]
        if reaction and reaction not in reaction_options:
            reaction_options.append(reaction)
        reaction_entry = ttk.Combobox(
            frame, width=5, values=reaction_options, state="readonly"
        )
        reaction_entry.set(reaction)
        reaction_entry.pack(side="left", padx=(4, 10))
        ttk.Button(
            frame,
            text="絵文字を選択...",
            command=lambda current_entry=reaction_entry: self._choose_emoji(
                current_entry
            ),
        ).pack(side="left", padx=(0, 10))
        ttk.Label(frame, text="移動先 Step").pack(side="left")
        target_entry = ttk.Entry(frame, width=10)
        target_entry.insert(0, target_step)
        target_entry.pack(side="left", padx=4)
        ttk.Button(
            frame,
            text="削除",
            command=lambda current_frame=frame: self._remove_branch(current_frame),
        ).pack(side="right")
        reaction_entry.bind("<<ComboboxSelected>>", self._mark_dirty)
        target_entry.bind("<KeyRelease>", self._mark_dirty)
        self.branch_rows.append((suffix, reaction_entry, target_entry, frame))

    def _set_emoji_target(
        self, target: ttk.Entry | ttk.Combobox, value: str
    ) -> None:
        if isinstance(target, ttk.Combobox):
            target.set(value)
        else:
            target.delete(0, tk.END)
            target.insert(0, value)

    def _choose_emoji(self, target: ttk.Entry | ttk.Combobox) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("絵文字を選択")
        dialog.transient(self)
        dialog.geometry("440x460")
        dialog.minsize(360, 320)

        controls = ttk.Frame(dialog, padding=8)
        controls.pack(fill="x")
        query = tk.StringVar()
        search = ttk.Entry(controls, textvariable=query)
        search.pack(fill="x", pady=(0, 6))
        search.insert(0, "")
        category = tk.StringVar(value="すべて")
        category_select = ttk.Combobox(
            controls,
            textvariable=category,
            values=_EMOJI_CATEGORIES,
            state="readonly",
        )
        category_select.pack(fill="x")

        results_frame = ttk.Frame(dialog, padding=(8, 0, 8, 8))
        results_frame.pack(fill="both", expand=True)
        results = ttk.Treeview(
            results_frame, columns=("emoji", "category", "keywords"), show="headings"
        )
        results.heading("emoji", text="絵文字")
        results.heading("category", text="カテゴリ")
        results.heading("keywords", text="名前・検索語")
        results.column("emoji", width=55, anchor="center", stretch=False)
        results.column("category", width=100, stretch=False)
        results.column("keywords", width=220)
        scrollbar = ttk.Scrollbar(
            results_frame, orient="vertical", command=results.yview
        )
        results.configure(yscrollcommand=scrollbar.set)
        results.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def refresh(*_args: object) -> None:
            for item in results.get_children():
                results.delete(item)
            options = filter_emoji_options(query.get(), category.get())
            current = target.get()
            if (
                current
                and not query.get().strip()
                and category.get() == "すべて"
                and not any(option[0] == current for option in options)
            ):
                matching = (
                    (current, "現在の設定", "CSV内の絵文字"),
                )
                options = [*matching, *options]
            for index, (emoji, group, keywords) in enumerate(options):
                results.insert(
                    "", "end", iid=f"emoji-{index}", values=(emoji, group, keywords)
                )

        def select(_event: tk.Event | None = None) -> None:
            selected = results.selection()
            if not selected:
                return
            self._set_emoji_target(target, results.item(selected[0], "values")[0])
            self._mark_dirty()
            dialog.destroy()

        query.trace_add("write", refresh)
        category_select.bind("<<ComboboxSelected>>", refresh)
        results.bind("<Double-1>", select)
        results.bind("<Return>", select)

        actions = ttk.Frame(dialog, padding=(8, 0, 8, 8))
        actions.pack(fill="x")
        ttk.Button(actions, text="選択", command=select).pack(side="right")
        ttk.Button(
            actions,
            text="クリア",
            command=lambda: (
                self._set_emoji_target(target, ""),
                self._mark_dirty(),
                dialog.destroy(),
            ),
        ).pack(side="right", padx=6)
        ttk.Button(actions, text="キャンセル", command=dialog.destroy).pack(side="right")

        refresh()
        search.focus_set()

    def _remove_branch(self, frame: ttk.Frame) -> None:
        self.branch_rows = [row for row in self.branch_rows if row[3] is not frame]
        frame.destroy()
        for index, (_suffix, _reaction, _target, branch_frame) in enumerate(
            self.branch_rows
        ):
            branch_frame.grid_configure(row=index)
        self._mark_dirty()

    def _commit_editor(self) -> None:
        if self.current_scenario_label is None or self.current_step_index is None:
            return
        step = self.scenarios[self.current_scenario_label][self.current_step_index]
        updated = dict(step)
        for key, widget in self.field_widgets.items():
            value = (
                widget.get("1.0", "end-1c")
                if isinstance(widget, tk.Text)
                else widget.get()
            )
            updated[key] = value

        branch_suffixes = {
            key.removeprefix("branch_reaction_")
            for key in updated
            if key.startswith("branch_reaction_")
        }
        for suffix in branch_suffixes:
            updated[f"branch_reaction_{suffix}"] = ""
            updated[f"branch_step_{suffix}"] = ""
        for suffix, reaction, target, _frame in self.branch_rows:
            updated[f"branch_reaction_{suffix}"] = reaction.get().strip()
            updated[f"branch_step_{suffix}"] = target.get().strip()
            for key in (f"branch_reaction_{suffix}", f"branch_step_{suffix}"):
                if key not in self.fieldnames:
                    self.fieldnames.append(key)

        if updated != step:
            step.clear()
            step.update(updated)
            csv_path, _scenario_id = self.scenario_sources[self.current_scenario_label]
            document = self.csv_documents[csv_path]
            document.fieldnames = self.fieldnames
            self.dirty_paths.add(csv_path)
            self._mark_dirty()

    def save(self) -> bool:
        self._commit_editor()
        if not self.dirty:
            return True
        paths = sorted(self.dirty_paths, key=lambda path: str(path).casefold())
        path_list = "\n".join(str(path) for path in paths)
        if not messagebox.askyesno(
            "上書き確認",
            f"変更したCSVに上書き保存しますか？\n{path_list}",
            parent=self,
        ):
            return False
        try:
            for csv_path in paths:
                document = self.csv_documents[csv_path]
                save_scenario_csv(
                    document.path,
                    document.rows,
                    document.fieldnames,
                    document.delimiter,
                    document.encoding,
                )
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror("保存エラー", str(error), parent=self)
            return False
        self.dirty_paths.clear()
        self.dirty = False
        self._update_dirty_status()
        messagebox.showinfo("保存完了", "CSVに保存しました。", parent=self)
        return True

    def _move_step(self, offset: int) -> None:
        selection = self.step_list.selection()
        if not selection:
            return
        current_index = int(selection[0])
        target_index = current_index + offset
        if 0 <= target_index < len(self.step_list.get_children()):
            target = str(target_index)
            self.step_list.selection_set(target)
            self.step_list.focus(target)
            self.step_list.see(target)
            self._show_step(target_index)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="シナリオCSVをGUIで表示・編集します。CSVをexeへドラッグ＆ドロップして起動できます。"
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        nargs="?",
        help="表示するシナリオCSVファイル",
    )
    parser.add_argument(
        "--scenario",
        help="起動時に選択するシナリオID",
    )
    args = parser.parse_args()
    ScenarioEditor(args.csv_file, args.scenario).mainloop()


if __name__ == "__main__":
    main()
