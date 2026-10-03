import csv
import io
import re

import discord
from function.security.permissions import can_manage_roles
import function.discord.role.edit_roll as edit_roll
from function.file.template_output_service import save_template_output, send_template_output

_ROLE_COLUMN_PATTERN = re.compile(r"ロール(\d+)\Z")

"""
    CSVによるメンバーロール設定コマンドを処理する。

    _find_member_by_username / _find_role:
        CSV指定に対応するメンバーまたはロールを検索する。

    _execute_row:
        CSVの1行分のロール操作を実行する。

    update_member_roles_from_csv:
        CSV全体を読み込み、メンバーのロールを更新する。

    main:
        添付CSVを読み込み、メンバーロール設定を実行する。
"""

def _find_member_by_username(
    guild: discord.Guild,
    username: str,
) -> discord.Member | None:
    """Discordユーザー名から対象メンバーを特定する。"""
    matches = [
        member
        for member in guild.members
        if member.name.casefold() == username.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _find_member(
    guild: discord.Guild,
    user_id: str,
    username: str,
    display_name: str,
) -> tuple[discord.Member | None, str | None]:
    """ユーザーIDを優先し、未指定ならユーザー名、表示名の順に検索する。"""
    if user_id:
        if not user_id.isdecimal():
            return None, f"ユーザーID「{user_id}」が正しくありません。"
        numeric_user_id = int(user_id)
        matches = [
            member for member in guild.members if member.id == numeric_user_id
        ]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"ユーザーID「{user_id}」のメンバーが見つかりません。"
        return None, f"ユーザーID「{user_id}」のメンバーを一意に特定できません。"

    if username:
        matches = [
            member
            for member in guild.members
            if member.name.casefold() == username.casefold()
        ]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, f"ユーザー名「{username}」のメンバーを一意に特定できません。"

    if display_name:
        matches = [
            member
            for member in guild.members
            if member.display_name.casefold() == display_name.casefold()
        ]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, f"表示名「{display_name}」のメンバーを一意に特定できません。"

    return None, "ユーザーID、ユーザー名、表示名に一致するメンバーが見つかりません。"


def _find_role(guild: discord.Guild, role_name: str) -> discord.Role | None:
    """変更可能なロールを名前から取得する。"""
    return next(
        (
            role
            for role in guild.roles
            if role.name == role_name
            and not role.is_default()
            and not role.managed
        ),
        None,
    )


async def _execute_row(
    guild: discord.Guild,
    action: str,
    user_id: str,
    username: str,
    display_name: str,
    role_names: list[str],
) -> str:
    """CSV 1 行分のロール操作を実行する。"""
    if action not in ("追加", "削除"):
        return "失敗: 1列目は「追加」または「削除」を指定してください。"
    role_names = list(dict.fromkeys(role_name for role_name in role_names if role_name))
    if not role_names:
        return "失敗: ロール名が空です。"

    member, member_error = _find_member(guild, user_id, username, display_name)
    if member is None:
        return f"失敗: {member_error}"

    if action == "削除":
        missing_roles = [
            role_name
            for role_name in role_names
            if _find_role(guild, role_name) is None
        ]
        if missing_roles:
            return f"失敗: ロール「{missing_roles[0]}」が見つかりません。"

    try:
        for role_name in role_names:
            role = _find_role(guild, role_name)
            if action == "追加":
                if role is None:
                    role = await edit_roll.add_role_to_server(guild, role_name)
                await member.add_roles(role)
                continue

            if role is None:
                return f"失敗: ロール「{role_name}」が見つかりません。"
            await member.remove_roles(role)
        return f"成功: ロールを{action}しました。"
    except (discord.Forbidden, discord.HTTPException):
        return "失敗: Discordの権限または通信エラーで操作できませんでした。"
    except ValueError as error:
        return f"失敗: {error}"


async def update_member_roles_from_csv(
    guild: discord.Guild,
    csv_text: str,
) -> tuple[str, int]:
    """CSVを処理し、実行結果列を追加したCSVを返す。"""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    if len(fieldnames) != len(set(fieldnames)):
        raise ValueError("CSVに重複した列名があります。")
    if "追加/削除" not in fieldnames:
        raise ValueError("CSVには「追加/削除」列が必要です。")
    if not {"ユーザーID", "ユーザー名", "表示名"}.intersection(fieldnames):
        raise ValueError("CSVには「ユーザーID」「ユーザー名」「表示名」のいずれかが必要です。")
    role_columns = [
        fieldname
        for fieldname in fieldnames
        if fieldname == "ロール" or _ROLE_COLUMN_PATTERN.fullmatch(fieldname)
    ]
    if not role_columns:
        raise ValueError("CSVには「ロール」または「ロール1」などの列が必要です。")

    fieldnames = list(fieldnames)
    if "result" not in fieldnames:
        fieldnames.append("result")
    if "reason" not in fieldnames:
        fieldnames.append("reason")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fieldnames)
    success_count = 0

    for row in reader:
        action = row.get("追加/削除", "").strip()
        user_id = (row.get("ユーザーID") or "").strip()
        username = row.get("ユーザー名", "").strip()
        display_name = (row.get("表示名") or "").strip()
        role_names = [
            (row.get(column) or "").strip()
            for column in role_columns
        ]
        operation_result = await _execute_row(
            guild,
            action,
            user_id,
            username,
            display_name,
            role_names,
        )
        succeeded = operation_result.startswith("成功")
        result = "成功" if succeeded else "失敗"
        reason = operation_result.partition(":")[2].strip() if not succeeded else ""
        if succeeded:
            success_count += 1
        output_row = [row.get(fieldname, "") or "" for fieldname in fieldnames]
        output_row[fieldnames.index("result")] = result
        output_row[fieldnames.index("reason")] = reason
        writer.writerow(output_row)

    return output.getvalue(), success_count


async def main(message: discord.Message) -> None:
    """添付されたCSVからメンバーのロールを操作し、結果CSVを送信する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/member role set + CSVファイル\n"
            "CSV形式: 追加/削除,ユーザーID,ユーザー名,表示名,ロール1,ロール2...\n"
            "ユーザーIDが空の場合はユーザー名、表示名の順で検索します。\n"
            "処理結果を result、失敗理由を reason 列に追加したCSVを返信します。"
        )
        return

    if not can_manage_roles(message.author):
        await message.channel.send("メンバーのロールを変更する権限がありません。")
        return

    csv_attachment = next(
        (
            attachment
            for attachment in message.attachments
            if attachment.filename.lower().endswith(".csv")
        ),
        None,
    )
    if csv_attachment is None:
        await message.channel.send(
            "CSVファイルを添付してください。使い方: /member role set + CSVファイル"
        )
        return

    try:
        csv_text = (await csv_attachment.read()).decode("utf-8-sig")
        result_csv, success_count = await update_member_roles_from_csv(
            message.guild,
            csv_text,
        )
    except (UnicodeDecodeError, ValueError) as error:
        await message.channel.send(f"CSVを読み込めませんでした: {error}")
        return

    result_path = save_template_output(
        "set/response",
        f"member_role_set_{message.guild.id}",
        result_csv.encode("utf-8-sig"),
    )
    await send_template_output(
        message.channel,
        f"{success_count}件の処理が成功しました。結果CSVを添付します。",
        result_path,
    )
