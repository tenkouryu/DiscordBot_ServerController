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


def _build_member_list_csv(members: list[discord.Member]) -> bytes:
    """メンバーと各メンバーのロールを個別のCSV列に出力する。"""
    member_rows = [
        (
            str(member.id),
            member.name,
            member.display_name,
            [role.name for role in member.roles],
        )
        for member in members
    ]
    max_role_count = max(
        (len(roles) for _, _, _, roles in member_rows),
        default=0,
    )

    output = io.StringIO(newline='')
    writer = csv.writer(output)
    role_headers = [f'Role{index}' for index in range(1, max_role_count + 1)]
    writer.writerow(['User ID', 'Name', 'Display Name', *role_headers])
    for user_id, name, display_name, roles in member_rows:
        empty_role_columns = [''] * (max_role_count - len(roles))
        writer.writerow(
            [user_id, name, display_name, *roles, *empty_role_columns]
        )

    return output.getvalue().encode('utf-8-sig')


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
    csv_data = _build_member_list_csv(members)
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