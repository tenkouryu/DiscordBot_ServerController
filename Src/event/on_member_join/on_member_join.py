import discord

"""
    Discordサーバーへのメンバー参加イベントを処理する。

    on_member_join_main:
        新しく参加したメンバーへ歓迎メッセージを送信する。
"""

async def on_member_join_main(
    client: discord.Client,
    member: discord.Member,
) -> None:
    print(f'{member}がメンバーとして参加しました')
