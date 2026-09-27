import discord
import csv
import io
from function.file.template_output_service import save_template_output

"""
    サーバーメンバー一覧取得コマンドを処理する。

    main:
        サーバーのメンバー一覧をCSVファイルにして送信する。
"""

async def main(client: discord.Client, message: discord.Message) -> None:
    if message.content.partition(' ')[2].strip() == '-h':
        await message.channel.send(
            '/server member list\n'
            'サーバーのメンバー一覧を CSV ファイルで取得します。'
        )
        return

    # メンバーのリストを取得する。
    members = message.guild.members
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['名前', '表示名', 'ロール'])
    for member in members:
        writer.writerow([member.name, member.display_name, ', '.join(role.name for role in member.roles)])

    result_path = save_template_output(
        'get/result',
        f'member_list_{message.guild.id}',
        output.getvalue().encode('utf-8-sig'),
    )
    await send_template_output(
        message.channel,
        'メンバーリストを送信します。',
        result_path,
    )