"""Scheduled Discord reminder delivery."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import discord


LOGGER = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))
POLL_INTERVAL_SECONDS = 30
MAX_CSV_REMINDERS = 500
REMINDER_CSV_HEADERS = (
    "datetime",
    "channel_id",
    "content",
    "mention_users",
    "mention_roles",
)


def _parse_reminder_data(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("reminders"), list):
        raise ValueError("reminders.json must contain a 'reminders' array")

    reminders: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, reminder in enumerate(data["reminders"]):
        if not isinstance(reminder, dict):
            raise ValueError(f"Reminder at index {index} must be an object")

        reminder_id = reminder.get("id")
        if not isinstance(reminder_id, str) or not reminder_id.strip():
            raise ValueError(f"Reminder at index {index} must have a non-empty string id")
        if reminder_id in seen_ids:
            raise ValueError(f"Duplicate reminder id: {reminder_id}")
        seen_ids.add(reminder_id)

        scheduled_at = reminder.get("datetime")
        if not isinstance(scheduled_at, str):
            raise ValueError(f"Reminder {reminder_id} must have an ISO 8601 datetime")
        try:
            parsed_datetime = datetime.fromisoformat(scheduled_at)
        except ValueError as error:
            raise ValueError(
                f"Reminder {reminder_id} has an invalid datetime"
            ) from error
        if parsed_datetime.utcoffset() != timedelta(hours=9):
            raise ValueError(
                f"Reminder {reminder_id} datetime must use the JST +09:00 offset"
            )

        channel_id = _parse_snowflake(reminder.get("channel_id"), reminder_id, "channel_id")
        content = reminder.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Reminder {reminder_id} must have non-empty content")
        if len(content) > 1900:
            raise ValueError(f"Reminder {reminder_id} content must be 1900 characters or less")

        users = _parse_snowflakes(reminder.get("mention_users", []), reminder_id, "mention_users")
        roles = _parse_snowflakes(reminder.get("mention_roles", []), reminder_id, "mention_roles")
        message_length = (
            len(content)
            + sum(len(f"<@{user_id}> ") for user_id in users)
            + sum(len(f"<@&{role_id}> ") for role_id in roles)
        )
        if message_length > 2000:
            raise ValueError(f"Reminder {reminder_id} exceeds Discord's 2000 character limit")

        reminders.append(
            {
                "id": reminder_id,
                "datetime": parsed_datetime,
                "channel_id": channel_id,
                "content": content,
                "mention_users": users,
                "mention_roles": roles,
            }
        )
    return reminders


def _read_reminders(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as file:
        return _parse_reminder_data(json.load(file))


def _parse_snowflake(value: Any, reminder_id: str, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Reminder {reminder_id} {field} must be a positive numeric ID")
    try:
        snowflake = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Reminder {reminder_id} {field} must be a positive numeric ID"
        ) from error
    if snowflake <= 0 or str(value) != str(snowflake):
        raise ValueError(f"Reminder {reminder_id} {field} must be a positive numeric ID")
    return snowflake


def _parse_snowflakes(value: Any, reminder_id: str, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"Reminder {reminder_id} {field} must be an array")
    result = [_parse_snowflake(item, reminder_id, field) for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"Reminder {reminder_id} {field} must not contain duplicate IDs")
    return result


def _read_sent_reminders(log_path: Path) -> set[tuple[str, str]]:
    if not log_path.exists():
        return set()

    sent: set[tuple[str, str]] = set()
    with log_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Reminder log contains invalid JSON on line {line_number}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"Reminder log line {line_number} must be an object")
            if record.get("status") == "sent":
                reminder_id = record.get("id")
                scheduled_at = record.get("datetime")
                if not isinstance(reminder_id, str) or not isinstance(scheduled_at, str):
                    raise ValueError(
                        f"Reminder log line {line_number} has an invalid sent record"
                    )
                sent.add((reminder_id, scheduled_at))
    return sent


def _append_log(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        file.flush()


def _write_reminders(path: Path, reminders: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(
        json.dumps({"reminders": reminders}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def load_reminders_for_editor(path: Path) -> list[dict[str, Any]]:
    """Load editable reminders as JSON-compatible values."""
    return [_serialize_reminder(reminder) for reminder in _read_reminders(path)]


def save_reminders_from_editor(
    path: Path,
    reminders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and atomically save reminders edited by the desktop tool."""
    normalized = validate_reminders_for_editor(reminders)
    _write_reminders(path, normalized)
    return normalized


def validate_reminders_for_editor(
    reminders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and normalize a proposed reminder list without saving it."""
    parsed = _parse_reminder_data({"reminders": reminders})
    return [_serialize_reminder(reminder) for reminder in parsed]


def _validate_reminder_payloads(reminders: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for reminder in reminders:
        reminder_id = reminder.get("id")
        if not isinstance(reminder_id, str) or not reminder_id.strip():
            raise ValueError("Every reminder must have a non-empty string id")
        if reminder_id in seen_ids:
            raise ValueError(f"Duplicate reminder id: {reminder_id}")
        seen_ids.add(reminder_id)

        content = reminder.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Reminder {reminder_id} must have non-empty content")
        if len(content) > 1900:
            raise ValueError(f"Reminder {reminder_id} content must be 1900 characters or less")

        users = _parse_snowflakes(
            reminder.get("mention_users", []), reminder_id, "mention_users"
        )
        roles = _parse_snowflakes(
            reminder.get("mention_roles", []), reminder_id, "mention_roles"
        )
        message_length = (
            len(content)
            + sum(len(f"<@{user_id}> ") for user_id in users)
            + sum(len(f"<@&{role_id}> ") for role_id in roles)
        )
        if message_length > 2000:
            raise ValueError(f"Reminder {reminder_id} exceeds Discord's 2000 character limit")


def _serialize_reminder(reminder: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": reminder["id"],
        "datetime": reminder["datetime"].isoformat(),
        "channel_id": str(reminder["channel_id"]),
        "content": reminder["content"],
        "mention_users": [str(user_id) for user_id in reminder["mention_users"]],
        "mention_roles": [str(role_id) for role_id in reminder["mention_roles"]],
    }


def parse_reminder_datetime(value: str, now: datetime | None = None) -> datetime:
    """Parse a reminder time in JST, accepting ISO 8601 or YYYY-MM-DD HH:MM."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(
                "日時は YYYY-MM-DD HH:MM または +09:00 付きISO 8601で指定してください。"
            ) from error

    if parsed.utcoffset() != timedelta(hours=9):
        raise ValueError("日時は日本時間（+09:00）で指定してください。")
    if parsed <= (now or datetime.now(JST)):
        raise ValueError("リマインダーの日時は現在より後に指定してください。")
    return parsed


def add_reminder(
    reminders_path: Path,
    datetime_value: str,
    channel_id: int,
    content: str,
    mention_users: list[int] | None = None,
    mention_roles: list[int] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and persist a newly scheduled reminder."""
    parsed_datetime = parse_reminder_datetime(datetime_value, now=now)
    reminder = {
        "id": uuid.uuid4().hex,
        "datetime": parsed_datetime.isoformat(timespec="seconds"),
        "channel_id": str(channel_id),
        "content": content,
        "mention_users": [str(user_id) for user_id in (mention_users or [])],
        "mention_roles": [str(role_id) for role_id in (mention_roles or [])],
    }
    existing = _read_reminders(reminders_path)
    reminders = [_serialize_reminder(item) for item in existing]
    reminders.append(reminder)
    _validate_reminder_payloads(reminders)
    _write_reminders(reminders_path, reminders)
    return reminder


def parse_reminder_csv(
    csv_text: str,
    now: datetime | None = None,
    *,
    allow_names: bool = False,
) -> list[dict[str, Any]]:
    """Parse and validate all reminder rows without changing the config file."""
    try:
        reader = csv.DictReader(io.StringIO(csv_text, newline=""))
        headers = reader.fieldnames
        if headers is None:
            raise ValueError("CSVにヘッダー行がありません。")
        normalized_headers = [header.strip() for header in headers]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("CSVの列名が重複しています。")

        required_headers = {"datetime", "channel_id", "content"}
        missing_headers = required_headers - set(normalized_headers)
        if missing_headers:
            raise ValueError(
                "必須列がありません: " + ", ".join(sorted(missing_headers))
            )
        unexpected_headers = set(normalized_headers) - set(REMINDER_CSV_HEADERS)
        if unexpected_headers:
            raise ValueError(
                "未対応の列があります: " + ", ".join(sorted(unexpected_headers))
            )

        reminders: list[dict[str, Any]] = []
        current_time = now or datetime.now(JST)
        for line_number, row in enumerate(reader, start=2):
            if len(reminders) >= MAX_CSV_REMINDERS:
                raise ValueError(
                    f"CSVには一度に{MAX_CSV_REMINDERS}件まで登録できます。"
                )
            if None in row:
                raise ValueError(f"{line_number}行目の列数がヘッダーと一致しません。")
            values = {
                header.strip(): (value or "").strip()
                for header, value in row.items()
            }
            if not any(values.values()):
                continue
            missing_values = [
                field for field in required_headers if not values.get(field)
            ]
            if missing_values:
                raise ValueError(
                    f"{line_number}行目に必須値がありません: "
                    + ", ".join(sorted(missing_values))
                )

            try:
                parsed_datetime = parse_reminder_datetime(
                    values["datetime"], now=current_time
                )
                channel_id = _parse_snowflake(
                    values["channel_id"], f"CSV {line_number}行目", "channel_id"
                )
                user_values = _parse_csv_values(
                    values.get("mention_users", ""),
                    f"CSV {line_number}行目",
                    "mention_users",
                )
                role_values = _parse_csv_values(
                    values.get("mention_roles", ""),
                    f"CSV {line_number}行目",
                    "mention_roles",
                )
                if allow_names:
                    users: list[int | str] = user_values
                    roles: list[int | str] = role_values
                else:
                    users = _parse_snowflakes(
                        user_values, f"CSV {line_number}行目", "mention_users"
                    )
                    roles = _parse_snowflakes(
                        role_values, f"CSV {line_number}行目", "mention_roles"
                    )
            except ValueError as error:
                raise ValueError(f"{line_number}行目: {error}") from error

            reminder = {
                "id": uuid.uuid4().hex,
                "datetime": parsed_datetime.isoformat(timespec="seconds"),
                "channel_id": str(channel_id),
                "content": values["content"],
                "mention_users": [str(user_id) for user_id in users],
                "mention_roles": [str(role_id) for role_id in roles],
            }
            if allow_names:
                _validate_unresolved_mention_lengths(reminder)
            reminders.append(reminder)

        if not reminders:
            raise ValueError("登録できるリマインダー行がありません。")
        if not allow_names:
            _validate_reminder_payloads(reminders)
        return reminders
    except csv.Error as error:
        raise ValueError(f"CSVを読み込めませんでした: {error}") from error


def _parse_csv_values(value: str, reminder_id: str, field: str) -> list[str]:
    if not value:
        return []
    values = [item.strip() for item in value.split(";")]
    if any(not item for item in values):
        raise ValueError(f"{reminder_id} {field} contains an empty entry")
    if len(values) != len({item.casefold() for item in values}):
        raise ValueError(f"{reminder_id} {field} contains duplicate entries")
    return values


def _validate_unresolved_mention_lengths(reminder: dict[str, Any]) -> None:
    content = reminder["content"]
    if len(content) > 1900:
        raise ValueError(
            f"Reminder {reminder['id']} content must be 1900 characters or less"
        )
    mention_length = sum(
        len(f"<@{item}> ") for item in reminder["mention_users"]
    ) + sum(len(f"<@&{item}> ") for item in reminder["mention_roles"])
    if len(content) + mention_length > 2000:
        raise ValueError(f"Reminder {reminder['id']} exceeds Discord's 2000 character limit")


def register_reminders_csv(
    reminders_path: Path,
    csv_text: str,
    *,
    allowed_channel_ids: set[int] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Validate a complete CSV batch and append it atomically to the config."""
    new_reminders = parse_reminder_csv(csv_text, now=now)
    if allowed_channel_ids is not None:
        for reminder in new_reminders:
            if int(reminder["channel_id"]) not in allowed_channel_ids:
                raise ValueError(
                    f"通知先チャンネル {reminder['channel_id']} はこのサーバーにありません。"
                )

    existing = _read_reminders(reminders_path)
    all_reminders = [_serialize_reminder(item) for item in existing]
    all_reminders.extend(new_reminders)
    _validate_reminder_payloads(all_reminders)
    _write_reminders(reminders_path, all_reminders)
    return new_reminders


async def register_reminders_csv_for_guild(
    reminders_path: Path,
    csv_text: str,
    guild: discord.Guild,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Resolve CSV mention names against one guild, then append the validated batch."""
    new_reminders = parse_reminder_csv(csv_text, now=now, allow_names=True)
    members = [member async for member in guild.fetch_members(limit=None)]
    roles = list(guild.roles)
    allowed_channel_ids = {channel.id for channel in guild.text_channels}
    for reminder in new_reminders:
        if int(reminder["channel_id"]) not in allowed_channel_ids:
            raise ValueError(
                f"通知先チャンネル {reminder['channel_id']} はこのサーバーにありません。"
            )

    def resolve_user(value: str, row_number: int) -> int:
        try:
            user_id = _parse_snowflake(value, f"CSV {row_number}行目", "mention_users")
        except ValueError:
            matches = [
                member
                for member in members
                if value.casefold()
                in {member.display_name.casefold(), member.name.casefold()}
            ]
            unique_members = {member.id: member for member in matches}
            if not unique_members:
                raise ValueError(
                    f"CSV {row_number}行目: ユーザー名「{value}」が見つかりません。"
                )
            if len(unique_members) > 1:
                raise ValueError(
                    f"CSV {row_number}行目: ユーザー名「{value}」が複数一致しました。"
                )
            return next(iter(unique_members))
        if not any(member.id == user_id for member in members):
            raise ValueError(
                f"CSV {row_number}行目: ユーザーID「{value}」がこのサーバーにありません。"
            )
        return user_id

    def resolve_role(value: str, row_number: int) -> int:
        try:
            role_id = _parse_snowflake(value, f"CSV {row_number}行目", "mention_roles")
        except ValueError:
            matches = [role for role in roles if role.name.casefold() == value.casefold()]
            if not matches:
                raise ValueError(
                    f"CSV {row_number}行目: ロール名「{value}」が見つかりません。"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"CSV {row_number}行目: ロール名「{value}」が複数一致しました。"
                )
            return matches[0].id
        if not any(role.id == role_id for role in roles):
            raise ValueError(
                f"CSV {row_number}行目: ロールID「{value}」がこのサーバーにありません。"
            )
        return role_id

    for row_number, reminder in enumerate(new_reminders, start=2):
        try:
            reminder["mention_users"] = [
                str(resolve_user(user, row_number))
                for user in reminder["mention_users"]
            ]
            reminder["mention_roles"] = [
                str(resolve_role(role, row_number))
                for role in reminder["mention_roles"]
            ]
        except ValueError as error:
            raise ValueError(str(error)) from error

    _validate_reminder_payloads(new_reminders)
    existing = _read_reminders(reminders_path)
    all_reminders = [_serialize_reminder(reminder) for reminder in existing]
    all_reminders.extend(new_reminders)
    _validate_reminder_payloads(all_reminders)
    _write_reminders(reminders_path, all_reminders)
    return new_reminders


def create_reminder_csv_template() -> bytes:
    """Create an empty UTF-8 CSV template for reminder registration."""
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\r\n").writerow(REMINDER_CSV_HEADERS)
    return output.getvalue().encode("utf-8-sig")


def delete_reminder(reminders_path: Path, reminder_id: str) -> dict[str, Any] | None:
    """Remove a pending reminder by ID and return the removed record."""
    existing = _read_reminders(reminders_path)
    removed = next((item for item in existing if item["id"] == reminder_id), None)
    if removed is None:
        return None

    with reminders_path.open(encoding="utf-8-sig") as file:
        data = json.load(file)
    data["reminders"] = [
        reminder
        for reminder in data["reminders"]
        if reminder.get("id") != reminder_id
    ]
    _write_reminders(reminders_path, data["reminders"])
    return removed


def _remove_reminder(path: Path, reminder_id: str, scheduled_at: str) -> None:
    with path.open(encoding="utf-8-sig") as file:
        data = json.load(file)
    current_reminders = data["reminders"]
    data["reminders"] = [
        reminder
        for reminder in current_reminders
        if not (
            reminder.get("id") == reminder_id
            and reminder.get("datetime") == scheduled_at
        )
    ]
    _write_reminders(path, data["reminders"])


async def process_due_reminders(
    client: discord.Client,
    reminders_path: Path,
    log_path: Path,
    now: datetime | None = None,
) -> None:
    current_time = now or datetime.now(timezone.utc)
    sent_reminders = _read_sent_reminders(log_path)
    reminders = _read_reminders(reminders_path)

    for reminder in reminders:
        scheduled_at = reminder["datetime"]
        scheduled_key = (reminder["id"], scheduled_at.isoformat())
        if scheduled_key in sent_reminders:
            _remove_reminder(reminders_path, reminder["id"], scheduled_at.isoformat())
            continue
        if scheduled_at.astimezone(timezone.utc) > current_time.astimezone(timezone.utc):
            continue

        try:
            channel = client.get_channel(reminder["channel_id"])
            if channel is None:
                channel = await client.fetch_channel(reminder["channel_id"])
            if not isinstance(channel, discord.abc.Messageable):
                raise ValueError(
                    f"Channel {reminder['channel_id']} does not support messages"
                )

            mention_text = " ".join(
                [f"<@{user_id}>" for user_id in reminder["mention_users"]]
                + [f"<@&{role_id}>" for role_id in reminder["mention_roles"]]
            )
            message = f"{mention_text}\n{reminder['content']}" if mention_text else reminder["content"]
            allowed_mentions = discord.AllowedMentions(
                everyone=False,
                users=[discord.Object(id=user_id) for user_id in reminder["mention_users"]],
                roles=[discord.Object(id=role_id) for role_id in reminder["mention_roles"]],
                replied_user=False,
            )
            await channel.send(message, allowed_mentions=allowed_mentions)
        except (discord.DiscordException, ValueError) as error:
            LOGGER.exception("Failed to send reminder %s", reminder["id"])
            _append_log(
                log_path,
                {
                    "id": reminder["id"],
                    "datetime": scheduled_at.isoformat(),
                    "attempted_at": current_time.isoformat(),
                    "channel_id": reminder["channel_id"],
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                },
            )
            continue

        _append_log(
            log_path,
            {
                "id": reminder["id"],
                "datetime": scheduled_at.isoformat(),
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "channel_id": reminder["channel_id"],
                "status": "sent",
            },
        )
        _remove_reminder(reminders_path, reminder["id"], scheduled_at.isoformat())


async def run_reminder_scheduler(
    client: discord.Client,
    reminders_path: Path,
    log_path: Path,
) -> None:
    while not client.is_closed():
        try:
            await process_due_reminders(client, reminders_path, log_path)
        except (OSError, ValueError, discord.DiscordException):
            LOGGER.exception("Reminder scheduler cycle failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
