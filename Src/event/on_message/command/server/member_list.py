import discord
import csv
import io
from zipfile import ZIP_DEFLATED, ZipFile
from function.file.template_output_service import save_template_output
from function.file.template_output_service import send_template_output


_CSV_COMPRESSION_THRESHOLD = 1_000_000


def _compress_csv(csv_data: bytes) -> bytes:
    """メンバー一覧CSVをZIP形式へ圧縮する。"""
    compressed = io.BytesIO()
    with ZipFile(compressed, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("server_member_list.csv", csv_data)
    return compressed.getvalue()

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

    csv_data = output.getvalue().encode('utf-8-sig')
    if len(csv_data) >= _CSV_COMPRESSION_THRESHOLD:
        result_content = _compress_csv(csv_data)
        result_suffix = ".zip"
        result_message = "メンバーリストを圧縮して送信します。"
    else:
        result_content = csv_data
        result_suffix = ".csv"
        result_message = "メンバーリストを送信します。"

    result_path = save_template_output(
        'get/result',
        f'member_list_{message.guild.id}',
        result_content,
        suffix=result_suffix,
    )
    await send_template_output(
        message.channel,
        result_message,
        result_path,
    )