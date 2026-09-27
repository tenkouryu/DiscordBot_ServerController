import csv
import io

import discord
from function.file.template_output_service import save_template_output
from function.security.permissions import can_manage_channels

"""
    チャンネル一覧取得コマンドを処理する。

    export_channels_to_csv:
        サーバーのチャンネル一覧をCSVデータへ変換する。

    main:
        チャンネル一覧CSVを作成して送信する。
"""

def export_channels_to_csv(guild: discord.Guild) -> bytes:
    """サーバーのチャンネル一覧をCSVデータとして作成する。"""
    if guild is None:
        raise ValueError("サーバーが指定されていません。")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["name", "type", "category"])
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            channel_type = "text"
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = "voice"
        else:
            continue

        writer.writerow([
            channel.name,
            channel_type,
            channel.category.name if channel.category else "",
        ])

    return output.getvalue().encode("utf-8-sig")


async def main(message: discord.Message) -> None:
    """サーバーのチャンネル一覧をCSVファイルとして送信する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/channel get\n"
            "サーバーのチャンネル一覧をCSVファイルで取得します。"
        )
        return

    if not can_manage_channels(message.author):
        await message.channel.send("チャンネルを管理する権限がありません。")
        return

    result_path = save_template_output(
        "get/result",
        f"channel_get_{message.guild.id}",
        export_channels_to_csv(message.guild),
    )
    await send_template_output(message.channel, "チャンネル一覧を送信します。", result_path)