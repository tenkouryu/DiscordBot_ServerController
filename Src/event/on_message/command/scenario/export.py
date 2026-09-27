import discord

from function.file.template_output_service import save_template_output, send_template_output
from function.scenario.scenario_service import export_scenario_csv

"""
    シナリオCSV出力コマンドを処理する。

    main:
        scenario_definitions.jsonをCSV形式で送信する。
"""


async def main(message: discord.Message) -> None:
    """登録済みシナリオをCSVファイルとして送信する。"""
    if message.content.partition(" ")[2].strip() == "-h":
        await message.channel.send(
            "/scenario export\n"
            "登録済みシナリオをCSVファイルで取得します。"
        )
        return

    try:
        scenario_file = export_scenario_csv()
    except (OSError, ValueError) as error:
        await message.channel.send(f"シナリオCSVを出力できませんでした: {error}")
        return

    result_path = save_template_output(
        "get/result",
        f"scenario_export_{message.guild.id}",
        scenario_file.getvalue(),
    )
    await send_template_output(
        message.channel,
        "登録済みシナリオのCSVです。",
        result_path,
    )