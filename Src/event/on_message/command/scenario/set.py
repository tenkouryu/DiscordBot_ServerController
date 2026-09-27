import csv
import io

import discord

from function.scenario.scenario_service import register_scenario_csv
from function.file.template_output_service import save_template_output


def _create_result_csv(csv_text: str, result: str, reason: str = "") -> bytes:
    """入力CSVの各行へ登録結果を追加する。"""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError("CSVにヘッダー行がありません。")

    fieldnames = rows[0]
    if "result" not in fieldnames:
        fieldnames.append("result")
    if "reason" not in fieldnames:
        fieldnames.append("reason")

    result_index = fieldnames.index("result")
    reason_index = fieldnames.index("reason")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fieldnames)
    for row in rows[1:]:
        row.extend([""] * (len(fieldnames) - len(row)))
        row[result_index] = result
        row[reason_index] = reason
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")

"""
    台本登録コマンドを処理する。

    main:
        添付されたCSVを読み込み、台本定義JSONへ登録する。
"""


async def main(message: discord.Message) -> None:
    """添付CSVを台本定義JSONへ登録する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/scenario set + CSVファイル\n"
            "台本登録用CSVを読み込み、処理結果を追記したCSVを返信します。"
        )
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
            "台本登録用のCSVファイルを添付してください。"
        )
        return

    try:
        csv_text = (await csv_attachment.read()).decode("utf-8-sig")
    except (UnicodeDecodeError, OSError) as error:
        await message.channel.send(f"台本を登録できませんでした: {error}")
        return

    try:
        registered_count = register_scenario_csv(csv_text)
        result_csv = _create_result_csv(csv_text, "成功")
    except (OSError, ValueError) as error:
        try:
            result_csv = _create_result_csv(csv_text, "失敗", str(error))
        except ValueError:
            await message.channel.send(f"台本を登録できませんでした: {error}")
            return
        registered_count = 0

    result_path = save_template_output(
        "set/response",
        f"scenario_set_{message.guild.id}",
        result_csv,
    )
    await send_template_output(
        message.channel,
        f"{registered_count}ステップ登録しました。結果CSVを添付します。",
        result_path,
    )
