import discord
import function.discord.message.send_message as send_message
from function.scenario.scenario_service import (
    advance_scenario,
    get_scenario_wait_type,
    resolve_scenario_mentions,
)

"""
    Discordメッセージ受信イベントを処理する。

    on_message_main:
        Bot自身のメッセージを除外し、シナリオ進行中の入力だけを処理する。
"""

async def on_message_main(
    client: discord.Client,
    message: discord.Message,
) -> None:
    # メッセージ送信者がBotの場合は無視する。
    if message.author.bot:
        return

    if message.guild is not None:
        try:
            wait_type = get_scenario_wait_type(
                message.guild.id,
                message.channel.id,
            )
        except (OSError, ValueError) as error:
            await message.channel.send(f"台本を進行できませんでした: {error}")
            return

        if wait_type is not None:
            if wait_type != "reaction" and not message.content.startswith('/'):
                try:
                    scenario_result = advance_scenario(
                        message.guild.id,
                        message.content,
                    )
                except (OSError, ValueError) as error:
                    await message.channel.send(
                        f"台本を進行できませんでした: {error}"
                    )
                    return
                if scenario_result is not None:
                    if scenario_result["response"]:
                        await message.channel.send(
                            resolve_scenario_mentions(
                                scenario_result["response"],
                                message.guild,
                            )
                        )
                    if scenario_result["instruction"]:
                        await message.channel.send(
                            resolve_scenario_mentions(
                                scenario_result["instruction"],
                                message.guild,
                            )
                        )
                return

            # reaction待ち、または台本以外のメッセージは無視する。
            return

    # 通常メッセージコマンドは使用せず、スラッシュコマンドで処理する。
        