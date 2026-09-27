import csv
import io

import discord
import function.discord.role.edit_roll as edit_roll
from function.file.template_output_service import save_template_output
from function.security.permissions import can_manage_roles

"""
    CSVによるサーバーロール設定コマンドを処理する。

    _parse_bool:
        CSVの文字列を権限設定用の真偽値へ変換する。

    set_roles_from_csv:
        CSV全体を読み込み、サーバーのロール設定を更新する。

    main:
        添付CSVを読み込み、サーバーロール設定を実行する。
"""

def _parse_bool(value: str, permission_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "on", "yes"}:
        return True
    if normalized in {"false", "0", "off", "no"}:
        return False
    raise ValueError(
        f'権限「{permission_name}」は true または false を指定してください。'
    )


async def set_roles_from_csv(guild: discord.Guild, csv_text: str) -> tuple[int, bytes]:
    """role_get.py の CSV を読み込み、結果列付きの CSV を返す。"""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    reader = csv.DictReader(io.StringIO(csv_text))
    required_columns = {"name"}
    if not required_columns.issubset(reader.fieldnames or set()):
        raise ValueError("CSVには name 列が必要です。")

    fieldnames = list(reader.fieldnames or [])
    permission_names = [
        column for column in fieldnames
        if column not in {"id", "name", "color", "result", "reason"}
    ]
    if "result" not in fieldnames:
        fieldnames.append("result")
    if "reason" not in fieldnames:
        fieldnames.append("reason")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fieldnames)
    success_count = 0

    for row in reader:
        role_name = (row.get("name") or "").strip()
        result = "成功"
        reason = ""
        try:
            if not role_name:
                raise ValueError("ロール名が空です。")

            permissions = {
                permission_name: _parse_bool(
                    row.get(permission_name, ""),
                    permission_name,
                )
                for permission_name in permission_names
            }
            await edit_roll.edit_role_settings(
                guild,
                role_name,
                (row.get("color") or "").strip(),
                permissions,
            )
            success_count += 1
        except (ValueError, discord.Forbidden, discord.HTTPException) as error:
            result = "失敗"
            reason = str(error)

        output_row = [row.get(fieldname, "") or "" for fieldname in fieldnames]
        output_row[fieldnames.index("result")] = result
        output_row[fieldnames.index("reason")] = reason
        writer.writerow(output_row)

    return success_count, output.getvalue().encode("utf-8-sig")


async def main(message: discord.Message) -> None:
    """添付されたロール設定 CSV を読み込み、サーバーへ反映する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/server role set + CSVファイル\n"
            "role_get.py で出力した CSV を添付すると、ロールの色と権限を更新します。\n"
            "処理結果を result、失敗理由を reason 列に追加したCSVを返信します。"
        )
        return

    if not can_manage_roles(message.author):
        await message.channel.send("ロールを変更する権限がありません。")
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
            "CSVファイルを添付してください。使い方: /server role set + CSVファイル"
        )
        return

    try:
        csv_text = (await csv_attachment.read()).decode("utf-8-sig")
        success_count, result_csv = await set_roles_from_csv(message.guild, csv_text)
    except (UnicodeDecodeError, ValueError) as error:
        await message.channel.send(f"CSVを読み込めませんでした: {error}")
        return

    result_path = save_template_output(
        "set/response",
        f"server_role_set_{message.guild.id}",
        result_csv,
    )
    await send_template_output(
        message.channel,
        f"{success_count}件のロール設定を更新しました。結果CSVを添付します。",
        result_path,
    )