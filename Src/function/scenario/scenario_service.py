from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import discord

from function.file.path_service import application_root

_SRC_ROOT = application_root()


"""
    台本の登録とサーバーごとの進行状態を管理する共通処理。

    register_scenario_csv:
        CSV形式の台本を定義JSONへ登録する。

    export_scenario_csv:
        シナリオ定義JSONをCSV形式へ変換する。

    list_scenarios:
        登録済み台本のIDとステップ数を取得する。

    delete_scenario:
        指定した台本と、その台本を進行中の状態を削除する。

    start_scenario:
        サーバーの台本進行を開始し、最初のステップを返す。

    set_scenario_message_id:
        現在の台本指示メッセージIDを保存する。

    advance_scenario:
        現在の指示が完了したかを確認し、完了していれば次のステップへ進める。
"""

_DEFAULT_DEFINITIONS_PATH = _SRC_ROOT / "config" / "scenario_definitions.json"
_DEFAULT_STATES_PATH = _SRC_ROOT / "config" / "scenario_states.json"
_REQUIRED_COLUMNS = {
    "scenario_id",
    "step",
    "instruction",
    "completion_type",
    "completion_value",
    "response",
}
_SCENARIO_COLUMNS = [
    "scenario_id",
    "step",
    "instruction",
    "completion_type",
    "completion_value",
    "response",
]


def _read_json(path: Path, default: Any) -> Any:
    """JSONファイルを読み込み、存在しない場合は初期値を返す。"""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    """JSONを一時ファイルへ書き込み、保存先へ置き換える。"""
    target_path = path.resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target_path.parent,
        delete=False,
    ) as temporary_file:
        json.dump(data, temporary_file, ensure_ascii=False, indent=2)
        temporary_path = Path(temporary_file.name)

    try:
        for attempt in range(5):
            try:
                os.replace(temporary_path, target_path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
    finally:
        temporary_path.unlink(missing_ok=True)


def register_scenario_csv(
    csv_text: str,
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
) -> int:
    """既存のシナリオを保持し、CSVに記載されたstepを更新する。"""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = set(reader.fieldnames or [])
    if not _REQUIRED_COLUMNS.issubset(fieldnames):
        missing_columns = _REQUIRED_COLUMNS - fieldnames
        raise ValueError(
            "CSVに必要な列がありません: " + ", ".join(sorted(missing_columns))
        )

    scenarios = _read_json(Path(definitions_path), {})
    updates: dict[str, dict[int, dict[str, Any]]] = {}
    for row in reader:
        scenario_id = (row.get("scenario_id") or "").strip()
        if not scenario_id:
            raise ValueError("scenario_idを指定してください。")
        try:
            step = int((row.get("step") or "").strip())
        except ValueError as error:
            raise ValueError("stepは整数で指定してください。") from error
        if step < 1:
            raise ValueError("stepは1以上で指定してください。")

        branch_map = _parse_branch_columns(row, scenario_id)
        update = updates.setdefault(scenario_id, {}).setdefault(
            step,
            {"base": None, "branch_map": {}},
        )
        if any(
            (row.get(column) or "").strip()
            for column in ("instruction", "completion_type", "completion_value", "response")
        ):
            update["base"] = {
                "step": step,
                "instruction": (row.get("instruction") or "").strip(),
                "completion_type": (row.get("completion_type") or "keyword").strip().lower(),
                "completion_value": (row.get("completion_value") or "").strip(),
                "response": (row.get("response") or "").strip(),
            }
        update["branch_map"].update(branch_map)

    registered_count = 0
    for scenario_id, step_updates in updates.items():
        scenario_steps = scenarios.setdefault(scenario_id, [])
        steps_by_number = {
            current_step["step"]: current_step for current_step in scenario_steps
        }
        for step, update in step_updates.items():
            existing_step = steps_by_number.get(step)
            if update["base"] is not None:
                existing_step = update["base"]
                existing_step["branch_map"] = update["branch_map"]
                steps_by_number[step] = existing_step
            elif existing_step is None:
                raise ValueError(
                    f"step {step}を更新する基本行がありません: {scenario_id}"
                )
            else:
                existing_step.setdefault("branch_map", {}).update(update["branch_map"])
            registered_count += 1
        scenario_steps[:] = sorted(steps_by_number.values(), key=lambda item: item["step"])

    _write_json(Path(definitions_path), scenarios)
    return registered_count


def _parse_branch_columns(
    row: dict[str, str | None],
    scenario_id: str,
) -> dict[str, dict[str, Any]]:
    """番号付き分岐列を1行から必要な数だけ読み込む。"""
    branch_map: dict[str, dict[str, Any]] = {}
    indexes = sorted(
        {
            key.rsplit("_", 1)[1]
            for key in row
            if isinstance(key, str)
            and key.startswith("branch_")
            and key.rsplit("_", 1)[-1].isdigit()
        },
        key=int,
    )
    for index in indexes:
        suffix = f"_{index}"
        reaction = (row.get(f"branch_reaction{suffix}") or "").strip()
        step_text = (row.get(f"branch_step{suffix}") or "").strip()
        if not reaction and not step_text:
            continue
        if not reaction:
            raise ValueError(f"branch_reaction{suffix}を指定してください。")
        branch: dict[str, Any] = {"scenario_id": scenario_id}
        if step_text:
            try:
                branch["step"] = int(step_text)
            except ValueError as error:
                raise ValueError(f"branch_step{suffix}は整数で指定してください。") from error
        branch_map[reaction] = branch

    if branch_map:
        return branch_map

    reaction = (row.get("branch_reaction") or "").strip()
    step_text = (row.get("branch_step") or "").strip()
    if reaction or step_text:
        if not reaction:
            raise ValueError("branch_reactionを指定してください。")
        branch: dict[str, Any] = {"scenario_id": scenario_id}
        if step_text:
            try:
                branch["step"] = int(step_text)
            except ValueError as error:
                raise ValueError("branch_stepは整数で指定してください。") from error
        return {reaction: branch}
    return {}


def list_scenarios(
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
) -> list[dict[str, int | str]]:
    """登録済み台本のIDとステップ数を一覧で返す。"""
    scenarios = _read_json(Path(definitions_path), {})
    return [
        {"scenario_id": scenario_id, "step_count": len(steps)}
        for scenario_id, steps in sorted(scenarios.items())
    ]


def export_scenario_csv(
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
) -> io.BytesIO:
    """シナリオ定義JSONをテンプレート形式のCSVへ変換する。"""
    scenarios = _read_json(Path(definitions_path), {})
    max_branch_count = max(
        2,
        max(
            (
                len(step.get("branch_map", {}))
                for steps in scenarios.values()
                for step in steps
            ),
            default=0,
        ),
    )
    fieldnames = list(_SCENARIO_COLUMNS)
    for index in range(1, max_branch_count + 1):
        fieldnames.extend(
            [
                f"branch_reaction_{index}",
                f"branch_step_{index}",
            ]
        )

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for scenario_id, steps in sorted(scenarios.items()):
        for step in sorted(steps, key=lambda item: item["step"]):
            row = {
                "scenario_id": scenario_id,
                "step": step["step"],
                "instruction": step.get("instruction", ""),
                "completion_type": step.get("completion_type", "keyword"),
                "completion_value": step.get("completion_value", ""),
                "response": step.get("response", ""),
            }
            for index, (reaction, branch) in enumerate(
                sorted(
                    (
                        (reaction, branch)
                        for reaction, branch in step.get("branch_map", {}).items()
                        if branch.get("scenario_id") == scenario_id
                    ),
                ),
                start=1,
            ):
                row[f"branch_reaction_{index}"] = reaction
                row[f"branch_step_{index}"] = branch.get("step", "")
            writer.writerow(row)

    return io.BytesIO(output.getvalue().encode("utf-8-sig"))


def delete_scenario(
    scenario_id: str,
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> int:
    """指定した台本を定義JSONと進行状態から削除する。"""
    scenario_id = scenario_id.strip()
    if not scenario_id:
        raise ValueError("削除する台本IDを指定してください。")

    definitions_file = Path(definitions_path)
    scenarios = _read_json(definitions_file, {})
    if scenario_id not in scenarios:
        raise ValueError(f"台本が見つかりません: {scenario_id}")

    del scenarios[scenario_id]
    _write_json(definitions_file, scenarios)

    states_file = Path(states_path)
    states = _read_json(states_file, {})
    active_guild_ids = [
        guild_id
        for guild_id, state in states.items()
        if state.get("scenario_id") == scenario_id
    ]
    for guild_id in active_guild_ids:
        del states[guild_id]
    if active_guild_ids:
        _write_json(states_file, states)

    return len(active_guild_ids)


def start_scenario(
    guild_id: int,
    scenario_id: str,
    start_step: int | None = None,
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> dict[str, Any]:
    """指定サーバーの台本進行を開始し、指定ステップを返す。"""
    scenarios = _read_json(Path(definitions_path), {})
    steps = scenarios.get(scenario_id)
    if not steps:
        raise ValueError(f"台本が見つかりません: {scenario_id}")

    selected_step = steps[0]
    if start_step is not None:
        selected_step = next(
            (step for step in steps if step["step"] == start_step),
            None,
        )
        if selected_step is None:
            raise ValueError(
                f"台本「{scenario_id}」にstep {start_step}はありません。"
            )

    states = _read_json(Path(states_path), {})
    states[str(guild_id)] = {
        "scenario_id": scenario_id,
        "step": selected_step["step"],
        "message_id": None,
        "channel_id": None,
    }
    _write_json(Path(states_path), states)
    return selected_step


def get_scenario_reaction_examples(step: dict[str, Any]) -> list[str]:
    """台本指示メッセージに付ける見本リアクションを返す。"""
    if step.get("completion_type") != "reaction":
        return []

    completion_value = step.get("completion_value", "")
    if completion_value not in {"", "*"}:
        return [completion_value]

    return [
        reaction
        for reaction in step.get("branch_map", {})
        if reaction != "*"
    ]


def resolve_scenario_mentions(text: str, guild: discord.Guild) -> str:
    """シナリオ内の@ユーザー名・@ロール名をDiscordメンションへ変換する。"""
    if "@" not in text:
        return text

    resolved_text = text
    roles = sorted(guild.roles, key=lambda role: len(role.name), reverse=True)
    members = sorted(guild.members, key=lambda member: len(member.display_name), reverse=True)

    for role in roles:
        if role.is_default() or not role.name:
            continue
        resolved_text = re.sub(
            rf"@{re.escape(role.name)}(?=$|\s|[、。,.!?！？])",
            f"<@&{role.id}>",
            resolved_text,
        )

    for member in members:
        names = [member.display_name, member.name]
        for name in sorted(set(names), key=len, reverse=True):
            if not name:
                continue
            resolved_text = re.sub(
                rf"@{re.escape(name)}(?=$|\s|[、。,.!?！？])",
                f"<@{member.id}>",
                resolved_text,
            )

    return resolved_text


def set_scenario_message_id(
    guild_id: int,
    message_id: int,
    channel_id: int | None = None,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> None:
    """現在の台本指示メッセージIDを保存する。"""
    states = _read_json(Path(states_path), {})
    state = states.get(str(guild_id))
    if state is None:
        raise ValueError("開始中の台本がありません。")
    state["message_id"] = message_id
    if channel_id is not None:
        state["channel_id"] = channel_id
    _write_json(Path(states_path), states)


def get_scenario_wait_type(
    guild_id: int,
    channel_id: int,
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> str | None:
    """指定チャンネルで待機中の台本条件を返す。"""
    states = _read_json(Path(states_path), {})
    state = states.get(str(guild_id))
    if state is None or state.get("channel_id") != channel_id:
        return None

    scenarios = _read_json(Path(definitions_path), {})
    steps = scenarios.get(state.get("scenario_id"), [])
    current_step = next(
        (step for step in steps if step.get("step") == state.get("step")),
        None,
    )
    return current_step.get("completion_type") if current_step else None


def has_active_scenario(
    guild_id: int,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> bool:
    """指定サーバーで台本が進行中か確認する。"""
    states = _read_json(Path(states_path), {})
    state = states.get(str(guild_id))
    return state is not None and state.get("channel_id") is not None


def advance_scenario(
    guild_id: int,
    completion_value: str,
    message_id: int | None = None,
    definitions_path: str | Path = _DEFAULT_DEFINITIONS_PATH,
    states_path: str | Path = _DEFAULT_STATES_PATH,
) -> dict[str, Any] | None:
    """現在ステップの完了を確認し、完了時は次のステップを返す。"""
    states = _read_json(Path(states_path), {})
    state = states.get(str(guild_id))
    if state is None:
        return None

    scenarios = _read_json(Path(definitions_path), {})
    steps = scenarios.get(state["scenario_id"], [])
    current_index = next(
        (index for index, step in enumerate(steps) if step["step"] == state["step"]),
        None,
    )
    if current_index is None:
        raise ValueError("現在の台本ステップが見つかりません。")

    current_step = steps[current_index]
    completion_type = current_step["completion_type"]
    if completion_type == "reaction" and state.get("message_id") != message_id:
        return None
    if completion_type != "reaction" and message_id is not None:
        return None
    expected_completion = current_step["completion_value"]
    if (
        completion_type == "reaction"
        and expected_completion not in {"", "*"}
        and completion_value.strip() != expected_completion
    ):
        return None
    if completion_type != "reaction" and completion_value.strip() != expected_completion:
        return None

    response = current_step["response"]
    branch_map = current_step.get("branch_map", {})
    branch = branch_map.get(completion_value)
    if branch is None and completion_type == "reaction":
        branch = branch_map.get("*")
    if branch is not None:
        next_scenario_id = branch["scenario_id"]
        next_steps = scenarios.get(next_scenario_id, [])
        next_step_number = branch.get("step", next_steps[0]["step"] if next_steps else None)
        next_index = next(
            (
                index
                for index, step in enumerate(next_steps)
                if step["step"] == next_step_number
            ),
            None,
        )
        if next_index is None:
            raise ValueError("分岐先の台本ステップが見つかりません。")
        state["scenario_id"] = next_scenario_id
        state["step"] = next_steps[next_index]["step"]
        _write_json(Path(states_path), states)
        next_step = next_steps[next_index]
        return {
            "response": response,
            "instruction": next_step["instruction"],
            "reaction_examples": get_scenario_reaction_examples(next_step),
            "completed": False,
        }

    next_index = current_index + 1
    if next_index >= len(steps):
        del states[str(guild_id)]
        _write_json(Path(states_path), states)
        return {"response": response, "instruction": None, "completed": True}

    next_step = steps[next_index]
    state["step"] = next_step["step"]
    _write_json(Path(states_path), states)
    return {
        "response": response,
        "instruction": next_step["instruction"],
        "reaction_examples": get_scenario_reaction_examples(next_step),
        "completed": False,
    }
