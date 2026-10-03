import csv
import io
import re

import discord
from function.file.template_output_service import save_template_output, send_template_output
from function.security.permissions import can_manage_roles


_ROLE_COLUMN_PATTERN = re.compile(r"Role(\d+)\Z")


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


def _get_role_columns(fieldnames: list[str]) -> list[str]:
    """Role1、Role2...列を番号順に取得する。"""
    role_columns = [
        (int(match.group(1)), fieldname)
        for fieldname in fieldnames
        if (match := _ROLE_COLUMN_PATTERN.fullmatch(fieldname))
    ]
    return [fieldname for _, fieldname in sorted(role_columns)]


async def _replace_member_roles(
    guild: discord.Guild,
    member: discord.Member,
    requested_role_names: list[str],
) -> str | None:
    """指定ロールへ置き換える。管理対象・デフォルトロールは維持する。"""
    desired_roles: list[discord.Role] = []
    seen_role_ids: set[int] = set()
    for role_name in requested_role_names:
        if not role_name:
            continue

        matching_roles = [role for role in guild.roles if role.name == role_name]
        if not matching_roles:
            return f"ロール「{role_name}」が見つかりません。"
        if len(matching_roles) > 1:
            return f"ロール「{role_name}」を一意に特定できません。"

        role = matching_roles[0]
        if role.is_default() or role.managed or role.id in seen_role_ids:
            continue
        desired_roles.append(role)
        seen_role_ids.add(role.id)

    protected_roles = [
        role
        for role in member.roles
        if role.is_default() or role.managed
    ]
    updated_roles = protected_roles + desired_roles
    current_role_ids = {role.id for role in member.roles}
    updated_role_ids = {role.id for role in updated_roles}
    if current_role_ids == updated_role_ids:
        return None

    try:
        await member.edit(roles=updated_roles, reason="CSVからメンバーロールを更新")
    except (discord.Forbidden, discord.HTTPException):
        return "Discordの権限または通信エラーで操作できませんでした。"
    return None


async def update_member_roles_from_csv(
    guild: discord.Guild,
    csv_text: str,
) -> tuple[str, int]:
    """メンバー一覧CSVのRole列を適用し、処理結果を追加したCSVを返す。"""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames
    if not fieldnames or len(fieldnames) != len(set(fieldnames)):
        raise ValueError("CSVの列名がありません。または同じ列名が重複しています。")
    if "Name" not in fieldnames:
        raise ValueError("CSVには「Name」列が必要です。")
    role_columns = _get_role_columns(fieldnames)
    if not role_columns:
        raise ValueError("CSVには「Role1」などのロール列が必要です。")

    output_fieldnames = list(fieldnames)
    if "result" not in output_fieldnames:
        output_fieldnames.append("result")
    if "reason" not in output_fieldnames:
        output_fieldnames.append("reason")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(output_fieldnames)
    success_count = 0

    for row in reader:
        username = (row.get("Name") or "").strip()
        member = _find_member_by_username(guild, username) if username else None
        if member is None:
            reason = (
                f"ユーザー名「{username}」のメンバーが見つからないか、一意に特定できません。"
            )
        else:
            requested_role_names = [
                (row.get(column) or "").strip()
                for column in role_columns
            ]
            reason = await _replace_member_roles(
                guild,
                member,
                requested_role_names,
            )

        result = "失敗" if reason else "成功"
        if not reason:
            success_count += 1
        output_row = [
            row.get(fieldname, "") or "" for fieldname in output_fieldnames
        ]
        output_row[output_fieldnames.index("result")] = result
        output_row[output_fieldnames.index("reason")] = reason or ""
        writer.writerow(output_row)

    return output.getvalue(), success_count


async def main(message: discord.Message) -> None:
    """添付されたメンバー一覧CSVからロールを置き換え、結果CSVを送信する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/member role update + CSVファイル\n"
            "Name、Role1、Role2...列を持つメンバー一覧CSVからロールを更新します。"
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
            "CSVファイルを添付してください。使い方: /member role update + CSVファイル"
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
        f"member_role_update_{message.guild.id}",
        result_csv.encode("utf-8-sig"),
    )
    await send_template_output(
        message.channel,
        f"{success_count}件の処理が成功しました。結果CSVを添付します。",
        result_path,
    )
