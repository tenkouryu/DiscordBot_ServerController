import csv
import io

import discord

"""
    メンバーロール設定CSVテンプレートコマンドを処理する。

    main:
        メンバーロール設定用CSVテンプレートを作成して送信する。
"""

async def main(message: discord.Message) -> None:
    """メンバーロール操作用 CSV テンプレートを送信する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/member role template\n"
            "メンバーロール操作用 CSV テンプレートを取得します。"
        )
        return

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["追加/削除", "ユーザーID", "ユーザー名", "表示名", "ロール1", "ロール2"]
    )
    writer.writerow([
        "追加または削除を入力",
        "対象メンバーのユーザーIDを入力",
        "IDがない場合はDiscordユーザー名を入力",
        "IDとユーザー名がない場合に入力",
        "対象ロール名を入力",
        "追加するロール名を入力",
    ])
    await message.channel.send(
        "メンバーロール操作用 CSV テンプレートです。",
        file=discord.File(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            filename="member_role_template.csv",
        ),
    )
