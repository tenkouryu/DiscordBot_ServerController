from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import discord
from function.file.template_output_service import save_template_output, send_template_output

from function.file.zip_service import compress_directory

"""
    チャンネルの添付ファイル取得コマンドを処理する。

    _safe_path_component / _unique_file_path:
        保存先パスや重複ファイル名を安全に扱う。

    _parse_start_date / _normalize_extensions:
        開始日と拡張子フィルターを解析する。

    _get_csv_columns / _get_optional_csv_columns:
        添付CSVの必須列と任意列を取得する。

    _find_text_channel:
        カテゴリー内のテキストチャンネルを検索する。

    archive_channels_from_csv:
        CSVで指定された複数チャンネルの添付ファイルを保存する。

    archive_channel_attachments:
        指定チャンネルの添付ファイルを保存する。

    main:
        添付ファイルをZIPにまとめて送信する。
"""

_CSV_COLUMNS = {
    "category_name": {"category_name", "category", "カテゴリ名"},
    "channel_name": {"channel_name", "channel", "チャンネル名"},
    "start_date": {"start_date", "date", "開始日"},
}
_OPTIONAL_CSV_COLUMNS = {
    "extension": {"extension", "file_extension", "拡張子"},
}


def _safe_path_component(value: str, fallback: str) -> str:
    """ファイルシステムで安全に使えるパス要素へ変換する。"""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return sanitized or fallback


def _unique_file_path(directory: Path, filename: str) -> Path:
    """同名ファイルを上書きしない保存先を返す。"""
    candidate = directory / _safe_path_component(filename, "attachment")
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _parse_start_date(value: str) -> datetime:
    """CSVの開始日をUTCの00:00として解析する。"""
    try:
        parsed_date = date.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError("開始日は YYYY-MM-DD 形式で指定してください。") from error

    return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)


def _normalize_extensions(value: str | None) -> frozenset[str] | None:
    """添付ファイル検索用の拡張子を正規化する。"""
    if value is None or not value.strip():
        return None

    extensions = set()
    for extension in value.split("|"):
        extension = extension.strip().lower()
        if not extension.startswith("."):
            extension = f".{extension}"
        if extension == "." or "/" in extension or "\\" in extension:
            raise ValueError(
                "拡張子を指定してください（例: png|jpg または .png|.jpg）。"
            )
        extensions.add(extension)
    return frozenset(extensions)


def _get_csv_columns(fieldnames: list[str] | None) -> dict[str, str]:
    normalized_fieldnames = {
        fieldname.strip(): fieldname
        for fieldname in (fieldnames or [])
        if fieldname
    }
    columns: dict[str, str] = {}
    for column_name, aliases in _CSV_COLUMNS.items():
        matched_column = next(
            (
                normalized_fieldname
                for alias, normalized_fieldname in normalized_fieldnames.items()
                if alias in aliases
            ),
            None,
        )
        if matched_column is None:
            raise ValueError(
                "CSVには category_name、channel_name、start_date 列が必要です。"
            )
        columns[column_name] = matched_column
    return columns


def _get_optional_csv_columns(fieldnames: list[str] | None) -> dict[str, str]:
    normalized_fieldnames = {
        fieldname.strip(): fieldname
        for fieldname in (fieldnames or [])
        if fieldname
    }
    columns: dict[str, str] = {}
    for column_name, aliases in _OPTIONAL_CSV_COLUMNS.items():
        matched_column = next(
            (
                normalized_fieldname
                for alias, normalized_fieldname in normalized_fieldnames.items()
                if alias in aliases
            ),
            None,
        )
        if matched_column is not None:
            columns[column_name] = matched_column
    return columns


def _find_text_channel(
    guild: discord.Guild,
    category_name: str,
    channel_name: str,
) -> discord.TextChannel:
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        raise ValueError(f"カテゴリーが見つかりません: {category_name}")

    channel = discord.utils.find(
        lambda candidate: (
            isinstance(candidate, discord.TextChannel)
            and candidate.name == channel_name
            and candidate.category_id == category.id
        ),
        guild.text_channels,
    )
    if channel is None:
        raise ValueError(
            f"チャンネルが見つかりません: {category_name}/{channel_name}"
        )
    return channel


async def archive_channels_from_csv(
    guild: discord.Guild,
    csv_text: str,
    destination: str | Path,
) -> tuple[int, list[str]]:
    """CSVで指定された複数チャンネルの添付ファイルを集約する。"""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    reader = csv.DictReader(io.StringIO(csv_text))
    columns = _get_csv_columns(reader.fieldnames)
    optional_columns = _get_optional_csv_columns(reader.fieldnames)
    downloaded_count = 0
    errors: list[str] = []

    for row_number, row in enumerate(reader, start=2):
        category_name = (row.get(columns["category_name"]) or "").strip()
        channel_name = (row.get(columns["channel_name"]) or "").strip()
        start_date_value = (row.get(columns["start_date"]) or "").strip()
        try:
            if not category_name or not channel_name:
                raise ValueError(
                    "カテゴリ名とチャンネル名を指定してください。"
                )
            channel = _find_text_channel(guild, category_name, channel_name)
            start_date = (
                _parse_start_date(start_date_value)
                if start_date_value
                else None
            )
            extension = (
                row.get(optional_columns["extension"])
                if "extension" in optional_columns
                else None
            )
            count, channel_errors = await archive_channel_attachments(
                channel,
                destination,
                start_date,
                extension,
            )
            downloaded_count += count
            errors.extend(
                f"{row_number}行目（{category_name}/{channel_name}）: {error}"
                for error in channel_errors
            )
        except (ValueError, discord.Forbidden, discord.HTTPException) as error:
            errors.append(
                f"{row_number}行目（{category_name}/{channel_name}）: {error}"
            )

    return downloaded_count, errors


async def archive_channel_attachments(
    channel: discord.TextChannel,
    destination: str | Path,
    start_date: datetime | None = None,
    extensions: str | None = None,
) -> tuple[int, list[str]]:
    """テキストチャンネルの添付ファイルを指定構成で保存する。"""
    if not isinstance(channel, discord.TextChannel):
        raise ValueError("テキストチャンネルを指定してください。")

    normalized_extensions = _normalize_extensions(extensions)

    category_name = _safe_path_component(
        channel.category.name if channel.category else "カテゴリーなし",
        "カテゴリーなし",
    )
    channel_name = _safe_path_component(channel.name, "チャンネル")
    channel_directory = Path(destination) / category_name / channel_name
    channel_directory.mkdir(parents=True, exist_ok=True)

    downloaded_count = 0
    errors: list[str] = []
    async for message in channel.history(
        limit=None,
        after=start_date,
        oldest_first=True,
    ):
        for attachment in message.attachments:
            if (
                normalized_extensions is not None
                and Path(attachment.filename).suffix.lower()
                not in normalized_extensions
            ):
                continue
            file_path = _unique_file_path(channel_directory, attachment.filename)
            try:
                file_path.write_bytes(await attachment.read())
                downloaded_count += 1
            except (discord.Forbidden, discord.HTTPException, OSError) as error:
                errors.append(f"{attachment.filename}: {error}")

    return downloaded_count, errors


async def main(message: discord.Message) -> None:
    """単一またはCSVで指定されたチャンネルの添付ファイルをZIPで送信する。"""
    arguments = message.content.partition(" ")[2].strip()
    if arguments == "-h":
        await message.channel.send(
            "/chat get #テキストチャンネル [開始日 YYYY-MM-DD] [拡張子]\n"
            "または /chat get + CSVファイル\n"
            "単一チャンネルまたはCSVで指定した複数チャンネルの"
            "添付ファイルをZIPにまとめます。拡張子は png|jpg または"
            " .png|.jpg のように指定できます。\n"
            "CSV形式: category_name,channel_name,start_date,extension"
        )
        return

    if not message.author.guild_permissions.manage_messages:
        await message.channel.send("メッセージを管理する権限がありません。")
        return

    csv_attachment = next(
        (
            attachment
            for attachment in message.attachments
            if attachment.filename.lower().endswith(".csv")
        ),
        None,
    )
    if csv_attachment is None and not message.channel_mentions:
        await message.channel.send(
            "取得対象のテキストチャンネルをメンションするか、"
            "CSVファイルを添付してください。"
        )
        return

    with TemporaryDirectory() as temporary_directory:
        output_directory = Path(temporary_directory) / "attachments"
        archive_path = Path(temporary_directory) / "chat_attachments.zip"
        try:
            if csv_attachment is not None:
                csv_text = (await csv_attachment.read()).decode("utf-8-sig")
                downloaded_count, errors = await archive_channels_from_csv(
                    message.guild,
                    csv_text,
                    output_directory,
                )
            else:
                target_channel = message.channel_mentions[0]
                if not isinstance(target_channel, discord.TextChannel):
                    await message.channel.send(
                        "取得対象にはテキストチャンネルを指定してください。"
                    )
                    return

                argument_parts = arguments.split()
                start_date = None
                extension = None
                if len(argument_parts) >= 2 and argument_parts[1]:
                    start_date = _parse_start_date(argument_parts[1])
                if len(argument_parts) >= 3:
                    extension = argument_parts[2]
                downloaded_count, errors = await archive_channel_attachments(
                    target_channel,
                    output_directory,
                    start_date,
                    extension,
                )
            if downloaded_count == 0:
                result = "添付ファイルが見つかりませんでした。"
                if errors:
                    result += "\n" + "\n".join(errors)
                await message.channel.send(result)
                return

            compress_directory(output_directory, archive_path)
            result = f"{downloaded_count}件の添付ファイルをZIP圧縮しました。"
            if errors:
                result += "\n取得できなかったファイル:\n" + "\n".join(errors)
            result_path = save_template_output(
                "get/result",
                f"chat_get_{message.guild.id}",
                archive_path.read_bytes(),
                suffix=".zip",
            )
            await send_template_output(message.channel, result, result_path)
        except (
            UnicodeDecodeError,
            discord.Forbidden,
            discord.HTTPException,
            OSError,
            ValueError,
        ) as error:
            await message.channel.send(f"添付ファイルを取得できませんでした: {error}")