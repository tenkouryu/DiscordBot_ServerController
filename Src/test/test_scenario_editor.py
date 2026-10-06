from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

from Src.tools.scenario_editor.scenario_editor import (
    _read_scenario_csv,
    filter_emoji_options,
    load_scenarios,
    load_scenario_documents,
    save_scenario_csv,
)


class ScenarioEditorTests(unittest.TestCase):
    def test_load_scenarios_groups_and_sorts_steps(self) -> None:
        rows = [
            ["alpha", "2", "second", "reaction", "✅", "done", "✅", "1"],
            ["beta", "1", "other scenario", "message", "", "", "", ""],
            ["alpha", "1", "first", "reaction", "✅", "start", "", ""],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenarios.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "scenario_id",
                        "step",
                        "instruction",
                        "completion_type",
                        "completion_value",
                        "response",
                        "branch_reaction_1",
                        "branch_step_1",
                    ]
                )
                writer.writerows(rows)

            scenarios = load_scenarios(path)

        self.assertEqual(list(scenarios), ["alpha", "beta"])
        self.assertEqual([step["step"] for step in scenarios["alpha"]], ["1", "2"])
        self.assertEqual(scenarios["alpha"][1]["branch_step_1"], "1")

    def test_load_scenarios_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text("scenario_id,step\nalpha,1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "必要な列がありません"):
                load_scenarios(path)

    def test_save_preserves_delimiter_encoding_columns_and_row_order(self) -> None:
        headers = [
            "scenario_id",
            "step",
            "instruction",
            "completion_type",
            "completion_value",
            "response",
            "branch_reaction_1",
            "branch_step_1",
            "note",
        ]
        rows = [
            ["alpha", "2", "二番目", "reaction", "確認", "完了", "OK", "1", "保持"],
            ["beta", "1", "別シナリオ", "message", "", "", "", "", "追加列"],
            ["alpha", "1", "一番目", "reaction", "確認", "開始", "", "", "順序"],
        ]
        source = io.StringIO(newline="")
        writer = csv.writer(source, delimiter=";", lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(rows)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenarios.csv"
            path.write_bytes(source.getvalue().encode("cp932"))
            _scenarios, loaded_rows, fieldnames, delimiter, encoding = (
                _read_scenario_csv(path)
            )
            loaded_rows[0]["instruction"] = "編集した指示"
            fieldnames.extend(["branch_reaction_2", "branch_step_2"])
            loaded_rows[0]["branch_reaction_2"] = "NG"
            loaded_rows[0]["branch_step_2"] = "3"

            save_scenario_csv(path, loaded_rows, fieldnames, delimiter, encoding)
            saved_text = path.read_bytes().decode("cp932")
            scenarios, reloaded_rows, *_ = _read_scenario_csv(path)

        self.assertEqual(delimiter, ";")
        self.assertEqual(encoding, "cp932")
        self.assertIn("scenario_id;step;", saved_text)
        self.assertEqual(
            [row["scenario_id"] for row in reloaded_rows],
            ["alpha", "beta", "alpha"],
        )
        self.assertEqual(scenarios["alpha"][1]["instruction"], "編集した指示")
        self.assertEqual(scenarios["alpha"][1]["note"], "保持")
        self.assertEqual(scenarios["alpha"][1]["branch_step_2"], "3")

    def test_emoji_options_filter_by_japanese_keyword_and_category(self) -> None:
        results = filter_emoji_options("拍手")
        self.assertTrue(results)
        self.assertEqual(results[0][0], "👏")
        self.assertTrue(
            all(option[1] == "手・人" for option in filter_emoji_options("", "手・人"))
        )
        self.assertEqual(filter_emoji_options("does-not-exist"), [])

    def test_load_scenario_documents_keeps_source_for_duplicate_ids(self) -> None:
        headers = [
            "scenario_id",
            "step",
            "instruction",
            "completion_type",
            "completion_value",
            "response",
        ]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = folder / "first.csv"
            second = folder / "second.csv"
            for path, instruction in ((first, "first file"), (second, "second file")):
                with path.open("w", encoding="utf-8-sig", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow(headers)
                    writer.writerow(["shared", "1", instruction, "keyword", "", ""])

            documents, scenarios = load_scenario_documents([second, first])

        self.assertEqual(set(documents), {first, second})
        self.assertEqual(list(scenarios), ["shared — first.csv", "shared — second.csv"])
        self.assertEqual(scenarios["shared — first.csv"][0], first)
        self.assertEqual(scenarios["shared — first.csv"][2][0]["instruction"], "first file")
        self.assertEqual(scenarios["shared — second.csv"][0], second)
        self.assertEqual(
            scenarios["shared — second.csv"][2][0]["instruction"], "second file"
        )


if __name__ == "__main__":
    unittest.main()
